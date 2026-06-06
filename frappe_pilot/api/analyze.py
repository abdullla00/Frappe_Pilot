# Advisor API — document-aware page Q&A with read-only agent (formerly Analyze)

import frappe

from frappe_pilot.api.analyze_agent import run_agent
from frappe_pilot.api.analyze_tools import parse_page_context
from frappe_pilot.utils.llm import has_api_key
from frappe_pilot.utils.navigation import process_reply_navigation, try_context_navigation
from frappe_pilot.utils.settings import get_advisor_config, user_has_pilot_access
from frappe_pilot.api.context_utils import (
	build_context_prefix,
	format_doc_summary_block,
	format_meta_summary_block,
	get_context_key,
	get_doc_summary,
	get_meta_summary,
	parse_route_description,
	resolve_form_context,
)

DIAGNOSE_TRIGGERS = frozenset({
	"diagnose this record",
	"flag anything unusual",
	"why are these records here?",
	"why is this total high?",
	"دەستنیشانکردنی کێشەکان",
})


def _resolve_mode(message, mode=""):
	if mode in ("explain", "diagnose"):
		return mode
	normalised = (message or "").strip().lower()
	if normalised in DIAGNOSE_TRIGGERS or normalised.startswith("diagnose "):
		return "diagnose"
	if "what's wrong" in normalised or "what is wrong" in normalised:
		return "diagnose"
	return "explain"


def _resolve_reply_locale(reply_locale, message, langs):
	if reply_locale in langs:
		return reply_locale
	from frappe_pilot.utils.i18n import detect_user_locale

	detected = detect_user_locale(message, langs)
	if detected:
		return detected
	non_en = [code for code in langs if code and code != "en"]
	if len(non_en) == 1:
		return non_en[0]
	return "en"


def _empty_response(**extra):
	base = {
		"chips": [],
		"chip_meta": {},
		"context_summary": "",
		"evidence": {"tools_used": [], "checks_run": 0},
		"nav_links": [],
		"navigation_action": None,
	}
	base.update(extra)
	return base


@frappe.whitelist()
def chat(
	message,
	doctype="",
	docname="",
	route="",
	list_doctype="",
	page_context="",
	mode="explain",
	reply_locale="",
):
	"""Advisor chat for the current page/document."""

	if not user_has_pilot_access():
		return _empty_response(reply="You do not have permission to use Frappe Pilot.")

	advisor_cfg = get_advisor_config()
	if not advisor_cfg.get("enabled"):
		return _empty_response(reply="The Advisor tab is disabled in Pilot Settings.")

	doctype, docname, route = resolve_form_context(doctype, docname, route)
	page_ctx = parse_page_context(page_context)

	from frappe_pilot.utils.settings import get_enabled_languages, get_pilot_settings, cint

	langs = get_enabled_languages()
	settings = get_pilot_settings()
	resolved_locale = _resolve_reply_locale(reply_locale, message, langs)

	if page_ctx.get("page_type") == "list" and page_ctx.get("list_doctype"):
		list_doctype = list_doctype or page_ctx.get("list_doctype")
	if page_ctx.get("page_type") == "report" and page_ctx.get("report_name"):
		route = route or f"query-report > {page_ctx.get('report_name')}"

	resolved_mode = _resolve_mode(message, mode)

	context_nav = try_context_navigation(
		message,
		doctype,
		docname,
		auto_navigate=bool(cint(settings.get("auto_navigate"))),
		reply_locale=resolved_locale,
	)
	if context_nav:
		return _empty_response(
			reply=context_nav["reply"],
			context_summary="Context navigation",
			nav_links=context_nav.get("nav_links") or [],
			navigation_action=context_nav.get("navigation_action"),
			reply_locale=resolved_locale,
		)

	if not has_api_key():
		return _empty_response(reply=None, needs_api_setup=True)

	seed_context, context_summary = build_analyze_context(
		doctype, docname, route, list_doctype, message, page_ctx=page_ctx
	)

	session_key = "ai_analyze_history"
	history = frappe.session.get(session_key) or []

	current_context = get_context_key(doctype, docname, list_doctype, route)
	last_context = frappe.session.get("ai_analyze_last_context") or ""
	if last_context != current_context:
		history = []
		frappe.session["ai_analyze_last_context"] = current_context

	if len(history) > 16:
		history = history[-16:]

	from frappe_pilot.utils.i18n import detect_user_locale, locale_context_note

	user_locale = detect_user_locale(message, langs) or resolved_locale
	prefix = build_context_prefix(doctype, docname, route, list_doctype)
	user_turn = locale_context_note(
		user_locale if user_locale and user_locale != "en" else None
	) + prefix + message
	history.append({"role": "user", "content": user_turn})

	try:
		agent_result = run_agent(
			user_turn,
			seed_context=seed_context,
			history=history[:-1],
			mode=resolved_mode,
			reply_locale=resolved_locale,
			page_context_raw=page_context,
			doctype=doctype,
			docname=docname,
			list_doctype=list_doctype,
			route=route,
		)

		if agent_result.get("needs_api_setup"):
			return _empty_response(
				reply=None,
				needs_api_setup=True,
				context_summary=context_summary,
				evidence=agent_result.get("evidence") or {"tools_used": [], "checks_run": 0},
			)

		reply_text = agent_result.get("reply", "")
		evidence = agent_result.get("evidence") or {"tools_used": [], "checks_run": 0}

		history.append({"role": "assistant", "content": reply_text})
		frappe.session[session_key] = history

		nav_result = process_reply_navigation(
			reply_text,
			message=message,
			doctype=doctype,
			docname=docname,
			list_doctype=list_doctype,
			report_name=page_ctx.get("report_name") or "",
			auto_navigate=bool(cint(settings.get("auto_navigate"))),
			reply_locale=resolved_locale,
		)

		suggestions = _get_suggestions(doctype, docname, list_doctype, route, page_ctx)
		return {
			"reply": nav_result["reply"],
			"chips": suggestions.get("chips") or [],
			"chip_meta": suggestions.get("chip_meta") or {},
			"context_summary": context_summary,
			"evidence": evidence,
			"nav_links": nav_result.get("nav_links") or [],
			"navigation_action": nav_result.get("navigation_action"),
			"reply_locale": resolved_locale,
		}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "AI Advisor Error")
		return _empty_response(
			reply=(
				"Something went wrong calling the LLM. Error: " + str(e) +
				". Check the Error Log for details."
			),
			context_summary=context_summary,
		)


