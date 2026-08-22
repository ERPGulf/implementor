import frappe


def execute(filters=None):
    filters = filters or {}

    conditions = []
    values = {}

    if filters.get("project"):
        conditions.append("t.project = %(project)s")
        values["project"] = filters["project"]

    if filters.get("division"):
        conditions.append("t.imp_division = %(division)s")
        values["division"] = filters["division"]

    if filters.get("status"):
        conditions.append("t.status = %(status)s")
        values["status"] = filters["status"]

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    data = frappe.db.sql(f"""
        SELECT
            p.project_name as project_name,
            t.subject as subject,
            t.imp_division as division,
            COALESCE(u.full_name, t.custom_division_lead) as lead_name,
            t.status as status,
            t.progress as percent,
            t.imp_deadline as due_date,
            CASE WHEN t.imp_deadline < CURDATE() AND t.status NOT IN ('Completed', 'Cancelled') THEN 1 ELSE 0 END as overdue,
            t.name as name
        FROM `tabTask` t
        LEFT JOIN `tabProject` p ON t.project = p.name
        LEFT JOIN `tabUser` u ON t.custom_division_lead = u.name
        {where_clause}
        ORDER BY p.project_name ASC, t.imp_deadline ASC
    """, values, as_dict=True)

    columns = [
        {"label": "Project", "fieldname": "project_name", "fieldtype": "Data", "width": 180},
        {"label": "Task", "fieldname": "subject", "fieldtype": "Data", "width": 200},
        {"label": "Division", "fieldname": "division", "fieldtype": "Data", "width": 110},
        {"label": "Lead", "fieldname": "lead_name", "fieldtype": "Data", "width": 140},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": "% Complete", "fieldname": "percent", "fieldtype": "Float", "width": 100},
        {"label": "Due Date", "fieldname": "due_date", "fieldtype": "Date", "width": 110},
        {"label": "Overdue", "fieldname": "overdue", "fieldtype": "Check", "width": 80},
        {"label": "Task ID", "fieldname": "name", "fieldtype": "Link", "options": "Task", "width": 0},
    ]

    total_count = len(data)
    overdue_count = sum(1 for row in data if row.get("overdue"))
    completed_count = sum(1 for row in data if row.get("status") == "Completed")

    report_summary = [
        {"value": total_count, "label": "Total Tasks", "datatype": "Int"},
        {"value": overdue_count, "label": "Overdue", "datatype": "Int", "indicator": "Red"},
        {"value": completed_count, "label": "Completed", "datatype": "Int", "indicator": "Green"},
    ]

    return columns, data, None, None, report_summary