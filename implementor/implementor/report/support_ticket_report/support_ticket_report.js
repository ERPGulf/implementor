// Copyright (c) 2026, ERPGulf.com and contributors
// For license information, please see license.txt

frappe.query_reports["Support Ticket Report"] = {
	filters: [

		{
			"fieldname": "customer",
			"fieldtype": "Link",
			"label": "Customer",
			"mandatory": 0,
			"options": "Customer",
			"wildcard_filter": 0
		},
		{
			"fieldname": "project",
			"fieldtype": "Link",
			"label": "Project",
			"mandatory": 0,
			"options": "Project",
			"wildcard_filter": 0
		},
		{
			"fieldname": "status",
			"fieldtype": "Select",
			"label": "Status",
			"mandatory": 0,
			"options": "\nNew\nTriaged\nIn Progress\nWaiting on Client\nResolved\nClosed",
			"wildcard_filter": 0
		},
		{
			"fieldname": "priority",
			"fieldtype": "Select",
			"label": "Priority",
			"mandatory": 0,
			"options": "\nEmergency\nUrgent\nNormal\nLow",
			"wildcard_filter": 0
		}

	],
	onload: function (report) {
		report.page.add_inner_button(__("Download Branded PDF"), function () {
			var filters = report.get_values();
			var url = "/api/method/implementor.implementor.report_pdf.download_report_pdf?report_name="
				+ encodeURIComponent(report.report_name)
				+ "&filters=" + encodeURIComponent(JSON.stringify(filters));
			window.open(url);
		});
	}
};
