# Copyright (c) 2026, Frappe Pilot and contributors

import json

import frappe
from frappe.utils import now


class ConversationManager:
	def __init__(self, agent_name: str, user: str | None = None):
		self.agent_name = agent_name
		self.user = user or frappe.session.user

	def create_new_conversation(self, title: str | None = None):
		title = title or f"Conversation with {self.agent_name}"
		conv = frappe.get_doc({
			"doctype": "Pilot Agent Conversation",
			"title": title,
			"agent": self.agent_name,
			"user": self.user,
			"status": "Active",
		})
		conv.insert(ignore_permissions=True)
		return conv

	def get_or_create_conversation(self, title: str | None = None, conversation_id: str | None = None):
		if conversation_id:
			try:
				conversation = frappe.get_doc("Pilot Agent Conversation", conversation_id)
				if conversation.status == "Active":
					return conversation
			except frappe.DoesNotExistError:
				pass

		existing = frappe.get_all(
			"Pilot Agent Conversation",
			filters={"agent": self.agent_name, "user": self.user, "status": "Active"},
			order_by="creation desc",
			limit=1,
		)
		if existing:
			return frappe.get_doc("Pilot Agent Conversation", existing[0].name)

		return self.create_new_conversation(title)

	def add_message(
		self,
		conversation,
		role: str,
		content,
		message_type: str = "Message",
		tool_call_id: str | None = None,
	):
		if not isinstance(content, str):
			content = json.dumps(content, default=str)

		message = frappe.get_doc({
			"doctype": "Pilot Agent Message",
			"conversation": conversation.name,
			"role": role,
			"content": content,
			"message_type": message_type,
			"tool_call_id": tool_call_id,
		})
		message.insert(ignore_permissions=True)
		frappe.db.set_value("Pilot Agent Conversation", conversation.name, "modified", now())
		return message

	def get_conversation_history(self, conversation_name: str, limit: int = 20) -> list[dict]:
		messages = frappe.get_all(
			"Pilot Agent Message",
			filters={"conversation": conversation_name},
			fields=["role", "content", "message_type", "tool_call_id", "creation"],
			order_by="creation asc",
			limit=limit if limit else 1000,
		)

		result = []
		for msg in messages:
			ctx = self._message_to_context(msg)
			if ctx is None:
				continue
			if isinstance(ctx, list):
				result.extend(ctx)
			else:
				result.append(ctx)
		return result

	def _message_to_context(self, msg: dict):
		role = msg.get("role") or "user"
		if role == "assistant" and msg.get("message_type") == "Tool Call" and msg.get("tool_call_id"):
			tool_call_doc = frappe.db.get_value(
				"Pilot Agent Tool Call",
				msg.get("tool_call_id"),
				["tool_name", "arguments_json"],
				as_dict=True,
			)
			if tool_call_doc:
				args = tool_call_doc.arguments_json
				if isinstance(args, dict):
					args = json.dumps(args)
				return {
					"role": "assistant",
					"content": None,
					"tool_calls": [{
						"id": msg.get("tool_call_id"),
						"type": "function",
						"function": {
							"name": tool_call_doc.tool_name,
							"arguments": args or "{}",
						},
					}],
				}

		if role == "tool":
			tool_name = ""
			if msg.get("tool_call_id"):
				tool_name = frappe.db.get_value("Pilot Agent Tool Call", msg.get("tool_call_id"), "tool_name") or ""
			return {
				"role": "tool",
				"content": msg.get("content") or "",
				"tool_call_id": msg.get("tool_call_id"),
				"name": tool_name,
			}

		return {"role": role, "content": msg.get("content") or ""}

	def close_conversation(self, conversation_name: str):
		frappe.db.set_value("Pilot Agent Conversation", conversation_name, "status", "Closed")
