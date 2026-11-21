# implementor/client_notifications.py
"""
Notifications for client-app users (Client Admin / Client User).

Each notification is sent two ways:
    1. a Notification Log row (type Alert, imp_kind = the code below). This is what the
       app's Notifications screen lists (client_api.get_notifications) and what the bell
       badge counts (client_api.home → unread_notifications).
    2. a Firebase push to the user's device token (Employee.custom_token, matched on
       Employee.user_id), queued after the transaction commits. Skipped quietly when the
       user has no token or Firebase is switched off in Whatsapp Saudi settings.

Only users with a client role are notified, and never for their own action.
Notifications to ERPGulf staff stay in client_api._notify.

kind codes (sent as `kind` in get_notifications and in the push data):
    ticket_waiting_on_client  ticket status → Waiting on Client          → ticket raiser
    ticket_resolved           ticket status → Resolved (confirm + rate)  → ticket raiser
    ticket_status_changed     any other ticket status change by our team → ticket raiser
    ticket_reply              our team comments on the ticket            → ticket raiser
    action_assigned           a to-do is assigned to a client user       → that user
    action_due_soon           daily: an open action is due tomorrow      → that user
    action_overdue            daily: an open action was due yesterday    → that user
    milestone_ready           a milestone becomes ready for sign-off     → the customer's Client Admins
    project_status_changed    the project's imp_status changes           → all the customer's client users
    payment_due               a milestone's payment_status → Pending     → Client Admins
    payment_overdue           a milestone's payment_status → Overdue     → Client Admins
    amc_expiring              daily: AMC ends in 30 or 7 days            → Client Admins
    amc_expired               daily: AMC ended yesterday                 → Client Admins
    server_down               server status check: → Offline             → all the customer's client users
    server_up                 server status check: Offline → Online      → all the customer's client users
    backup_overdue            OCI check: no confirmed backup in 26 hours → all the customer's client users
    backup_failed             OCI check: the newest backup run failed    → all the customer's client users
    training_scheduled        a Training Session is added or moved       → all the customer's client users
    training_reminder         daily: a Training Session is tomorrow      → all the customer's client users

Daily checks: daily_reminders(), cron "0 8 * * *" in hooks.py.
"""

import json

import frappe
from firebase_admin import credentials, messaging
from firebase_admin.exceptions import InvalidArgumentError

from implementor.api import _strip_html
from implementor.implementor.auth import is_admin

CLIENT_ADMIN = "Client Admin"
CLIENT_USER = "Client User"

# ticket status → (kind, title, body template)
_TICKET_STATUS = {
    "Waiting on Client": (
        "ticket_waiting_on_client",
        "Your reply is needed",
        "Ticket {name}: {subject} is waiting for your reply.",
    ),
    "Resolved": (
        "ticket_resolved",
        "Ticket resolved",
        "Ticket {name}: {subject} has been resolved. Please check the fix and rate our support.",
    ),
}
_TICKET_STATUS_DEFAULT = ("ticket_status_changed", "Ticket updated", "Ticket {name}: {subject} is now {status}.")


# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------

def has_client_role(user):
    if not user or user in ("Guest", "Administrator"):
        return False
    roles = frappe.get_roles(user)
    return CLIENT_ADMIN in roles or CLIENT_USER in roles


def is_client_user(user):
    """A client acting in the app (client role, not staff). Their own actions never notify them."""
    return has_client_role(user) and not is_admin(user)


def notify_client(users, kind, title, body, doctype=None, name=None, skip_actor=True, once_per_day=False):
    """Write a Notification Log row and queue a push for each user in `users` that has a client role.

    skip_actor: leave out the session user (their own action). False for system events (server,
        backup), which may run inside a client's request.
    once_per_day: skip a user who already got this kind for this record today (daily checks run again).
    """
    actor = frappe.session.user
    for user in dict.fromkeys(u for u in users if u):
        if (skip_actor and user == actor) or not has_client_role(user):
            continue
        if once_per_day and frappe.db.exists("Notification Log", {
            "for_user": user, "imp_kind": kind, "document_name": name,
            "creation": [">=", frappe.utils.today()],
        }):
            continue
        log = frappe.get_doc({
            "doctype": "Notification Log",
            "subject": body,
            "for_user": user,
            "type": "Alert",
            "imp_kind": kind,
            "document_type": doctype,
            "document_name": name,
        }).insert(ignore_permissions=True)
        frappe.enqueue(
            "implementor.client_notifications.send_push",
            queue="short",
            enqueue_after_commit=True,
            user=user,
            title=title,
            body=body,
            data={
                "type": "notification",
                "screen": "Notification",
                "kind": kind,
                "notification": log.name,
                "notification_log": log.name,
                "document_type": doctype or "",
                "document_name": name or "",
            },
        )


