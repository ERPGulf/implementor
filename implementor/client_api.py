# implementor/client_api.py
"""
Mobile client-app API for ERPGulf clients.

Reads and writes ONLY the doctypes Implementor already has:
    Project (+ Project Module, Payment Milestone child tables), Task, ToDo,
    Support Ticket, Server, Server Activity, Training Session, Integration,
    Notification Log, Comment, File, Contact.

No new doctypes. A few fields were added where the app needs data that had
nowhere to live (ratings and module on Support Ticket, site URL on Server,
action type on ToDo, hours included on Project).

Errors carry `error_code` beside the message so the app never matches text.

Status-like values (project status, health, milestone status, urgency,
ticket status, priority and type, ...) are sent as lowercase codes such as
"in_progress" or "waiting_on_client", never as the desk label. The app maps
each code to its own label, so renaming an option in the desk can't break it.

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

Background jobs (hooks.py → scheduler_events):
    refresh_oci_backups   every 10 minutes
    check_server_status   every 5 minutes

All endpoints: /api/method/implementor.client_api.<function>
"""

import base64
import html
import json
import mimetypes
import os
import re
from urllib.parse import quote
from zoneinfo import ZoneInfo

import frappe
import requests
from frappe import _
from frappe.utils import (
    add_to_date,
    cint,
    date_diff,
    get_datetime,
    get_system_timezone,
    getdate,
    now_datetime,
    nowdate,
)
from werkzeug.wrappers import Response

from implementor.api import _strip_html
from implementor.implementor.auth import is_admin

CLIENT_ADMIN = "Client Admin"
CLIENT_USER = "Client User"
OPEN_TICKET_STATUSES = ("New", "Triaged", "In Progress", "Waiting on Client", "Resolved")
CLOSED_TICKET_STATUSES = ("Closed",)
WAITING_TICKET_STATUSES = ("Waiting on Client", "Resolved")
TICKET_FLOW = ["New", "Triaged", "In Progress", "Waiting on Client", "Resolved", "Closed"]
SIGNOFF_TAG = "[client-signoff]"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ACTION_UPLOAD_TYPES = (".pdf", ".jpg", ".jpeg", ".png")
AMC_EXPIRING_DAYS = 30
DONE_ACTIONS_DAYS = 30
OCI_REFRESH_MIN_SECONDS = 120
OCI_CACHED_RUNS = 10  # runs the scheduler caches; smaller limits are served from the same cache
STATUS_SLOW_SECONDS = 3
STATUS_TIMEOUT_SECONDS = 10
OCI_REGION_LABELS = {
    "me-jeddah-1": "Jeddah",
    "me-riyadh-1": "Riyadh",
    "me-dubai-1": "Dubai",
    "me-abudhabi-1": "Abu Dhabi",
    "il-jerusalem-1": "Jerusalem",
    "ap-mumbai-1": "Mumbai",
    "ap-hyderabad-1": "Hyderabad",
    "eu-frankfurt-1": "Frankfurt",
    "uk-london-1": "London",
    "us-ashburn-1": "Ashburn",
}
# OCI schedule period → app frequency; OCI backup state → app state
OCI_PERIODS = {"ONE_HOUR": "hourly", "ONE_DAY": "daily", "ONE_WEEK": "weekly", "ONE_MONTH": "monthly", "ONE_YEAR": "yearly"}
OCI_STATES = {
    "AVAILABLE": "confirmed", "CREATING": "running", "REQUEST_RECEIVED": "queued",
    "FAULTY": "failed", "TERMINATING": "deleted", "TERMINATED": "deleted",
}


class ClientAPIError(frappe.ValidationError):
    def __init__(self, message, error_code, http_status_code=417):
        super().__init__(message)
        self.error_code = error_code
        self.http_status_code = http_status_code


def _fail(message, error_code, exception=None):
    """Raise a client-safe error: message in _server_messages, error_code beside it."""
    frappe.local.response["error_code"] = error_code
    frappe.msgprint(message, title=_("Error"), indicator="red")
    raise ClientAPIError(
        message=message,
        error_code=error_code,
        http_status_code=getattr(exception, "http_status_code", 417),
    )


def _require(**params):
    """417 instead of a 500 TypeError when the app leaves out a required parameter."""
    for name, value in params.items():
        if value in (None, ""):
            _fail(_("{0} is required").format(name), "missing_parameter")


def _iso(value):
    """Datetime as ISO 8601 with the server's offset, e.g. 2026-10-28T15:13:48+03:00."""
    if not value:
        return None
    tz = ZoneInfo(get_system_timezone())
    dt = get_datetime(value)
    dt = dt.replace(tzinfo=tz) if dt.tzinfo is None else dt.astimezone(tz)
    return dt.isoformat(timespec="seconds")


def _code(value):
    """Desk label → stable lowercase code: 'Waiting on Client' → 'waiting_on_client', 'Green' → 'green'."""
    if not value:
        return None
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_") or None


def _option_for(doctype, fieldname, value):
    """Accept a code ('bug_report') or a label ('Bug Report'); return the stored option, or None."""
    if not value:
        return None
    for option in _options(doctype, fieldname):
        if value == option or _code(value) == _code(option):
            return option
    return None


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
    # client app users are System Users, so Frappe would attach the Python traceback (`exc`) to errors
    frappe.local.flags.disable_traceback = True
    user = frappe.session.user
    if not user or user == "Guest":
        _fail(_("Please log in"), "not_logged_in", frappe.AuthenticationError)

    allowed = _customers_for_user(user)
    staff = is_admin(user)

    if customer:
        if customer not in allowed and not staff:
            _fail(_("Not permitted"), "not_permitted", frappe.PermissionError)
        if not frappe.db.exists("Customer", customer):
            _fail(_("Customer not found"), "not_found", frappe.DoesNotExistError)
    elif allowed:
        customer = allowed[0]
    else:
        _fail(_("This user is not linked to a customer"), "no_client_linked", frappe.PermissionError)

    roles = frappe.get_roles(user)
    return frappe._dict(
        user=user,
        customer=customer,
        customers=allowed,
        is_client_admin=staff or CLIENT_ADMIN in roles,
    )


