# Copyright (c) 2026, ERPGulf.com and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import now_datetime


class Server(Document):
	def validate(self):
		# the client app shows when the Online/Offline status was last confirmed
		if self.meta.has_field("custom_status") and (self.is_new() or self.has_value_changed("custom_status")):
			self.status_checked_at = now_datetime()
