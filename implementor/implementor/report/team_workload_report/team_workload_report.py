import frappe


def execute(filters=None):
    filters = filters or {}

    conditions = []
    values = {}

    if filters.get("division"):
        conditions.append("u.imp_division = %(division)s")
        values["division"] = filters["division"]

    where_clause = ("AND " + " AND ".join(conditions)) if conditions else ""

    data = frappe.db.sql(f"""
        SELECT
            u.full_name as user_name,
            u.imp_division as division,
            (SELECT COUNT(*) FROM `tabToDo` td WHERE td.allocated_to = u.name AND td.status = 'Open') as open_todos,
            (SELECT COUNT(*) FROM `tabTask` t WHERE t.custom_division_lead = u.name AND t.status NOT IN ('Completed', 'Cancelled')) as open_tasks_led,
            (SELECT COUNT(*) FROM `tabToDo` td WHERE td.allocated_to = u.name AND td.imp_urgency = 'Emergency' AND td.status = 'Open') as emergency_items,
            (
                (SELECT COUNT(*) FROM `tabToDo` td WHERE td.allocated_to = u.name AND td.status = 'Open')
                +
                (SELECT COUNT(*) FROM `tabTask` t WHERE t.custom_division_lead = u.name AND t.status NOT IN ('Completed', 'Cancelled'))
            ) as total_workload
        FROM `tabUser` u
        WHERE u.enabled = 1
        {where_clause}
        HAVING total_workload > 0
        ORDER BY total_workload DESC
    """, values, as_dict=True)

    for row in data:
        row["overloaded"] = 1 if row["total_workload"] > 8 else 0

    columns = [
        {"label": "User", "fieldname": "user_name", "fieldtype": "Data", "width": 180},
        {"label": "Division", "fieldname": "division", "fieldtype": "Data", "width": 110},
        {"label": "Open ToDos", "fieldname": "open_todos", "fieldtype": "Int", "width": 100},
        {"label": "Open Tasks (Led)", "fieldname": "open_tasks_led", "fieldtype": "Int", "width": 130},
        {"label": "Emergency Items", "fieldname": "emergency_items", "fieldtype": "Int", "width": 120},
        {"label": "Total Workload", "fieldname": "total_workload", "fieldtype": "Int", "width": 120},
        {"label": "Overloaded", "fieldname": "overloaded", "fieldtype": "Check", "width": 90},
    ]

    total_people = len(data)
    overloaded_count = sum(1 for row in data if row.get("overloaded"))
    total_emergency = sum(row.get("emergency_items") or 0 for row in data)

    report_summary = [
        {"value": total_people, "label": "Team Members", "datatype": "Int"},
        {"value": overloaded_count, "label": "Overloaded", "datatype": "Int", "indicator": "Red"},
        {"value": total_emergency, "label": "Emergency Items", "datatype": "Int", "indicator": "Orange"},
    ]

    return columns, data, None, None, report_summary