def _check_project(ctx, project):
    if not project or frappe.db.get_value("Project", project, "customer") != ctx.customer:
        _fail(_("Not permitted"), "not_permitted", frappe.PermissionError)


def _check_server(ctx, server):
    if not server or frappe.db.get_value("Server", server, "customer") != ctx.customer:
        _fail(_("Not permitted"), "not_permitted", frappe.PermissionError)


def _check_ticket(ctx, ticket):
    row = frappe.db.get_value("Support Ticket", ticket, ["customer", "raised_by"], as_dict=True)
    if not row:
        _fail(_("Ticket {0} not found").format(ticket), "not_found", frappe.DoesNotExistError)
    if row.customer != ctx.customer:
        _fail(_("Not permitted"), "not_permitted", frappe.PermissionError)
    if not ctx.is_client_admin and row.raised_by != ctx.user:
        _fail(_("Not permitted"), "not_permitted", frappe.PermissionError)


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

@frappe.whitelist(methods=["GET"])
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
        "is_client_admin": ctx.is_client_admin,
    }


# --------------------------------------------------------------------------
# Home and services
# --------------------------------------------------------------------------

_PROJECT_FIELDS = [
    "name", "project_name", "imp_status", "imp_current_stage", "imp_health",
    "imp_percent", "percent_complete", "expected_start_date", "expected_end_date",
    "imp_deadline", "imp_go_live_date", "imp_project_manager", "status", "custom_hours_included",
]


def _display_title(title, customer, customer_name):
    """'ERPNext Implementation - Hamza Trading' → 'ERPNext Implementation'; the app already knows the customer."""
    if not title or " - " not in title:
        return title
    head, tail = title.rsplit(" - ", 1)
    names = [n.lower() for n in (customer_name, customer) if n]
    return head.strip() if any(tail.strip().lower().startswith(n) for n in names) else title


def _contract_status(end):
    days = _days_left(end)
    if days is None:
        return None
    if days < 0:
        return "expired"
    return "expiring" if days <= AMC_EXPIRING_DAYS else "active"


def _project_tickets(project):
    statuses = frappe.get_all("Support Ticket", filters={"project": project}, pluck="status")
    return {
        "open": len([s for s in statuses if s in OPEN_TICKET_STATUSES]),
        "closed": len([s for s in statuses if s in CLOSED_TICKET_STATUSES]),
    }


def _project_summary(p, customer=None, customer_name=None):
    kind = _project_kind(p.imp_status)
    end = p.expected_end_date or p.imp_deadline
    out = {
        "name": p.name,
        "title": p.project_name,
        "display_title": _display_title(p.project_name, customer, customer_name),
        "kind": kind,
        "status": _code(p.imp_status),
        "start_date": p.expected_start_date,
        "end_date": end,
        "days_left": _days_left(end),
        "project_manager": _full_name(p.imp_project_manager),
    }
    if kind == "implementation":
        phases = _options("Project", "imp_current_stage")
        out["stage"] = p.imp_current_stage
        out["phase"] = (
            {"index": phases.index(p.imp_current_stage) + 1, "count": len(phases), "name": p.imp_current_stage}
            if p.imp_current_stage in phases else None
        )
        out["health"] = _code(p.imp_health)
        out["percent"] = p.imp_percent if p.imp_percent is not None else p.percent_complete
        out["go_live_date"] = p.imp_go_live_date or p.imp_deadline
        out["go_live_days_left"] = _days_left(out["go_live_date"])
        out["next_milestone"] = _next_milestone(p.name)
    else:
        # stage, health and percent describe an implementation, not a support contract
        out["contract_status"] = _contract_status(end)
        out["elapsed_percent"] = _elapsed_pct(p.expected_start_date, end)
        out["hours_used"] = _hours_used(p.name)
        out["hours_included"] = p.custom_hours_included or None
        out["tickets"] = _project_tickets(p.name)
    return out


def _customer_projects(ctx, kind=None):
    filters = {"customer": ctx.customer, "status": ["!=", "Cancelled"], "custom_close_project": 0}
    if kind == "amc":
        filters["imp_status"] = "AMC"
    elif kind == "implementation":
        filters["imp_status"] = ["!=", "AMC"]
    return frappe.get_all("Project", filters=filters, fields=_PROJECT_FIELDS, order_by="modified desc")


def _project_summaries(ctx, kind=None):
    customer_name = frappe.db.get_value("Customer", ctx.customer, "customer_name")
    return [_project_summary(p, ctx.customer, customer_name) for p in _customer_projects(ctx, kind)]


_SERVER_FIELDS = [
    "name", "server_name", "site_url", "environment", "provider", "region", "specs",
    "custom_status", "status_checked_at", "custom_last_backup",
    "erpnext_version", "frappe_version", "backup_schedule", "ssl_expiry", "last_restore_test",
]


def _last_backup(s, oci):
    """Latest run from the cached OCI read, else the manually recorded time. Returns (last_backup, overdue)."""
    if oci and oci.get("available"):
        runs = oci.get("backups") or []
        latest = {"at": runs[0]["at"], "state": runs[0]["state"]} if runs else None
        return latest, oci.get("overdue")
    if s.custom_last_backup:
        overdue = bool(s.backup_schedule) and get_datetime(s.custom_last_backup) < add_to_date(now_datetime(), hours=-26)
        return {"at": _iso(s.custom_last_backup), "state": "recorded"}, overdue
    return None, None


