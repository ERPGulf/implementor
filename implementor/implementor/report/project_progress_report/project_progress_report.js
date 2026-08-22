// Copyright (c) 2026, ERPGulf.com and contributors
// For license information, please see license.txt

frappe.query_reports["Project Progress Report"] = {
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
			"fieldname": "division",
			"fieldtype": "Select",
			"label": "Division",
			"mandatory": 0,
			"options": "\nFunctional\nTechnical\nInfra-Cloud",
			"wildcard_filter": 0
		},
		{
			"fieldname": "status",
			"fieldtype": "Select",
			"label": "Status",
			"mandatory": 0,
			"options": "\nOpen\nWorking\nPending Review\nOverdue\nTemplate\nCompleted\nCancelled",
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
