# Copyright (c) 2026, Frappe Pilot and contributors

"""openai-agents FunctionTool wrappers for Pilot CRUD tools."""

import asyncio
import importlib
import inspect
import json
import re
from typing import Any, Callable

import frappe
from agents import FunctionTool

from frappe_pilot.ai.tool_registry import PermissionAwareToolRegistry

MUTATING_TOOL_TYPES = PermissionAwareToolRegistry.MUTATING_TOOL_TYPES

CRUD_TOOL_TYPES = {
	"Get List": "frappe_pilot.ai.sdk_tools.handle_get_list",
	"Get Document": "frappe_pilot.ai.sdk_tools.handle_get_document",
	"Create Document": "frappe_pilot.ai.sdk_tools.handle_create_document",
	"Update Document": "frappe_pilot.ai.sdk_tools.handle_update_document",
	"Delete Document": "frappe_pilot.ai.sdk_tools.handle_delete_document",
}

DEFAULT_PARAMETERS = {
	"Get List": {
		"type": "object",
		"properties": {
			"filters": {"type": "object"},
			"fields": {"type": "array", "items": {"type": "string"}},
			"limit": {"type": "integer"},
		},
	},
	"Get Document": {
		"type": "object",
		"properties": {"document_id": {"type": "string"}},
		"required": ["document_id"],
	},
	"Create Document": {
		"type": "object",
		"properties": {"doc": {"type": "object"}},
		"required": ["doc"],
	},
	"Update Document": {
		"type": "object",
		"properties": {
			"document_id": {"type": "string"},
			"data": {"type": "object"},
		},
		"required": ["document_id", "data"],
	},
	"Delete Document": {
		"type": "object",
		"properties": {"document_id": {"type": "string"}},
		"required": ["document_id"],
	},
}


def serialize_tools(tools: list) -> list[dict[str, Any]]:
	serialized = []
	for tool in tools or []:
		serialized.append({
			"type": "function",
			"function": {
				"name": getattr(tool, "name", ""),
				"description": getattr(tool, "description", "") or "",
				"parameters": getattr(tool, "params_json_schema", {}) or {},
			},
		})
	return serialized


def create_agent_tools(agent) -> list[FunctionTool]:
	tools = []
	for function_doc in PermissionAwareToolRegistry.get_allowed_tools(agent, frappe.session.user):
		try:
			function_path = function_doc.function_path
			if not function_path and function_doc.tool_type in CRUD_TOOL_TYPES:
				function_path = CRUD_TOOL_TYPES[function_doc.tool_type]

			if not function_path:
				continue

			params = DEFAULT_PARAMETERS.get(function_doc.tool_type, {"type": "object", "properties": {}})
			if function_doc.parameters_json:
				if isinstance(function_doc.parameters_json, dict):
					params = function_doc.parameters_json
				elif isinstance(function_doc.parameters_json, str):
					params = json.loads(function_doc.parameters_json)

			extra_args = {}
			if function_doc.reference_doctype:
				extra_args["reference_doctype"] = function_doc.reference_doctype

			tool = create_function_tool(
				name=function_doc.tool_name,
				description=function_doc.description,
				tool_name=function_path,
				parameters=params,
				extra_args=extra_args,
				tool_type=function_doc.tool_type,
			)
			if tool:
				tools.append(tool)
		except Exception as e:
			frappe.log_error(f"Error loading tool {function_doc.name}: {e}", "Pilot SDK Tools")
	return tools


