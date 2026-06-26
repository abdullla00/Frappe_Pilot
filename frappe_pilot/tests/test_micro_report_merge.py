# Copyright (c) 2026, Aditya Boi and Contributors

from frappe.tests import UnitTestCase

from frappe_pilot.utils.micro_report import build_micro_report


class TestMicroReportMerge(UnitTestCase):
	def test_three_tool_results_merge(self):
		tool_results = [
			{"tool": "run_report", "report_name": "P&L", "rows": [{"account": "Income", "amount": 100}], "columns": ["account", "amount"]},
			{"tool": "get_list_count", "doctype": "Sales Invoice", "count": 2},
			{
				"tool": "get_list_sample",
				"doctype": "Customer",
				"rows": [{"name": "C1"}],
				"columns": [{"fieldname": "name", "label": "Name"}],
				"row_count": 1,
			},
		]
		report = build_micro_report(tool_results)
		self.assertTrue(report.get("tables") or report.get("kpis"))

	def test_meta_mismatch_warning(self):
		tool_results = [
			{"tool": "run_report", "report_name": "P&L", "company": "Co A", "rows": [{"x": 1}], "columns": ["x"]},
			{"tool": "run_report", "report_name": "BS", "company": "Co B", "rows": [{"y": 2}], "columns": ["y"]},
		]
		report = build_micro_report(tool_results, {"company": "Co A"})
		warnings = report.get("warnings") or []
		self.assertTrue(any("companies" in (w.get("error") or "").lower() for w in warnings))
