# implementor/escalation.py
import frappe
from frappe.utils import now_datetime, add_to_date


def run():
	"""
	Runs every 15 minutes (see hooks.py scheduler_events).
	Finds Task/ToDo items marked Emergency, not yet done, whose
	imp_last_moved is 4+ hours stale, and escalates them.
	"""
	threshold = add_to_date(now_datetime(), hours=-4)

	_escalate_tasks(threshold)
	_escalate_todos(threshold)


def _escalate_tasks(threshold):
	tasks = frappe.get_all(
		"Task",
		filters={
			"imp_urgency": "Emergency",
			"status": ["!=", "Done"],
			"imp_last_moved": ["<=", threshold],
			"imp_escalated": 0,
		},
		fields=["name", "subject", "imp_division_lead", "project"],
	)
	for t in tasks:
		project_manager = frappe.db.get_value("Project", t.project, "imp_project_manager")
		recipients = [r for r in [t.imp_division_lead, project_manager] if r]
		_notify(recipients, "Task", t.name, t.subject or t.name)
		frappe.db.set_value("Task", t.name, "imp_escalated", 1)


def _escalate_todos(threshold):
	todos = frappe.get_all(
		"ToDo",
		filters={
			"imp_urgency": "Emergency",
			"imp_done": 0,
			"reference_type": "Task",
		},
		fields=["name", "description", "allocated_to", "reference_name", "modified"],
	)
	for td in todos:
		if td.modified and td.modified <= threshold:
			task = frappe.db.get_value("Task", td.reference_name, ["project", "imp_division_lead"], as_dict=True)
			project_manager = frappe.db.get_value("Project", task.project, "imp_project_manager") if task else None
			recipients = [r for r in [td.allocated_to, project_manager] if r]
			_notify(recipients, "ToDo", td.name, td.description or td.name)
			frappe.db.set_value("ToDo", td.name, "imp_escalated", 1)


def _notify(recipients, doctype, name, subject):
	for user in set(recipients):
		frappe.get_doc({
			"doctype": "Notification Log",
			"subject": f"Escalated: {subject}",
			"for_user": user,
			"type": "Alert",
			"document_type": doctype,
			"document_name": name,
		}).insert(ignore_permissions=True)
