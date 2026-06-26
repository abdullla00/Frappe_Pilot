# Insight request logging

from __future__ import annotations

import json

import frappe

from frappe_pilot.utils.settings import get_insight_config

VALID_STATUSES = frozenset({"Success", "Partial", "Error"})


def log_insight_turn(
	*,
	status: str,
	message: str = "",
	preset_id: str = "",
	reports_used=None,
	tools_used=None,
	filters_applied=None,
	sub_queries_json=None,
	sql_query: str = "",
	provider: str = "",
	model: str = "",
	prompt_tokens=None,
	completion_tokens=None,
	duration_ms=None,
	error_message: str = "",
):
	cfg = get_insight_config()
	if not cfg.get("enable_logging"):
		return None

	if not frappe.db.exists("DocType", "Pilot Insight Log"):
		return None

	resolved_status = status if status in VALID_STATUSES else "Error"

	try:
		doc = frappe.get_doc(
			{
				"doctype": "Pilot Insight Log",
				"user": frappe.session.user,
				"status": resolved_status,
				"preset_id": preset_id or "",
				"message_preview": (message or "")[:200],
				"reports_used": json.dumps(reports_used or [], default=str),
				"tools_used": json.dumps(tools_used or [], default=str),
				"filters_applied": json.dumps(filters_applied or [], default=str),
				"sub_queries_json": json.dumps(sub_queries_json or [], default=str),
				"sql_query": (sql_query or "")[:2000],
				"provider": provider or "",
				"model": model or "",
				"prompt_tokens": prompt_tokens,
				"completion_tokens": completion_tokens,
				"duration_ms": duration_ms,
				"error_message": (error_message or "")[:500],
			}
		)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return doc.name
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Pilot Insight Log Error")
		return None
