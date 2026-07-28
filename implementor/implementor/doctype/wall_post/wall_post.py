# Copyright (c) 2026, ERPGulf.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

class WallPost(Document):
	def before_insert(self):
		if not self.posted_on:
			self.posted_on = now_datetime()