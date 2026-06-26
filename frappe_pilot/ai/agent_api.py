# Copyright (c) 2026, Frappe Pilot and contributors

"""Whitelisted API endpoints for Pilot agents."""

import frappe
from frappe import _

from frappe_pilot.ai.agent_integration import run_agent_sync
from frappe_pilot.ai.execution_modes import confirm_staged_action as apply_staged_action
from frappe_pilot.ai.permissions_api import CAPABILITIES, get_user_capabilities, has_capability


@frappe.whitelist()
def run_agent(agent_name: str, message: str, conversation_id: str | None = None):
	if not has_capability(frappe.session.user, "agent.use"):
		frappe.throw(_("You don't have permission to run agents."), frappe.PermissionError)
	return run_agent_sync(agent_name=agent_name, message=message, conversation_id=conversation_id)


@frappe.whitelist()
def list_agents():
	if not has_capability(frappe.session.user, "agent.use"):
		frappe.throw(_("You don't have permission to list agents."), frappe.PermissionError)
	return frappe.get_all(
		"Pilot Agent",
		filters={"disabled": 0},
		fields=["name", "agent_name", "description", "provider", "model", "execution_mode"],
		order_by="agent_name asc",
	)


@frappe.whitelist()
def get_conversation(conversation_id: str):
	if not has_capability(frappe.session.user, "chat.view_own"):
		frappe.throw(_("You don't have permission to view conversations."), frappe.PermissionError)
	if not frappe.db.exists("Pilot Agent Conversation", conversation_id):
		frappe.throw(_("Conversation not found."))

	conversation = frappe.get_doc("Pilot Agent Conversation", conversation_id)
	if conversation.user != frappe.session.user and not has_capability(frappe.session.user, "chat.view_all"):
		frappe.throw(_("You don't have permission to view this conversation."), frappe.PermissionError)

	messages = frappe.get_all(
		"Pilot Agent Message",
		filters={"conversation": conversation_id},
		fields=["name", "role", "content", "message_type", "tool_call_id", "creation"],
		order_by="creation asc",
	)
	return {"conversation": conversation.as_dict(), "messages": messages}


@frappe.whitelist()
def list_runs(agent_name: str | None = None, limit: int = 20):
	if not has_capability(frappe.session.user, "agent.use"):
		frappe.throw(_("You don't have permission to view runs."), frappe.PermissionError)

	filters = {}
	if agent_name:
		filters["agent"] = agent_name
	if not has_capability(frappe.session.user, "chat.view_all"):
		conversations = frappe.get_all(
			"Pilot Agent Conversation",
			filters={"user": frappe.session.user},
			pluck="name",
		)
		if not conversations:
			return []
		filters["conversation"] = ["in", conversations]

	return frappe.get_all(
		"Pilot Agent Run",
		filters=filters,
		fields=[
			"name", "agent", "conversation", "status", "prompt_tokens",
			"completion_tokens", "total_cost", "latency_ms", "creation",
		],
		order_by="creation desc",
		limit=int(limit or 20),
	)


@frappe.whitelist()
def confirm_staged_action(session_key: str):
	if not has_capability(frappe.session.user, "agent.use"):
		frappe.throw(_("You don't have permission to confirm actions."), frappe.PermissionError)
	return apply_staged_action(session_key)


@frappe.whitelist()
def list_capabilities():
	return {
		"catalogue": CAPABILITIES,
		"user_capabilities": get_user_capabilities(frappe.session.user),
	}


@frappe.whitelist()
def get_me():
	return {
		"user": frappe.session.user,
		"full_name": frappe.get_value("User", frappe.session.user, "full_name"),
		"capabilities": get_user_capabilities(frappe.session.user),
	}


@frappe.whitelist()
def get_agents():
	return list_agents()


@frappe.whitelist()
def get_agent(name: str):
	if not has_capability(frappe.session.user, "agent.use"):
		frappe.throw(_("You don't have permission to view agents."), frappe.PermissionError)
	if not frappe.db.exists("Pilot Agent", name):
		frappe.throw(_("Agent not found."))
	return frappe.get_doc("Pilot Agent", name).as_dict()


@frappe.whitelist()
def send_message(agent_name: str, message: str, conversation_id: str | None = None):
	return run_agent(agent_name=agent_name, message=message, conversation_id=conversation_id)


@frappe.whitelist()
def get_conversation_messages(conversation_id: str):
	data = get_conversation(conversation_id)
	return data.get("messages") or []


@frappe.whitelist()
def get_executions(limit: int = 50):
	return list_runs(limit=limit)


@frappe.whitelist()
def get_roles():
	if not has_capability(frappe.session.user, "roles.manage"):
		frappe.throw(_("You don't have permission to view roles."), frappe.PermissionError)
	return frappe.get_all(
		"Pilot Role",
		fields=["name", "role_name", "description"],
		order_by="role_name asc",
	)
