# implementor/api.py
import frappe
from frappe.utils import getdate, nowdate, date_diff
from frappe import _
import json
import re

def _remaining_days(deadline):
    if not deadline:
        return None
    return date_diff(getdate(deadline), getdate(nowdate()))


def _reaction_counts(doctype, name):
    Reaction = frappe.qb.DocType("Reaction")
    rows = (
        frappe.qb.from_(Reaction)
        .select(Reaction.reaction_type, Reaction.user)
        .where(Reaction.reference_doctype == doctype)
        .where(Reaction.reference_name == name)
    ).run(as_dict=True)

    current_user = frappe.session.user
    result = {}
    for r in rows:
        bucket = result.setdefault(
            r.reaction_type,
            {"count": 0, "users": [], "reacted_by_me": False},
        )
        bucket["count"] += 1
        bucket["users"].append(r.user)
        if r.user == current_user:
            bucket["reacted_by_me"] = True
    return result

def _wall_count(doctype, name):
    return frappe.db.count("Wall Post", {"reference_doctype": doctype, "reference_name": name})

def _strip_html(value):
    if not isinstance(value, str):
        return value
    text = re.sub(r"<[^>]+>", "", value)
    return text.strip()

_NOISE_FIELDS = {"actual_time", "total_costing_amount", "total_billable_amount", "modified", "modified_by"}

def _recent_activity(doctype, name, limit=5):
    raw_versions = frappe.get_all(
        "Version",
        filters={"ref_doctype": doctype, "docname": name},
        fields=["name", "owner", "creation", "data"],
        order_by="creation desc",
        limit=limit,
    )

    cleaned = []
    for v in raw_versions:
        try:
            parsed = frappe.parse_json(v.data)
        except Exception:
            continue

        changes = []
        for field, old_val, new_val in parsed.get("changed", []):
            if field in _NOISE_FIELDS:
                continue
            changes.append({
                "field": field,
                "old_value": _strip_html(old_val),
                "new_value": _strip_html(new_val),
            })

        if changes:
            cleaned.append({
                "owner": v.owner,
                "creation": v.creation,
                "changes": changes,
            })

    return cleaned

RECIPIENT_FIELD = {
    "Project": "imp_project_manager",
    "Task": "_assign",
    "ToDo": "allocated_to"
}

def parsed_recipients(raw_value):
    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed,list):
            users = parsed
        elif isinstance(parsed,str):
            users = [parsed]
        else:
            users = [str(parsed)]
    except (ValueError, TypeError):
        users = str(raw_value).split(",")
    return [u.strip() for u in users if u and str(u).strip()]
 


@frappe.whitelist(allow_guest=True)
def send_slack_message(doctype, name, mode, message):
    doc = frappe.get_doc(doctype, name)
    if mode == "dm":
        raw_value = getattr(doc, RECIPIENT_FIELD[doctype], None)
        if not raw_value:
            frappe.throw("No user assigned to message.")
        users = parsed_recipients(raw_value)
        results = []
        failed = []
        for user in users:
            slack_id = frappe.db.get_value("User", user, "slack_user_id")
            if not slack_id:
                failed.append(f"{user} (no Slack ID set)")
                continue
            resp = requests.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {frappe.db.get_single_value('Implementor Settings', 'slack_b_token')}", "Content-Type": "application/json"},
                json={"channel": slack_id, "text": message}
            )
            data = resp.json()
            if not data.get("ok"):
                failed.append(f"{user} ({data.get('error')})")
            else:
                results.append(user)
        if failed and not results:
            frappe.throw(f"Could not send to: " + ", ".join(failed))
        elif failed:
            frappe.msgprint("Sent, but failed for: " + ", ".join(failed), indicator="orange", alert=True)
        return {"sent_to": results, "failed": failed}

    else:  # channel mode
        field = "slack_channel_id" if mode == "slack_channel" else "whatsapp_channel_id"
        target = getattr(doc, field, None)
        if not target:
            frappe.throw("No channel configured for this record.")

        resp = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {frappe.db.get_single_value('Implementor Settings', 'slack_b_token')}", "Content-Type": "application/json"},
            json={"channel": target, "text": message}
        )
        return [resp.json()]
