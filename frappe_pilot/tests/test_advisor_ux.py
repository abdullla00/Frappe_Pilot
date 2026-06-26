# Tests for Advisor tab UX pipeline

import frappe
from frappe.tests import UnitTestCase

from frappe_pilot.utils.advisor_card import build_calculation_card, validate_advisor_card
from frappe_pilot.utils.advisor_calc import try_calc_fast_path
from frappe_pilot.utils.advisor_intent import (
	INTENT_CALCULATION,
	INTENT_DIAGNOSE,
	INTENT_SUMMARY,
	detect_intent,
	extract_days,
	is_analytical_message,
)
from frappe_pilot.utils.advisor_reply import (
	compose_brief_advisor_reply,
	finalize_advisor_reply,
	looks_like_tool_planning,
)
from frappe_pilot.utils.navigation import filter_self_nav_links


class TestAdvisorIntent(UnitTestCase):
	def test_calculation_intent(self):
		intent = detect_intent("if we rent these items for 4 days how much total?")
		self.assertEqual(intent["intent"], INTENT_CALCULATION)
		self.assertEqual(intent["days"], 4)

	def test_summary_intent(self):
		intent = detect_intent("Summarize this quotation")
		self.assertEqual(intent["intent"], INTENT_SUMMARY)

	def test_diagnose_intent(self):
		intent = detect_intent("Diagnose this record")
		self.assertEqual(intent["intent"], INTENT_DIAGNOSE)

	def test_extract_days(self):
		self.assertEqual(extract_days("rent for 7 days"), 7)

	def test_analytical_message(self):
		self.assertTrue(is_analytical_message("how much for 4 days"))
		self.assertFalse(is_analytical_message("open sales invoice"))


class TestAdvisorReply(UnitTestCase):
	def test_brief_calculation_reply(self):
		card = build_calculation_card(
			title="Estimated total · 4 days",
			days=4,
			rows=[{"label": "Item A", "amount": 800000, "calculation": "200k × 4"}],
			total=800000,
			currency="IQD",
		)
		reply = compose_brief_advisor_reply(card)
		self.assertIn("4 days", reply)
		self.assertIn("800", reply)

	def test_tool_planning_suppressed(self):
		raw = (
			"I will fetch get_document and get_list_sample to proceed with the analysis "
			"and then submit_advisor_card with the results for your review."
		)
		self.assertTrue(looks_like_tool_planning(raw))
		card = build_calculation_card(title="T", days=1, rows=[], total=100, currency="USD")
		final = finalize_advisor_reply(raw, advisor_card=card, message="total for 1 day")
		self.assertNotIn("get_document", final.lower())

	def test_read_only_offer_stripped(self):
		final = finalize_advisor_reply("I'll update the quantity for you.", message="explain")
		self.assertNotIn("I'll update", final)


class TestAdvisorNavFilter(UnitTestCase):
	def test_self_nav_removed(self):
		links = [{
			"type": "form",
			"doctype": "Quotation",
			"name": "SAL-QTN-2026-00015",
			"label": "Open quotation",
			"route": ["Form", "Quotation", "SAL-QTN-2026-00015"],
		}]
		filtered = filter_self_nav_links(
			links,
			doctype="Quotation",
			docname="SAL-QTN-2026-00015",
		)
		self.assertEqual(filtered, [])


class TestAdvisorCardValidation(UnitTestCase):
	def test_total_mismatch_warning(self):
		card = validate_advisor_card({
			"type": "calculation",
			"total": 1000,
			"rows": [{"label": "A", "amount": 400}, {"label": "B", "amount": 400}],
		})
		self.assertTrue(any("differs" in w for w in card.get("warnings") or []))

	def test_evidence_mismatch_warning(self):
		card = validate_advisor_card(
			{
				"type": "calculation",
				"total": 1000,
				"rows": [{"label": "A", "amount": 1000, "calculation": "x"}],
			},
			evidence={"lines": [{"role": "rental", "rate": 100, "days": 4, "qty": 1}], "days": 4},
		)
		self.assertTrue(any("hook evidence" in w for w in card.get("warnings") or []))


class TestQuotationCalcMath(UnitTestCase):
	def test_mixed_rental_and_stock_lines(self):
		if not frappe.db.exists("Module Def", "Frappe Trs"):
			self.skipTest("frappe_trs not installed")
		from frappe_trs.advisor.calc.quotation import _is_rental_line

		doc = frappe._dict({"custom_is_rental_order": 1})
		rental_row = frappe._dict({
			"item_code": "GC-AST-26-007-Rental",
			"rate": 200000,
			"qty": 1,
			"item_group": "Rental",
		})
		stock_row = frappe._dict({"item_code": "Stock-Item", "rate": 50000, "qty": 2})
		self.assertTrue(_is_rental_line(rental_row, doc))
		self.assertFalse(_is_rental_line(stock_row, doc))
		days = 4
		rental_amount = float(rental_row.rate) * days
		stock_amount = float(stock_row.rate) * float(stock_row.qty)
		self.assertEqual(rental_amount + stock_amount, 900000)


class TestCalcFastPath(UnitTestCase):
	def test_fast_path_returns_none_without_days(self):
		self.assertIsNone(try_calc_fast_path(
			doctype="Quotation",
			docname="TEST",
			message="how much total",
			intent_info={"intent": INTENT_CALCULATION},
		))


class TestTRSRegistry(UnitTestCase):
	def test_trs_profiles_cover_standalone_doctypes(self):
		if not frappe.db.exists("Module Def", "Frappe Trs"):
			self.skipTest("frappe_trs not installed")
		from frappe_trs.advisor.registry import get_all_profiles

		profiles = get_all_profiles()
		standalone = frappe.get_all(
			"DocType",
			filters={"module": "Frappe Trs", "istable": 0, "issingle": 0},
			pluck="name",
		)
		for doctype in standalone:
			self.assertIn(doctype, profiles, f"Missing profile for {doctype}")

	def test_quotation_profile_keeps_calc_handler(self):
		if not frappe.db.exists("Module Def", "Frappe Trs"):
			self.skipTest("frappe_trs not installed")
		from frappe_trs.advisor.registry import get_all_profiles

		profile = get_all_profiles().get("Quotation") or {}
		self.assertEqual(profile.get("calc_handler"), "quotation")
		self.assertEqual(profile.get("check_handler"), "quotation")
		self.assertTrue(profile.get("analyze_chips"))
