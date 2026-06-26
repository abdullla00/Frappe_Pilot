# Insight Agent — business analytics tool loop

from __future__ import annotations

import hashlib
import json

import frappe

from frappe_pilot.api.insight_tools import _truncate_result, execute_insight_tool
from frappe_pilot.utils.llm import (
	ProviderExhaustedError,
	chat_completion,
	has_api_key,
	has_tool_calling_provider,
	_is_rate_limit,
	llm_rate_limit_message,
)
from frappe_pilot.utils.micro_report import (
	build_micro_report,
	compact_micro_report_digest,
	compose_brief_insight_reply,
	micro_report_json,
)
from frappe_pilot.utils.settings import get_insight_config, get_enabled_languages

EVIDENCE_SESSION_KEY = "last_insight_evidence"
# Session-only prior-answer metadata for follow-up turns (not the localStorage context bar).


def _format_llm_error(exc):
	if isinstance(exc, ProviderExhaustedError):
		return str(exc)
	if _is_rate_limit(exc):
		return llm_rate_limit_message(None, exc)
	return f"Something went wrong calling the LLM: {exc}"


INSIGHT_TOOLS = [
	{
		"type": "function",
		"function": {
			"name": "list_reports",
			"description": "List available ERPNext reports by module or search keyword",
			"parameters": {
				"type": "object",
				"properties": {
					"module": {"type": "string"},
					"search": {"type": "string"},
				},
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "run_report",
			"description": "Run an ERPNext script report with filters and return sample rows",
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
			"name": "run_multi_report",
			"description": "Run up to 3 reports in one batch (e.g. P&L and AR summary together)",
			"parameters": {
				"type": "object",
				"properties": {
					"reports": {
						"type": "array",
						"items": {
							"type": "object",
							"properties": {
								"report_name": {"type": "string"},
								"filters": {"type": "object"},
								"title": {"type": "string"},
							},
						},
					},
				},
				"required": ["reports"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "get_list_count",
			"description": "Count documents matching list filters for a readable DocType",
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
			"name": "get_list_sample",
			"description": "Fetch sample rows from a readable DocType with filters and fields",
			"parameters": {
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"filters": {"type": "array"},
					"fields": {"type": "array", "items": {"type": "string"}},
					"limit": {"type": "integer"},
					"title": {
						"type": "string",
						"description": "Short section title for the UI table (e.g. 'Unpaid Sales Invoices · Job Order linked')",
					},
				},
				"required": ["doctype"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "get_doctype_meta",
			"description": "Get DocType schema (fields, labels) before querying unfamiliar DocTypes",
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
			"name": "get_related_doctypes",
			"description": "Discover Link/Table relationships for cross-doctype questions",
			"parameters": {
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"target_doctype": {"type": "string"},
					"depth": {"type": "integer"},
				},
				"required": ["doctype"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "get_child_table_sample",
			"description": "Fetch child table line items for parent documents",
			"parameters": {
				"type": "object",
				"properties": {
					"parent_doctype": {"type": "string"},
					"parent_filters": {"type": "array"},
					"child_table": {"type": "string"},
					"fields": {"type": "array", "items": {"type": "string"}},
					"limit": {"type": "integer"},
				},
				"required": ["parent_doctype", "child_table"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "get_budget_summary",
			"description": "Run Budget Variance Report for company/fiscal year",
			"parameters": {
				"type": "object",
				"properties": {
					"company": {"type": "string"},
					"fiscal_year": {"type": "string"},
					"cost_center": {"type": "string"},
				},
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "get_financial_snapshot",
			"description": "Run P&L and Balance Sheet for a quick CFO summary",
			"parameters": {
				"type": "object",
				"properties": {
					"company": {"type": "string"},
					"from_date": {"type": "string"},
					"to_date": {"type": "string"},
				},
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "compare_periods",
			"description": "Run the same report for current and previous period filters",
			"parameters": {
				"type": "object",
				"properties": {
					"report_name": {"type": "string"},
					"current_filters": {"type": "object"},
					"previous_filters": {"type": "object"},
				},
				"required": ["report_name"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "get_list_aggregate",
			"description": "Grouped aggregate query on a readable DocType (e.g. top customers)",
			"parameters": {
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"filters": {"type": "array"},
					"group_by": {"type": "string"},
					"sum_field": {"type": "string"},
					"limit": {"type": "integer"},
				},
				"required": ["doctype"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "run_readonly_query",
			"description": "Last resort: read-only SELECT for joins. Prefer get_list_sample first.",
			"parameters": {
				"type": "object",
				"properties": {
					"query": {"type": "string"},
					"title": {"type": "string"},
					"columns": {"type": "array", "items": {"type": "string"}},
				},
				"required": ["query"],
			},
		},
	},
]

INSIGHT_SYSTEM_PROMPT = """
You are a business intelligence assistant embedded in the ERPNext desk sidebar (Insight tab).
You answer cross-module questions about company performance using read-only tools.

## Rules
- ALWAYS call tools before stating numbers. Never invent figures.
- Use list_reports to discover report names when unsure.
- Use run_report for financial/operational reports; get_list_count for document counts.
- Use get_list_sample when the user asks for a list of records with specific fields.
- For get_list_sample: request ONLY fields the user asked for (+ name for identification).
- Map business terms: valid till / validity → due_date; client / party → customer.
- Do not add list-view, audit, or extra columns unless explicitly requested.
- READ-ONLY — never claim to modify data.

## Multi-part questions
- Decompose into independent sub-queries (one report OR one doctype list each).
- Prefer run_multi_report when comparing multiple financial reports in one answer.
- Use get_doctype_meta before get_list_sample on unfamiliar DocTypes.
- Use get_related_doctypes to discover Link/Table joins before cross-doctype questions.
- Use get_child_table_sample for line items before SQL.
- Use run_readonly_query ONLY when a join/filter cannot be done with get_list_sample filters.
- Never fabricate cross-doctype numbers — fetch each source with tools.

## Reply style (critical)
- The UI renders a KPI card and data table below your message — do NOT repeat row-level data.
- After tools complete, write at most 2 short sentences. Never describe your tool plan.
- NEVER write phrases like "I will fetch", "Let me use get_list_sample", or repeat tool names in the reply.
- Keep answers to count + one highlight; point to the table card for details.
- Never list invoice numbers, customer names row-by-row, or bullet lists of records.
- When a micro-report JSON is provided, narrate ONLY headline facts — details belong in the table.

## List queries (Job Order / Rental Order / similar)
- Use one get_list_sample per distinct link type with a distinct `title` and only the link field needed.
- Example: unpaid + job_order set → title "Unpaid Sales Invoices · Job Order linked", fields [name, job_order, outstanding_amount].
- Do NOT call get_list_count when get_list_sample already returns rows (row_count is included).
- Skip get_related_doctypes when the user already named the link fields (job_order, rental_order).
"""

INSIGHT_NARRATE_APPEND = """
## Narration format (critical)
- A structured card with KPIs and a data table is shown below your reply.
- Write at most 3 short sentences. State the total count and one useful highlight only.
- Do NOT list individual records, invoice IDs, or line-by-line details.
- End with a phrase like "See the table below for the full list."
"""


def _get_active_tools():
	cfg = get_insight_config()
	disabled = cfg.get("disabled_tools") or frozenset()
	default_disabled = {"run_readonly_query"}
	effective_disabled = disabled | default_disabled
	if not cfg.get("enable_readonly_sql"):
		effective_disabled = effective_disabled | {"run_readonly_query"}
	return [t for t in INSIGHT_TOOLS if t["function"]["name"] not in effective_disabled]


def _supports_tool_calling():
	return has_tool_calling_provider()


def _followup_context_note(cfg) -> str:
	mode = (cfg.get("followup_context") or "compact").strip().lower()
	if mode == "off":
		return ""
	evidence = frappe.session.get(EVIDENCE_SESSION_KEY) or {}
	if not evidence:
		return ""
	parts = ["Previous Insight answer context:"]
	for tbl in evidence.get("tables") or []:
		parts.append(
			f"- {tbl.get('title') or tbl.get('doctype')}: "
			f"{tbl.get('row_count', '?')} rows"
			f"{(' (' + tbl.get('doctype') + ')') if tbl.get('doctype') else ''}"
		)
	for entry in evidence.get("filters_applied") or []:
		if isinstance(entry, dict):
			parts.append(f"- Prior tool {entry.get('tool')}: filters {entry.get('filters')}")
	return "\n".join(parts)


def _build_system_prompt(reply_locale=None, extra_context: str = ""):
	from frappe_pilot.utils.i18n import get_llm_language_instruction
	from frappe_pilot.utils.navigation import get_reply_locale_instruction

	cfg = get_insight_config()
	parts = [INSIGHT_SYSTEM_PROMPT.strip()]

	followup = _followup_context_note(cfg)
	if followup:
		parts.append("\n## Prior turn\n" + followup)

	if extra_context:
		parts.append("\n## Context\n" + extra_context)

	langs = get_enabled_languages()
	locale_note = get_reply_locale_instruction(reply_locale, langs)
	if locale_note:
		parts.append(locale_note)
	elif reply_locale in langs and reply_locale != "en":
		lang_note = get_llm_language_instruction(langs)
		if lang_note:
			parts.append(lang_note)
	return "\n".join(parts)


def _extract_usage(response):
	prompt_tokens = completion_tokens = None
	try:
		usage = getattr(response, "usage", None)
		if usage:
			prompt_tokens = getattr(usage, "prompt_tokens", None)
			completion_tokens = getattr(usage, "completion_tokens", None)
	except Exception:
		pass
	return prompt_tokens, completion_tokens


def _call_llm(messages, *, use_tools=True, cfg=None):
	cfg = cfg or get_insight_config()
	tools = _get_active_tools() if use_tools and _supports_tool_calling() else None
	max_tokens = cfg["max_tokens"] if use_tools else cfg["max_tokens_final"]
	response, provider, label = chat_completion(
		messages=messages,
		model=cfg["model"],
		max_tokens=max_tokens,
		temperature=cfg["temperature"],
		tools=tools,
		tool_choice="auto" if tools else None,
	)
	return response, provider, label


def _micro_report_has_table(micro_report: dict | None) -> bool:
	if not micro_report:
		return False
	for table in micro_report.get("tables") or []:
		if table.get("rows"):
			return True
	return False


def _should_brief_narrate(micro_report: dict | None) -> bool:
	if not micro_report or micro_report.get("error"):
		return False
	if _micro_report_has_table(micro_report):
		return True
	return len(micro_report.get("kpis") or []) > 0


def _looks_like_tool_planning(text: str) -> bool:
	if not text or len(text) < 120:
		return False
	lower = text.lower()
	markers = (
		"get_list_sample",
		"i will fetch",
		"let me fetch",
		"let me use",
		"let me proceed",
		"let me start",
		"let me run",
	)
	return sum(1 for marker in markers if marker in lower) >= 2


def _resolve_insight_reply(
	micro_report: dict | None,
	raw_reply: str,
	*,
	message: str = "",
	reply_locale=None,
	history=None,
) -> tuple[str | None, int | None, int | None, bool]:
	"""Prefer deterministic brief replies when the card already shows table data."""
	history = history or []
	prompt_tokens = completion_tokens = None

	if _micro_report_has_table(micro_report):
		brief = compose_brief_insight_reply(micro_report)
		if brief:
			return brief, prompt_tokens, completion_tokens, False
		return "See the table below for details.", prompt_tokens, completion_tokens, False

	if not micro_report or not _should_brief_narrate(micro_report):
		if _looks_like_tool_planning(raw_reply):
			brief = compose_brief_insight_reply(micro_report)
			if brief:
				return brief, prompt_tokens, completion_tokens, False
			return "Data retrieved — see the card below.", prompt_tokens, completion_tokens, False
		return raw_reply, prompt_tokens, completion_tokens, False

	narrate = narrate_micro_report(
		micro_report,
		message,
		reply_locale=reply_locale,
		history=history,
	)
	if narrate.get("needs_api_setup"):
		return None, None, None, True
	if narrate.get("reply") and not _looks_like_tool_planning(narrate["reply"]):
		return (
			narrate["reply"],
			narrate.get("prompt_tokens"),
			narrate.get("completion_tokens"),
			False,
		)

	brief = compose_brief_insight_reply(micro_report)
	if brief:
		return brief, prompt_tokens, completion_tokens, False
	return raw_reply, prompt_tokens, completion_tokens, False


def narrate_micro_report(
	micro_report: dict,
	message: str = "",
	*,
	reply_locale=None,
	history=None,
) -> dict:
	cfg = get_insight_config()
	history = history or []

	if not has_api_key():
		return {"reply": None, "needs_api_setup": True}

	system = _build_system_prompt(
		reply_locale,
		extra_context="Micro-report data (narrate only, do not invent numbers):\n"
		+ micro_report_json(micro_report)
		+ "\n\n"
		+ INSIGHT_NARRATE_APPEND.strip(),
	)
	messages = [{"role": "system", "content": system}] + list(history)
	user_msg = message or "Summarize this business insight."
	messages.append({"role": "user", "content": user_msg})

	try:
		response, provider, label = _call_llm(messages, use_tools=False, cfg=cfg)
		prompt_tokens, completion_tokens = _extract_usage(response)
		reply = response.choices[0].message.content or "Summary unavailable."
		return {
			"reply": reply,
			"provider": provider,
			"model": cfg["model"],
			"prompt_tokens": prompt_tokens,
			"completion_tokens": completion_tokens,
		}
	except Exception as exc:
		result = {"reply": _format_llm_error(exc)}
		if isinstance(exc, ProviderExhaustedError) and getattr(exc, "payload", None):
			result["llm_exhausted"] = exc.payload
		return result


def _filters_hash(filters) -> str:
	if not filters:
		return ""
	payload = json.dumps(filters, sort_keys=True, default=str)
	return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _record_tool_evidence(
	tool_name: str,
	tool_args: dict,
	result: dict,
	*,
	tools_used: list,
	reports_used: list,
	filters_applied: list,
	sub_queries: list,
):
	tools_used.append(tool_name)
	entry = {
		"tool": tool_name,
		"doctype": tool_args.get("doctype") or tool_args.get("parent_doctype"),
		"report": tool_args.get("report_name"),
		"filters": result.get("filters") or tool_args.get("filters"),
	}
	if tool_name == "run_readonly_query":
		entry["query"] = tool_args.get("query") or result.get("query") or ""
	filters_applied.append(entry)

	filters = entry.get("filters") or {}
	row_count = result.get("row_count")
	if row_count is None and result.get("rows") is not None:
		row_count = len(result.get("rows") or [])
	elif row_count is None and result.get("count") is not None:
		row_count = result.get("count")

	sub_queries.append(
		{
			"tool": tool_name,
			"doctype": entry.get("doctype") or "",
			"report": entry.get("report") or "",
			"row_count": row_count,
			"duration_ms": result.get("duration_ms"),
			"filters_hash": _filters_hash(filters),
			"status": "error" if result.get("error") else "success",
		}
	)

	if tool_name == "run_report" and tool_args.get("report_name"):
		reports_used.append(tool_args["report_name"])
	elif tool_name == "run_multi_report":
		for spec in tool_args.get("reports") or []:
			if isinstance(spec, dict) and spec.get("report_name"):
				reports_used.append(spec["report_name"])
	elif tool_name == "get_budget_summary":
		reports_used.append("Budget Variance Report")
	elif tool_name == "get_financial_snapshot":
		reports_used.extend(["Profit and Loss Statement", "Balance Sheet"])
	elif tool_name == "compare_periods" and tool_args.get("report_name"):
		reports_used.append(tool_args["report_name"])


def _finalize_response(
	reply: str,
	micro_report: dict,
	evidence: dict,
	*,
	provider,
	cfg,
	prompt_tokens,
	completion_tokens,
	context=None,
):
	from frappe_pilot.utils.micro_report import build_last_insight_evidence

	cfg_followup = get_insight_config()
	if cfg_followup.get("followup_context", "compact") != "off" and micro_report:
		frappe.session[EVIDENCE_SESSION_KEY] = build_last_insight_evidence(micro_report, evidence)

	return {
		"reply": reply,
		"micro_report": micro_report,
		"evidence": evidence,
		"provider": provider,
		"model": cfg["model"],
		"prompt_tokens": prompt_tokens,
		"completion_tokens": completion_tokens,
	}


def run_insight_agent(
	message,
	*,
	history=None,
	reply_locale=None,
	context=None,
):
	cfg = get_insight_config()
	history = history or []
	ctx_note = json.dumps(context or {}, default=str)
	system_prompt = _build_system_prompt(reply_locale, extra_context=f"User context: {ctx_note}")

	messages = [{"role": "system", "content": system_prompt}] + list(history)
	messages.append({"role": "user", "content": message})

	if not has_api_key():
		return {
			"reply": None,
			"needs_api_setup": True,
			"evidence": {"tools_used": [], "reports_used": [], "filters_applied": []},
		}

	tools_used: list[str] = []
	reports_used: list[str] = []
	filters_applied: list[dict] = []
	sub_queries: list[dict] = []
	tool_results: list[dict] = []
	max_passes = cfg["max_passes"]
	max_tools_per_turn = cfg.get("max_tools_per_turn") or 3
	provider = model = None
	prompt_tokens = completion_tokens = None

	for pass_num in range(max_passes):
		use_tools = pass_num < max_passes - 1 and _supports_tool_calling()
		try:
			response, provider, _ = _call_llm(messages, use_tools=use_tools, cfg=cfg)
			pt, ct = _extract_usage(response)
			if pt is not None:
				prompt_tokens = pt
			if ct is not None:
				completion_tokens = ct
		except Exception as exc:
			if "tool_use_failed" in str(exc) and use_tools:
				try:
					response, provider, _ = _call_llm(messages, use_tools=False, cfg=cfg)
				except Exception as fallback_exc:
					return {
						"reply": _format_llm_error(fallback_exc),
						"evidence": {
							"tools_used": tools_used,
							"reports_used": reports_used,
							"filters_applied": filters_applied,
						},
					}
			else:
				result = {
					"reply": _format_llm_error(exc),
					"evidence": {
						"tools_used": tools_used,
						"reports_used": reports_used,
						"filters_applied": filters_applied,
					},
				}
				if isinstance(exc, ProviderExhaustedError) and getattr(exc, "payload", None):
					result["llm_exhausted"] = exc.payload
				return result

		msg = response.choices[0].message
		if not getattr(msg, "tool_calls", None):
			micro_report = build_micro_report(tool_results, context)
			raw_reply = msg.content or "I could not generate a response."
			reply, narrate_pt, narrate_ct, needs_setup = _resolve_insight_reply(
				micro_report,
				raw_reply,
				message=message,
				reply_locale=reply_locale,
				history=history,
			)
			if needs_setup:
				return {
					"reply": None,
					"needs_api_setup": True,
					"evidence": {
						"tools_used": tools_used,
						"reports_used": reports_used,
						"filters_applied": filters_applied,
					},
				}
			if narrate_pt is not None:
				prompt_tokens = narrate_pt
			if narrate_ct is not None:
				completion_tokens = narrate_ct

			digest = compact_micro_report_digest(micro_report)
			if digest and cfg.get("followup_context") == "compact":
				reply = f"{reply}\n{digest}".strip()

			evidence = {
				"tools_used": tools_used,
				"reports_used": reports_used,
				"filters_applied": filters_applied,
				"sub_queries": sub_queries,
			}
			return _finalize_response(
				reply,
				micro_report,
				evidence,
				provider=provider,
				cfg=cfg,
				prompt_tokens=prompt_tokens,
				completion_tokens=completion_tokens,
				context=context,
			)

		tool_calls = list(msg.tool_calls or [])[:max_tools_per_turn]
		assistant_tool_calls = []

		for tool_call in tool_calls:
			tool_name = tool_call.function.name
			try:
				tool_args = json.loads(tool_call.function.arguments or "{}")
			except json.JSONDecodeError:
				tool_args = {}

			if tool_name == "get_list_sample" and message:
				tool_args["user_message"] = message

			result = execute_insight_tool(tool_name, tool_args)
			_record_tool_evidence(
				tool_name,
				tool_args,
				result if isinstance(result, dict) else {},
				tools_used=tools_used,
				reports_used=reports_used,
				filters_applied=filters_applied,
				sub_queries=sub_queries,
			)
			tool_results.append(result)

			assistant_tool_calls.append(
				{
					"id": tool_call.id,
					"type": "function",
					"function": {
						"name": tool_name,
						"arguments": tool_call.function.arguments,
					},
				}
			)

		messages.append(
			{
				"role": "assistant",
				"content": None,
				"tool_calls": assistant_tool_calls,
			}
		)

		for tool_call, result in zip(tool_calls, tool_results[-len(tool_calls) :]):
			truncated = _truncate_result(result) if isinstance(result, dict) else result
			messages.append(
				{
					"role": "tool",
					"tool_call_id": tool_call.id,
					"content": json.dumps(truncated, default=str),
				}
			)

	micro_report = build_micro_report(tool_results, context)
	if not tools_used:
		reply = (
			"Insight could not run any data lookups. "
			"Check Pilot Settings → Insight limits (Agent Max Passes must be at least 1)."
		)
	else:
		reply = "I reached the maximum number of data lookups. Please ask a more specific question."

	if _micro_report_has_table(micro_report):
		brief = compose_brief_insight_reply(micro_report)
		if brief:
			reply = brief

	evidence = {
		"tools_used": tools_used,
		"reports_used": reports_used,
		"filters_applied": filters_applied,
		"sub_queries": sub_queries,
	}
	return _finalize_response(
		reply,
		micro_report,
		evidence,
		provider=provider,
		cfg=cfg,
		prompt_tokens=prompt_tokens,
		completion_tokens=completion_tokens,
		context=context,
	)
