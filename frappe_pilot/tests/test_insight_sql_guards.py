# Copyright (c) 2026, Aditya Boi and Contributors

from frappe.tests import UnitTestCase

from frappe_pilot.utils.insight_sql import (
	_can_enforce_row_permissions,
	_inject_company_filters,
	_parse_tab_doctypes,
	_strip_disallowed_columns,
	_validate_query,
)


class TestInsightSqlGuards(UnitTestCase):
	def test_reject_insert_and_multi_statement(self):
		self.assertIsNotNone(_validate_query("DELETE FROM tabUser"))
		self.assertIsNotNone(_validate_query("SELECT 1; DROP TABLE tabUser"))

	def test_parse_tab_doctypes(self):
		dts = _parse_tab_doctypes("SELECT name FROM `tabUser` LIMIT 5")
		self.assertIn("User", dts)

	def test_inject_company_requires_context(self):
		result = _inject_company_filters(
			"SELECT name FROM `tabSales Invoice`",
			["Sales Invoice"],
			"",
		)
		self.assertIsInstance(result, dict)
		self.assertEqual(result.get("error"), "company_required")

	def test_inject_company_appends_predicate(self):
		result = _inject_company_filters(
			"SELECT name FROM `tabSales Invoice` WHERE docstatus = 1",
			["Sales Invoice"],
			"Test Co",
		)
		self.assertIsInstance(result, str)
		self.assertIn("company", result.lower())
		self.assertIn("Test Co", result)

	def test_row_permission_unenforceable_on_join(self):
		self.assertFalse(
			_can_enforce_row_permissions(
				"SELECT a.name FROM `tabSales Invoice` a JOIN `tabCustomer` c ON a.customer = c.name",
				"Sales Invoice",
			)
		)

	def test_strip_disallowed_columns_keeps_name(self):
		rows = [{"name": "SI-1", "secret_field": "x", "customer": "A"}]
		out = _strip_disallowed_columns(rows, ["Sales Invoice"])
		self.assertIn("name", out[0])
