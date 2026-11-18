import frappe


def execute():
	"""Undo backfill_milestone_completed_on. It set completed_on from each row's last-modified time, which
	moves forward whenever the Project is saved, so old milestones showed completion dates after their
	sign-off. Project has no change tracking to recover the real dates, so those rows go back to null.
	Rows stamped by stamp_milestone_completion after the backfill ran are real and are kept."""
	backfilled_at = frappe.db.get_value(
		"Patch Log", {"patch": "implementor.patches.backfill_milestone_completed_on"}, "creation"
	)
	if not backfilled_at:
		return
	frappe.db.sql(
		"""
		update `tabPayment Milestone`
		set completed_on = null
		where completed_on is not null and completed_on <= %s
		""",
		backfilled_at,
	)
