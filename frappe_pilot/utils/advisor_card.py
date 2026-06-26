# Advisor structured card schema, validation, and formatting.

import frappe

CARD_TYPES = frozenset({"calculation", "summary", "diagnose"})
MAX_ROWS = 20


def _format_currency(amount, currency=""):
	if amount is None:
		return ""
	try:
		return frappe.format_value(float(amount), {"fieldtype": "Currency", "options": currency or None})
	except Exception:
		return str(amount)


def validate_advisor_card(card: dict, *, evidence: dict | None = None) -> dict:
	"""Validate card shape; return card with warnings[] — never silent fixes."""
	if not isinstance(card, dict):
		return {"error": "Card must be a JSON object", "valid": False}

	result = dict(card)
	warnings = list(result.get("warnings") or [])
	card_type = result.get("type") or result.get("card_type")

	if card_type not in CARD_TYPES:
		warnings.append(f"Unknown card type: {card_type}")
		result["valid"] = False
		result["warnings"] = warnings
		return result

	result["type"] = card_type
	rows = result.get("rows") or result.get("lines") or []
	if len(rows) > MAX_ROWS:
		warnings.append(f"Truncated to {MAX_ROWS} rows")
		result["rows"] = rows[:MAX_ROWS]

	if card_type == "calculation":
		total = result.get("total")
		computed = 0.0
		has_amounts = False
		for row in result.get("rows") or []:
			amount = row.get("amount")
			if amount is not None:
				has_amounts = True
				try:
					computed += float(amount)
				except (TypeError, ValueError):
					warnings.append(f"Invalid amount on row: {row.get('label') or row.get('item')}")
		if has_amounts and total is not None:
			try:
				if abs(float(total) - computed) > 0.01:
					warnings.append(
						f"Total {total} differs from row sum {computed:.2f}"
					)
			except (TypeError, ValueError):
				warnings.append("Invalid total value")

		if evidence and evidence.get("lines"):
			hook_total = 0.0
			for line in evidence.get("lines") or []:
				rate = float(line.get("rate") or 0)
				days = line.get("days") or evidence.get("days")
				qty = float(line.get("qty") or 1)
				if line.get("role") == "rental" and days:
					hook_total += rate * float(days)
				else:
					hook_total += rate * qty
			if total is not None and hook_total and abs(float(total) - hook_total) > 0.01:
				warnings.append(
					f"Card total {total} differs from hook evidence {hook_total:.2f}"
				)

	result["valid"] = not any("Unknown card type" in w for w in warnings)
	result["warnings"] = warnings
	result.setdefault("footer", "Before taxes and discounts. Update quantities on the form manually — Advisor is read-only.")
	return result


def normalize_advisor_card(card: dict, *, evidence: dict | None = None) -> dict:
	"""Ensure consistent keys for frontend renderer."""
	if not card or card.get("error"):
		return card
	normalized = validate_advisor_card(card, evidence=evidence)
	currency = normalized.get("currency") or ""

	for row in normalized.get("rows") or []:
		if row.get("amount") is not None and not row.get("amount_display"):
			row["amount_display"] = _format_currency(row.get("amount"), currency)
		if not row.get("calculation") and row.get("formula"):
			row["calculation"] = row.get("formula")

	if normalized.get("total") is not None and not normalized.get("total_display"):
		normalized["total_display"] = _format_currency(normalized.get("total"), currency)

	return normalized


def build_calculation_card(
	*,
	title: str,
	days: int | None,
	rows: list[dict],
	total: float,
	currency: str = "",
	assumptions: list[str] | None = None,
) -> dict:
	return normalize_advisor_card({
		"type": "calculation",
		"title": title,
		"days": days,
		"rows": rows,
		"total": total,
		"currency": currency,
		"assumptions": assumptions or [],
	})


def build_summary_card(*, title: str, headline: str, rows: list[dict] | None = None, status: str = "") -> dict:
	return normalize_advisor_card({
		"type": "summary",
		"title": title,
		"headline": headline,
		"status": status,
		"rows": rows or [],
	})


def build_diagnose_card(*, title: str, findings: list[dict], evidence: list[str] | None = None, verify: list[str] | None = None) -> dict:
	return normalize_advisor_card({
		"type": "diagnose",
		"title": title,
		"findings": findings,
		"issues": findings,
		"evidence": evidence or [],
		"verify": verify or [],
	})
