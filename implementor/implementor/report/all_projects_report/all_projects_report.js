// Copyright (c) 2026, ERPGulf.com and contributors
// For license information, please see license.txt

frappe.query_reports["All Projects Report"] = {
	filters: [
		{
			"fieldname": "status",
			"fieldtype": "Select",
			"label": "Status",
			"mandatory": 0,
			"options": "\nDiscovery\nActive\nGo-Live\nAMC\nHypercare\nClosed",
			"wildcard_filter": 0
		},
		{
			"fieldname": "pm",
			"fieldtype": "Link",
			"label": "Project Manager",
			"mandatory": 0,
			"options": "User",
			"wildcard_filter": 0
		},
		{
			"fieldname": "customer",
			"fieldtype": "Link",
			"label": "Client",
			"mandatory": 0,
			"options": "Customer",
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