FIREBASE_APP = "implementor_client"

def _firebase_app():
    """The client app's own Firebase connection (Implementor Settings), separate from
    whatsapp_saudi's default one. None when client push is off or not set up."""
    import firebase_admin

    settings = frappe.get_single("Implementor Settings")
    if not settings.enable_client_push:
        return None
    try:
        return firebase_admin.get_app(FIREBASE_APP)
    except ValueError:
        pass
    raw = settings.get_password("firebase_service_account", raise_exception=False)
    if not raw:
        return None
    info = json.loads(raw)
    return firebase_admin.initialize_app(credentials.Certificate(info), name=FIREBASE_APP)



def send_push(user, title, body, data=None):
    """Background job: one push to the user's device. Never raises."""
    token = frappe.db.get_value("Employee", {"user_id": user}, "custom_token")
    if not token:
        return
    try:
        app = _firebase_app()
        if not app:
            return
        messaging.send(messaging.Message(
            token=token,
            notification=messaging.Notification(title=title, body=body),
            data={str(k): str(v) for k, v in (data or {}).items()},
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(sound="default", channel_id="general", priority="high"),
            ),
            apns=messaging.APNSConfig(
                headers={"apns-priority": "10"},
                payload=messaging.APNSPayload(aps=messaging.Aps(
                    alert=messaging.ApsAlert(title=title, body=body), sound="default",
                )),
            )
        ),app=app)
    except (messaging.UnregisteredError, InvalidArgumentError) as e:
        # FCM rejects the token itself (app uninstalled, or not a token): stop sending to it
        _clear_token(user, token)
        frappe.log_error(
            title="Client push failed",
            message=f"User: {user}\nFCM rejected the device token ({e.code}); it was cleared.\n\n{frappe.get_traceback()}",
        )
    except Exception:
        frappe.log_error(title="Client push failed", message=f"User: {user}\n\n{frappe.get_traceback()}")


@frappe.whitelist(methods=["POST"])
def clear_device_token():
    """Client app sign-out: forget the signed-in user's push token so no more pushes go to that device.
    Called before the session is dropped. Always 200; cleared is false when there was nothing to clear.
    No customer check, so sign-out never fails for a user without a client link."""
    user = frappe.session.user  # Guest is refused by @frappe.whitelist before this runs
    token = frappe.db.get_value("Employee", {"user_id": user}, "custom_token")
    if token:
        _clear_token(user, token)
    return {"success": True, "cleared": bool(token)}


def _clear_token(user, token):
    """Empty a rejected token on the Employee and on the Support Tickets that copied it
    (sync_employee_token). Only where it is still this token, in case the app registered a new one."""
    frappe.db.set_value("Employee", {"user_id": user, "custom_token": token}, "custom_token", None,
                        update_modified=False)
    frappe.db.set_value("Support Ticket", {"raised_by": user, "custom_token": token}, "custom_token", None,
                        update_modified=False)


def _client_admins(customer):
    return _client_users(customer, admins_only=True)


def _client_users(customer, admins_only=False):
    """Client users linked to the customer through Contact (Contact.user, else Contact.email_id).
    admins_only: only those with the Client Admin role."""
    if not customer:
        return []
    contacts = frappe.get_all(
        "Dynamic Link",
        filters={"parenttype": "Contact", "link_doctype": "Customer", "link_name": customer},
        pluck="parent",
    )
    users = []
    for c in frappe.get_all("Contact", filters={"name": ["in", contacts or [""]]}, fields=["user", "email_id"]):
        user = c.user or (c.email_id and frappe.db.get_value("User", {"email": c.email_id}))
        if not user:
            continue
        roles = frappe.get_roles(user)
        if CLIENT_ADMIN in roles or (not admins_only and CLIENT_USER in roles):
            users.append(user)
    return list(dict.fromkeys(users))


# --------------------------------------------------------------------------
# Hooks (wired in hooks.py → doc_events)
# --------------------------------------------------------------------------

def on_ticket_update(doc, method=None):
    """Support Ticket on_update: tell the raiser when our team changes the status."""
    before = doc.get_doc_before_save()
    if not before or before.status == doc.status or doc.status == "New":
        return
    if is_client_user(frappe.session.user):  # the client's own actions (comment, confirm fix)
        return
    kind, title, body = _TICKET_STATUS.get(doc.status, _TICKET_STATUS_DEFAULT)
    notify_client(
        [doc.raised_by], kind, title,
        body.format(name=doc.name, subject=doc.subject, status=doc.status),
        "Support Ticket", doc.name,
    )