@frappe.whitelist()
def get_projects(filters=None):
    filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
    # filters.setdefault("imp_status", ["!=", "Closed"])

    rows = frappe.get_list(
        "Project",
        fields=[
            "name", "project_name as title", "customer as client",
            "imp_status as del_status", "imp_project_manager as pm",
            "imp_percent as percent", "imp_deadline as deadline",
            "notes as description","slack_channel_id", "whatsapp_channel_id", "percent_complete" 
        ],
    )
    for r in rows:
        r["description"] = _strip_html(r.get("description"))
        r["remaining_days"] = _remaining_days(r.get("deadline"))
        r["reaction_counts"] = _reaction_counts("Project", r["name"])
        r["wall_count"] = _wall_count("Project", r["name"])
        r["activity"] = _recent_activity("Project", r["name"], limit=5)
        r["comments"] = _comments("Project", r["name"], limit=5)
        r["attachments"] = _attachments("Project", r["name"])
    return rows


@frappe.whitelist()
def get_doc_url(doc=None,id=None):
    if not doc or not id:
        frappe.throw("Both 'doc' and 'id' parameters are required")

    if not frappe.db.exists(doc, id):
        frappe.throw(f"{doc} {id} does not exist")
    doc_lowerCase = doc.lower().replace(" ", "-")
    url = frappe.utils.get_url(f"/app/{doc_lowerCase}/{id}")
    return url


@frappe.whitelist()
def get_tasks(project=None):
    filters = {"project": project} if project else {}

    rows = frappe.get_list(
        "Task",
        filters=filters,
        fields=[
            "name", "subject as title", "project", "imp_stage as stage",
            "imp_division as division",
            "status", "imp_urgency as urgency", "progress as percent",
            "imp_deadline as deadline", "imp_division_lead as lead","imp_started_on as started_on",
            "imp_doing as doing", "imp_escalated as escalated",
            "description", "_assign", "slack_channel_id", "whatsapp_channel_id", "completed_on", "completed_by","imp_module"
        ],
    )
    for r in rows:
        r["description"] = _strip_html(r.get("description"))
        r["remaining_days"] = _remaining_days(r.get("deadline"))
        r["reaction_counts"] = _reaction_counts("Task", r["name"])
        r["wall_count"] = _wall_count("Task", r["name"])
        r["assigned_to"] = json.loads(r.get("_assign") or "[]")
        del r["_assign"]
        r["activity"] = _recent_activity("Task", r["name"], limit=5)
        r["comments"] = _comments("Task", r["name"], limit=5)
        r["attachments"] = _attachments("Task", r["name"])
        r["modules"] = _project_modules(r.get("project"))
        r["imp_module"] = frappe.db.get_value("Project Module", r.get("imp_module"), "module_name") if r.get("imp_module") else None
    return rows

@frappe.whitelist()
def get_todos(task=None, project=None):
    filters = {}

    if task:
        filters["reference_type"] = "Task"
        filters["reference_name"] = task
    elif project:
        task_names = frappe.get_all("Task", filters={"project": project}, pluck="name")
        if not task_names:
            return []
        filters["reference_type"] = "Task"
        filters["reference_name"] = ["in", task_names]

    rows = frappe.get_list(
        "ToDo",
        filters=filters,
        fields=[
            "name", "description as title", "reference_type", "reference_name as task",
            "allocated_to as assignee", "status", "priority", "imp_done as done",
            "imp_urgency as urgency", "date as deadline", "imp_escalated as escalated",
            "slack_channel_id", "whatsapp_channel_id","imp_module"
        ],
    )

    task_ids = list({r["task"] for r in rows if r.get("task")})
    task_to_project = {}
    if task_ids:
        task_rows = frappe.get_all("Task", filters={"name": ["in", task_ids]}, fields=["name", "project"])
        task_to_project = {t.name: t.project for t in task_rows}

    for r in rows:
        r["title"] = _strip_html(r.get("title"))
        r["remaining_days"] = _remaining_days(r.get("deadline"))
        r["reaction_counts"] = _reaction_counts("ToDo", r["name"])
        r["wall_count"] = _wall_count("ToDo", r["name"])
        r["activity"] = _recent_activity("ToDo", r["name"], limit=5)
        r["comments"] = _comments("ToDo", r["name"], limit=5)
        r["attachments"] = _attachments("ToDo", r["name"])
        r["modules"] = _project_modules(task_to_project.get(r.get("task")))
        r["imp_module"] = frappe.db.get_value("Project Module", r.get("imp_module"), "module_name") if r.get("imp_module") else None
    return rows

