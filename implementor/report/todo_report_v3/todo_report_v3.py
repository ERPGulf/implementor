import frappe


def execute(filters=None):
    filters = filters or {}

    conditions = ["todo.reference_type = 'Task'"]
    values = {}

    if filters.get("from_date"):
        conditions.append("todo.date >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("todo.date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("allocated_to"):
        conditions.append("todo.allocated_to = %(allocated_to)s")
        values["allocated_to"] = filters["allocated_to"]

    if filters.get("project"):
        conditions.append("project.name = %(project)s")
        values["project"] = filters["project"]

    if filters.get("task"):
        conditions.append("task.name = %(task)s")
        values["task"] = filters["task"]

    if filters.get("status"):
        conditions.append("todo.status = %(status)s")
        values["status"] = filters["status"]

    if filters.get("priority"):
        conditions.append("todo.priority = %(priority)s")
        values["priority"] = filters["priority"]

    where_clause = " AND ".join(conditions)

    data = frappe.db.sql(f"""
        SELECT
            todo.date as date,
            COALESCE(user.full_name, todo.allocated_to) as allocated_to,
            todo.priority as priority,
            todo.status as status,
            project.project_name as project_name,
            task.subject as subject,
            todo.assigned_by as assigned_by,
            LEFT(todo.description, 80) as description,
            CASE WHEN todo.date < CURDATE() AND todo.status = 'Open' THEN 1 ELSE 0 END as overdue,
            todo.name as name
        FROM `tabToDo` todo
        LEFT JOIN `tabTask` task
            ON todo.reference_type = 'Task' AND todo.reference_name = task.name
        LEFT JOIN `tabProject` project
            ON task.project = project.name
        LEFT JOIN `tabUser` user
            ON todo.allocated_to = user.name
        WHERE {where_clause}
        ORDER BY user.full_name ASC, todo.date ASC
    """, values, as_dict=True)

    columns = [
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 110},
        {"label": "Allocated To", "fieldname": "allocated_to", "fieldtype": "Data", "width": 150},
        {"label": "Priority", "fieldname": "priority", "fieldtype": "Data", "width": 90},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 90},
        {"label": "Project", "fieldname": "project_name", "fieldtype": "Data", "width": 180},
        {"label": "Task", "fieldname": "subject", "fieldtype": "Data", "width": 200},
        {"label": "Assigned By", "fieldname": "assigned_by", "fieldtype": "Data", "width": 150},
        {"label": "Description", "fieldname": "description", "fieldtype": "Data", "width": 250},
        {"label": "Overdue", "fieldname": "overdue", "fieldtype": "Check", "width": 70},
        {"label": "ToDo", "fieldname": "name", "fieldtype": "Link", "options": "ToDo", "width": 0},
    ]

    total_count = len(data)
    overdue_count = sum(1 for row in data if row.get("overdue"))
    completed_count = sum(1 for row in data if row.get("status") == "Closed")

    report_summary = [
        {"value": total_count, "label": "Total ToDos", "datatype": "Int"},
        {"value": overdue_count, "label": "Overdue", "datatype": "Int", "indicator": "Red"},
        {"value": completed_count, "label": "Completed", "datatype": "Int", "indicator": "Green"},
    ]

    return columns, data, None, None, report_summary
