import frappe


def execute(filters=None):
    filters = filters or {}

    date_conditions = []
    values = {}

    if filters.get("from_date"):
        date_conditions.append("t.imp_started_on >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        date_conditions.append("t.imp_started_on <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    date_where = ("AND " + " AND ".join(date_conditions)) if date_conditions else ""

    data = frappe.db.sql(f"""
        SELECT
            p.project_name as project_name,
            COUNT(DISTINCT t.name) as total_tasks,
            SUM(CASE WHEN t.status = 'Completed' THEN 1 ELSE 0 END) as completed_tasks,
            SUM(CASE WHEN t.status NOT IN ('Completed', 'Cancelled') THEN 1 ELSE 0 END) as open_tasks,
            ROUND(AVG(t.progress), 1) as avg_progress,
            (SELECT COUNT(*) FROM `tabToDo` td
                WHERE td.reference_type = 'Task' AND td.reference_name IN (
                    SELECT name FROM `tabTask` t2 WHERE t2.project = p.name
                )
            ) as total_todos,
            (SELECT COUNT(*) FROM `tabToDo` td
                WHERE td.reference_type = 'Task' AND td.status = 'Closed' AND td.reference_name IN (
                    SELECT name FROM `tabTask` t2 WHERE t2.project = p.name
                )
            ) as todos_completed
        FROM `tabTask` t
        LEFT JOIN `tabProject` p ON t.project = p.name
        WHERE t.project IS NOT NULL
        {date_where}
        GROUP BY t.project
        ORDER BY completed_tasks DESC
    """, values, as_dict=True)

    columns = [
        {"label": "Project", "fieldname": "project_name", "fieldtype": "Data", "width": 200},
        {"label": "Total Tasks", "fieldname": "total_tasks", "fieldtype": "Int", "width": 110},
        {"label": "Completed Tasks", "fieldname": "completed_tasks", "fieldtype": "Int", "width": 130},
        {"label": "Open Tasks", "fieldname": "open_tasks", "fieldtype": "Int", "width": 110},
        {"label": "Avg Progress %", "fieldname": "avg_progress", "fieldtype": "Float", "width": 120},
        {"label": "Total Todos", "fieldname": "total_todos", "fieldtype": "Int", "width": 110},
        {"label": "Todos Completed", "fieldname": "todos_completed", "fieldtype": "Int", "width": 130},
    ]

    total_projects = len(data)
    total_completed_tasks = sum(row.get("completed_tasks") or 0 for row in data)
    most_active = data[0]["project_name"] if data else "N/A"

    report_summary = [
        {"value": total_projects, "label": "Active Projects", "datatype": "Int"},
        {"value": total_completed_tasks, "label": "Tasks Completed", "datatype": "Int", "indicator": "Green"},
        {"value": most_active, "label": "Most Active Project", "datatype": "Data"},
    ]

    return columns, data, None, None, report_summary