def _project_modules(project_name):
	if not project_name:
		return []
	return frappe.get_all(
		"Project Module",
		filters={"parent": project_name, "parenttype": "Project", "parentfield": "imp_modules"},
		fields=["module_name", "in_scope", "notes"],
		order_by="idx asc",
	)
 
def _comments(doctype, name, limit=5):
    rows = frappe.get_all(
        "Comment",
        filters={"reference_doctype": doctype, "reference_name": name, "comment_type": "Comment"},
        fields=["content", "comment_email", "creation"],
        order_by="creation desc",
        limit=limit,
    )
    for r in rows:
        r["content"] = _strip_html(r.get("content"))
    return rows


def _attachments(doctype, name):
    return frappe.get_all(
        "File",
        filters={"attached_to_doctype": doctype, "attached_to_name": name},
        fields=["file_name", "file_url"],
    )
 
@frappe.whitelist()
def get_tickets(filters=None):
    filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
    return frappe.get_list(
        "Support Ticket",
        filters=filters,
        fields=["name", "subject", "customer", "project", "ticket_type",
                "priority", "status", "sla_due", "converted_task"],
    )
import requests

@frappe.whitelist()
def send_whatsapp(message=None):
        # response = requests.post("https://slack.com/api/chat.postMessage",headers={
        # 	"Authorization": f"Bearer {frappe.db.get_single_value('Implementor Settings', 'slack_b_token')}",
        # 	"Content-Type": "application/json",
        # }, json={
        # 	"channel": "U0809P2573M",
        # 	"text": message
        # })
        # data = response.json()
        return ""

@frappe.whitelist()
def get_integrations(project=None):
    filters = {"project": project} if project else {}
    return frappe.get_list(
        "Integration",
        filters=filters,
        fields=["name", "integration_name", "type", "vendor", "status",
                "owner_user", "project", "customer"],
    )


@frappe.whitelist()
def get_servers(client=None):
    filters = {"customer": client} if client else {}
    return frappe.get_list(
        "Server",
        filters=filters,
        fields=["name", "server_name", "customer", "environment", "provider",
                "erpnext_version", "frappe_version", "ssl_expiry", "last_restore_test"],
    )
 
 
@frappe.whitelist()
def get_detail(doctype, name):
    if doctype not in ("Project", "Task", "ToDo", "Support Ticket"):
        frappe.throw("Unsupported doctype for get_detail")

    if not frappe.has_permission(doctype, "read", name):
        frappe.throw("Not permitted", frappe.PermissionError)

    doc = frappe.get_doc(doctype, name)
    data = doc.as_dict()

    data["attachments"] = frappe.get_all(
        "File",
        filters={"attached_to_doctype": doctype, "attached_to_name": name},
        fields=["file_name", "file_url"],
    )
    data["work_notes"] = frappe.get_all(
        "Comment",
        filters={"reference_doctype": doctype, "reference_name": name, "comment_type": "Comment"},
        fields=["content", "comment_email", "creation"],
        order_by="creation asc",
    )
    data["wall"] = frappe.get_all(
        "Wall Post",
        filters={"reference_doctype": doctype, "reference_name": name},
        fields=["text", "user", "posted_on"],
        order_by="posted_on asc",
    )
    data["reactions"] = _reaction_counts(doctype, name)
    data["activity"] = frappe.get_all(
        "Version",
        filters={"ref_doctype": doctype, "docname": name},
        fields=["data", "owner", "creation"],
        order_by="creation desc",
        limit=20,
    )
    return data

@frappe.whitelist()
def get_div_options():
    field = frappe.get_meta("Task").get_field("imp_division")
    if not field or not field.options:
        return []
    return [opt for opt in field.options.split("\n") if opt]

@frappe.whitelist()
def get_project_status_options():
    field = frappe.get_meta("Project").get_field("imp_status")
    if not field or not field.options:
        return []
    return [opt for opt in field.options.split("\n") if opt]

