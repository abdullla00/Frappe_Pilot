# Copyright (c) 2026, Aditya Boi and Contributors

from frappe.tests import UnitTestCase

from frappe_pilot.utils.micro_report import (
	build_from_list_sample_result,
	build_micro_report,
	compose_brief_insight_reply,
	infer_list_sample_title,
)


class TestListSampleTables(UnitTestCase):
	def test_infer_title_job_order_unpaid(self):
		title = infer_list_sample_title(
			"Sales Invoice",
			filters=[
				["outstanding_amount", ">", 0],
				["job_order", "is", "set"],
			],
		)
		self.assertIn("Unpaid", title)
		self.assertIn("Job Order", title)

	def test_infer_title_rental_order_only(self):
		title = infer_list_sample_title(
			"Sales Invoice",
			filters=[
				["outstanding_amount", ">", 0],
				["rental_order", "is", "set"],
			],
		)
		self.assertIn("Rental Order", title)
		self.assertNotIn("Job Order", title)

	def test_prune_empty_link_column(self):
		tool_result = {
			"fields": ["name", "job_order", "rental_order"],
			"rows": [
				{"name": "SINV-1", "job_order": "JO-1", "rental_order": None},
				{"name": "SINV-2", "job_order": "JO-2", "rental_order": ""},
			],
			"row_count": 2,
		}
		report = build_from_list_sample_result(
			"Sales Invoice",
			[["job_order", "is", "set"]],
			tool_result,
		)
		table = report["tables"][0]
		col_names = [c["fieldname"] for c in table["columns"]]
		self.assertIn("job_order", col_names)
		self.assertNotIn("rental_order", col_names)
		self.assertIn("Job Order", table["title"])

	def test_skip_redundant_count_kpi_when_table_exists(self):
		tool_results = [
			{
				"doctype": "Sales Invoice",
				"filters": [["job_order", "is", "set"]],
				"fields": ["name", "job_order"],
				"rows": [{"name": "SINV-1", "job_order": "JO-1"}],
				"row_count": 1,
			},
			{"doctype": "Sales Invoice", "count": 1},
		]
		report = build_micro_report(tool_results)
		kpi_labels = [k.get("label") for k in report.get("kpis") or []]
		self.assertNotIn("Sales Invoice count", kpi_labels)

	def test_brief_reply_multi_section(self):
		micro_report = {
			"tables": [
				{"title": "Unpaid Sales Invoice · Job Order linked", "row_count": 2, "rows": [{}, {}]},
				{"title": "Unpaid Sales Invoice · Rental Order linked", "row_count": 7, "rows": [{}] * 7},
			]
		}
		reply = compose_brief_insight_reply(micro_report)
		self.assertIn("9 records", reply)
		self.assertIn("2 lists", reply)
		self.assertLess(len(reply), 220)
