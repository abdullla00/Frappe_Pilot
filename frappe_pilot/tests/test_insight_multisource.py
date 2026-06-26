# Copyright (c) 2026, Aditya Boi and Contributors
# See license.txt

from frappe.tests import UnitTestCase

from frappe_pilot.utils.insight_sql import _validate_query
from frappe_pilot.utils.micro_report import build_micro_report, build_snapshot_sources, empty_micro_report


class TestInsightMultiSource(UnitTestCase):
	def test_build_micro_report_merges_multiple_tools(self):
		tool_results = [
			{
				"tool": "get_list_count",
				"doctype": "Sales Invoice",
				"count": 5,
				"filters": {"docstatus": 1},
			},
			{
				"tool": "get_list_sample",
				"doctype": "Sales Invoice",
				"rows": [{"name": "SI-001", "customer": "Test"}],
				"columns": [{"fieldname": "name", "label": "Name"}],
				"row_count": 1,
			},
		]
		report = build_micro_report(tool_results, {"company": "Test Co"})
		self.assertTrue(report.get("kpis") or report.get("tables"))
		self.assertIsInstance(report.get("warnings"), list)

	def test_build_micro_report_partial_failure(self):
		tool_results = [
			{"tool": "run_report", "error": "Report not found"},
			{
				"tool": "get_list_count",
				"doctype": "Customer",
				"count": 3,
			},
		]
		report = build_micro_report(tool_results)
		self.assertTrue(report.get("warnings"))
		self.assertTrue(report.get("kpis") or report.get("tables"))

	def test_build_micro_report_all_fail(self):
		tool_results = [
			{"tool": "run_report", "error": "fail one"},
			{"tool": "get_list_count", "error": "fail two"},
		]
		report = build_micro_report(tool_results)
		self.assertEqual(len(report.get("warnings") or []), 2)
		self.assertTrue(report.get("error"))

	def test_build_snapshot_sources(self):
		tables = [
			{"report_name": "Profit and Loss Statement", "row_count": 10},
			{"doctype": "Sales Invoice", "row_count": 5},
		]
		sources = build_snapshot_sources(tables)
		self.assertEqual(len(sources), 2)
		self.assertEqual(sources[0]["type"], "report")
		self.assertEqual(sources[1]["type"], "list")

	def test_sql_validate_select_only(self):
		self.assertIsNone(_validate_query("SELECT name FROM `tabUser` LIMIT 10"))
		self.assertIsNotNone(_validate_query("DELETE FROM tabUser"))
		self.assertIsNotNone(_validate_query("SELECT 1; DROP TABLE tabUser"))

	def test_empty_micro_report_shape(self):
		report = empty_micro_report(error="test")
		self.assertEqual(report["error"], "test")
		self.assertIn("warnings", report)

	def test_dedupe_identical_tables(self):
		from frappe_pilot.utils.micro_report import _dedupe_tables

		table = {
			"doctype": "Sales Invoice",
			"title": "Sales Invoice",
			"rows": [{"name": "SI-1"}],
			"row_count": 1,
		}
		self.assertEqual(len(_dedupe_tables([table, table])), 1)