@frappe.whitelist()
def set_status(doctype, name, status):
    doc = frappe.get_doc(doctype, name)
    doc.status = status if doctype != "Project" else doc.status
    if doctype == "Project":
        doc.imp_status = status
    else:
        doc.status = status
    doc.save()
    return doc.as_dict()


@frappe.whitelist()
def set_urgency(doctype, name, urgency):
    if doctype not in ("Task", "ToDo"):
        frappe.throw(_("Urgency is only applicable to Task or ToDo, not {0}").format(doctype))
    if not urgency:
        frappe.throw(_("Urgency value is required"))
    if not frappe.db.exists(doctype, name):
        frappe.throw(_("{0} {1} does not exist").format(doctype, name))
    if not frappe.has_permission(doctype, "write", name):
        frappe.throw("Not permitted", frappe.PermissionError)

    frappe.db.set_value(doctype, name, "imp_urgency", urgency)

    if doctype == "Task":
        frappe.db.set_value(doctype, name, "imp_last_moved", frappe.utils.now_datetime())

    return {"ok": True}

@frappe.whitelist()
def set_project_manager(project, project_manager):
    if not frappe.db.exists("Project", project):
        frappe.throw(_("Project {0} does not exist").format(project))
    if not frappe.db.exists("User", project_manager):
        frappe.throw(_("User {0} does not exist").format(project_manager))

    doc = frappe.get_doc("Project", project)
    doc.imp_project_manager = project_manager
    doc.save()

    return {"project": project, "project_manager": project_manager}

@frappe.whitelist()
def set_division(task, division):
    if not frappe.db.exists("Task", task):
        frappe.throw(_("Task {0} does not exist").format(task))

    lead = frappe.db.get_value(
        "User", {"imp_division": division, "imp_is_division_lead": 1}, "name"
    )
    doc = frappe.get_doc("Task", task)
    doc.imp_division = division
    doc.imp_division_lead = lead
    doc.save()

    return {"division": division, "lead": lead}

@frappe.whitelist()
def assign_todo(todo, user):
    if not frappe.db.exists("ToDo", todo):
        frappe.throw(_("ToDo {0} does not exist").format(todo))
    if not frappe.db.exists("User", user):
        frappe.throw(_("User {0} does not exist").format(user))
    if not frappe.has_permission("ToDo", "write", todo):
        frappe.throw("Not permitted", frappe.PermissionError)

    old_user = frappe.db.get_value("ToDo", todo, "allocated_to")
    frappe.db.set_value("ToDo", todo, "allocated_to", user)

    return {"ok": True, "todo": todo, "reassigned_from": old_user, "reassigned_to": user}
@frappe.whitelist()
def saveDueDate(doctype=None, name=None, dateStr=None):
    if doctype is None or name is None or dateStr is None:
        frappe.msgprint("Doctype, name, and date are required")
        return
    if doctype in ("Project","Task"):
        frappe.db.set_value(doctype, name, 'imp_deadline', dateStr)
    else:
        frappe.db.set_value(doctype, name, 'date', dateStr)
    return dateStr


@frappe.whitelist()
def toggle_reaction(doctype, name, reaction_type):
    user = frappe.session.user
    existing = frappe.db.exists("Reaction", {
        "reference_doctype": doctype, "reference_name": name,
        "user": user, "reaction_type": reaction_type,
    })
    if existing:
        frappe.delete_doc("Reaction", existing, ignore_permissions=False)
    else:
        frappe.get_doc({
            "doctype": "Reaction", "reference_doctype": doctype,
            "reference_name": name, "user": user, "reaction_type": reaction_type,
        }).insert()
    return _reaction_counts(doctype, name)


@frappe.whitelist()
def add_wall_post(doctype, name, text):
    frappe.get_doc({
        "doctype": "Wall Post", "reference_doctype": doctype,
        "reference_name": name, "user": frappe.session.user, "text": text,
    }).insert()
    return {"ok": True}


@frappe.whitelist()
def add_work_note(doctype, name, text):
    doc = frappe.get_doc(doctype, name)
    doc.add_comment("Comment", text=text)
    return {"ok": True}


