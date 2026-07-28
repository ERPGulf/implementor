# # Copyright (c) 2026, ERPGulf.com and contributors
# # For license information, please see license.txt

import frappe
from frappe.model.document import Document

class Reaction(Document):
	def validate(self):
		existing = frappe.db.exists("Reaction", {
			"reference_doctype": self.reference_doctype,
			"reference_name": self.reference_name,
			"user": self.user,
			"reaction_type": self.reaction_type,
			"name": ["!=", self.name],
		})
		if existing:
			frappe.throw("This reaction already exists for this user and item.")