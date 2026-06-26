# Copyright (c) 2026, Frappe Pilot and contributors

"""LiteLLM provider with tool calling for Pilot agents."""

import asyncio
import json
import os
from types import SimpleNamespace

import frappe
import litellm
from litellm import APIError, BadRequestError, ContextWindowExceededError, InternalServerError, RateLimitError
from litellm.utils import trim_messages

from frappe_pilot.ai.cost_calculator import calculate_cost
from frappe_pilot.ai.execution_modes import is_mutating_tool, stage_mutating_action
from frappe_pilot.ai.sdk_tools import serialize_tools
from frappe_pilot.utils.llm import get_effective_api_key


class SimpleResult:
	def __init__(self, final_output, usage=None, new_items=None, cost=0.0):
		self.final_output = final_output
		self.usage = usage or {}
		self.new_items = new_items or []
		self.cost = cost


def resolve_model_config(model_link: str) -> tuple[str, str]:
	"""Return (litellm_model_name, provider_name) from Pilot LLM Model link."""
	model_doc = frappe.get_doc("Pilot LLM Model", model_link)
	provider_name = model_doc.llm_provider
	model_name = model_doc.model_name
	return _normalize_model_name(model_name, provider_name), provider_name


def _normalize_model_name(model: str, provider: str) -> str:
	if "/" in model:
		return model

	provider_doc = frappe.db.get_value(
		"LLM Provider",
		provider,
		["provider_code"],
		as_dict=True,
	) or {}
	code = (provider_doc.get("provider_code") or provider or "").lower()
	prefix_map = {
		"openai": "openai",
		"anthropic": "anthropic",
		"google": "gemini",
		"gemini": "gemini",
		"groq": "groq",
		"mistral": "mistral",
		"openrouter": "openrouter",
	}
	prefix = prefix_map.get(code, code)
	return f"{prefix}/{model}"


def _setup_api_key(provider_name: str, api_key: str, completion_kwargs: dict):
	env_var_providers = {
		"openrouter": "OPENROUTER_API_KEY",
		"xai": "XAI_API_KEY",
		"deepseek": "DEEPSEEK_API_KEY",
		"mistral": "MISTRAL_API_KEY",
		"dashscope": "DASHSCOPE_API_KEY",
		"google": "GEMINI_API_KEY",
		"cohere": "COHERE_API_KEY",
		"perplexity": "PERPLEXITY_API_KEY",
	}
	if provider_name in env_var_providers:
		os.environ[env_var_providers[provider_name]] = api_key
	else:
		completion_kwargs["api_key"] = api_key


async def _execute_tool_call(tool, args_json, context=None, tool_call_id=None):
	args_str = args_json if isinstance(args_json, str) else json.dumps(args_json or {})
	invoke_ctx = context
	if isinstance(context, dict):
		from agents.tool_context import ToolContext
		from agents.usage import Usage

		invoke_ctx = ToolContext(
			context,
			usage=Usage(),
			tool_name=tool.name,
			tool_call_id=tool_call_id or "",
			tool_arguments=args_str,
		)
	return await tool.on_invoke_tool(invoke_ctx, args_str)


def _find_tool(agent, tool_name):
	return next((t for t in (getattr(agent, "tools", None) or []) if t.name == tool_name), None)