@frappe.whitelist()
def create_project(payload):
    payload = frappe.parse_json(payload) if isinstance(payload, str) else payload
    doc = frappe.get_doc({"doctype": "Project", **payload})
    doc.insert()
    return doc.as_dict()


@frappe.whitelist()
def create_task(project, payload):
    payload = frappe.parse_json(payload) if isinstance(payload, str) else payload
    doc = frappe.get_doc({"doctype": "Task", "project": project, **payload})
    doc.insert()
    return doc.as_dict()


@frappe.whitelist()
def create_todo(task, payload):
    payload = frappe.parse_json(payload) if isinstance(payload, str) else payload
    doc = frappe.get_doc({
        "doctype": "ToDo", "reference_type": "Task", "reference_name": task, **payload,
    })
    doc.insert()
    return doc.as_dict()


@frappe.whitelist()
def convert_ticket_to_task(ticket, project, task_type, division):
    ticket_doc = frappe.get_doc("Support Ticket", ticket)
    lead = frappe.db.get_value("User", {"imp_division": division, "imp_is_division_lead": 1}, "name")

    task = frappe.get_doc({
        "doctype": "Task",
        "project": project,
        "subject": ticket_doc.subject,
        "imp_task_type": task_type,
        "imp_division": division,
        "imp_division_lead": lead,
        "imp_urgency": ticket_doc.priority,
        "imp_source_ticket": ticket,
    })
    task.insert()

    ticket_doc.project = project
    ticket_doc.converted_task = task.name
    ticket_doc.status = "In Progress"
    ticket_doc.save()

    return {"task": task.name}


@frappe.whitelist()
def set_ticket_status(ticket, status):
    frappe.db.set_value("Support Ticket", ticket, "status", status)
    return {"ok": True}
@frappe.whitelist()
def resolve_task_context(task):
	project = frappe.db.get_value("Task", task, "project")
	return {"task": task, "project": project}

@frappe.whitelist()
def resolve_todo_context(todo):
	reference_type, reference_name = frappe.db.get_value(
		"ToDo", todo, ["reference_type", "reference_name"]
	)
	if reference_type != "Task" or not reference_name:
		return {"todo": todo, "task": None, "project": None}
	project = frappe.db.get_value("Task", reference_name, "project")
	return {"todo": todo, "task": reference_name, "project": project}