def _server_summary(s):
    oci = _oci_cached(s.name)
    last_backup, overdue = _last_backup(s, oci)
    return {
        "name": s.name,
        "server_name": s.server_name,
        "site_url": s.site_url,
        "environment": s.environment,
        "provider": s.provider,
        "region": s.region,
        "region_label": OCI_REGION_LABELS.get(s.region),
        "status": _code(s.custom_status),
        "status_checked_at": _iso(s.status_checked_at),
        "erpnext_version": s.erpnext_version,
        "backup_schedule": s.backup_schedule,
        "backup_policy_name": ((oci or {}).get("policy") or {}).get("name"),
        "last_backup": last_backup,
        "overdue": overdue,
        "ssl_expiry": s.ssl_expiry,
        "ssl_days_left": _days_left(s.ssl_expiry),
        "last_restore_test": s.last_restore_test,
    }


def _customer_servers(ctx):
    return frappe.get_all("Server", filters={"customer": ctx.customer}, fields=_SERVER_FIELDS)


@frappe.whitelist()
def home(customer=None):
    """Counts and actions for Home; its service cards come from get_services."""
    ctx = _ctx(customer)
    ticket_filters = {"customer": ctx.customer, "status": ["in", OPEN_TICKET_STATUSES]}
    if not ctx.is_client_admin:
        ticket_filters["raised_by"] = ctx.user
    tickets = frappe.get_all("Support Ticket", filters=ticket_filters, fields=["status"])

    return {
        "customer": ctx.customer,
        "customer_name": frappe.db.get_value("Customer", ctx.customer, "customer_name"),
        "tickets": {
            "open": len(tickets),
            "waiting_for_you": len([t for t in tickets if t.status in WAITING_TICKET_STATUSES]),
        },
        "my_actions": _my_todos(ctx),
        "unread_notifications": frappe.db.count("Notification Log", {"for_user": ctx.user, "read": 0}),
    }


@frappe.whitelist()
def get_services(customer=None):
    """Services grouped the way the app shows them; Home and the Services list both read this."""
    ctx = _ctx(customer)
    projects = _project_summaries(ctx)
    return {
        "implementation": [p for p in projects if p["kind"] == "implementation"],
        "amc": [p for p in projects if p["kind"] == "amc"],
        "hosting": [_server_summary(s) for s in _customer_servers(ctx)],
    }


# --------------------------------------------------------------------------
# Projects, phases, modules, milestones
# --------------------------------------------------------------------------

SIGNOFF_READY = ("Completed", "Due")
SIGNOFF_REMARKS = " signed off by client: "


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
        content = r.content or ""
        row_name = content[len(SIGNOFF_TAG):].strip().split(" ")[0]
        if row_name:
            remarks = content.split(SIGNOFF_REMARKS, 1)[1] if SIGNOFF_REMARKS in content else None
            out[row_name] = {
                "by": _full_name(r.comment_email),
                "on": _iso(r.creation),
                "remarks": html.unescape(remarks) if remarks else None,
            }
    return out


def _milestone_state(r, signed_off, ready, is_admin):
    """The one state the Milestones tab shows, so every app applies the same rules."""
    if signed_off:
        return "signed_off"
    if ready:
        return "ready_for_sign_off" if is_admin else "awaiting_admin_sign_off"
    if r.completion_status == "On Hold":
        return "on_hold"
    if r.end_date and getdate(r.end_date) < getdate(nowdate()):
        return "overdue"
    if r.completion_status in ("In Progress", "Partially Completed"):
        return "in_progress"
    return "upcoming"


def _milestones(project, is_admin=False):
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
        signed_off = signed.get(r.name)
        ready = not signed_off and r.completion_status in SIGNOFF_READY
        out.append({
            "id": r.name,
            "title": r.m_title,
            "duration": r.duration,
            "start_date": r.start_date,
            "end_date": r.end_date,
            "days_left": None if done else _days_left(r.end_date),
            "status": _code(r.completion_status),
            "display_state": _milestone_state(r, signed_off, ready, is_admin),
            "percent": r.milestone_completion_perc,
            "modules": r.no_of_modules,
            "signed_off": signed_off,
            "ready_for_sign_off": ready,
            "can_sign_off": ready and is_admin,
        })
    return out


def _milestone_counts(ms):
    # ms holds the returned items, so status is already a code here
    return {
        "milestones": ms,
        "signed_off": len([m for m in ms if m["signed_off"]]),
        "completed": len([m for m in ms if m["status"] == "completed"]),
        "total": len(ms),
    }


def _next_milestone(project):
    for m in _milestones(project):
        if m["status"] != "completed" or m["ready_for_sign_off"]:
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
        out.append({
            "module": r.module_name,
            "in_scope": r.in_scope,
            "status": _code(r.module_status),
            "percent": percent,
        })
    return out


@frappe.whitelist()
def get_projects(customer=None, kind=None):
    """kind: implementation | amc | (empty for all)"""
    ctx = _ctx(customer)
    return _project_summaries(ctx, kind)


@frappe.whitelist()
def get_project(project=None, customer=None):
    """Project screen: header, phases, modules, milestones, training, integrations, actions."""
    ctx = _ctx(customer)
    _require(project=project)
    _check_project(ctx, project)
    p = frappe.db.get_value("Project", project, _PROJECT_FIELDS, as_dict=True)

    # phases only describe an implementation; an AMC project gets none
    phases = _options("Project", "imp_current_stage") if _project_kind(p.imp_status) == "implementation" else []
    current = phases.index(p.imp_current_stage) if p.imp_current_stage in phases else -1

    training = frappe.get_all(
        "Training Session",
        filters={"project": project},
        fields=["name", "topic", "trainer", "schedule"],
        order_by="schedule asc",
    )
    for t in training:
        t["trainer"] = _full_name(t.trainer)
        t["schedule"] = _iso(t.schedule)

    integrations = frappe.get_all(
        "Integration",
        filters={"project": project},
        fields=["name", "integration_name", "type", "vendor", "status"],
    )
    for i in integrations:
        i["status"] = _code(i.status)

    # same rule as get_tickets: a Client User only sees tickets they raised
    waiting_filters = {"project": project, "status": ["in", WAITING_TICKET_STATUSES]}
    if not ctx.is_client_admin:
        waiting_filters["raised_by"] = ctx.user
    waiting = frappe.get_all("Support Ticket", filters=waiting_filters, fields=["name", "subject", "status"])
    for w in waiting:
        w["status"] = _code(w.status)

    data = _project_summary(p, ctx.customer, frappe.db.get_value("Customer", ctx.customer, "customer_name"))
    data.update({
        "phases": [
            {"name": ph, "state": "done" if i < current else ("current" if i == current else "upcoming")}
            for i, ph in enumerate(phases)
        ],
        "modules": _modules(project),
        "milestones": _milestones(project, ctx.is_client_admin),
        "training": training,
        "integrations": integrations,
        "my_actions": _my_todos(ctx, project),
        "tickets_waiting_for_you": waiting,
    })
    return data


