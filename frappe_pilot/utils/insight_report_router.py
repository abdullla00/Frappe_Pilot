# Report intent router — synonym map to canonical ERPNext report names

from __future__ import annotations

import frappe

from frappe_pilot.utils.report_catalogue import report_exists

REPORT_INTENTS: dict[str, list[str]] = {
	"Profit and Loss Statement": [
		"p&l",
		"p and l",
		"profit and loss",
		"profit",
		"loss",
		"income statement",
	],
	"Balance Sheet": [
		"balance sheet",
		"cash position",
		"cash balance",
		"bank balance",
	],
	"Accounts Receivable Summary": [
		"accounts receivable",
		"ar summary",
		"receivables",
		"ar ",
	],
	"Accounts Payable": [
		"accounts payable",
		"ap summary",
		"payables",
		"bills due",
	],
	"Item Shortage Report": [
		"stock shortage",
		"below reorder",
		"reorder level",
	],
	"Budget Variance Report": [
		"budget variance",
		"budget vs actual",
		"budget actual",
	],
}


def resolve_report_intent(text: str) -> str | None:
	"""Return canonical report name if text matches a known intent."""
	normalized = (text or "").lower().strip()
	if not normalized:
		return None

	for report_name, phrases in REPORT_INTENTS.items():
		for phrase in sorted(phrases, key=len, reverse=True):
			if phrase in normalized and report_exists(report_name):
				return report_name

	if report_exists(normalized):
		return normalized

	match = frappe.db.get_value("Report", {"report_name": text}, "report_name")
	if match and report_exists(match):
		return match

	return None


def suggested_reports_for_prompt(limit: int = 8) -> list[str]:
	return list(REPORT_INTENTS.keys())[:limit]
