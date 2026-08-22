import frappe


def execute(filters=None):
    filters = filters or {}

    conditions = []
    values = {}

    if filters.get("status"):
        conditions.append("imp_status = %(status)s")
        values["status"] = filters["status"]

    if filters.get("pm"):
        conditions.append("imp_project_manager = %(pm)s")
        values["pm"] = filters["pm"]

    if filters.get("customer"):
        conditions.append("customer = %(customer)s")
        values["customer"] = filters["customer"]

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    data = frappe.db.sql(f"""
        SELECT
            p.name as name,
            p.project_name as project_name,
            p.customer as customer,
            COALESCE(u.full_name, p.imp_project_manager) as pm_name,
            p.imp_status as status,
            p.percent_complete as percent_complete,
            p.imp_deadline as due_date,
            CASE WHEN p.imp_deadline < CURDATE() AND p.imp_status != 'Closed' THEN 1 ELSE 0 END as overdue
        FROM `tabProject` p
        LEFT JOIN `tabUser` u ON p.imp_project_manager = u.name
        {where_clause}
        ORDER BY p.project_name ASC
    """, values, as_dict=True)

    columns = [
        {"label": "Project", "fieldname": "project_name", "fieldtype": "Data", "width": 200},
        {"label": "Client", "fieldname": "customer", "fieldtype": "Data", "width": 160},
        {"label": "PM", "fieldname": "pm_name", "fieldtype": "Data", "width": 150},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": "% Complete", "fieldname": "percent_complete", "fieldtype": "Float", "width": 100},
        {"label": "Due Date", "fieldname": "due_date", "fieldtype": "Date", "width": 110},
        {"label": "Overdue", "fieldname": "overdue", "fieldtype": "Check", "width": 80},
        {"label": "Project ID", "fieldname": "name", "fieldtype": "Link", "options": "Project", "width": 0},
    ]

    total_count = len(data)
    overdue_count = sum(1 for row in data if row.get("overdue"))
    active_count = sum(1 for row in data if row.get("status") not in ("Closed", None))

    report_summary = [
        {"value": total_count, "label": "Total Projects", "datatype": "Int"},
        {"value": overdue_count, "label": "Overdue", "datatype": "Int", "indicator": "Red"},
        {"value": active_count, "label": "Active", "datatype": "Int", "indicator": "Green"},
    ]

    return columns, data, None, None, report_summary