@frappe.whitelist()
def get_milestones(project=None, customer=None):
    ctx = _ctx(customer)
    _require(project=project)
    _check_project(ctx, project)
    return _milestone_counts(_milestones(project, ctx.is_client_admin))


@frappe.whitelist(methods=["POST"])
def sign_off_milestone(project=None, milestone=None, remarks=None, customer=None):
    """Client Admin accepts a milestone that is Completed or Due. A repeat returns the current state."""
    ctx = _ctx(customer)
    _require(project=project, milestone=milestone)
    _check_project(ctx, project)
    if not ctx.is_client_admin:
        _fail(_("Only a Client Admin can sign off milestones"), "not_client_admin", frappe.PermissionError)

    row = frappe.db.get_value(
        "Payment Milestone",
        {"name": milestone, "parent": project, "parenttype": "Project"},
        ["name", "m_title", "completion_status"],
        as_dict=True,
    )
    if not row:
        _fail(_("Milestone not found"), "not_found", frappe.DoesNotExistError)

    # a phone retrying after a dropped response must not get an error for a sign-off that worked
    if row.name not in _signoffs(project):
        if row.completion_status not in SIGNOFF_READY:
            _fail(_("This milestone is not ready for sign-off"), "not_ready_for_sign_off")
        text = f"{SIGNOFF_TAG} {row.name} Milestone '{row.m_title}' signed off by client"
        if remarks:
            text += f": {frappe.utils.escape_html(remarks)}"  # _signoffs reads it back after SIGNOFF_REMARKS
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

    _close_signoff_actions(project, row)
    return _milestone_counts(_milestones(project, ctx.is_client_admin))


def _signoff_target(todo, titles):
    """Milestone id a sign-off action is about. titles: {m_title: id} for the action's project."""
    if todo.reference_type == "Payment Milestone":
        return todo.reference_name
    text = _strip_html(todo.description) or ""
    if "sign off" not in text.lower():
        return None
    return next((mid for title, mid in titles.items() if title and f"'{title}'" in text), None)


def _close_signoff_actions(project, row):
    """Close the open "Sign off the '<title>' milestone" actions once that milestone is signed off."""
    todos = frappe.get_all(
        "ToDo",
        filters={"imp_done": 0, "status": "Open", "reference_type": ["in", ["Project", "Payment Milestone"]],
                 "reference_name": ["in", [project, row.name]]},
        fields=["name", "description", "reference_type", "reference_name"],
    )
    for t in todos:
        if _signoff_target(t, {row.m_title: row.name}) == row.name:
            frappe.db.set_value("ToDo", t.name, {"imp_done": 1, "status": "Closed"})


# --------------------------------------------------------------------------
# AMC
# --------------------------------------------------------------------------

@frappe.whitelist()
def get_amc(project=None, customer=None):
    ctx = _ctx(customer)
    _require(project=project)
    _check_project(ctx, project)
    p = frappe.db.get_value("Project", project, _PROJECT_FIELDS, as_dict=True)
    if p.imp_status != "AMC":
        _fail(_("Not an AMC project"), "not_amc_project")
    return _project_summary(p, ctx.customer, frappe.db.get_value("Customer", ctx.customer, "customer_name"))


# --------------------------------------------------------------------------
# Hosting and backup
# --------------------------------------------------------------------------

def _spec_gb(match):
    value = float(match.group(1)) * (1024 if match.group(2) == "tb" else 1)
    return int(value) if value.is_integer() else value


def _parse_specs(text):
    """'4 OCPU (Ampere A1)\n24 GB RAM\n200 GB Block Volume\nUbuntu 22.04 LTS' → cpu, memory_gb, storage_gb, os."""
    out = {"cpu": None, "memory_gb": None, "storage_gb": None, "os": None}
    for line in (text or "").splitlines():
        line = line.strip()
        low = line.lower()
        size = re.match(r"([\d.]+)\s*(gb|tb)\b", low)
        if not line:
            continue
        if "cpu" in low and not out["cpu"]:
            out["cpu"] = line
        elif size and ("ram" in low or "memory" in low):
            out["memory_gb"] = _spec_gb(size)
        elif size and out["storage_gb"] is None:
            out["storage_gb"] = _spec_gb(size)
        elif not out["os"]:
            out["os"] = line
    return out


@frappe.whitelist()
def get_servers(customer=None):
    ctx = _ctx(customer)
    return [_server_summary(s) for s in _customer_servers(ctx)]


@frappe.whitelist()
def get_server(server=None, customer=None):
    ctx = _ctx(customer)
    _require(server=server)
    _check_server(ctx, server)
    s = frappe.db.get_value("Server", server, _SERVER_FIELDS, as_dict=True)
    activity = frappe.get_all(
        "Server Activity",
        filters={"server": server},
        fields=["activity_type", "date", "downtime_window", "workflow_state"],
        order_by="date desc",
        limit=20,
    )
    for a in activity:
        a["date"] = _iso(a.date)
        a["activity_type"] = _code(a.activity_type)
        a["workflow_state"] = _code(a.workflow_state)
    data = _server_summary(s)
    data.update({
        "specs": _parse_specs(s.specs),
        "specs_text": s.specs,
        "frappe_version": s.frappe_version,
        "activity": activity,
    })
    return data


