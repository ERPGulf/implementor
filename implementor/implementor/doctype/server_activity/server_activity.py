# Copyright (c) 2026, ERPGulf.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ServerActivity(Document):
	def on_trash(self):
		if "System Manager" not in frappe.get_roles(frappe.session.user):
			frappe.throw("Server Activity records cannot be deleted. This is an immutable audit log.")