def build_analyze_context(
	doctype="",
	docname="",
	route="",
	list_doctype="",
	user_message="",
	page_ctx=None,
):
	doctype, docname, route = resolve_form_context(doctype, docname, route)
	page_ctx = page_ctx or {}

	lines = [
		"## Current page context for analysis",
		"Use tools to fetch additional data when needed. This seed is a snapshot only.",
		"",
	]
	summary_label = ""

	if doctype and docname:
		budget = get_advisor_config().get("context_char_budget", 7000)
		doc_summary = get_doc_summary(doctype, docname, user_message=user_message)
		block = format_doc_summary_block(doc_summary, char_budget=budget)
		lines.append(block)
		if doc_summary.get("permission_denied"):
			summary_label = "Permission denied"
		elif doc_summary.get("error"):
			summary_label = doc_summary["error"]
		else:
			summary_label = f"{doctype} {docname} ({doc_summary.get('docstatus', '')})"

	elif doctype:
		meta_summary = get_meta_summary(doctype)
		lines.append(format_meta_summary_block(meta_summary, new_document=True))
		summary_label = f"New {doctype} form"

	elif list_doctype:
		meta_summary = get_meta_summary(list_doctype, include_list_view=True)
		lines.extend([
			f"The user is on the **{list_doctype} List** page.",
			"Use get_list_sample and get_list_count tools to fetch row data and counts.",
			"",
			format_meta_summary_block(meta_summary),
		])
		if page_ctx.get("list_filters"):
			lines.append(f"Active list filters (from browser): {page_ctx.get('list_filters')}")
		summary_label = f"{list_doctype} List"

	elif page_ctx.get("page_type") == "report" and page_ctx.get("report_name"):
		report_name = page_ctx.get("report_name")
		lines.extend([
			f"The user is on report **{report_name}**.",
			"Use run_report_sample tool to fetch report data with current filters.",
			f"Report filters (from browser): {page_ctx.get('report_filters') or {}}",
		])
		summary_label = f"Report: {report_name}"

	elif route:
		lines.append(parse_route_description(route))
		lines.append(
			"If this is a report, use run_report_sample. If a list, use get_list_sample."
		)
		summary_label = "Page context only"

	else:
		lines.append(
			"The user is on the ERPNext home dashboard. "
			"No specific document is open."
		)
		summary_label = "Home dashboard"

	return "\n".join(lines), summary_label


def _get_suggestions(doctype, docname, list_doctype, route, page_ctx=None):
	from frappe_pilot.api.suggestions import build_suggestions

	return build_suggestions(
		tab="advisor",
		doctype=doctype or "",
		docname=docname or "",
		route=route or "",
		list_doctype=list_doctype or "",
		page_ctx=page_ctx or {},
	)


@frappe.whitelist()
def clear_history():
	frappe.session["ai_analyze_history"] = []
	frappe.session["ai_analyze_last_context"] = ""
	return {"status": "ok", "message": "Advisor conversation cleared."}