@frappe.whitelist()
def get_backups(server=None, limit=10, refresh=0, customer=None):
    """Backup policy and recent runs. Live data comes from OCI when configured."""
    ctx = _ctx(customer)
    _require(server=server)
    _check_server(ctx, server)
    s = frappe.db.get_value("Server", server, _SERVER_FIELDS, as_dict=True)
    restores = frappe.get_all(
        "Server Activity",
        filters={"server": server, "activity_type": "Restore"},
        fields=["date", "workflow_state", "downtime_window"],
        order_by="date desc",
        limit=5,
    )
    for r in restores:
        r["date"] = _iso(r.date)
        r["workflow_state"] = _code(r.workflow_state)
    return {
        "server": server,
        "server_name": s.server_name,
        "backup_schedule": s.backup_schedule,
        "last_restore_test": s.last_restore_test,
        "restores": restores,
        "oci": _oci_backups(s, min(cint(limit) or OCI_CACHED_RUNS, 50), cint(refresh)),
    }


def _oci_cached(server):
    """The last OCI read for a server (filled by get_backups and the scheduler), or None."""
    return frappe.cache().get_value(f"implementor_oci_latest:{server}")


def _keep(seconds):
    """Retention in the largest whole unit: 1209600 → (2, 'weeks')."""
    seconds = int(seconds or 0)
    for unit, size in (("years", 365 * 86400), ("months", 30 * 86400), ("weeks", 7 * 86400), ("days", 86400), ("hours", 3600)):
        if seconds >= size and seconds % size == 0:
            return seconds // size, unit
    return round(seconds / 86400), "days"


def _first_runs(result, limit):
    """The OCI result with only the newest `limit` runs, so a small limit can use the scheduler's cache."""
    runs = result.get("backups") or []
    if not result.get("available") or len(runs) <= limit:
        return result
    out = dict(result)
    out["backups"] = runs[:limit]
    return out


def refresh_oci_backups():
    """Scheduler (every 10 minutes): read OCI so client requests never wait on it."""
    if not (frappe.conf.get("implementor_oci") or {}).get("compartment_id"):
        return
    for s in frappe.get_all("Server", filters={"customer": ["is", "set"]}, fields=_SERVER_FIELDS):
        _oci_backups(s, OCI_CACHED_RUNS, refresh=1, scheduled=True)


def check_server_status():
    """Scheduler (every 5 minutes): ping each server's site and save Online, Degraded or Offline."""
    servers = frappe.get_all(
        "Server", filters={"customer": ["is", "set"], "site_url": ["is", "set"]}, fields=["name", "site_url"]
    )
    for s in servers:
        url = s.site_url.strip()
        url = url if url.startswith("http") else f"https://{url}"
        try:
            r = requests.get(f"{url.rstrip('/')}/api/method/ping", timeout=STATUS_TIMEOUT_SECONDS)
            slow = r.elapsed.total_seconds() > STATUS_SLOW_SECONDS
            status = "Online" if r.ok and not slow else "Degraded"
        except requests.RequestException:
            status = "Offline"
        frappe.db.set_value(
            "Server", s.name,
            {"custom_status": status, "status_checked_at": now_datetime()},
            update_modified=False,
        )
    frappe.db.commit()


def _oci_backups(server, limit, refresh, scheduled=False):
    """
    Reads the boot volume backups of the server's OCI instance.

    site_config.json:
      "implementor_oci": {
        "config_file": "/home/frappe/.oci/config",
        "profile": "DEFAULT",
        "compartment_id": "ocid1.compartment...",
        "instances": {"<Server name>": "ocid1.instance..."}   # optional; else matched by display name
      }

    The reason OCI is unavailable goes to the Error Log, never to the client.
    """
    conf = frappe.conf.get("implementor_oci") or {}
    if not conf.get("compartment_id"):
        return {"available": False}
    try:
        import oci
    except ImportError:
        frappe.log_error("OCI SDK is not installed", "client_api: OCI backup lookup failed")
        return {"available": False}

    # read at least as many runs as the scheduler does, so every limit up to that shares its cache
    fetch = max(limit, OCI_CACHED_RUNS)
    key = f"implementor_oci_backups:{server.name}:{fetch}"
    if refresh and not scheduled:
        # any client can ask for refresh=1, so one forced OCI call per server every couple of minutes
        throttle = f"implementor_oci_refreshed:{server.name}"
        if frappe.cache().get_value(throttle):
            refresh = 0
        else:
            frappe.cache().set_value(throttle, 1, expires_in_sec=OCI_REFRESH_MIN_SECONDS)
    if not refresh:
        cached = frappe.cache().get_value(key)
        if cached:
            return _first_runs(cached, limit)

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
                frappe.log_error(f"No OCI instance named {server.server_name}", "client_api: OCI backup lookup failed")
                return {"available": False}
            instance = found[0]

        attachments = compute.list_boot_volume_attachments(
            availability_domain=instance.availability_domain,
            compartment_id=instance.compartment_id,
            instance_id=instance.id,
        ).data
        if not attachments:
            frappe.log_error(f"No boot volume attached to {server.server_name}", "client_api: OCI backup lookup failed")
            return {"available": False}
        volume_id = attachments[0].boot_volume_id

        policy, schedules = None, []
        assigned = storage.get_volume_backup_policy_asset_assignment(asset_id=volume_id).data
        if assigned:
            pol = storage.get_volume_backup_policy(assigned[0].policy_id).data
            schedules = pol.schedules or []
            policy = {"name": pol.display_name, "rules": []}
            for sc in schedules:
                keep_value, keep_unit = _keep(sc.retention_seconds)
                policy["rules"].append({
                    "frequency": OCI_PERIODS.get(sc.period, (sc.period or "").lower()),
                    "type": (sc.backup_type or "").lower(),
                    "keep_value": keep_value,
                    "keep_unit": keep_unit,
                })

        backups = storage.list_boot_volume_backups(
            compartment_id=instance.compartment_id,
            boot_volume_id=volume_id,
            sort_by="TIMECREATED",
            sort_order="DESC",
            limit=fetch,
        ).data

        def frequency(b):
            # a run's frequency is the policy schedule with its type and retention
            if b.source_type == "MANUAL":
                return "manual"
            if b.time_created and b.expiration_time:
                kept = (b.expiration_time - b.time_created).total_seconds()
                for sc in schedules:
                    if (sc.backup_type or "") == (b.type or "") and abs(kept - (sc.retention_seconds or 0)) < 86400:
                        return OCI_PERIODS.get(sc.period)
            return None

        runs = [
            {
                "name": b.display_name,
                "at": _iso(b.time_created),
                "expires_at": _iso(b.expiration_time),
                "frequency": frequency(b),
                "type": (b.type or "").lower(),
                "state": OCI_STATES.get(b.lifecycle_state, (b.lifecycle_state or "").lower()),
                "size_gb": b.size_in_gbs,
            }
            for b in backups
        ]
        created = [b.time_created for b in backups]

        errors = []
        for i, r in enumerate(runs):
            if r["state"] != "failed":
                continue
            # newest-first, so the next confirmed run after a failure sits earlier in the list
            retry = next((x for x in reversed(runs[:i]) if x["state"] == "confirmed"), None)
            errors.append({
                "at": r["at"],
                "message": "The backup did not complete.",
                "resolved_at": retry["at"] if retry else None,
                "resolution": "A later backup completed and was confirmed." if retry else None,
            })

        last_ok = next((created[i] for i, r in enumerate(runs) if r["state"] == "confirmed"), None)
        tz = ZoneInfo(get_system_timezone())
        overdue = bool(policy) and (
            not last_ok or last_ok.astimezone(tz).replace(tzinfo=None) < add_to_date(now_datetime(), hours=-26)
        )
        result = {
            "available": True,
            "fetched_at": _iso(now_datetime()),
            "policy": policy,
            "backups": runs,
            "errors": errors,
            "last_confirmed_at": _iso(last_ok),
            "overdue": overdue,
        }
        frappe.cache().set_value(key, result, expires_in_sec=900)
        frappe.cache().set_value(f"implementor_oci_latest:{server.name}", result, expires_in_sec=86400)
        return _first_runs(result, limit)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "client_api: OCI backup lookup failed")
        return {"available": False}


