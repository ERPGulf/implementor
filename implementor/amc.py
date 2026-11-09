import frappe
from frappe.utils import date_diff


def create_amc_milestone(doc, method=None):
    """When a Project's imp_status changes to AMC, add the default AMC milestone."""
    if doc.imp_status != "AMC":
        return

    before = doc.get_doc_before_save()
    if before and before.imp_status == "AMC":
        return  # it was already AMC — this is just a normal save

    already_has_amc = any(m.get("custom_is_amc") for m in doc.get("payment_milestone"))
    if already_has_amc:
        return  # e.g. moved out of AMC and back in — don't duplicate

    start, end = doc.expected_start_date, doc.imp_deadline
    doc.append("payment_milestone", {
        "m_title": "AMC – 1 year",
        "payment_": 100,
        "start_date": start,
        "end_date": end,
        "duration": (date_diff(end, start) + 1) if start and end else None,
        "completion_status": "In Progress",
        "payment_status": "Pending",
        "custom_is_amc": 1,
    })