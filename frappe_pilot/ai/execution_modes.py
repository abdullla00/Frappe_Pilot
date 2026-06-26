# Copyright (c) 2026, Frappe Pilot and contributors

"""Safe vs Direct execution modes for mutating agent tools."""

import json

import frappe

STAGE_CACHE_PREFIX = "pilot_staged_action:"


def is_mutating_tool(tool_name: str) -> bool:
	tool_type = frappe.db.get_value("Pilot Agent Tool Function", {"tool_name": tool_name}, "tool_type")
	if not tool_type:
		return False
	return bool(frappe.db.get_value("Pilot Agent Tool Type", tool_type, "is_mutating"))


def stage_mutating_action(tool_name: str, tool_args, context: dict | None = None) -> str:
	"""Store a pending mutating tool call in Redis. Returns session_key."""
	session_key = frappe.generate_hash(length=24)
	payload = {
		"tool_name": tool_name,
		"tool_args": tool_args if isinstance(tool_args, dict) else json.loads(tool_args or "{}"),
		"user": frappe.session.user,
		"agent_name": (context or {}).get("agent_name"),
		"conversation_id": (context or {}).get("conversation_id"),
		"agent_run_id": (context or {}).get("agent_run_id"),
	}
	expiry_sec = int(frappe.db.get_single_value("Pilot Settings", "preview_expiry_minutes") or 5) * 60
	frappe.cache().set_value(f"{STAGE_CACHE_PREFIX}{session_key}", payload, expires_in_sec=expiry_sec)
	return session_key


def confirm_staged_action(session_key: str) -> dict:
	"""Apply a staged mutating action after user confirmation."""
	cache_key = f"{STAGE_CACHE_PREFIX}{session_key}"
	pending = frappe.cache().get_value(cache_key)
	if not pending:
		return {"success": False, "error": "Staged action not found or expired."}
	if pending.get("user") != frappe.session.user:
		return {"success": False, "error": "Session mismatch."}

	from frappe_pilot.ai.tool_registry import execute_tool_function

	result = execute_tool_function(pending["tool_name"], pending.get("tool_args") or {})
	frappe.cache().delete_value(cache_key)
	return {"success": True, "result": result, "session_key": session_key}