# --------------------------------------------------------------------------
# Things waiting on the client (ToDos allocated to them)
# --------------------------------------------------------------------------

def _action_cta(todo, milestone):
    """What the action asks for: upload, sign_off, review or mark_done. imp_cta wins when set."""
    if todo.imp_cta:
        return _code(todo.imp_cta)
    if milestone:
        return "sign_off"
    text = (_strip_html(todo.description) or "").strip().lower()
    if text.startswith(("upload", "share", "send", "attach", "provide")):
        return "upload"
    if text.startswith(("review", "approve", "check", "verify")):
        return "review"
    return "mark_done"


def _my_todos(ctx, project=None, status="open"):
    """status: open (default) | done (finished in the last DONE_ACTIONS_DAYS days)."""
    fields = ["name", "description", "date", "reference_type", "reference_name", "imp_urgency", "imp_cta", "modified"]
    if status == "done":
        rows = frappe.get_all(
            "ToDo",
            filters={"allocated_to": ctx.user, "status": ["!=", "Cancelled"],
                     "modified": [">=", add_to_date(now_datetime(), days=-DONE_ACTIONS_DAYS)]},
            or_filters={"imp_done": 1, "status": "Closed"},
            fields=fields,
            order_by="modified desc",
        )
    else:
        rows = frappe.get_all(
            "ToDo",
            filters={"allocated_to": ctx.user, "imp_done": 0, "status": ["not in", ["Cancelled", "Closed"]]},
            fields=fields,
            order_by="date asc",
        )
    titles = {}
    out = []
    for r in rows:
        proj = None
        if r.reference_type == "Project":
            proj = r.reference_name
        elif r.reference_type == "Task":
            proj = frappe.db.get_value("Task", r.reference_name, "project")
        elif r.reference_type == "Payment Milestone":
            proj = frappe.db.get_value("Payment Milestone", r.reference_name, "parent")
        if proj and frappe.db.get_value("Project", proj, "customer") != ctx.customer:
            continue
        if project and proj != project:
            continue
        if proj not in titles:
            titles[proj] = dict(frappe.get_all(
                "Payment Milestone", filters={"parent": proj, "parenttype": "Project"}, fields=["m_title", "name"], as_list=True
            )) if proj else {}
        milestone = _signoff_target(r, titles[proj])
        if milestone:
            reference = {"doctype": "Payment Milestone", "name": milestone}
        elif r.reference_type and r.reference_name:
            reference = {"doctype": r.reference_type, "name": r.reference_name}
        else:
            reference = None
        done = status == "done"
        out.append({
            "name": r.name,
            "text": _strip_html(r.description),
            "due": r.date,
            "days_left": None if done else _days_left(r.date),
            "urgency": _code(r.imp_urgency),
            "project": proj,
            "cta": _action_cta(r, milestone),
            "reference": reference,
            "status": "done" if done else "open",
            "completed_on": _iso(r.modified) if done else None,
        })
    return out


def _own_todo(ctx, todo):
    row = frappe.db.get_value(
        "ToDo", todo, ["allocated_to", "reference_type", "reference_name", "assigned_by", "imp_done", "description"], as_dict=True
    )
    if not row or row.allocated_to != ctx.user:
        _fail(_("Not permitted"), "not_permitted", frappe.PermissionError)
    return row


def _complete_todo(todo, row):
    if row.imp_done:  # a repeat after a dropped response changes nothing
        return
    frappe.db.set_value("ToDo", todo, {"imp_done": 1, "status": "Closed"})
    if row.reference_type == "Task" and row.reference_name:
        from implementor.rollup import _recompute_task_progress
        _recompute_task_progress(row.reference_name)
    _notify(row.assigned_by, "Client completed: " + (_strip_html(row.description) or todo)[:120], "ToDo", todo)