@frappe.whitelist()
def dashboard_summary(group_by=None, project_id=None):
    project_filters = {"imp_status": ["!=", "Closed"]}
    if project_id:
        project_filters["name"] = project_id

    projects = frappe.get_list(
        "Project",
        filters=project_filters,
        fields=["name", "imp_status", "imp_percent", "imp_deadline", "imp_health", "customer","percent_complete"],
    )

    task_filters = {}
    if project_id:
        task_filters["project"] = project_id

    tasks = frappe.get_list(
        "Task",
        filters=task_filters,
        fields=["name", "status", "subject", "imp_urgency", "imp_stage", "imp_division",
                "imp_deadline", "imp_escalated", "project", "progress"],
    )

    due_7d = len([t for t in tasks if t.imp_deadline and 0 <= _remaining_days(t.imp_deadline) <= 7])
    overdue = len([t for t in tasks if t.imp_deadline and _remaining_days(t.imp_deadline) < 0])
    escalated = len([t for t in tasks if t.imp_escalated])
    avg_progress = round(sum((p.percent_complete or 0) for p in projects) / len(projects)) if projects else 0

    def _bucket(rows, field):
        out = {}
        for r in rows:
            key = r.get(field) or "Unspecified"
            out[key] = out.get(key, 0) + 1
        return out

    def _avg_bucket(rows, group_field, value_field):
        groups = {}
        for r in rows:
            key = r.get(group_field) or "Unspecified"
            groups.setdefault(key, []).append(r.get(value_field) or 0)
        return {k: round(sum(v) / len(v)) for k, v in groups.items()}

    todo_filters = {"reference_type": "Task"}
    if project_id:
        task_ids_for_project = [t.name for t in tasks]
        if not task_ids_for_project:
            todos = []
        else:
            todo_filters["reference_name"] = ["in", task_ids_for_project]
            todos = frappe.get_list(
                "ToDo",
                filters=todo_filters,
                fields=["name", "description", "imp_urgency", "date", "imp_escalated", "imp_done", "reference_name"],
            )
    else:
        todos = frappe.get_list(
            "ToDo",
            filters=todo_filters,
            fields=["name", "description", "imp_urgency", "date", "imp_escalated", "imp_done", "reference_name"],
        )

    deadlines_soon = (
        [{**t, "doctype": "Task", "title": t.subject, "deadline": t.imp_deadline} for t in tasks if t.imp_deadline and _remaining_days(t.imp_deadline) <= 7]
        + [{**d, "doctype": "ToDo", "title": d.description, "deadline": d.date} for d in todos if d.date and not d.imp_done and _remaining_days(d.date) <= 7]
    )

    emergencies = (
        [{**t, "doctype": "Task", "title": t.subject} for t in tasks if t.imp_urgency == "Emergency" and t.status != "Done"]
        + [{**d, "doctype": "ToDo", "title": d.description} for d in todos if d.imp_urgency == "Emergency" and not d.imp_done]
    )

    result = {
    "project_id": project_id,
    "projects": len(projects),
    "tasks": len(tasks),
    "avg_progress": avg_progress,
    "due_7d": due_7d,
    "overdue": overdue,
    "escalated": escalated,
    "by_status": _bucket(tasks, "status"),
    "by_urgency": _bucket(tasks, "imp_urgency"),
    "by_stage": _bucket(tasks, "imp_stage"),
    "by_division": _bucket(tasks, "imp_division"),
    "stage_avg_progress": _avg_bucket(tasks, "imp_stage", "progress"),  # dict: {stage: avg%}
    "completion_perc": round((projects[0].percent_complete or 0) if project_id and projects else avg_progress),  # number
    "deadlines_soon": deadlines_soon,
    "emergencies": emergencies,
}

    if group_by == "client" and not project_id:
        by_client = {}
        for p in projects:
            by_client.setdefault(p.customer, []).append(p)
        result["by_client"] = {
            client: {
                "count": len(rows),
                "avg_percent": round(sum((r.imp_percent or 0) for r in rows) / len(rows)),
            }
            for client, rows in by_client.items()
        }

    return result

@frappe.whitelist()
def notifications():
    rows = frappe.get_list(
        "Notification Log",
        filters={"for_user": frappe.session.user, "read": 0},
        fields=["name", "subject", "document_type", "document_name", "creation","type"],
        order_by="creation desc",
        limit_page_length=50,
    )
    for r in rows:
        r["deadline"] = None
        if r.document_type == "Task":
            r["deadline"] = frappe.db.get_value("Task", r.document_name, "imp_deadline")
        elif r.document_type == "ToDo":
            r["deadline"] = frappe.db.get_value("ToDo", r.document_name, "date")

    return rows


@frappe.whitelist()
def emergencies():
    tasks = frappe.get_list(
        "Task",
        filters={"imp_urgency": "Emergency", "status": ["!=", "Done"]},
        fields=["name", "subject as title", "imp_escalated as escalated", "imp_deadline as deadline"],
    )
    for t in tasks:
        t["remaining_days"] = _remaining_days(t.get("deadline"))
    return tasks


@frappe.whitelist()
def my_work():
    user = frappe.session.user
    return {
        "pm_projects": frappe.get_list("Project", filters={"imp_project_manager": user}, fields=["name", "project_name"]),
        "leading_tasks": frappe.get_list("Task", filters={"imp_division_lead": user}, fields=["name", "subject"]),
        "doing_tasks": frappe.get_list("Task", filters={"imp_doing": user}, fields=["name", "subject"]),
        "assigned_todos": frappe.get_list("ToDo", filters={"allocated_to": user, "imp_done": 0}, fields=["name", "description"]),
    }