def create_function_tool(
	name: str,
	description: str,
	tool_name: str,
	parameters: dict[str, Any],
	extra_args: dict[str, Any] | None = None,
	tool_type: str | None = None,
) -> FunctionTool | None:
	function = get_function_from_name(tool_name)
	if not function:
		return None

	_extra_args = extra_args or {}

	async def on_invoke_tool(ctx=None, args_json: str = None) -> str:
		try:
			if args_json is None and isinstance(ctx, str):
				args_json = ctx
				ctx = None
			args_dict = json.loads(args_json or "{}")
			if isinstance(ctx, dict):
				args_dict.update({k: v for k, v in ctx.items() if k in ("conversation_id", "agent_run_id", "agent_name")})
			elif hasattr(ctx, "context") and isinstance(ctx.context, dict):
				args_dict.update(ctx.context)
			if _extra_args:
				args_dict.update(_extra_args)

			sig = inspect.signature(function)
			accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
			if accepts_kwargs:
				result = function(**args_dict)
			else:
				result = function(**{k: v for k, v in args_dict.items() if k in sig.parameters})

			if asyncio.iscoroutine(result):
				result = await result
			if hasattr(result, "as_dict"):
				result = result.as_dict()
			return json.dumps(result, default=str) if isinstance(result, (dict, list)) else str(result)
		except Exception as e:
			return json.dumps({"error": str(e)})

	safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name or "")[:128]
	return FunctionTool(
		name=safe_name,
		description=description,
		params_json_schema=parameters,
		on_invoke_tool=on_invoke_tool,
		strict_json_schema=False,
	)


def get_function_from_name(tool_name: str) -> Callable | None:
	try:
		module_name, func_name = tool_name.rsplit(".", 1)
		module = importlib.import_module(module_name)
		function = getattr(module, func_name, None)
		return function if callable(function) else None
	except Exception:
		return None


def handle_get_list(filters=None, fields=None, limit=20, order_by="modified desc", reference_doctype=None, **kwargs):
	if not reference_doctype:
		return {"success": False, "error": "No reference doctype provided."}
	if not frappe.has_permission(reference_doctype, "read"):
		return {"success": False, "error": "Read permission denied.", "permission_denied": True}
	if not fields:
		fields = ["name", "modified"]
	result = frappe.get_list(
		reference_doctype,
		filters=filters,
		fields=fields,
		limit_page_length=limit or 20,
		order_by=order_by,
	)
	return {"success": True, "result": result}


def handle_get_document(document_id=None, reference_doctype=None, **filters):
	if not reference_doctype:
		return {"success": False, "error": "No reference doctype provided."}
	if not document_id:
		return {"success": False, "error": "document_id is required."}
	if not frappe.db.exists(reference_doctype, document_id):
		return {"success": False, "error": "Document not found."}
	doc = frappe.get_doc(reference_doctype, document_id)
	doc.check_permission("read")
	doc.apply_fieldlevel_read_permissions()
	return {"success": True, "result": doc.as_dict()}


def handle_create_document(reference_doctype=None, doc=None, ignore_permissions=False, **kwargs):
	if not reference_doctype:
		return {"success": False, "error": "No reference doctype provided."}
	if not ignore_permissions and not frappe.has_permission(reference_doctype, "create"):
		return {"success": False, "error": "Create permission denied.", "permission_denied": True}
	payload = doc if isinstance(doc, dict) else kwargs
	new_doc = frappe.get_doc({"doctype": reference_doctype, **payload})
	new_doc.insert(ignore_permissions=ignore_permissions)
	return {"success": True, "result": new_doc.as_dict()}


def handle_update_document(document_id=None, data=None, reference_doctype=None, ignore_permissions=False, **kwargs):
	if not reference_doctype or not document_id:
		return {"success": False, "error": "reference_doctype and document_id are required."}
	if not ignore_permissions and not frappe.has_permission(reference_doctype, "write", doc=document_id):
		return {"success": False, "error": "Write permission denied.", "permission_denied": True}
	data = data or {}
	doc = frappe.get_doc(reference_doctype, document_id)
	for field, value in data.items():
		doc.set(field, value)
	doc.save(ignore_permissions=ignore_permissions)
	frappe.db.commit()
	return {"success": True, "result": doc.as_dict()}


def handle_delete_document(document_id=None, reference_doctype=None, ignore_permissions=False, **kwargs):
	if not reference_doctype or not document_id:
		return {"success": False, "error": "reference_doctype and document_id are required."}
	if not ignore_permissions and not frappe.has_permission(reference_doctype, "delete", doc=document_id):
		return {"success": False, "error": "Delete permission denied.", "permission_denied": True}
	frappe.delete_doc(reference_doctype, document_id, ignore_permissions=ignore_permissions)
	return {"success": True, "message": f"{reference_doctype} {document_id} deleted."}
