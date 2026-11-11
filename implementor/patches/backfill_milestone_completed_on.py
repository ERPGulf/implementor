import frappe


def execute():
	"""Payment Milestone.completed_on is new; give milestones that were already Completed their row's
	last-modified time, the closest record we have of when they were completed."""
	frappe.db.sql(
		"""
		update `tabPayment Milestone`
		set completed_on = modified
		where completion_status = 'Completed' and completed_on is null
		"""
	)
