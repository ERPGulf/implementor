import frappe
from frappe.utils import date_diff

def _timeline_label(start_date, delivery_date):
    if not start_date or not delivery_date:
        return "—"
    days = date_diff(delivery_date, start_date)
    if days < 0:
        return "—"
    months = round(days / 30)
    if months == 0:
        return "{} days".format(days)
    return "{} Month{}".format(months, "" if months == 1 else "s")

def _project_modules(project_name):
    if not project_name:
        return []
    return frappe.get_all(
        "Project Module",
        filters={"parent": project_name, "parenttype": "Project", "parentfield": "imp_modules"},
        fields=["module_name", "in_scope", "notes", "module_status"],
        order_by="idx asc",
    )


def _project_milestones(project_name):
    doc = frappe.get_doc("Project", project_name)
    return [
        {
            "title": m.m_title,
            "weight": float(m.payment_ or 0),
            "completion_status": m.completion_status,
            "payment_status": m.payment_status,
            "end_date":m.end_date
        }
        for m in doc.get("payment_milestone")
    ]


@frappe.whitelist()
def get_milestone_dashboard():
    if not frappe.has_permission("Project", "read"):
        frappe.throw("Not permitted", frappe.PermissionError)

    projects = frappe.get_list(
        "Project",
        filters={"status": ["!=", "Cancelled"]},
        fields=[
            "name", "custom_quote_no as quote_no", "customer as client", "project_name as product",
            "expected_start_date as start_date", "imp_deadline as delivery_date",
            "imp_status as project_status", "imp_current_stage as current_phase",
            "percent_complete", "custom_next_activity as next_activity", "custom_remarks as remarks",
        ],
        order_by="modified desc",
    )

    result = []
    for p in projects:
        milestones = _project_milestones(p.name)
        modules = _project_modules(p.name)

        received_pct = sum(m["weight"] for m in milestones if m["payment_status"] == "Paid")
        pending_pct = sum(m["weight"] for m in milestones if m["payment_status"] != "Paid")
        next_ms = next((m["title"] for m in milestones if m["payment_status"] != "Paid"), None)

        modules_completed = len([m for m in modules if m.get("module_status") == "Completed"])
        current_module = next((m["module_name"] for m in modules if m.get("module_status") == "In Progress"), None)

        result.append({
            "quote_no": p.quote_no or "—",
            "client": p.client,
            "product": p.product,
            "modules": modules, 
            "start_date": p.start_date,
            "delivery_date": p.delivery_date,
            "project_status": p.project_status,
            "timeline": _timeline_label(p.start_date, p.delivery_date),
            "current_phase": p.current_phase,
            "overall_percent": p.percent_complete,
            "milestones": milestones,
            "payment_received_pct": received_pct,
            "payment_pending_pct": pending_pct,
            "next_payment_milestone": next_ms or "—",
            "modules_completed": modules_completed,
            "modules_total": len(modules),
            "current_module": current_module or "—",
            "next_activity": p.next_activity or "Not logged",
            "remarks": p.remarks or "None",
        })

    return result