def on_comment_insert(doc, method=None):
    """Comment after_insert: tell the ticket raiser when our team replies on the ticket."""
    if doc.reference_doctype != "Support Ticket" or doc.comment_type != "Comment":
        return
    if is_client_user(doc.comment_email or doc.owner):
        return
    ticket = frappe.db.get_value("Support Ticket", doc.reference_name, ["raised_by", "subject"], as_dict=True)
    if not ticket:
        return
    text = (_strip_html(doc.content) or "").strip()
    author = doc.comment_by or frappe.utils.get_fullname(doc.comment_email or doc.owner) or "Our team"
    notify_client(
        [ticket.raised_by], "ticket_reply", f"New reply on ticket {doc.reference_name}",
        f"{author} replied on ticket {doc.reference_name}: {text[:120]}",
        "Support Ticket", doc.reference_name,
    )


def on_todo_update(doc, method=None):
    """ToDo on_update: tell a client user when an action is assigned to them (new or reassigned)."""
    before = doc.get_doc_before_save()
    if before and before.allocated_to == doc.allocated_to:
        return
    action_assigned(doc)


def action_assigned(todo):
    """Notify the allocated client user about an open action. `todo` is a ToDo doc or name."""
    if isinstance(todo, str):
        todo = frappe.get_doc("ToDo", todo)
    if todo.get("imp_done") or todo.status in ("Closed", "Cancelled"):
        return
    text = (_strip_html(todo.description) or "").strip().rstrip(".")
    due = f" (due {frappe.utils.formatdate(todo.date)})" if todo.date else ""
    notify_client(
        [todo.allocated_to], "action_assigned", "New action for you",
        f"{text[:120]}{due}", "ToDo", todo.name,
    )


def on_project_update(doc, method=None):
    """Project on_update: project status, milestone ready for sign-off, milestone payment due/overdue."""
    before = doc.get_doc_before_save()
    if not before:
        return
    if before.imp_status != doc.imp_status and doc.imp_status:
        notify_client(
            _client_users(doc.customer), "project_status_changed", "Project update",
            f"{doc.project_name} is now {doc.imp_status}.", "Project", doc.name,
        )
    _milestones_ready(doc, before)
    _payments_due(doc, before)


_PAYMENT_STATUS = {
    "Pending": ("payment_due", "Payment due", "Payment for {title} on {project} is due."),
    "Overdue": ("payment_overdue", "Payment overdue", "Payment for {title} on {project} is overdue."),
}


def _payments_due(doc, before):
    """A milestone's payment_status changed to Pending or Overdue: tell the Client Admins."""
    old = {r.name: r.payment_status for r in before.get("payment_milestone") or []}
    admins = None
    for r in doc.get("payment_milestone") or []:
        if r.payment_status not in _PAYMENT_STATUS or old.get(r.name) == r.payment_status:
            continue
        if r.name not in old and r.payment_status == "Pending":  # a new row starts as Pending
            continue
        admins = admins if admins is not None else _client_admins(doc.customer)
        kind, title, body = _PAYMENT_STATUS[r.payment_status]
        notify_client(admins, kind, title, body.format(title=r.m_title, project=doc.project_name), "Project", doc.name)


def _milestones_ready(doc, before):
    """A milestone became ready for sign-off: tell the customer's Client Admins."""
    from implementor.client_api import SIGNOFF_READY, _signoffs

    old = {r.name: r.completion_status for r in before.get("payment_milestone") or []}
    is_amc = 1 if doc.imp_status == "AMC" else 0
    newly_ready = [
        r for r in doc.get("payment_milestone") or []
        if (r.custom_is_amc or 0) == is_amc
        and r.completion_status in SIGNOFF_READY
        and old.get(r.name) not in SIGNOFF_READY
    ]
    if not newly_ready:
        return
    signed = _signoffs(doc.name)
    admins = _client_admins(doc.customer)
    for r in newly_ready:
        if r.name in signed:
            continue
        notify_client(
            admins, "milestone_ready", "Milestone ready for sign-off",
            f"{r.m_title} on {doc.project_name} is ready for your sign-off.",
            "Project", doc.name,
        )


def on_training_update(doc, method=None):
    """Training Session on_update: tell the customer's client users when a session is added or moved."""
    if not doc.schedule or not doc.project:
        return
    before = doc.get_doc_before_save()
    if before and before.schedule == doc.schedule:
        return
    project = frappe.db.get_value("Project", doc.project, ["customer", "project_name"], as_dict=True)
    if not project:
        return
    when = frappe.utils.format_datetime(doc.schedule, "dd-MM-yyyy hh:mm a")
    body = (f"Training \"{doc.topic}\" moved to {when}." if before
            else f"Training \"{doc.topic}\" on {project.project_name} is scheduled for {when}.")
    notify_client(_client_users(project.customer), "training_scheduled", "Training session", body,
                  "Training Session", doc.name)


# --------------------------------------------------------------------------
# Called from the client_api scheduler jobs
# --------------------------------------------------------------------------

