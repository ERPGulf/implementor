import frappe


def execute(filters=None):
    filters = filters or {}

    conditions = []
    values = {}

    if filters.get("project"):
        conditions.append("pm.parent = %(project)s")
        values["project"] = filters["project"]

    if filters.get("payment_status"):
        conditions.append("pm.payment_status = %(payment_status)s")
        values["payment_status"] = filters["payment_status"]

    if filters.get("completion_status"):
        conditions.append("pm.completion_status = %(completion_status)s")
        values["completion_status"] = filters["completion_status"]

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    data = frappe.db.sql(f"""
        SELECT
            p.project_name as project_name,
            pm.m_title as m_title,
            pm.duration as duration,
            pm.payment_ as payment_percent,
            pm.completion_status as completion_status,
            pm.payment_status as payment_status,
            pm.start_date as start_date,
            pm.end_date as end_date,
            CASE WHEN pm.end_date < CURDATE() AND pm.payment_status != 'Paid' THEN 1 ELSE 0 END as overdue_payment
        FROM `tabPayment Milestone` pm
        LEFT JOIN `tabProject` p ON pm.parent = p.name
        {where_clause}
        ORDER BY p.project_name ASC, pm.end_date ASC
    """, values, as_dict=True)

    columns = [
        {"label": "Project", "fieldname": "project_name", "fieldtype": "Data", "width": 180},
        {"label": "Milestone", "fieldname": "m_title", "fieldtype": "Data", "width": 160},
        {"label": "Duration (days)", "fieldname": "duration", "fieldtype": "Data", "width": 110},
        {"label": "Payment %", "fieldname": "payment_percent", "fieldtype": "Float", "width": 100},
        {"label": "Completion Status", "fieldname": "completion_status", "fieldtype": "Data", "width": 140},
        {"label": "Payment Status", "fieldname": "payment_status", "fieldtype": "Data", "width": 120},
        {"label": "Start Date", "fieldname": "start_date", "fieldtype": "Date", "width": 110},
        {"label": "End Date", "fieldname": "end_date", "fieldtype": "Date", "width": 110},
        {"label": "Overdue Payment", "fieldname": "overdue_payment", "fieldtype": "Check", "width": 110},
    ]

    total_count = len(data)
    overdue_count = sum(1 for row in data if row.get("overdue_payment"))
    paid_count = sum(1 for row in data if row.get("payment_status") == "Paid")

    report_summary = [
        {"value": total_count, "label": "Total Milestones", "datatype": "Int"},
        {"value": overdue_count, "label": "Overdue Payments", "datatype": "Int", "indicator": "Red"},
        {"value": paid_count, "label": "Paid", "datatype": "Int", "indicator": "Green"},
    ]

    return columns, data, None, None, report_summary