async def run(agent, enhanced_prompt, provider, model, context=None):
	try:
		litellm.drop_params = True
		agent_doc = None
		if context and context.get("agent_name"):
			try:
				agent_doc = frappe.get_doc("Pilot Agent", context["agent_name"])
			except Exception:
				pass

		normalized_model, provider_name = resolve_model_config(model) if frappe.db.exists("Pilot LLM Model", model) else (
			_normalize_model_name(model, provider),
			provider,
		)
		api_key = get_effective_api_key(provider_name)
		if not api_key:
			frappe.throw(f"API key not configured for provider '{provider_name}'.")

		messages = []
		if agent.instructions:
			messages.append({"role": "system", "content": agent.instructions})
		if context and context.get("conversation_history"):
			messages.extend(context["conversation_history"])
		messages.append({"role": "user", "content": enhanced_prompt})

		tools = serialize_tools(getattr(agent, "tools", None)) or None
		total_usage = {"input_tokens": 0, "output_tokens": 0}
		total_cost = 0.0
		all_new_items = []
		max_rounds = getattr(agent, "max_turns", 10) or 10

		for _round in range(max_rounds):
			temperature = 0.7
			if agent_doc and agent_doc.temperature is not None:
				temperature = agent_doc.temperature

			completion_kwargs = {"model": normalized_model, "temperature": temperature}
			try:
				messages = trim_messages(messages=messages, model=normalized_model)
			except Exception:
				pass
			completion_kwargs["messages"] = messages

			litellm_provider = normalized_model.split("/")[0]
			_setup_api_key(litellm_provider, api_key, completion_kwargs)
			if tools:
				completion_kwargs["tools"] = tools
				completion_kwargs["tool_choice"] = "auto"

			try:
				response = await asyncio.to_thread(litellm.completion, **completion_kwargs)
			except BadRequestError as e:
				if completion_kwargs.get("tools"):
					completion_kwargs.pop("tools", None)
					completion_kwargs.pop("tool_choice", None)
					response = await asyncio.to_thread(litellm.completion, **completion_kwargs)
				else:
					raise e
			except (InternalServerError, APIError) as e:
				return SimpleResult(f"LLM error: {e}", total_usage, all_new_items, cost=total_cost)
			except (RateLimitError, ContextWindowExceededError):
				raise

			usage = response.usage
			round_input = int(getattr(usage, "prompt_tokens", 0) or 0)
			round_output = int(getattr(usage, "completion_tokens", 0) or 0)
			total_usage["input_tokens"] += round_input
			total_usage["output_tokens"] += round_output
			round_cost, _ = calculate_cost(model, round_input, round_output, litellm_response=response)
			total_cost += round_cost

			choice = response.choices[0].message
			assistant_message = {"role": "assistant", "content": choice.content}
			if hasattr(choice, "tool_calls") and choice.tool_calls:
				assistant_message["tool_calls"] = choice.tool_calls
			messages.append(assistant_message)

			if not (hasattr(choice, "tool_calls") and choice.tool_calls):
				return SimpleResult(choice.content or "", total_usage, all_new_items, cost=total_cost)

			tool_results = []
			for tool_call in choice.tool_calls:
				function_call = tool_call.function
				tool_name = function_call.name
				tool_args = function_call.arguments
				all_new_items.append(SimpleNamespace(
					type="tool_call_item",
					raw_item=SimpleNamespace(name=tool_name, arguments=tool_args, id=tool_call.id),
				))

				tool_to_run = _find_tool(agent, tool_name)
				result_content = ""
				if tool_to_run:
					try:
						if agent_doc and (agent_doc.execution_mode or "Direct") == "Safe" and is_mutating_tool(tool_name):
							session_key = stage_mutating_action(tool_name, tool_args, context)
							result_content = json.dumps({
								"staged": True,
								"session_key": session_key,
								"message": "Action staged for confirmation. Call confirm_staged_action to apply.",
							})
						else:
							result_content = await _execute_tool_call(tool_to_run, tool_args, context, tool_call.id)
					except Exception as e:
						result_content = json.dumps({"error": str(e)})
				else:
					result_content = json.dumps({"error": f"Tool '{tool_name}' not found."})

				all_new_items.append(SimpleNamespace(
					type="tool_call_output_item",
					raw_item={"name": tool_name, "output": result_content, "id": tool_call.id},
				))
				tool_results.append({
					"role": "tool",
					"tool_call_id": tool_call.id,
					"name": tool_name,
					"content": str(result_content),
				})
			messages.extend(tool_results)

		return SimpleResult("Agent stopped after max tool rounds.", total_usage, all_new_items, cost=total_cost)
	except Exception as e:
		frappe.log_error(f"LiteLLM Provider Error: {e}", "Pilot LiteLLM")
		return SimpleResult(f"LiteLLM Provider Error: {e}")
