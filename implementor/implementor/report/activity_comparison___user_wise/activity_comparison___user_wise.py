import frappe


def execute(filters=None):
    filters = filters or {}

    date_conditions = []
    values = {}

    if filters.get("from_date"):
        date_conditions.append("todo.date >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        date_conditions.append("todo.date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    date_where = ("AND " + " AND ".join(date_conditions)) if date_conditions else ""

    data = frappe.db.sql(f"""
        SELECT
            COALESCE(u.full_name, todo.allocated_to) as user_name,
            SUM(CASE WHEN todo.status = 'Closed' THEN 1 ELSE 0 END) as todos_completed,
            SUM(CASE WHEN todo.status = 'Open' THEN 1 ELSE 0 END) as todos_open,
            COUNT(*) as total_todos,
            ROUND(
                (SUM(CASE WHEN todo.status = 'Closed' THEN 1 ELSE 0 END) / COUNT(*)) * 100, 1
            ) as completion_rate,
            (SELECT COUNT(*) FROM `tabTask` t WHERE t.custom_division_lead = todo.allocated_to) as tasks_led
        FROM `tabToDo` todo
        LEFT JOIN `tabUser` u ON todo.allocated_to = u.name
        WHERE todo.allocated_to IS NOT NULL
        {date_where}
        GROUP BY todo.allocated_to
        ORDER BY todos_completed DESC
    """, values, as_dict=True)

    columns = [
        {"label": "User", "fieldname": "user_name", "fieldtype": "Data", "width": 180},
        {"label": "Todos Completed", "fieldname": "todos_completed", "fieldtype": "Int", "width": 130},
        {"label": "Todos Open", "fieldname": "todos_open", "fieldtype": "Int", "width": 110},
        {"label": "Total Todos", "fieldname": "total_todos", "fieldtype": "Int", "width": 110},
        {"label": "Completion %", "fieldname": "completion_rate", "fieldtype": "Float", "width": 110},
        {"label": "Tasks Led", "fieldname": "tasks_led", "fieldtype": "Int", "width": 100},
    ]

    total_users = len(data)
    total_completed = sum(row.get("todos_completed") or 0 for row in data)
    top_performer = data[0]["user_name"] if data else "N/A"

    report_summary = [
        {"value": total_users, "label": "Active Users", "datatype": "Int"},
        {"value": total_completed, "label": "Total Completed", "datatype": "Int", "indicator": "Green"},
        {"value": top_performer, "label": "Top Performer", "datatype": "Data"},
    ]

    return columns, data, None, None, report_summary