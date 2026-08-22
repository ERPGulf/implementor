import frappe


def execute(filters=None):
    filters = filters or {}

    conditions = []
    values = {}

    if filters.get("customer"):
        conditions.append("customer = %(customer)s")
        values["customer"] = filters["customer"]

    if filters.get("project"):
        conditions.append("project = %(project)s")
        values["project"] = filters["project"]

    if filters.get("status"):
        conditions.append("status = %(status)s")
        values["status"] = filters["status"]

    if filters.get("priority"):
        conditions.append("priority = %(priority)s")
        values["priority"] = filters["priority"]

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    data = frappe.db.sql(f"""
        SELECT
            name,
            subject,
            customer,
            project,
            ticket_type,
            priority,
            status,
            sla_due,
            CASE WHEN sla_due < NOW() AND status NOT IN ('Resolved', 'Closed') THEN 1 ELSE 0 END as sla_breached,
            converted_task
        FROM `tabSupport Ticket`
        {where_clause}
        ORDER BY sla_due ASC
    """, values, as_dict=True)

    columns = [
        {"label": "Subject", "fieldname": "subject", "fieldtype": "Data", "width": 220},
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Data", "width": 160},
        {"label": "Project", "fieldname": "project", "fieldtype": "Data", "width": 160},
        {"label": "Type", "fieldname": "ticket_type", "fieldtype": "Data", "width": 110},
        {"label": "Priority", "fieldname": "priority", "fieldtype": "Data", "width": 90},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": "SLA Due", "fieldname": "sla_due", "fieldtype": "Datetime", "width": 150},
        {"label": "SLA Breached", "fieldname": "sla_breached", "fieldtype": "Check", "width": 100},
        {"label": "Converted Task", "fieldname": "converted_task", "fieldtype": "Link", "options": "Task", "width": 140},
        {"label": "Ticket ID", "fieldname": "name", "fieldtype": "Link", "options": "Support Ticket", "width": 0},
    ]

    total_count = len(data)
    breached_count = sum(1 for row in data if row.get("sla_breached"))
    resolved_count = sum(1 for row in data if row.get("status") in ("Resolved", "Closed"))

    report_summary = [
        {"value": total_count, "label": "Total Tickets", "datatype": "Int"},
        {"value": breached_count, "label": "SLA Breached", "datatype": "Int", "indicator": "Red"},
        {"value": resolved_count, "label": "Resolved", "datatype": "Int", "indicator": "Green"},
    ]

    return columns, data, None, None, report_summary