def server_status_changed(server, old, new):
    """check_server_status: the server went Offline, or came back Online from Offline."""
    if new == old or not (new == "Offline" or (new == "Online" and old == "Offline")):
        return
    s = frappe.db.get_value("Server", server, ["customer", "server_name", "environment"], as_dict=True)
    if not s:
        return
    label = f"{s.server_name} ({s.environment})" if s.environment else s.server_name
    if new == "Offline":
        kind, title, body = "server_down", "Server down", f"{label} is not responding. Our team is checking it."
    else:
        kind, title, body = "server_up", "Server back online", f"{label} is back online."
    notify_client(_client_users(s.customer), kind, title, body, "Server", server, skip_actor=False)


def backup_checked(server, previous, result):
    """_oci_backups: compare the new OCI read with the cached one; notify on the change only."""
    if not result.get("available"):
        return
    previous = previous if (previous or {}).get("available") else {}
    users = None
    label = server.server_name or server.name

    if result.get("overdue") and not previous.get("overdue"):
        users = _client_users(server.customer)
        notify_client(users, "backup_overdue", "Backup overdue",
                      f"{label} has had no confirmed backup in the last 26 hours. Our team is checking it.",
                      "Server", server.name, skip_actor=False)

    runs, old_runs = result.get("backups") or [], previous.get("backups") or []
    latest = runs[0] if runs else None
    if latest and latest.get("state") == "failed" and (not old_runs or old_runs[0].get("name") != latest.get("name")):
        users = users if users is not None else _client_users(server.customer)
        notify_client(users, "backup_failed", "Backup failed",
                      f"The latest backup of {label} did not complete. Our team is checking it.",
                      "Server", server.name, skip_actor=False)


# --------------------------------------------------------------------------
# Daily checks (hooks.py → scheduler_events, 8 AM)
# --------------------------------------------------------------------------

AMC_NOTICE_DAYS = (30, 7)


def daily_reminders():
    for fn in (_action_reminders, _amc_reminders, _training_reminders):
        try:
            fn()
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title=f"Client notifications: {fn.__name__} failed")


def _action_reminders():
    today = frappe.utils.getdate()
    for day, kind, title, word in (
        (frappe.utils.add_days(today, 1), "action_due_soon", "Action due tomorrow", "is due tomorrow"),
        (frappe.utils.add_days(today, -1), "action_overdue", "Action overdue", "was due yesterday"),
    ):
        todos = frappe.get_all(
            "ToDo",
            filters={"date": day, "imp_done": 0, "status": "Open", "allocated_to": ["is", "set"]},
            fields=["name", "description", "allocated_to"],
        )
        for t in todos:
            text = (_strip_html(t.description) or "").strip().rstrip(".")
            notify_client([t.allocated_to], kind, title, f"{text[:120]} {word}.", "ToDo", t.name,
                          skip_actor=False, once_per_day=True)


def _amc_reminders():
    today = frappe.utils.getdate()
    projects = frappe.get_all(
        "Project",
        filters={"imp_status": "AMC", "status": ["!=", "Cancelled"], "custom_close_project": 0,
                 "customer": ["is", "set"]},
        fields=["name", "project_name", "customer", "expected_end_date", "imp_deadline"],
    )
    for p in projects:
        end = p.expected_end_date or p.imp_deadline
        if not end:
            continue
        days = frappe.utils.date_diff(end, today)
        if days in AMC_NOTICE_DAYS:
            kind, title = "amc_expiring", "AMC renewal"
            body = f"Your support contract {p.project_name} ends in {days} days, on {frappe.utils.formatdate(end)}."
        elif days == -1:
            kind, title = "amc_expired", "AMC expired"
            body = f"Your support contract {p.project_name} ended on {frappe.utils.formatdate(end)}. Contact us to renew."
        else:
            continue
        notify_client(_client_admins(p.customer), kind, title, body, "Project", p.name,
                      skip_actor=False, once_per_day=True)


def _training_reminders():
    tomorrow = frappe.utils.add_days(frappe.utils.getdate(), 1)
    sessions = frappe.get_all(
        "Training Session",
        filters={"schedule": ["between", [f"{tomorrow} 00:00:00", f"{tomorrow} 23:59:59"]], "project": ["is", "set"]},
        fields=["name", "topic", "project", "schedule"],
    )
    for s in sessions:
        customer = frappe.db.get_value("Project", s.project, "customer")
        when = frappe.utils.format_datetime(s.schedule, "hh:mm a")
        notify_client(_client_users(customer), "training_reminder", "Training tomorrow",
                      f"Reminder: training \"{s.topic}\" is tomorrow at {when}.", "Training Session", s.name,
                      skip_actor=False, once_per_day=True)