# implementor/rollup.py
import frappe
from frappe.utils import now_datetime


def on_todo(doc, method=None):
	"""Recompute the parent Task's progress whenever a linked ToDo changes."""
	if doc.reference_type != "Task" or not doc.reference_name:
		return
	_recompute_task_progress(doc.reference_name)


def on_task(doc, method=None):
    _stamp_last_moved(doc)
    if doc.project:
        _recompute_project_percent(doc.project)
    if doc.has_value_changed("imp_division") and doc.imp_division == "Technical":
        _auto_assign_technical(doc)


def _auto_assign_technical(doc):
    from frappe.desk.form.assign_to import add as assign_to_add

    users = frappe.get_all(
        "Has Role",
        filters={"role": "Technical Consultant", "parenttype": "User"},
        fields=["parent"],
    )
    candidates = [u.parent for u in users if frappe.db.get_value("User", u.parent, "enabled")]
    if not candidates:
        return

    last = frappe.db.get_single_value("Implementor Settings", "last_technical_assignee")
    next_index = (candidates.index(last) + 1) % len(candidates) if last in candidates else 0
    next_user = candidates[next_index]

    assign_to_add(
    {"assign_to": [next_user], "doctype": "Task", "name": doc.name}
)
    frappe.db.set_single_value("Implementor Settings", "last_technical_assignee", next_user)


def _recompute_task_progress(task_name):
	total = frappe.db.count("ToDo", {"reference_type": "Task", "reference_name": task_name})
	if not total:
		return  # no todos yet — leave manual/current progress alone
	done = frappe.db.count(
		"ToDo",
		{"reference_type": "Task", "reference_name": task_name, "imp_done": 1},
	)
	percent = round((done / total) * 100)
	# update without triggering a full save cycle / infinite loop
	frappe.db.set_value("Task", task_name, "progress", percent)
	# Task.progress changing doesn't itself fire on_task doc_event automatically
	# via db.set_value, so trigger the project roll-up explicitly:
	task_doc = frappe.get_doc("Task", task_name)
	if task_doc.project:
		_recompute_project_percent(task_doc.project)


def _recompute_project_percent(project_name):
	project = frappe.get_doc("Project", project_name)
	tasks = frappe.get_all(
		"Task",
		filters={"project": project_name},
		fields=["progress", "imp_estimated_hours"],
	)
	if not tasks:
		return

	if project.imp_progress_weighting == "By estimated hours":
		total_hours = sum((t.imp_estimated_hours or 0) for t in tasks)
		if total_hours > 0:
			weighted = sum((t.progress or 0) * (t.imp_estimated_hours or 0) for t in tasks)
			percent = round(weighted / total_hours)
		else:
			# no hours entered anywhere — fall back to simple average
			percent = round(sum((t.progress or 0) for t in tasks) / len(tasks))
	else:
		# Simple mode: plain average
		percent = round(sum((t.progress or 0) for t in tasks) / len(tasks))

	frappe.db.set_value("Project", project_name, "imp_percent", percent)


def _stamp_last_moved(doc):
	"""Update imp_last_moved whenever status or imp_urgency changes."""
	if doc.has_value_changed("status") or doc.has_value_changed("imp_urgency"):
		doc.db_set("imp_last_moved", now_datetime(), update_modified=False)
		# In-progress transition extras
		if doc.has_value_changed("status") and doc.status == "In Progress":
			if not doc.imp_started_on:
				doc.db_set("imp_started_on", now_datetime(), update_modified=False)
			if not doc.imp_doing:
				doc.db_set("imp_doing", doc.imp_division_lead or frappe.session.user, update_modified=False)