@frappe.whitelist()
def get_my_actions(customer=None, status="open", project=None):
    ctx = _ctx(customer)
    if status not in ("open", "done"):
        _fail(_("status must be open or done"), "invalid_parameter")
    if project:
        _check_project(ctx, project)
    return _my_todos(ctx, project, status)


@frappe.whitelist(methods=["POST"])
def complete_action(todo=None, customer=None):
    ctx = _ctx(customer)
    _require(todo=todo)
    _complete_todo(todo, _own_todo(ctx, todo))
    return _my_todos(ctx)


def _uploaded_file(filename, filedata):
    """A multipart `file`, or `filename` + base64 `filedata` (as upload_ticket_attachment takes)."""
    upload = frappe.request.files.get("file") if frappe.request and frappe.request.files else None
    if upload:
        filename, content = upload.filename, upload.stream.read()
    else:
        _require(file=filedata, filename=filename)
        if "," in filedata and filedata.strip().startswith("data:"):
            filedata = filedata.split(",", 1)[1]
        try:
            content = base64.b64decode(filedata)
        except Exception:
            _fail(_("Invalid file data"), "invalid_file")
    if not content:
        _fail(_("The file is empty"), "invalid_file")
    if len(content) > MAX_UPLOAD_BYTES:
        _fail(_("File is larger than 10 MB"), "file_too_large")
    if os.path.splitext(filename or "")[1].lower() not in ACTION_UPLOAD_TYPES:
        _fail(_("Only PDF, JPG and PNG files are allowed"), "invalid_file_type")
    return filename, content


@frappe.whitelist(methods=["POST"])
def upload_action_attachment(todo=None, filename=None, filedata=None, note=None, complete=0, customer=None):
    """Answer an action that asks for a file: one file per call, complete=1 on the last one."""
    ctx = _ctx(customer)
    _require(todo=todo)
    row = _own_todo(ctx, todo)
    if not row.imp_done:  # a retry on a finished action just returns the list
        filename, content = _uploaded_file(filename, filedata)
        if row.reference_type and row.reference_name:
            attach_to = (row.reference_type, row.reference_name)
        else:
            attach_to = ("ToDo", todo)
        frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "attached_to_doctype": attach_to[0],
            "attached_to_name": attach_to[1],
            "is_private": 1,
            "content": content,
        }).insert(ignore_permissions=True)
        if note and note.strip():
            frappe.get_doc({
                "doctype": "Comment",
                "comment_type": "Comment",
                "reference_doctype": attach_to[0],
                "reference_name": attach_to[1],
                "content": frappe.utils.escape_html(f"{filename}: {note.strip()}"),
                "comment_email": ctx.user,
                "comment_by": _full_name(ctx.user),
            }).insert(ignore_permissions=True)
        if cint(complete):
            _complete_todo(todo, row)
    return _my_todos(ctx)


# --------------------------------------------------------------------------
# Tickets (Support Ticket)
# --------------------------------------------------------------------------

_TICKET_FIELDS = [
    "name", "subject", "project", "ticket_type", "priority", "status",
    "raised_by", "creation", "modified", "sla_due", "converted_task", "module",
]
_RATING_FIELDS = ["rating_overall", "rating_quality", "rating_communication", "rating_response_time"]
RATING_STARS = 5


@frappe.whitelist()
def get_ticket_options(customer=None):
    """Dropdown values for the Raise Ticket form. Send `value` back to create_ticket; show `label`."""
    ctx = _ctx(customer)
    projects = _customer_projects(ctx)
    modules = frappe.get_all(
        "Project Module",
        filters={"parenttype": "Project", "parent": ["in", [p.name for p in projects] or [""]]},
        pluck="module_name",
    )
    return {
        "ticket_types": [{"value": _code(o), "label": o} for o in _options("Support Ticket", "ticket_type")],
        "priorities": [{"value": _code(o), "label": o} for o in _options("Support Ticket", "priority")],
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
    page_size = min(cint(limit) or 30, 100)

    rows = frappe.get_all(
        "Support Ticket",
        filters=filters,
        or_filters=or_filters,
        fields=_TICKET_FIELDS,
        order_by="creation desc",
        limit_start=cint(offset),
        limit_page_length=page_size + 1,  # one extra row tells us whether another page exists
    )
    # top-level key beside `message`, so the list itself keeps its shape
    frappe.response["has_more"] = len(rows) > page_size
    rows = rows[:page_size]
    for r in rows:
        r["created"] = r.creation
        proj = frappe.db.get_value("Project", r.project, ["imp_status", "project_name"], as_dict=True) if r.project else None
        r["project_title"] = proj.project_name if proj else None
        r["project_kind"] = _project_kind(proj.imp_status) if proj else None
        r["needs_you"] = r.status in WAITING_TICKET_STATUSES
        r["status"] = _code(r.status)
        r["priority"] = _code(r.priority)
        r["ticket_type"] = _code(r.ticket_type)
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
def get_ticket(ticket=None, customer=None):
    ctx = _ctx(customer)
    _require(ticket=ticket)
    _check_ticket(ctx, ticket)
    t = frappe.db.get_value("Support Ticket", ticket, _TICKET_FIELDS + ["description", "resolution_notes"] + _RATING_FIELDS, as_dict=True)

    history = _ticket_history(ticket, t.creation)
    if history[-1]["status"] != t.status:
        # Support Ticket has Track Changes off, so Version rows may be missing.
        history.append({"status": t.status, "at": t.modified})
    reached = {}
    for h in history:
        reached[h["status"]] = h["at"]
    cur = TICKET_FLOW.index(t.status) if t.status in TICKET_FLOW else 0
    steps = [
        {"status": _code(s), "at": reached.get(s), "done": i < cur, "current": i == cur}
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
        "module": t.module,
        "ticket_type": _code(t.ticket_type),
        "priority": _code(t.priority),
        "status": _code(t.status),
        "raised_by": _full_name(t.raised_by),
        "created": t.creation,
        "sla_due": t.sla_due,
        "resolution_notes": _strip_html(t.resolution_notes),
        "assigned_to": assigned,
        "hours_logged": hours,
        "progress": progress,
        "steps": steps,
        "history": [{"status": _code(h["status"]), "at": h["at"]} for h in history],
        "needs_confirmation": t.status == "Resolved",
        "ratings": {f: round(t[f] * RATING_STARS) if t[f] else None for f in _RATING_FIELDS},
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
def create_ticket(subject=None, description=None, ticket_type=None, priority=None, project=None,
                  module=None, reference=None, customer=None):
    """Raise a Support Ticket. ticket_type and priority take the code from get_ticket_options
    (older builds may still send the label). Module is saved on its own field and, for older app
    builds, also written into the description with the screen/document."""
    ctx = _ctx(customer)
    if not (subject or "").strip():
        _fail(_("Subject is required"), "missing_parameter")
    if project:
        _check_project(ctx, project)

    type_option = _option_for("Support Ticket", "ticket_type", ticket_type) if ticket_type else "Support"
    if not type_option:
        _fail(_("Invalid ticket type"), "invalid_ticket_type")
    priority_option = _option_for("Support Ticket", "priority", priority) if priority else "Normal"
    if not priority_option:
        _fail(_("Invalid priority"), "invalid_priority")

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
        "subject": subject.strip()[:140],
        "customer": ctx.customer,
        "project": project,
        "raised_by": ctx.user,
        "ticket_type": type_option,
        "priority": priority_option,
        "status": "New",
        "module": (module or "").strip() or None,
        "description": "\n".join(lines).strip(),
    })
    doc.insert(ignore_permissions=True)

    if project:
        _notify(frappe.db.get_value("Project", project, "imp_project_manager"),
                f"New ticket {doc.name}: {doc.subject}", "Support Ticket", doc.name)
    return get_ticket(doc.name, customer=ctx.customer)


