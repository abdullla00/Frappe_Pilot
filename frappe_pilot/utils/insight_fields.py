# Field intent resolver for Insight get_list_sample queries

from __future__ import annotations

import re

import frappe

# Business-term synonyms → fieldname (validated against DocType meta)
FIELD_SYNONYMS: dict[str, list[str]] = {
	"due_date": [
		"valid till",
		"validity",
		"valid until",
		"due date",
		"due",
		"payment due",
		"expiry",
		"expires",
	],
	"customer": ["customer", "client", "party", "buyer", "debtor"],
	"supplier": ["supplier", "vendor", "creditor"],
	"posting_date": ["posting date", "invoice date", "bill date"],
	"grand_total": ["grand total", "invoice amount"],
	"outstanding_amount": ["outstanding", "unpaid amount", "balance due", "remaining amount"],
	"status": ["status", "state"],
	"item_code": ["item code", "sku"],
	"item_name": ["item name", "product name"],
	"qty": ["quantity", "qty", "units"],
	"company": ["company"],
	"project": ["project"],
	"cost_center": ["cost center"],
}


def _normalize_text(text: str) -> str:
	return re.sub(r"\s+", " ", (text or "").lower().strip())


def _valid_fieldnames(doctype: str) -> set[str]:
	meta = frappe.get_meta(doctype)
	names = {f.fieldname for f in meta.fields if f.fieldname}
	names.add("name")
	return names


def _fields_from_message(message: str, doctype: str) -> list[str]:
	msg = _normalize_text(message)
	if not msg:
		return []

	valid = _valid_fieldnames(doctype)
	matched: list[str] = []
	seen: set[str] = set()

	for fieldname, phrases in FIELD_SYNONYMS.items():
		if fieldname not in valid:
			continue
		for phrase in sorted(phrases, key=len, reverse=True):
			if phrase in msg and fieldname not in seen:
				matched.append(fieldname)
				seen.add(fieldname)
				break

	meta = frappe.get_meta(doctype)
	for field in meta.fields:
		if field.fieldname not in valid or field.fieldname in seen:
			continue
		label = _normalize_text(field.label or "")
		if label and len(label) > 2 and label in msg:
			matched.append(field.fieldname)
			seen.add(field.fieldname)

	return matched


def resolve_list_fields(
	doctype: str,
	requested_fields: list | None = None,
	*,
	user_message: str = "",
	doctype_meta=None,
) -> list[str]:
	"""Return minimal field list: name + user-intent fields only."""
	if not doctype:
		return ["name"]

	valid = _valid_fieldnames(doctype)
	if not valid:
		return ["name"]

	if doctype_meta and isinstance(doctype_meta, dict):
		for entry in doctype_meta.get("fields") or []:
			fn = entry.get("fieldname")
			label = _normalize_text(entry.get("label") or "")
			if fn and label and fn in valid and label in _normalize_text(user_message):
				if fn not in (requested_fields or []):
					requested_fields = list(requested_fields or []) + [fn]

	llm_fields: list[str] = []
	for f in requested_fields or []:
		fn = (f or "").strip()
		if fn and fn in valid:
			llm_fields.append(fn)

	intent_fields = _fields_from_message(user_message, doctype)

	if intent_fields:
		result: list[str] = ["name"]
		for fn in intent_fields:
			if fn != "name" and fn not in result:
				result.append(fn)
		return result

	if llm_fields:
		result: list[str] = []
		for fn in llm_fields:
			if fn not in result:
				result.append(fn)
		if "name" not in result:
			result.insert(0, "name")
		return result

	return ["name"]
