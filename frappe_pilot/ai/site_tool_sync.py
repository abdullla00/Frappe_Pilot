# Copyright (c) 2026, Frappe Pilot and contributors

"""Lazy materialization of CRUD tools when Pilot Agent links DocTypes/modules."""

import json

import frappe

from frappe_pilot.ai.sdk_tools import DEFAULT_PARAMETERS
from frappe_pilot.api.coding_agent import BANNED_DOCTYPES

TOOL_TYPE_SPECS = [
	("Get Document", 0),
	("Get List", 0),
	("Create Document", 1),
	("Update Document", 1),
	("Delete Document", 1),
]


def _ensure_tool_types():
	for type_name, is_mutating in TOOL_TYPE_SPECS:
		if not frappe.db.exists("Pilot Agent Tool Type", type_name):
			frappe.get_doc({
				"doctype": "Pilot Agent Tool Type",
				"name1": type_name,
				"is_mutating": is_mutating,
			}).insert(ignore_permissions=True)


def _slug(doctype_name: str) -> str:
	return doctype_name.lower().replace(" ", "_")


def _tool_name(tool_type: str, doctype_name: str) -> str:
	prefix = {
		"Get Document": "get",
		"Get List": "list",
		"Create Document": "create",
		"Update Document": "update",
		"Delete Document": "delete",
	}.get(tool_type, "tool")
	return f"{prefix}_{_slug(doctype_name)}"


def _tool_description(tool_type: str, doctype_name: str) -> str:
	return f"{tool_type} for {doctype_name}"


def _resolve_doctypes(agent_doc) -> set[str]:
	doctypes = set()
	for row in agent_doc.get("linked_doctypes") or []:
		if row.doctype_name and row.doctype_name not in BANNED_DOCTYPES:
			doctypes.add(row.doctype_name)
	for row in agent_doc.get("linked_modules") or []:
		if not row.module_name:
			continue
		for dt in frappe.get_all("DocType", filters={"module": row.module_name}, pluck="name"):
			if dt not in BANNED_DOCTYPES:
				doctypes.add(dt)
	return doctypes


def _upsert_tool_function(tool_type: str, doctype_name: str, source_app: str | None = None):
	tool_name = _tool_name(tool_type, doctype_name)
	payload = {
		"tool_name": tool_name,
		"tool_type": tool_type,
		"description": _tool_description(tool_type, doctype_name),
		"reference_doctype": doctype_name,
		"source_app": source_app or frappe.get_meta(doctype_name).app or "",
		"auto_synced": 1,
		"lazy_synced": 1,
		"parameters_json": json.dumps(
			DEFAULT_PARAMETERS.get(tool_type, {"type": "object", "properties": {}})
		),
	}
	if frappe.db.exists("Pilot Agent Tool Function", tool_name):
		doc = frappe.get_doc("Pilot Agent Tool Function", tool_name)
		doc.update(payload)
		doc.save(ignore_permissions=True)
		return doc.name

	doc = frappe.get_doc({"doctype": "Pilot Agent Tool Function", **payload})
	doc.insert(ignore_permissions=True)
	return doc.name


def _attach_tool_to_agent(agent_doc, tool_function_name: str):
	existing = {row.tool_function for row in (agent_doc.get("agent_tool") or [])}
	if tool_function_name in existing:
		return
	agent_doc.append("agent_tool", {"tool_function": tool_function_name})


def materialize_tools_for_agent(agent_doc, include_write_tools: bool = False):
	"""Create/update Pilot Agent Tool Function rows for linked scopes."""
	_ensure_tool_types()
	created = []
	for doctype_name in sorted(_resolve_doctypes(agent_doc)):
		if not frappe.db.exists("DocType", doctype_name):
			continue
		for tool_type, is_mutating in TOOL_TYPE_SPECS:
			if is_mutating and not include_write_tools:
				continue
			tool_function_name = _upsert_tool_function(tool_type, doctype_name)
			_attach_tool_to_agent(agent_doc, tool_function_name)
			created.append(tool_function_name)
	return created


def sync_agent_tools(agent_doc):
	"""Entry point for Pilot Agent validate/save."""
	return materialize_tools_for_agent(agent_doc, include_write_tools=agent_doc.execution_mode == "Direct")
