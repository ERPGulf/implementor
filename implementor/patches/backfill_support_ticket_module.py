import frappe


def execute():
    """Older tickets only kept the module as a "Module: …" line in the description."""
    tickets = frappe.get_all(
        "Support Ticket",
        filters={"module": ["is", "not set"], "description": ["like", "Module: %"]},
        fields=["name", "description"],
    )
    for t in tickets:
        first_line = (t.description or "").splitlines()[0]
        module = first_line[len("Module: "):].strip()
        if module:
            frappe.db.set_value("Support Ticket", t.name, "module", module, update_modified=False)
