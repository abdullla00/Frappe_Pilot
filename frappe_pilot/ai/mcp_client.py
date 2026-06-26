"""MCP client helpers for Pilot MCP Server documents."""

import json

import frappe
import requests
from frappe import _
from frappe.utils import now_datetime


def _build_headers(server_doc) -> dict:
	headers = {"Content-Type": "application/json"}
	if server_doc.auth_type and server_doc.auth_type != "none":
		name = server_doc.auth_header_name or "Authorization"
		value = server_doc.get_password("auth_header_value") if server_doc.auth_header_value else ""
		if value:
			headers[name] = value
	for row in server_doc.get("custom_headers") or []:
		if row.header_name:
			headers[row.header_name] = row.header_value or ""
	return headers


def sync_mcp_server_tools(server_name: str) -> dict:
	"""Fetch tools from an MCP server and update its child table."""
	server = frappe.get_doc("Pilot MCP Server", server_name)
	payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
	response = requests.post(
		server.server_url,
		headers=_build_headers(server),
		json=payload,
		timeout=server.timeout_seconds or 30,
	)
	response.raise_for_status()
	data = response.json()
	tools = data.get("result", {}).get("tools") or data.get("tools") or []

	server.set("tools", [])
	for tool in tools:
		server.append(
			"tools",
			{
				"tool_name": tool.get("name"),
				"description": tool.get("description"),
				"parameters": json.dumps(tool.get("inputSchema") or tool.get("parameters") or {}),
				"enabled": 1,
			},
		)
	server.last_sync = now_datetime()
	server.save(ignore_permissions=True)
	frappe.db.commit()
	return {"tools": len(tools)}


def execute_mcp_tool(server_name: str, tool_name: str, arguments: dict | None = None) -> dict:
	"""Execute a tool on an MCP server synchronously."""
	server = frappe.get_doc("Pilot MCP Server", server_name)
	payload = {
		"jsonrpc": "2.0",
		"id": 1,
		"method": "tools/call",
		"params": {"name": tool_name, "arguments": arguments or {}},
	}
	response = requests.post(
		server.server_url,
		headers=_build_headers(server),
		json=payload,
		timeout=server.timeout_seconds or 30,
	)
	response.raise_for_status()
	return response.json()


def auto_sync_mcp_server_tools():
	"""Hourly sync for MCP servers with auto sync enabled."""
	if not frappe.db.exists("DocType", "Pilot MCP Server"):
		return
	servers = frappe.get_all(
		"Pilot MCP Server",
		filters={"enabled": 1, "enable_auto_sync": 1},
		pluck="name",
	)
	for name in servers:
		try:
			sync_mcp_server_tools(name)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"MCP Auto Sync: {name}")


@frappe.whitelist()
def sync_tools(server_name: str):
	frappe.only_for("System Manager")
	return sync_mcp_server_tools(server_name)
