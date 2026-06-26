# Copyright (c) 2026, Frappe Pilot and contributors

"""Pilot agent run loop with tool calls and logging."""

import asyncio
import concurrent.futures
import json
import time
import frappe
from agents import Agent, ModelSettings
from frappe import _
from frappe.utils import now_datetime

from frappe_pilot.ai.conversation_manager import ConversationManager
from frappe_pilot.ai.cost_calculator import calculate_cost
from frappe_pilot.ai.run import RunProvider
from frappe_pilot.ai.sdk_tools import create_agent_tools


class AgentManager:
	def __init__(self, agent_name: str):
		self.agent_doc = frappe.get_doc("Pilot Agent", agent_name)
		self.tools = create_agent_tools(self.agent_doc)

	def create_agent(self) -> Agent:
		instructions = self.agent_doc.instructions or ""
		model_settings = ModelSettings(temperature=self.agent_doc.temperature or 0.2)
		agent = Agent(
			name=self.agent_doc.agent_name,
			instructions=instructions,
			model=self.agent_doc.model,
			tools=self.tools or [],
			model_settings=model_settings,
		)
		agent.max_turns = 10
		return agent


def _is_user_allowed(agent_doc, user: str) -> bool:
	if user == "Guest":
		return False
	allowed_roles = [r.role for r in (agent_doc.get("allowed_roles") or []) if r.role]
	if not allowed_roles:
		return True
	user_roles = frappe.get_roles(user)
	return any(role in user_roles for role in allowed_roles)


def _run_async_safely(coro):
	try:
		current_loop = asyncio.get_running_loop()
	except RuntimeError:
		current_loop = None

	if current_loop and current_loop.is_running():
		site = frappe.local.site
		user = getattr(frappe.session, "user", None)

		def _thread_worker():
			frappe.init(site)
			frappe.connect()
			if user:
				frappe.set_user(user)
			try:
				new_loop = asyncio.new_event_loop()
				asyncio.set_event_loop(new_loop)
				try:
					return new_loop.run_until_complete(coro)
				finally:
					new_loop.close()
			finally:
				frappe.destroy()

		with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
			return executor.submit(_thread_worker).result()

	new_loop = asyncio.new_event_loop()
	asyncio.set_event_loop(new_loop)
	try:
		return new_loop.run_until_complete(coro)
	finally:
		new_loop.close()


def log_tool_call(run_name, raw_call, tool_result=None, is_output=False):
	if is_output:
		call_id = raw_call.get("id")
		tool_name = raw_call.get("name")
		tool_call_name = frappe.db.get_value(
			"Pilot Agent Tool Call",
			{"run": run_name, "tool_name": tool_name},
			"name",
			order_by="creation desc",
		)
		if not tool_call_name:
			return None
		doc = frappe.get_doc("Pilot Agent Tool Call", tool_call_name)
		doc.status = "Completed"
		if tool_result is not None:
			if isinstance(tool_result, str):
				try:
					doc.result_json = json.loads(tool_result)
				except Exception:
					doc.result_json = {"output": tool_result}
			else:
				doc.result_json = tool_result
		doc.save(ignore_permissions=True)
		return tool_call_name

	tool_name = getattr(raw_call, "name", None) or raw_call.get("name")
	args = getattr(raw_call, "arguments", None) or raw_call.get("arguments")
	if isinstance(args, str):
		try:
			args_json = json.loads(args)
		except Exception:
			args_json = {"raw": args}
	else:
		args_json = args or {}

	doc = frappe.get_doc({
		"doctype": "Pilot Agent Tool Call",
		"run": run_name,
		"tool_name": tool_name,
		"status": "Started",
		"arguments_json": args_json,
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def run_agent_sync(agent_name: str, message: str, conversation_id: str | None = None) -> dict:
	if not agent_name:
		frappe.throw(_("Agent name is required"))

	agent_doc = frappe.get_doc("Pilot Agent", agent_name)
	if agent_doc.disabled:
		frappe.throw(_("This agent is disabled."))
	if not _is_user_allowed(agent_doc, frappe.session.user):
		frappe.throw(_("You are not authorized to use this agent."), frappe.PermissionError)

	start = time.time()
	conv_manager = ConversationManager(agent_name=agent_name)
	conversation = conv_manager.get_or_create_conversation(
		title=f"Chat with {agent_name}",
		conversation_id=conversation_id,
	)

	run_doc = frappe.get_doc({
		"doctype": "Pilot Agent Run",
		"agent": agent_name,
		"conversation": conversation.name,
		"status": "Started",
	})
	run_doc.insert(ignore_permissions=True)

	if message:
		conv_manager.add_message(conversation, "user", message)

	history = conv_manager.get_conversation_history(conversation.name, limit=20)
	manager = AgentManager(agent_name)
	agent = manager.create_agent()

	context = {
		"agent_name": agent_name,
		"conversation_id": conversation.name,
		"agent_run_id": run_doc.name,
		"conversation_history": history,
	}
	enhanced_prompt = message or ""
	run_coro = RunProvider.run(agent, enhanced_prompt, agent_doc.provider, agent_doc.model, context)
	result = _run_async_safely(run_coro)

	new_items = getattr(result, "new_items", []) or []
	for item in new_items:
		if item.type == "tool_call_item":
			raw = item.raw_item
			tool_call_id = log_tool_call(run_doc.name, raw, is_output=False)
			conv_manager.add_message(
				conversation,
				"assistant",
				f"Calling tool: {getattr(raw, 'name', '')}",
				message_type="Tool Call",
				tool_call_id=tool_call_id,
			)
		elif item.type == "tool_call_output_item":
			raw = item.raw_item
			tool_call_id = log_tool_call(run_doc.name, raw, tool_result=raw.get("output"), is_output=True)
			conv_manager.add_message(
				conversation,
				"tool",
				raw.get("output"),
				message_type="Tool Result",
				tool_call_id=tool_call_id,
			)

	final_output = getattr(result, "final_output", str(result))
	usage = getattr(result, "usage", {}) or {}
	input_tokens = int(usage.get("input_tokens", 0) or 0)
	output_tokens = int(usage.get("output_tokens", 0) or 0)
	cost = getattr(result, "cost", 0) or 0
	if not cost:
		cost, _ = calculate_cost(agent_doc.model, input_tokens, output_tokens)

	latency_ms = int((time.time() - start) * 1000)
	conv_manager.add_message(conversation, "assistant", final_output)
	run_doc.db_set({
		"status": "Success",
		"prompt_tokens": input_tokens,
		"completion_tokens": output_tokens,
		"total_cost": cost,
		"latency_ms": latency_ms,
	})
	frappe.db.commit()

	return {
		"success": True,
		"response": final_output,
		"conversation_id": conversation.name,
		"run_id": run_doc.name,
		"usage": {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost": cost},
	}
