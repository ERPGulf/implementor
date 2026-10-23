# implementor/client_api.py
"""
Mobile client-app API for ERPGulf clients.

Reads and writes ONLY the doctypes Implementor already has:
    Project (+ Project Module, Payment Milestone child tables), Task, ToDo,
    Support Ticket, Server, Server Activity, Training Session, Integration,
    Notification Log, Comment, File, Contact.

No new doctypes, no new fields.

Who is the client?
    The logged-in user is linked to a Customer through a standard ERPNext
    Contact (Contact.user = the user, with a Dynamic Link to the Customer).
    Every endpoint resolves that Customer first and only returns its data.
    Client users have no desk permissions on these doctypes, so this layer
    scopes everything itself and then reads with ignore_permissions.

Login is NOT handled here. Sign-up, sign-in, OTP and cold boot come from the
separate auth app used with @erpgulf/auth-sdk (ERPGulf/ui-shared-code). It
returns a standard Frappe OAuth bearer token; the app sends
"Authorization: Bearer <access_token>" and Frappe sets frappe.session.user,
which is all this module relies on.

All endpoints: /api/method/implementor.client_api.<function>
"""

import base64
import json

import frappe
from frappe import _
from frappe.utils import (
    add_to_date,
    cint,
    date_diff,
    get_datetime,
    getdate,
    now_datetime,
    nowdate,
)

from implementor.api import _strip_html
from implementor.implementor.auth import is_admin

CLIENT_ADMIN = "Client Admin"
OPEN_TICKET_STATUSES = ("New", "Triaged", "In Progress", "Waiting on Client", "Resolved")
CLOSED_TICKET_STATUSES = ("Closed",)
TICKET_FLOW = ["New", "Triaged", "In Progress", "Waiting on Client", "Resolved", "Closed"]
SIGNOFF_TAG = "[client-signoff]"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


# --------------------------------------------------------------------------
# Context and scoping
# --------------------------------------------------------------------------

def _customers_for_user(user):
    """
    Contact.user is the primary link. If the auth app created the User
    without setting Contact.user, fall back to the User's email or mobile
    (both verified at sign-in) matched against the Contact's own records.
    """
    contacts = frappe.get_all("Contact", filters={"user": user}, pluck="name")
    if not contacts:
        u = frappe.db.get_value("User", user, ["email", "mobile_no"], as_dict=True) or {}
        if u.get("email"):
            contacts = frappe.get_all(
                "Contact Email", filters={"parenttype": "Contact", "email_id": u["email"]}, pluck="parent"
            )
        # employee_app signs in an Employee by cell_number and issues the token
        # for Employee.user_id, so that number is the verified one.
        phones = [u.get("mobile_no"), frappe.db.get_value("Employee", {"user_id": user}, "cell_number")]
        for phone in [p for p in phones if p]:
            if contacts:
                break
            contacts = frappe.get_all(
                "Contact Phone", filters={"parenttype": "Contact", "phone": phone}, pluck="parent"
            )
            digits = "".join(ch for ch in phone if ch.isdigit())
            if not contacts and len(digits) >= 9:
                contacts = frappe.get_all(
                    "Contact Phone",
                    filters={"parenttype": "Contact", "phone": ["like", f"%{digits[-9:]}"]},
                    pluck="parent",
                )
    if not contacts:
        return []
    links = frappe.get_all(
        "Dynamic Link",
        filters={"parenttype": "Contact", "parent": ["in", contacts], "link_doctype": "Customer"},
        pluck="link_name",
    )
    return list(dict.fromkeys(links))