@frappe.whitelist()
def toggle_todo_done(todo):
    if not frappe.has_permission("ToDo", "write", todo):
        frappe.throw("Not permitted", frappe.PermissionError)

    current = frappe.db.get_value("ToDo", todo, "imp_done")
    new_value = 0 if current else 1

    frappe.db.set_value("ToDo", todo, {
        "imp_done": new_value,
        "status": "Closed" if new_value else "Open",
    })

    from implementor.rollup import _recompute_task_progress
    task_name = frappe.db.get_value("ToDo", todo, "reference_name")
    if task_name:
        _recompute_task_progress(task_name)

    task_percent = frappe.db.get_value("Task", task_name, "progress") if task_name else None
    project_name = frappe.db.get_value("Task", task_name, "project") if task_name else None
    project_percent = frappe.db.get_value("Project", project_name, "imp_percent") if project_name else None

    return {
        "todo": todo,
        "done": bool(new_value),
        "status": "Closed" if new_value else "Open",
        "task": task_name,
        "task_percent": task_percent,
        "project": project_name,
        "project_percent": project_percent,
    }
 
 
 
@frappe.whitelist()
def get_users(role=None):
    role_aliases = {
        "pm": "Projects Manager",
    }
    resolved_role = role_aliases.get(role, role) if role else None

    if not resolved_role:
        return frappe.get_all(
            "User",
            filters={"enabled": 1},
            fields=["name", "full_name", "user_image", "imp_division"],
            order_by="full_name asc",
        )

    if not frappe.db.exists("Role", resolved_role):
        frappe.throw(f"Role '{resolved_role}' does not exist")

    rows = frappe.get_all(
        "Has Role",
        filters={"role": resolved_role, "parenttype": "User"},
        fields=["parent as user"],
    )
    user_names = [r.user for r in rows]
    if not user_names:
        return []

    return frappe.get_all(
        "User",
        filters={"name": ["in", user_names], "enabled": 1},
        fields=["name", "full_name", "user_image", "imp_division"],
        order_by="full_name asc",
    )
 
@frappe.whitelist()
def add_attachment(doctype, name):

    if doctype not in ("Project", "Task", "ToDo"):
        frappe.throw(f"Attachments are only supported on Project, Task, or ToDo, not {doctype}")

    if not frappe.db.exists(doctype, name):
        frappe.throw(f"{doctype} {name} does not exist")

    if not frappe.has_permission(doctype, "write", name):
        frappe.throw("Not permitted", frappe.PermissionError)

    from frappe.utils.file_manager import save_file
    uploaded_files = frappe.request.files.getlist("files")

    if not uploaded_files:
        frappe.throw("No file was uploaded")

    saved = []
    for file_obj in uploaded_files:
        file_doc = save_file(
            fname=file_obj.filename,
            content=file_obj.stream.read(),
            dt=doctype,
            dn=name,
            is_private=1,
        )
        saved.append({"file_name": file_doc.file_name, "file_url": file_doc.file_url, "name": file_doc.name})

    return {"ok": True, "attached": saved}
 

@frappe.whitelist()
def update_description(doctype, name, description):
    
    if doctype not in ("Project", "Task", "ToDo"):
        frappe.throw(f"Description update is only supported on Project, Task, or ToDo, not {doctype}")

    if not frappe.db.exists(doctype, name):
        frappe.throw(f"{doctype} {name} does not exist")

    if not frappe.has_permission(doctype, "write", name):
        frappe.throw("Not permitted", frappe.PermissionError)

    fieldname = "notes" if doctype == "Project" else "description"
    frappe.db.set_value(doctype, name, fieldname, description)

    return {"ok": True, "doctype": doctype, "name": name, "description": _strip_html(description)}


_FIELDTYPE_MAP = {
    "Select": "select",
    "Link": "select",       # options is a doctype name — see note below, not a literal option list
    "Data": "text",
    "Small Text": "text",
    "Text": "text",
    "Text Editor": "text",
    "Int": "number",
    "Float": "number",
    "Currency": "number",
    "Percent": "number",
    "Date": "date",
    "Datetime": "date",
    "Check": "boolean",
}


@frappe.whitelist()
def get_filter_fields(doctype, fieldnames):
    if isinstance(fieldnames, str):
        fieldnames = frappe.parse_json(fieldnames)

    if not frappe.db.exists("DocType", doctype):
        frappe.throw(f"DocType {doctype} does not exist")

    meta = frappe.get_meta(doctype)
    result = []
    for fieldname in fieldnames:
        field = meta.get_field(fieldname)
        if not field:
            continue 

        entry = {
            "name": fieldname,
            "label": field.label or fieldname,
            "type": _FIELDTYPE_MAP.get(field.fieldtype, "text"),
        }

        if field.fieldtype == "Select" and field.options:
            entry["options"] = [opt for opt in field.options.split("\n") if opt]
        elif field.fieldtype == "Link" and field.options:
            entry["link_doctype"] = field.options

        result.append(entry)

    return result

