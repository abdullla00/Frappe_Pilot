# Copyright (c) 2026, Frappe Pilot and contributors

"""Permission-aware tool loading and execution for Pilot agents."""

import importlib
import json

import frappe

TOOL_DOCTYPE = "Pilot Agent Tool Function"


class PermissionAwareToolRegistry:
	TOOL_PERMISSIONS = {
		"Get Document": {"permission": "read"},
		"Get List": {"permission": "read"},
		"Create Document": {"permission": "create"},
		"Update Document": {"permission": "write"},
		"Delete Document": {"permission": "delete"},
	}

	MUTATING_TOOL_TYPES = {
		"Create Document",
		"Update Document",
		"Delete Document",
		"Set Value",
		"POST",
	}

	@classmethod
	def get_allowed_tools(cls, agent_doc, user: str) -> list:
		tools = []
		for tool_link in agent_doc.get("agent_tool") or []:
			try:
				tool_doc = frappe.get_doc(TOOL_DOCTYPE, tool_link.tool_function)
				if cls._can_use_tool(tool_doc, user):
					tools.append(tool_doc)
			except Exception as e:
				frappe.log_error(f"Tool permission check failed for {tool_link.tool_function}: {e}", "Tool Registry")
		return tools

	@classmethod
	def _can_use_tool(cls, tool_doc, user: str) -> bool:
		if user == "Guest":
			return False

		tool_type = tool_doc.tool_type
		if tool_doc.reference_doctype:
			perm_type = cls.TOOL_PERMISSIONS.get(tool_type, {}).get("permission")
			if perm_type and not frappe.has_permission(tool_doc.reference_doctype, ptype=perm_type, user=user):
				return False
		return True


def execute_tool_function(tool_name: str, args: dict | None = None) -> dict:
	"""Execute a Pilot Agent Tool Function by tool_name with permission checks."""
	args = args or {}
	tool_doc = frappe.get_doc(TOOL_DOCTYPE, tool_name) if frappe.db.exists(TOOL_DOCTYPE, tool_name) else None
	if not tool_doc:
		tool_doc_name = frappe.db.get_value(TOOL_DOCTYPE, {"tool_name": tool_name}, "name")
		if not tool_doc_name:
			return {"success": False, "error": f"Tool '{tool_name}' not found."}
		tool_doc = frappe.get_doc(TOOL_DOCTYPE, tool_doc_name)

	if not PermissionAwareToolRegistry._can_use_tool(tool_doc, frappe.session.user):
		return {"success": False, "error": "Permission denied.", "permission_denied": True}

	from frappe_pilot.ai import sdk_tools

	handler_map = {
		"Get List": sdk_tools.handle_get_list,
		"Get Document": sdk_tools.handle_get_document,
		"Create Document": sdk_tools.handle_create_document,
		"Update Document": sdk_tools.handle_update_document,
		"Delete Document": sdk_tools.handle_delete_document,
	}
	handler = handler_map.get(tool_doc.tool_type)
	if tool_doc.function_path:
		module_name, func_name = tool_doc.function_path.rsplit(".", 1)
		module = importlib.import_module(module_name)
		handler = getattr(module, func_name)
	elif not handler:
		return {"success": False, "error": f"No handler for tool type '{tool_doc.tool_type}'."}

	extra = {}
	if tool_doc.reference_doctype:
		extra["reference_doctype"] = tool_doc.reference_doctype
	return handler(**{**args, **extra})