@frappe.whitelist(methods=["POST"])
def add_ticket_comment(ticket=None, text=None, customer=None):
    ctx = _ctx(customer)
    _require(ticket=ticket)
    _check_ticket(ctx, ticket)
    text = (text or "").strip()
    if not text:
        _fail(_("Comment is empty"), "comment_required")
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
def confirm_fix(ticket=None, fixed=None, comment=None, customer=None, rating_overall=None,
                rating_quality=None, rating_communication=None, rating_response_time=None):
    """Client testing step: on a Resolved ticket, close it or send it back.
    Ratings are optional, 1–5 stars each."""
    ctx = _ctx(customer)
    _require(ticket=ticket, fixed=fixed)
    _check_ticket(ctx, ticket)
    if frappe.db.get_value("Support Ticket", ticket, "status") != "Resolved":
        _fail(_("This ticket is not waiting for your confirmation"), "not_waiting_for_confirmation")

    ratings = {}
    for field, value in (("rating_overall", rating_overall), ("rating_quality", rating_quality),
                         ("rating_communication", rating_communication),
                         ("rating_response_time", rating_response_time)):
        if value in (None, ""):
            continue
        stars = cint(value)
        if str(stars) != str(value).strip() or not 1 <= stars <= 5:
            _fail(_("{0} must be a whole number from 1 to 5").format(field), "invalid_rating")
        ratings[field] = stars / RATING_STARS  # Rating fields store a 0–1 fraction
    if ratings:
        frappe.db.set_value("Support Ticket", ticket, ratings)

    if cint(fixed):
        _set_ticket_status(ticket, "Closed")
        note = "Client confirmed the fix."
    else:
        if not (comment or "").strip():
            _fail(_("Please tell us what is still wrong"), "comment_required")
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
def upload_ticket_attachment(ticket=None, filename=None, filedata=None, customer=None):
    """filedata: base64 string (screenshot or screen recording)."""
    ctx = _ctx(customer)
    _require(ticket=ticket, filename=filename, filedata=filedata)
    _check_ticket(ctx, ticket)
    if "," in filedata and filedata.strip().startswith("data:"):
        filedata = filedata.split(",", 1)[1]
    try:
        content = base64.b64decode(filedata)
    except Exception:
        _fail(_("Invalid file data"), "invalid_file")
    if len(content) > MAX_UPLOAD_BYTES:
        _fail(_("File is larger than 10 MB"), "file_too_large")

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
def download_attachment(file=None, customer=None):
    ctx = _ctx(customer)
    _require(file=file)
    row = frappe.db.get_value("File", file, ["attached_to_doctype", "attached_to_name"], as_dict=True)
    # unknown file and another record's file answer the same, so IDs can't be probed
    if not row or row.attached_to_doctype != "Support Ticket":
        _fail(_("Not permitted"), "not_permitted", frappe.PermissionError)
    _check_ticket(ctx, row.attached_to_name)
    f = frappe.get_doc("File", file)
    # built by hand: Frappe's download response leaves filename unquoted
    name = (f.file_name or "download").replace("\r", "").replace("\n", "")
    stem, ext = os.path.splitext(name)
    ascii_stem = stem.encode("ascii", "ignore").decode().replace('"', "").replace("\\", "").strip()
    ascii_name = (ascii_stem or "download") + ext.encode("ascii", "ignore").decode()
    response = Response(f.get_content(), mimetype=mimetypes.guess_type(name)[0] or "application/octet-stream")
    response.headers["Content-Disposition"] = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"
    return response


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
    _require(name=name)
    if frappe.db.get_value("Notification Log", name, "for_user") != ctx.user:
        _fail(_("Not permitted"), "not_permitted", frappe.PermissionError)
    frappe.db.set_value("Notification Log", name, "read", 1, update_modified=False)
    return {"success": True}