def _ctx(customer=None):
    """Resolve the session user and the Customer they may see."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Please log in"), frappe.AuthenticationError)

    allowed = _customers_for_user(user)
    staff = is_admin(user)

    if customer:
        if customer not in allowed and not staff:
            frappe.throw(_("Not permitted"), frappe.PermissionError)
        if not frappe.db.exists("Customer", customer):
            frappe.throw(_("Customer not found"), frappe.DoesNotExistError)
    elif allowed:
        customer = allowed[0]
    else:
        frappe.throw(_("This user is not linked to a customer"), frappe.PermissionError)

    roles = frappe.get_roles(user)
    return frappe._dict(
        user=user,
        customer=customer,
        customers=allowed,
        is_client_admin=staff or CLIENT_ADMIN in roles,
    )


def _check_project(ctx, project):
    if not project or frappe.db.get_value("Project", project, "customer") != ctx.customer:
        frappe.throw(_("Not permitted"), frappe.PermissionError)


def _check_server(ctx, server):
    if not server or frappe.db.get_value("Server", server, "customer") != ctx.customer:
        frappe.throw(_("Not permitted"), frappe.PermissionError)


def _check_ticket(ctx, ticket):
    row = frappe.db.get_value("Support Ticket", ticket, ["customer", "raised_by"], as_dict=True)
    if not row or row.customer != ctx.customer:
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    if not ctx.is_client_admin and row.raised_by != ctx.user:
        frappe.throw(_("Not permitted"), frappe.PermissionError)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def _days_left(d):
    return date_diff(getdate(d), getdate(nowdate())) if d else None


def _elapsed_pct(start, end):
    if not start or not end:
        return None
    total = date_diff(getdate(end), getdate(start))
    if total <= 0:
        return 100
    done = date_diff(getdate(nowdate()), getdate(start))
    return max(0, min(100, round(done * 100 / total)))


def _options(doctype, fieldname):
    field = frappe.get_meta(doctype).get_field(fieldname)
    return [o for o in (field.options or "").split("\n") if o] if field else []


def _full_name(user):
    if not user:
        return None
    return frappe.db.get_value("User", user, "full_name") or user


def _parse_assign(raw):
    try:
        return json.loads(raw) if raw else []
    except (ValueError, TypeError):
        return []


def _project_kind(imp_status):
    return "amc" if imp_status == "AMC" else "implementation"


def _hours_used(project):
    rows = frappe.get_all("Task", filters={"project": project}, fields=[{"SUM": "imp_actual_hours", "as": "h"}])
    return round(float(rows[0].h or 0), 2) if rows else 0


# --------------------------------------------------------------------------
# Profile
# --------------------------------------------------------------------------

@frappe.whitelist()
def me(customer=None):
    ctx = _ctx(customer)
    user = frappe.db.get_value("User", ctx.user, ["full_name", "email", "mobile_no", "user_image"], as_dict=True)
    return {
        "user": ctx.user,
        "full_name": user.full_name,
        "email": user.email,
        "mobile_no": user.mobile_no,
        "user_image": user.user_image,
        "customer": ctx.customer,
        "customer_name": frappe.db.get_value("Customer", ctx.customer, "customer_name"),
        "customers": [
            {"name": c, "customer_name": frappe.db.get_value("Customer", c, "customer_name")}
            for c in ctx.customers
        ],
        "is_client_admin": ctx.is_client_admin,
    }


# --------------------------------------------------------------------------
# Home and services
# --------------------------------------------------------------------------

_PROJECT_FIELDS = [
    "name", "project_name", "imp_status", "imp_current_stage", "imp_health",
    "imp_percent", "percent_complete", "expected_start_date", "expected_end_date",
    "imp_deadline", "imp_go_live_date", "imp_project_manager", "status",
]


def _project_summary(p):
    kind = _project_kind(p.imp_status)
    end = p.expected_end_date or p.imp_deadline
    out = {
        "name": p.name,
        "title": p.project_name,
        "kind": kind,
        "status": p.imp_status,
        "stage": p.imp_current_stage,
        "health": p.imp_health,
        "percent": p.imp_percent if p.imp_percent is not None else p.percent_complete,
        "start_date": p.expected_start_date,
        "end_date": end,
        "days_left": _days_left(end),
        "project_manager": _full_name(p.imp_project_manager),
    }
    if kind == "implementation":
        out["go_live_date"] = p.imp_go_live_date or p.imp_deadline
        out["go_live_days_left"] = _days_left(out["go_live_date"])
        out["next_milestone"] = _next_milestone(p.name)
    else:
        out["elapsed_percent"] = _elapsed_pct(p.expected_start_date, end)
        out["hours_used"] = _hours_used(p.name)
    return out


def _customer_projects(ctx, kind=None):
    filters = {"customer": ctx.customer, "status": ["!=", "Cancelled"], "custom_close_project": 0}
    if kind == "amc":
        filters["imp_status"] = "AMC"
    elif kind == "implementation":
        filters["imp_status"] = ["!=", "AMC"]
    return frappe.get_all("Project", filters=filters, fields=_PROJECT_FIELDS, order_by="modified desc")


def _server_summary(s):
    return {
        "name": s.name,
        "server_name": s.server_name,
        "environment": s.environment,
        "provider": s.provider,
        "region": s.region,
        "backup_schedule": s.backup_schedule,
        "ssl_expiry": s.ssl_expiry,
        "ssl_days_left": _days_left(s.ssl_expiry),
        "last_restore_test": s.last_restore_test,
    }


_SERVER_FIELDS = [
    "name", "server_name", "environment", "provider", "region", "specs","custom_status","custom_last_backup",
    "erpnext_version", "frappe_version", "backup_schedule", "ssl_expiry", "last_restore_test",
]


@frappe.whitelist()
def home(customer=None):
    """Everything the Home screen needs in one call."""
    ctx = _ctx(customer)
    projects = [_project_summary(p) for p in _customer_projects(ctx)]
    servers = frappe.get_all("Server", filters={"customer": ctx.customer}, fields=_SERVER_FIELDS)

    ticket_filters = {"customer": ctx.customer, "status": ["in", OPEN_TICKET_STATUSES]}
    if not ctx.is_client_admin:
        ticket_filters["raised_by"] = ctx.user
    tickets = frappe.get_all("Support Ticket", filters=ticket_filters, fields=["status"])

    return {
        "customer": ctx.customer,
        "customer_name": frappe.db.get_value("Customer", ctx.customer, "customer_name"),
        "implementations": [p for p in projects if p["kind"] == "implementation"],
        "amc": [p for p in projects if p["kind"] == "amc"],
        "servers": [_server_summary(s) for s in servers],
        "tickets": {
            "open": len(tickets),
            "waiting_for_you": len([t for t in tickets if t.status in ("Waiting on Client", "Resolved")]),
        },
        "my_actions": len(_my_todos(ctx)),
        "unread_notifications": frappe.db.count("Notification Log", {"for_user": ctx.user, "read": 0}),
    }


@frappe.whitelist()
def get_services(customer=None):
    """Services grouped the way the app shows them."""
    ctx = _ctx(customer)
    projects = [_project_summary(p) for p in _customer_projects(ctx)]
    servers = [_server_summary(s) for s in frappe.get_all("Server", filters={"customer": ctx.customer}, fields=_SERVER_FIELDS)]
    return {
        "implementation": [p for p in projects if p["kind"] == "implementation"],
        "amc": [p for p in projects if p["kind"] == "amc"],
        "hosting": servers,
        "backup": [s for s in servers if s["backup_schedule"]],
    }


# --------------------------------------------------------------------------
# Projects, phases, modules, milestones
# --------------------------------------------------------------------------

def _signoffs(project):
    """Client sign-offs are stored as Info comments on the Project."""
    rows = frappe.get_all(
        "Comment",
        filters={
            "reference_doctype": "Project",
            "reference_name": project,
            "comment_type": "Info",
            "content": ["like", SIGNOFF_TAG + "%"],
        },
        fields=["content", "comment_email", "creation"],
        order_by="creation asc",
    )
    out = {}
    for r in rows:
        row_name = (r.content or "")[len(SIGNOFF_TAG):].strip().split(" ")[0]
        if row_name:
            out[row_name] = {"by": _full_name(r.comment_email), "on": r.creation}
    return out


def _milestones(project):
    rows = frappe.get_all(
        "Payment Milestone",
        filters={"parent": project, "parenttype": "Project", "parentfield": "payment_milestone"},
        fields=[
            "name", "idx", "m_title", "duration", "start_date", "end_date",
            "completion_status", "milestone_completion_perc", "no_of_modules",
        ],
        order_by="idx asc",
    )
    signed = _signoffs(project)
    out = []
    for r in rows:
        done = r.completion_status == "Completed"
        out.append({
            "id": r.name,
            "title": r.m_title,
            "duration": r.duration,
            "start_date": r.start_date,
            "end_date": r.end_date,
            "days_left": None if done else _days_left(r.end_date),
            "status": r.completion_status,
            "percent": r.milestone_completion_perc,
            "modules": r.no_of_modules,
            "signed_off": signed.get(r.name),
            "can_sign_off": r.name not in signed and r.completion_status in ("Completed", "Due"),
        })
    return out


def _next_milestone(project):
    for m in _milestones(project):
        if m["status"] != "Completed" or (m["can_sign_off"] and not m["signed_off"]):
            return {"title": m["title"], "end_date": m["end_date"], "days_left": m["days_left"], "status": m["status"]}
    return None


def _modules(project):
    rows = frappe.get_all(
        "Project Module",
        filters={"parent": project, "parenttype": "Project", "parentfield": "imp_modules"},
        fields=["module_name", "in_scope", "module_status"],
        order_by="idx asc",
    )
    tasks = frappe.get_all("Task", filters={"project": project}, fields=["imp_module", "progress"])
    out = []
    for r in rows:
        prog = [t.progress or 0 for t in tasks if t.imp_module == r.module_name]
        if prog:
            percent = round(sum(prog) / len(prog))
        else:
            percent = {"Completed": 100, "Not Started": 0}.get(r.module_status)
        out.append({"module": r.module_name, "in_scope": r.in_scope, "status": r.module_status, "percent": percent})
    return out


@frappe.whitelist()
def get_projects(customer=None, kind=None):
    """kind: implementation | amc | (empty for all)"""
    ctx = _ctx(customer)
    return [_project_summary(p) for p in _customer_projects(ctx, kind)]


@frappe.whitelist()
def get_project(project, customer=None):
    """Project screen: header, phases, modules, milestones, training, integrations, actions."""
    ctx = _ctx(customer)
    _check_project(ctx, project)
    p = frappe.db.get_value("Project", project, _PROJECT_FIELDS, as_dict=True)

    phases = _options("Project", "imp_current_stage")
    current = phases.index(p.imp_current_stage) if p.imp_current_stage in phases else -1

    training = frappe.get_all(
        "Training Session",
        filters={"project": project},
        fields=["name", "topic", "trainer", "schedule"],
        order_by="schedule asc",
    )
    for t in training:
        t["trainer"] = _full_name(t.trainer)

    integrations = frappe.get_all(
        "Integration",
        filters={"project": project},
        fields=["name", "integration_name", "type", "vendor", "status"],
    )

    data = _project_summary(p)
    data.update({
        "phases": [
            {"name": ph, "state": "done" if i < current else ("current" if i == current else "upcoming")}
            for i, ph in enumerate(phases)
        ],
        "modules": _modules(project),
        "milestones": _milestones(project),
        "training": training,
        "integrations": integrations,
        "my_actions": _my_todos(ctx, project),
        "tickets_waiting_for_you": frappe.get_all(
            "Support Ticket",
            filters={"project": project, "status": ["in", ["Waiting on Client", "Resolved"]]},
            fields=["name", "subject", "status"],
        ),
    })
    return data


@frappe.whitelist()
def get_milestones(project, customer=None):
    ctx = _ctx(customer)
    _check_project(ctx, project)
    ms = _milestones(project)
    return {
        "milestones": ms,
        "signed_off": len([m for m in ms if m["signed_off"]]),
        "completed": len([m for m in ms if m["status"] == "Completed"]),
        "total": len(ms),
    }


@frappe.whitelist(methods=["POST"])
def sign_off_milestone(project, milestone, remarks=None, customer=None):
    """Client Admin accepts a milestone that is Completed or Due."""
    ctx = _ctx(customer)
    _check_project(ctx, project)
    if not ctx.is_client_admin:
        frappe.throw(_("Only a Client Admin can sign off milestones"), frappe.PermissionError)

    row = frappe.db.get_value(
        "Payment Milestone",
        {"name": milestone, "parent": project, "parenttype": "Project"},
        ["name", "m_title", "completion_status"],
        as_dict=True,
    )
    if not row:
        frappe.throw(_("Milestone not found"), frappe.DoesNotExistError)
    if row.completion_status not in ("Completed", "Due"):
        frappe.throw(_("This milestone is not ready for sign-off"))
    if row.name in _signoffs(project):
        frappe.throw(_("Already signed off"))

    text = f"{SIGNOFF_TAG} {row.name} Milestone '{row.m_title}' signed off by client"
    if remarks:
        text += f": {frappe.utils.escape_html(remarks)}"
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Project",
        "reference_name": project,
        "content": text,
        "comment_email": ctx.user,
        "comment_by": _full_name(ctx.user),
    }).insert(ignore_permissions=True)

    pm = frappe.db.get_value("Project", project, "imp_project_manager")
    _notify(pm, f"Milestone signed off: {row.m_title}", "Project", project)
    return _milestones(project)


# --------------------------------------------------------------------------
# AMC
# --------------------------------------------------------------------------

@frappe.whitelist()
def get_amc(project, customer=None):
    ctx = _ctx(customer)
    _check_project(ctx, project)
    p = frappe.db.get_value("Project", project, _PROJECT_FIELDS, as_dict=True)
    if p.imp_status != "AMC":
        frappe.throw(_("Not an AMC project"))
    data = _project_summary(p)
    tickets = frappe.get_all("Support Ticket", filters={"project": project}, fields=["status"])
    data["tickets"] = {
        "open": len([t for t in tickets if t.status in OPEN_TICKET_STATUSES]),
        "closed": len([t for t in tickets if t.status in CLOSED_TICKET_STATUSES]),
    }
    return data


# --------------------------------------------------------------------------
# Hosting and backup
# --------------------------------------------------------------------------

@frappe.whitelist()
def get_servers(customer=None):
    ctx = _ctx(customer)
    servers = frappe.get_all("Server", filters={"customer": ctx.customer}, fields=_SERVER_FIELDS)
    return [_server_summary(s) for s in servers]


@frappe.whitelist()
def get_server(server, customer=None):
    ctx = _ctx(customer)
    _check_server(ctx, server)
    s = frappe.db.get_value("Server", server, _SERVER_FIELDS, as_dict=True)
    data = _server_summary(s)
    data.update({
        "specs": s.specs,
        "erpnext_version": s.erpnext_version,
        "frappe_version": s.frappe_version,
        "activity": frappe.get_all(
            "Server Activity",
            filters={"server": server},
            fields=["activity_type", "date", "downtime_window", "workflow_state"],
            order_by="date desc",
            limit=20,
        ),
    })
    return data


@frappe.whitelist()
def get_backups(server, limit=10, refresh=0, customer=None):
    """Backup policy and recent runs. Live data comes from OCI when configured."""
    ctx = _ctx(customer)
    _check_server(ctx, server)
    s = frappe.db.get_value("Server", server, _SERVER_FIELDS, as_dict=True)
    restores = frappe.get_all(
        "Server Activity",
        filters={"server": server, "activity_type": "Restore"},
        fields=["date", "workflow_state", "downtime_window"],
        order_by="date desc",
        limit=5,
    )
    return {
        "server": server,
        "server_name": s.server_name,
        "backup_schedule": s.backup_schedule,
        "last_restore_test": s.last_restore_test,
        "restores": restores,
        "oci": _oci_backups(s, min(cint(limit) or 10, 50), cint(refresh)),
    }


def _oci_backups(server, limit, refresh):
    """
    Reads the boot volume backups of the server's OCI instance.

    site_config.json:
      "implementor_oci": {
        "config_file": "/home/frappe/.oci/config",
        "profile": "DEFAULT",
        "compartment_id": "ocid1.compartment...",
        "instances": {"<Server name>": "ocid1.instance..."}   # optional; else matched by display name
      }
    """
    conf = frappe.conf.get("implementor_oci") or {}
    if not conf.get("compartment_id"):
        return {"available": False, "reason": "OCI is not configured"}
    try:
        import oci
    except ImportError:
        return {"available": False, "reason": "OCI SDK is not installed"}

    key = f"implementor_oci_backups:{server.name}:{limit}"
    if not refresh:
        cached = frappe.cache().get_value(key)
        if cached:
            return cached

    try:
        config = oci.config.from_file(conf.get("config_file", "~/.oci/config"), conf.get("profile", "DEFAULT"))
        compartment = conf["compartment_id"]
        compute = oci.core.ComputeClient(config)
        storage = oci.core.BlockstorageClient(config)

        instance_id = (conf.get("instances") or {}).get(server.name) or (conf.get("instances") or {}).get(server.server_name)
        if instance_id:
            instance = compute.get_instance(instance_id).data
        else:
            found = [
                i for i in compute.list_instances(compartment_id=compartment, display_name=server.server_name).data
                if i.lifecycle_state != "TERMINATED"
            ]
            if not found:
                return {"available": False, "reason": f"No OCI instance named {server.server_name}"}
            instance = found[0]

        attachments = compute.list_boot_volume_attachments(
            availability_domain=instance.availability_domain,
            compartment_id=instance.compartment_id,
            instance_id=instance.id,
        ).data
        if not attachments:
            return {"available": False, "reason": "No boot volume attached"}
        volume_id = attachments[0].boot_volume_id

        policy = None
        assigned = storage.get_volume_backup_policy_asset_assignment(asset_id=volume_id).data
        if assigned:
            pol = storage.get_volume_backup_policy(assigned[0].policy_id).data
            policy = {
                "name": pol.display_name,
                "schedules": [
                    {
                        "backup_type": sc.backup_type,
                        "period": sc.period,
                        "retention_days": round((sc.retention_seconds or 0) / 86400),
                        "time_zone": getattr(sc, "time_zone", None),
                    }
                    for sc in (pol.schedules or [])
                ],
            }

        backups = storage.list_boot_volume_backups(
            compartment_id=instance.compartment_id,
            boot_volume_id=volume_id,
            sort_by="TIMECREATED",
            sort_order="DESC",
            limit=limit,
        ).data

        runs = [
            {
                "name": b.display_name,
                "state": b.lifecycle_state,
                "confirmed": b.lifecycle_state == "AVAILABLE",
                "failed": b.lifecycle_state == "FAULTY",
                "type": b.type,
                "source": b.source_type,
                "created": str(b.time_created) if b.time_created else None,
                "expires": str(b.expiration_time) if b.expiration_time else None,
                "size_gb": b.size_in_gbs,
            }
            for b in backups
        ]
        last_ok = next((r["created"] for r in runs if r["confirmed"]), None)
        overdue = bool(policy) and (
            not last_ok or get_datetime(last_ok[:19]) < add_to_date(now_datetime(), hours=-26)
        )
        result = {
            "available": True,
            "policy": policy,
            "backups": runs,
            "errors": [r for r in runs if r["failed"]],
            "last_confirmed": last_ok,
            "overdue": overdue,
            "checked_at": str(now_datetime()),
        }
        frappe.cache().set_value(key, result, expires_in_sec=600)
        return result
    except Exception:
        frappe.log_error(frappe.get_traceback(), "client_api: OCI backup lookup failed")
        return {"available": False, "reason": "Could not reach OCI"}


# --------------------------------------------------------------------------
# Things waiting on the client (ToDos allocated to them)
# --------------------------------------------------------------------------

def _my_todos(ctx, project=None):
    rows = frappe.get_all(
        "ToDo",
        filters={"allocated_to": ctx.user, "imp_done": 0, "status": ["not in", ["Cancelled", "Closed"]]},
        fields=["name", "description", "date", "reference_type", "reference_name", "imp_urgency"],
        order_by="date asc",
    )
    out = []
    for r in rows:
        proj = None
        if r.reference_type == "Project":
            proj = r.reference_name
        elif r.reference_type == "Task":
            proj = frappe.db.get_value("Task", r.reference_name, "project")
        if proj and frappe.db.get_value("Project", proj, "customer") != ctx.customer:
            continue
        if project and proj != project:
            continue
        out.append({
            "name": r.name,
            "text": _strip_html(r.description),
            "due": r.date,
            "days_left": _days_left(r.date),
            "urgency": r.imp_urgency,
            "project": proj,
        })
    return out


@frappe.whitelist()
def get_my_actions(customer=None):
    ctx = _ctx(customer)
    return _my_todos(ctx)


@frappe.whitelist(methods=["POST"])
def complete_action(todo, customer=None):
    ctx = _ctx(customer)
    row = frappe.db.get_value("ToDo", todo, ["allocated_to", "reference_type", "reference_name", "assigned_by"], as_dict=True)
    if not row or row.allocated_to != ctx.user:
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    frappe.db.set_value("ToDo", todo, {"imp_done": 1, "status": "Closed"})
    if row.reference_type == "Task" and row.reference_name:
        from implementor.rollup import _recompute_task_progress
        _recompute_task_progress(row.reference_name)
    _notify(row.assigned_by, "Client completed: " + (_strip_html(frappe.db.get_value("ToDo", todo, "description")) or todo)[:120], "ToDo", todo)
    return _my_todos(ctx)


# --------------------------------------------------------------------------
# Tickets (Support Ticket)
# --------------------------------------------------------------------------

_TICKET_FIELDS = [
    "name", "subject", "project", "ticket_type", "priority", "status",
    "raised_by", "creation", "modified", "sla_due", "converted_task",
]


@frappe.whitelist()
def get_ticket_options(customer=None):
    """Dropdown values for the Raise Ticket form."""
    ctx = _ctx(customer)
    projects = _customer_projects(ctx)
    modules = frappe.get_all(
        "Project Module",
        filters={"parenttype": "Project", "parent": ["in", [p.name for p in projects] or [""]]},
        pluck="module_name",
    )
    return {
        "ticket_types": _options("Support Ticket", "ticket_type"),
        "priorities": _options("Support Ticket", "priority"),
        "projects": [{"name": p.name, "title": p.project_name, "kind": _project_kind(p.imp_status)} for p in projects],
        "modules": sorted(set(m for m in modules if m)),
    }


@frappe.whitelist()
def get_tickets(scope="open", project=None, search=None, limit=30, offset=0, customer=None):
    """scope: open | closed | all"""
    ctx = _ctx(customer)
    filters = {"customer": ctx.customer}
    if scope == "open":
        filters["status"] = ["in", OPEN_TICKET_STATUSES]
    elif scope == "closed":
        filters["status"] = ["in", CLOSED_TICKET_STATUSES]
    if project:
        _check_project(ctx, project)
        filters["project"] = project
    if not ctx.is_client_admin:
        filters["raised_by"] = ctx.user
    or_filters = None
    if search:
        or_filters = {"subject": ["like", f"%{search}%"], "name": ["like", f"%{search}%"]}

    rows = frappe.get_all(
        "Support Ticket",
        filters=filters,
        or_filters=or_filters,
        fields=_TICKET_FIELDS,
        order_by="creation desc",
        limit_start=cint(offset),
        limit_page_length=min(cint(limit) or 30, 100),
    )
    for r in rows:
        r["project_kind"] = _project_kind(frappe.db.get_value("Project", r.project, "imp_status")) if r.project else None
        r["needs_you"] = r.status in ("Waiting on Client", "Resolved")
    return rows


def _ticket_history(ticket, created):
    history = [{"status": "New", "at": created}]
    versions = frappe.get_all(
        "Version",
        filters={"ref_doctype": "Support Ticket", "docname": ticket},
        fields=["data", "creation"],
        order_by="creation asc",
    )
    for v in versions:
        try:
            changed = frappe.parse_json(v.data).get("changed", [])
        except Exception:
            continue
        for field, _old, new in changed:
            if field == "status" and new:
                history.append({"status": new, "at": v.creation})
    return history


@frappe.whitelist()
def get_ticket(ticket, customer=None):
    ctx = _ctx(customer)
    _check_ticket(ctx, ticket)
    t = frappe.db.get_value("Support Ticket", ticket, _TICKET_FIELDS + ["description", "resolution_notes"], as_dict=True)

    history = _ticket_history(ticket, t.creation)
    if history[-1]["status"] != t.status:
        # Support Ticket has Track Changes off, so Version rows may be missing.
        history.append({"status": t.status, "at": t.modified})
    reached = {}
    for h in history:
        reached[h["status"]] = h["at"]
    cur = TICKET_FLOW.index(t.status) if t.status in TICKET_FLOW else 0
    steps = [
        {"status": s, "at": reached.get(s), "done": i < cur, "current": i == cur}
        for i, s in enumerate(TICKET_FLOW)
        if s != "Waiting on Client" or s in reached or t.status == s
    ]

    assigned, hours, progress = [], None, None
    if t.converted_task:
        task = frappe.db.get_value("Task", t.converted_task, ["_assign", "imp_doing", "imp_actual_hours", "progress"], as_dict=True)
        if task:
            users = _parse_assign(task._assign) or ([task.imp_doing] if task.imp_doing else [])
            assigned = [_full_name(u) for u in users]
            hours, progress = task.imp_actual_hours, task.progress

    comments = frappe.get_all(
        "Comment",
        filters={"reference_doctype": "Support Ticket", "reference_name": ticket, "comment_type": "Comment"},
        fields=["name", "content", "comment_email", "comment_by", "creation"],
        order_by="creation asc",
    )

    return {
        "name": t.name,
        "subject": t.subject,
        "description": _strip_html(t.description),
        "project": t.project,
        "project_title": frappe.db.get_value("Project", t.project, "project_name") if t.project else None,
        "ticket_type": t.ticket_type,
        "priority": t.priority,
        "status": t.status,
        "raised_by": _full_name(t.raised_by),
        "created": t.creation,
        "sla_due": t.sla_due,
        "resolution_notes": _strip_html(t.resolution_notes),
        "assigned_to": assigned,
        "hours_logged": hours,
        "progress": progress,
        "steps": steps,
        "history": history,
        "needs_confirmation": t.status == "Resolved",
        "comments": [
            {
                "id": c.name,
                "text": _strip_html(c.content),
                "by": c.comment_by or _full_name(c.comment_email),
                "mine": c.comment_email == ctx.user,
                "at": c.creation,
            }
            for c in comments
        ],
        "attachments": frappe.get_all(
            "File",
            filters={"attached_to_doctype": "Support Ticket", "attached_to_name": ticket},
            fields=["name", "file_name", "file_size", "creation"],
        ),
    }


@frappe.whitelist(methods=["POST"])
def create_ticket(subject, description=None, ticket_type=None, priority=None, project=None,
                  module=None, reference=None, customer=None):
    """Raise a Support Ticket. Module and screen/document go into the description (no new fields)."""
    ctx = _ctx(customer)
    if project:
        _check_project(ctx, project)
    if ticket_type and ticket_type not in _options("Support Ticket", "ticket_type"):
        frappe.throw(_("Invalid ticket type"))
    if priority and priority not in _options("Support Ticket", "priority"):
        frappe.throw(_("Invalid priority"))

    lines = []
    if module:
        lines.append(f"Module: {module}")
    if reference:
        lines.append(f"Screen or document: {reference}")
    if lines:
        lines.append("")
    lines.append(description or "")

    doc = frappe.get_doc({
        "doctype": "Support Ticket",
        "subject": (subject or "").strip()[:140],
        "customer": ctx.customer,
        "project": project,
        "raised_by": ctx.user,
        "ticket_type": ticket_type or "Support",
        "priority": priority or "Normal",
        "status": "New",
        "description": "\n".join(lines).strip(),
    })
    if not doc.subject:
        frappe.throw(_("Subject is required"))
    doc.insert(ignore_permissions=True)

    if project:
        _notify(frappe.db.get_value("Project", project, "imp_project_manager"),
                f"New ticket {doc.name}: {doc.subject}", "Support Ticket", doc.name)
    return get_ticket(doc.name, customer=ctx.customer)


@frappe.whitelist(methods=["POST"])
def add_ticket_comment(ticket, text, customer=None):
    ctx = _ctx(customer)
    _check_ticket(ctx, ticket)
    text = (text or "").strip()
    if not text:
        frappe.throw(_("Comment is empty"))
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Comment",
        "reference_doctype": "Support Ticket",
        "reference_name": ticket,
        "content": frappe.utils.escape_html(text),
        "comment_email": ctx.user,
        "comment_by": _full_name(ctx.user),
    }).insert(ignore_permissions=True)

    if frappe.db.get_value("Support Ticket", ticket, "status") == "Waiting on Client":
        _set_ticket_status(ticket, "In Progress")
    return get_ticket(ticket, customer=ctx.customer)


@frappe.whitelist(methods=["POST"])
def confirm_fix(ticket, fixed, comment=None, customer=None):
    """Client testing step: on a Resolved ticket, close it or send it back."""
    ctx = _ctx(customer)
    _check_ticket(ctx, ticket)
    if frappe.db.get_value("Support Ticket", ticket, "status") != "Resolved":
        frappe.throw(_("This ticket is not waiting for your confirmation"))

    if cint(fixed):
        _set_ticket_status(ticket, "Closed")
        note = "Client confirmed the fix."
    else:
        if not (comment or "").strip():
            frappe.throw(_("Please tell us what is still wrong"))
        _set_ticket_status(ticket, "In Progress")
        note = "Client reports it is still an issue."
    if comment:
        note += " " + comment.strip()
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Comment",
        "reference_doctype": "Support Ticket",
        "reference_name": ticket,
        "content": frappe.utils.escape_html(note),
        "comment_email": ctx.user,
        "comment_by": _full_name(ctx.user),
    }).insert(ignore_permissions=True)
    return get_ticket(ticket, customer=ctx.customer)


def _set_ticket_status(ticket, status):
    doc = frappe.get_doc("Support Ticket", ticket)
    doc.status = status
    doc.save(ignore_permissions=True)  # save (not db.set_value) so Version history records it


@frappe.whitelist(methods=["POST"])
def upload_ticket_attachment(ticket, filename, filedata, customer=None):
    """filedata: base64 string (screenshot or screen recording)."""
    ctx = _ctx(customer)
    _check_ticket(ctx, ticket)
    if "," in filedata and filedata.strip().startswith("data:"):
        filedata = filedata.split(",", 1)[1]
    try:
        content = base64.b64decode(filedata)
    except Exception:
        frappe.throw(_("Invalid file data"))
    if len(content) > MAX_UPLOAD_BYTES:
        frappe.throw(_("File is larger than 10 MB"))

    f = frappe.get_doc({
        "doctype": "File",
        "file_name": filename,
        "attached_to_doctype": "Support Ticket",
        "attached_to_name": ticket,
        "is_private": 1,
        "content": content,
    })
    f.insert(ignore_permissions=True)
    return {"name": f.name, "file_name": f.file_name, "file_size": f.file_size}


@frappe.whitelist()
def download_attachment(file, customer=None):
    ctx = _ctx(customer)
    f = frappe.get_doc("File", file)
    if f.attached_to_doctype != "Support Ticket":
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    _check_ticket(ctx, f.attached_to_name)
    frappe.local.response.filename = f.file_name
    frappe.local.response.filecontent = f.get_content()
    frappe.local.response.type = "download"


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------

def _notify(user, subject, doctype, name):
    if not user:
        return
    frappe.get_doc({
        "doctype": "Notification Log",
        "subject": subject,
        "for_user": user,
        "type": "Alert",
        "document_type": doctype,
        "document_name": name,
    }).insert(ignore_permissions=True)


@frappe.whitelist()
def get_notifications(unread_only=0, limit=30, customer=None):
    ctx = _ctx(customer)
    filters = {"for_user": ctx.user}
    if cint(unread_only):
        filters["read"] = 0
    return frappe.get_all(
        "Notification Log",
        filters=filters,
        fields=["name", "subject", "document_type", "document_name", "read", "creation"],
        order_by="creation desc",
        limit_page_length=min(cint(limit) or 30, 100),
    )


@frappe.whitelist(methods=["POST"])
def mark_notification_read(name=None, mark_all=0, customer=None):
    ctx = _ctx(customer)
    if cint(mark_all):
        for n in frappe.get_all("Notification Log", filters={"for_user": ctx.user, "read": 0}, pluck="name"):
            frappe.db.set_value("Notification Log", n, "read", 1, update_modified=False)
        return {"success": True}
    if frappe.db.get_value("Notification Log", name, "for_user") != ctx.user:
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    frappe.db.set_value("Notification Log", name, "read", 1, update_modified=False)
    return {"success": True}