@frappe.whitelist()
def update_task_completion(task_id, completed_on=None, completed_by=None):

	if not frappe.db.exists("Task", task_id):
		frappe.throw(f"Task {task_id} does not exist")

	if not frappe.has_permission("Task", "write", task_id):
		frappe.throw("Not permitted", frappe.PermissionError)

	updates = {}
	if completed_on is not None:
		updates["completed_on"] = completed_on
	if completed_by is not None:
		if not frappe.db.exists("User", completed_by):
			frappe.throw(f"User {completed_by} does not exist")
		updates["completed_by"] = completed_by

	if not updates:
		frappe.throw("At least one of completed_on or completed_by must be provided")

	frappe.db.set_value("Task", task_id, updates)

	return {
		"task": task_id,
		"updated_fields": list(updates.keys()),
		"completed_on": frappe.db.get_value("Task", task_id, "completed_on"),
		"completed_by": frappe.db.get_value("Task", task_id, "completed_by"),
	}
 
 
@frappe.whitelist()
def get_project_percent_by_task(task_id):
	if not frappe.db.exists("Task", task_id):
		frappe.throw(f"Task {task_id} does not exist")

	if not frappe.has_permission("Task", "read", task_id):
		frappe.throw("Not permitted", frappe.PermissionError)

	project_id = frappe.db.get_value("Task", task_id, "project")
	if not project_id:
		frappe.throw(f"Task {task_id} is not linked to any project")

	if not frappe.has_permission("Project", "read", project_id):
		frappe.throw("Not permitted on linked project", frappe.PermissionError)

	percent = frappe.db.get_value("Project", project_id, "percent_complete")

	return {
		"task": task_id,
		"project": project_id,
		"percent_complete": percent or 0,
	}
 
 

# add this to implementor/api.py (or implementor/seed.py)
import frappe

import frappe

@frappe.whitelist()
def seed_dummy_projects(count=4):
    count = int(count)
    created = []

    sample_data = [
        {"name": "Al-Rossais Trading", "customer": "test", "status": "Active", "task": "Chart of accounts setup", "stage": "Config", "urgency": "Normal"},
        {"name": "Gulf Foods", "customer": "Palmer Productions Ltd.", "status": "Active", "task": "ZATCA onboarding", "stage": "Integration", "urgency": "Urgent"},
        {"name": "Najd Logistics", "customer": "West View Software Ltd.", "status": "Discovery", "task": "HR module setup", "stage": "Config", "urgency": "Normal"},
        {"name": "Rimal Retail", "customer": "Grant Plastics Ltd.", "status": "Active", "task": "Bank gateway integration", "stage": "Integration", "urgency": "Emergency"},
    ]

    for i in range(count):
        sample = sample_data[i % len(sample_data)]

        project = frappe.get_doc({
            "doctype": "Project",
            "project_name": sample["name"],
            "customer": sample["customer"],
            "imp_status": sample["status"],
            "imp_project_manager": frappe.session.user,
            "imp_percent": 0,
            "imp_deadline": frappe.utils.add_days(frappe.utils.nowdate(), 15 + i * 5),
        })
        project.insert()

        task = frappe.get_doc({
            "doctype": "Task",
            "project": project.name,
            "subject": sample["task"],
            "imp_stage": sample["stage"],
            "imp_division": "Functional",
            "imp_division_lead": frappe.session.user,
            "status": "Open",
            "imp_urgency": sample["urgency"],
            "progress": 0,
            "imp_deadline": frappe.utils.add_days(frappe.utils.nowdate(), 5 + i * 2),
        })
        task.insert()

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "reference_type": "Task",
            "reference_name": task.name,
            "description": "First task item",
            "allocated_to": frappe.session.user,
            "imp_done": 0,
            "imp_urgency": "Normal",
            "date": frappe.utils.nowdate(),
        })
        todo.insert()

        created.append({"project": project.name, "task": task.name, "todo": todo.name})

    return created