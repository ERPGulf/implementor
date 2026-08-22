// Copyright (c) 2026, ERPGulf.com and contributors
// For license information, please see license.txt

frappe.query_reports["Billing and Collection Report"] = {
	filters: [
		{
			"fieldname": "project",
			"fieldtype": "Link",
			"label": "Project",
			"mandatory": 0,
			"options": "Project",
			"wildcard_filter": 0
		},
		{
			"fieldname": "customer",
			"fieldtype": "Link",
			"label": "Customer",
			"mandatory": 0,
			"options": "Customer",
			"wildcard_filter": 0
		},
		{
			"fieldname": "payment_status",
			"fieldtype": "Select",
			"label": "Payment Status",
			"mandatory": 0,
			"options": "\nPaid\nUnPaid\nOverdue\nPartially Paid\nPending",
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
