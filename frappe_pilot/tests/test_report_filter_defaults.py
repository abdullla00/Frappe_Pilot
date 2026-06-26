# Copyright (c) 2026, Aditya Boi and Contributors

from frappe.tests import UnitTestCase

from frappe_pilot.utils.i18n import expand_split_chips
from frappe_pilot.utils.report_defaults import apply_report_filter_defaults


class TestReportFilterDefaults(UnitTestCase):
	def test_mtd_filters_use_date_range(self):
		filters = apply_report_filter_defaults(
			{
				"company": "Test Co",
				"from_date": "2026-06-01",
				"to_date": "2026-06-30",
				"periodicity": "Monthly",
			}
		)
		self.assertEqual(filters["filter_based_on"], "Date Range")
		self.assertEqual(str(filters["period_start_date"]), "2026-06-01")
		self.assertEqual(str(filters["period_end_date"]), "2026-06-30")

	def test_yearly_defaults_use_fiscal_year(self):
		filters = apply_report_filter_defaults({"company": "Galiska Company", "periodicity": "Yearly"})
		self.assertEqual(filters["filter_based_on"], "Fiscal Year")
		self.assertTrue(filters.get("from_fiscal_year"))
		self.assertTrue(filters.get("period_start_date"))
		self.assertTrue(filters.get("period_end_date"))


class TestInsightChipI18n(UnitTestCase):
	def test_expand_split_chips_accepts_structured_dicts(self):
		raw = [
			{
				"label": "P&L this month",
				"prompt": "P&L this month",
				"preset_id": "pl_this_month",
				"mode": "insight_preset",
			}
		]
		out = expand_split_chips(raw, ["en", "ckb"], max_en=4)
		self.assertEqual(len(out), 1)
		self.assertEqual(out[0]["mode"], "insight_preset")
		self.assertEqual(out[0]["preset_id"], "pl_this_month")
