# Analyze Agent — read-only tool-using loop

import json
import re

import frappe

from frappe_pilot.api.analyze_tools import execute_tool, parse_page_context
from frappe_pilot.api.advisor_prompts import GUIDE_SYSTEM_PROMPT
from frappe_pilot.utils.llm import chat_completion, get_active_provider, has_api_key, _is_rate_limit, groq_rate_limit_message
from frappe_pilot.utils.settings import get_analyze_config, get_enabled_languages



def _format_llm_error(exc):
	exc_str = str(exc)
	if _is_rate_limit(exc):
		return groq_rate_limit_message(exc)
	return f"Something went wrong calling the LLM: {exc_str}"


ANALYZE_TOOLS = [
	{
		"type": "function",
		"function": {
			"name": "get_document",
			"description": "Load full field values and child tables for a document",
			"parameters": {
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"docname": {"type": "string"},
				},
				"required": ["doctype", "docname"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "get_linked_documents",
			"description": "Fetch linked documents (1-hop Link fields) with key field values",
			"parameters": {
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"docname": {"type": "string"},
				},
				"required": ["doctype", "docname"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "get_doctype_meta",
			"description": "Get DocType schema: fields, mandatory fields, list columns, workflow name",
			"parameters": {
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"include_list_view": {"type": "boolean"},
				},
				"required": ["doctype"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "get_workflow_state",
			"description": "Get current workflow state and available transitions for a document",
			"parameters": {
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"docname": {"type": "string"},
				},
				"required": ["doctype", "docname"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "get_timeline",
			"description": "Get recent versions and comments for a document",
			"parameters": {
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"docname": {"type": "string"},
				},
				"required": ["doctype", "docname"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "get_gl_entries",
			"description": "Get GL Entry rows for Sales Invoice, Purchase Invoice, Payment Entry, or Journal Entry",
			"parameters": {
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"docname": {"type": "string"},
				},
				"required": ["doctype", "docname"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "get_list_sample",
			"description": "Fetch sample rows from a list view with filters",
			"parameters": {
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"filters": {"type": "array"},
					"fields": {"type": "array"},
				},
				"required": ["doctype"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "get_list_count",
			"description": "Count documents matching list filters",
			"parameters": {
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"filters": {"type": "array"},
				},
				"required": ["doctype"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "run_report_sample",
			"description": "Run a query report with filters and return sample rows",
			"parameters": {
				"type": "object",
				"properties": {
					"report_name": {"type": "string"},
					"filters": {"type": "object"},
				},
				"required": ["report_name"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "run_document_checks",
			"description": "Run deterministic issue checks on a document",
			"parameters": {
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"docname": {"type": "string"},
				},
				"required": ["doctype", "docname"],
			},
		},
	},
]

BASE_AGENT_RULES = """
You are an analytical ERPNext assistant embedded as a sidebar inside ERPNext.
You answer questions about the SPECIFIC document, list, or report the user is viewing.

## Tool rules
- You have read-only tools to fetch document data, linked records, GL entries, list rows, report results, and automated checks.
- For "why", "issue", "wrong", "unusual", or "diagnose" questions: call run_document_checks and relevant fetch tools BEFORE answering.
- For list questions about which records appear: call get_list_sample and get_list_count.
- For report questions about numbers or totals: call run_report_sample first.
- NEVER invent field values, row counts, or totals not returned by tools or the seed context below.
- If a tool returns empty or permission_denied, state what was checked — do not guess.

## Accuracy rules
- Ground every answer in tool results and the seed context block.
- Quote exact field values from tool output.
- Map synonyms: "rental order reference" → header field "Rental Order".
- READ-ONLY — never claim to modify data.
"""

EXPLAIN_MODE_RULES = """
## Mode: explain
- Lead with the direct answer in the first sentence.
- Under 80 words for single-field questions; under 120 words for summaries.
- At most 3 bullet points when listing multiple items.
"""

NAVIGATION_RULES = """
## Navigation rules
- When mentioning a specific document, report, list, workspace, or setup page the user can open,
  wrap it in a nav token: [[nav:type|target|name|label]]
  Examples:
    [[nav:form|Sales Invoice|ACC-SINV-2026-00001|Open invoice]]
    [[nav:list|Customer||Customer list]]
    [[nav:report|Sales Register||Sales Register report]]
    [[nav:setup|Custom Field|CF-00001|Custom Field]]
- Use nav tokens for referenced document IDs, reports, and navigable pages.
- When the user says "go to", "open", "take me to", "navigate to" (or Kurdish equivalents),
  include a primary nav token for the destination.
- Do NOT invent document names — only tokenize IDs from tools or seed context.
- Keep DocType names and document IDs in English inside tokens.
- Tell users WHERE to click in the ERPNext menu when explaining workflows.
"""

DIAGNOSE_MODE_RULES = """
## Mode: diagnose
- Structure your answer with these sections:
  **Findings** — bullet list of issues found (or "No issues detected")
  **Evidence** — cite tool results and field values
  **Likely cause** — one short paragraph
  **What to verify** — 1-2 concrete checks for the user
- Max 150 words total.
- Always call run_document_checks when analyzing a saved document.
"""


def _get_active_tools():
	cfg = get_analyze_config()
	disabled = cfg.get("disabled_tools") or frozenset()
	return [t for t in ANALYZE_TOOLS if t["function"]["name"] not in disabled]


def _supports_tool_calling():
	return get_active_provider() in ("Groq", "OpenAI")


def _build_system_prompt(seed_context, mode="explain", reply_locale=None):
	from frappe_pilot.utils.i18n import get_llm_language_instruction
	from frappe_pilot.utils.navigation import get_reply_locale_instruction

	cfg = get_analyze_config()
	langs = get_enabled_languages()
	parts = [BASE_AGENT_RULES, GUIDE_SYSTEM_PROMPT.strip(), NAVIGATION_RULES.strip()]
	if mode == "diagnose":
		parts.append(DIAGNOSE_MODE_RULES)
	else:
		parts.append(EXPLAIN_MODE_RULES)
	if cfg.get("custom_analyze_prompt"):
		parts.append("\n## Additional instructions\n" + cfg["custom_analyze_prompt"])
	parts.append("\n## Seed context (page snapshot)\n" + seed_context)

	locale_note = get_reply_locale_instruction(reply_locale, langs)
	if locale_note:
		parts.append(locale_note)
	elif reply_locale in langs and reply_locale != "en":
		lang_note = get_llm_language_instruction(langs)
		if lang_note:
			parts.append(lang_note)
	return "\n".join(parts)


def _call_llm(messages, *, use_tools=True, mode="explain"):
	cfg = get_analyze_config()
	tools = _get_active_tools() if use_tools and _supports_tool_calling() else None
	temp = cfg["diagnose_temperature"] if mode == "diagnose" else cfg["temperature"]
	max_tokens = cfg["max_tokens"] if use_tools else cfg["max_tokens_final"]

	return chat_completion(
		messages=messages,
		model=cfg["model"],
		max_tokens=max_tokens,
		temperature=temp,
		tools=tools,
		tool_choice="auto" if tools else None,
	)


def run_agent(
	message,
	*,
	seed_context="",
	history=None,
	mode="explain",
	reply_locale=None,
	page_context_raw="",
	doctype="",
	docname="",
	list_doctype="",
	route="",
):
	cfg = get_analyze_config()
	page_context = parse_page_context(page_context_raw)
	history = history or []
	system_prompt = _build_system_prompt(seed_context, mode=mode, reply_locale=reply_locale)

	messages = [{"role": "system", "content": system_prompt}] + list(history)
	messages.append({"role": "user", "content": message})

	if not has_api_key():
		return {
			"reply": None,
			"needs_api_setup": True,
			"evidence": {"tools_used": [], "checks_run": 0},
		}

	tools_used = []
	checks_run = 0
	max_passes = cfg["max_passes"]

	for pass_num in range(max_passes):
		use_tools = pass_num < max_passes - 1 and _supports_tool_calling()
		try:
			response, _, _ = _call_llm(messages, use_tools=use_tools, mode=mode)
		except Exception as exc:
			exc_str = str(exc)
			if "tool_use_failed" in exc_str and use_tools:
				try:
					response, _, _ = _call_llm(messages, use_tools=False, mode=mode)
				except Exception as fallback_exc:
					return {
						"reply": _format_llm_error(fallback_exc),
						"evidence": {"tools_used": tools_used, "checks_run": checks_run},
					}
			else:
				frappe.log_error(frappe.get_traceback(), "Analyze Agent Error")
				return {
					"reply": _format_llm_error(exc),
					"evidence": {"tools_used": tools_used, "checks_run": checks_run},
				}

		msg = response.choices[0].message

		if not getattr(msg, "tool_calls", None):
			reply = msg.content or "I could not generate a response. Please try rephrasing."
			return {
				"reply": reply,
				"evidence": {"tools_used": tools_used, "checks_run": checks_run},
			}

		tool_call = msg.tool_calls[0]
		tool_name = tool_call.function.name
		try:
			tool_args = json.loads(tool_call.function.arguments or "{}")
		except json.JSONDecodeError:
			tool_args = {}

		if cfg.get("debug_log_tool_calls"):
			frappe.log_error(
				json.dumps({"tool": tool_name, "args": tool_args}, default=str),
				"Pilot Analyze Tool Call",
			)

		result = execute_tool(
			tool_name,
			tool_args,
			page_context=page_context,
			default_doctype=doctype,
			default_docname=docname,
		)

		tools_used.append(tool_name)
		if tool_name == "run_document_checks":
			checks_run = result.get("issue_count", 0) if isinstance(result, dict) else 0

		messages.append({
			"role": "assistant",
			"content": None,
			"tool_calls": [{
				"id": tool_call.id,
				"type": "function",
				"function": {
					"name": tool_name,
					"arguments": tool_call.function.arguments,
				},
			}],
		})
		messages.append({
			"role": "tool",
			"tool_call_id": tool_call.id,
			"content": json.dumps(result, default=str),
		})

	return {
		"reply": "I reached the maximum number of data lookups. Please ask a more specific question.",
		"evidence": {"tools_used": tools_used, "checks_run": checks_run},
	}
