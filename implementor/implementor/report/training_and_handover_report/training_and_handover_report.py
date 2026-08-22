import frappe


def execute(filters=None):
    filters = filters or {}

    conditions = ["t.imp_stage IN ('Training', 'Go-Live', 'Hypercare')"]
    values = {}

    if filters.get("project"):
        conditions.append("t.project = %(project)s")
        values["project"] = filters["project"]

    if filters.get("status"):
        conditions.append("t.status = %(status)s")
        values["status"] = filters["status"]

    where_clause = "WHERE " + " AND ".join(conditions)

    data = frappe.db.sql(f"""
        SELECT
            p.project_name as project_name,
            t.subject as subject,
            t.imp_stage as stage,
            COALESCE(u.full_name, t.custom_division_lead) as lead_name,
            t.status as status,
            t.imp_deadline as due_date,
            t.completed_on as completed_on,
            CASE WHEN t.completed_on IS NOT NULL THEN 1 ELSE 0 END as signed_off
        FROM `tabTask` t
        LEFT JOIN `tabProject` p ON t.project = p.name
        LEFT JOIN `tabUser` u ON t.custom_division_lead = u.name
        {where_clause}
        ORDER BY p.project_name ASC, t.imp_deadline ASC
    """, values, as_dict=True)

    columns = [
        {"label": "Project", "fieldname": "project_name", "fieldtype": "Data", "width": 180},
        {"label": "Task", "fieldname": "subject", "fieldtype": "Data", "width": 220},
        {"label": "Stage", "fieldname": "stage", "fieldtype": "Data", "width": 110},
        {"label": "Lead", "fieldname": "lead_name", "fieldtype": "Data", "width": 140},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": "Due Date", "fieldname": "due_date", "fieldtype": "Date", "width": 110},
        {"label": "Completed On", "fieldname": "completed_on", "fieldtype": "Date", "width": 120},
        {"label": "Sign-off Done", "fieldname": "signed_off", "fieldtype": "Check", "width": 100},
    ]

    total_count = len(data)
    signed_off_count = sum(1 for row in data if row.get("signed_off"))
    pending_count = total_count - signed_off_count

    report_summary = [
        {"value": total_count, "label": "Total Items", "datatype": "Int"},
        {"value": pending_count, "label": "Pending Sign-off", "datatype": "Int", "indicator": "Red"},
        {"value": signed_off_count, "label": "Signed Off", "datatype": "Int", "indicator": "Green"},
    ]

    return columns, data, None, None, report_summary