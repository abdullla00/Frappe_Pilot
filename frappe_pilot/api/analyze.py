# Advisor API — document-aware page Q&A with read-only agent (formerly Analyze)

import frappe

from frappe_pilot.api.analyze_agent import run_agent
from frappe_pilot.api.analyze_tools import parse_page_context
from frappe_pilot.utils.llm import has_api_key
from frappe_pilot.utils.advisor_calc import try_calc_fast_path
from frappe_pilot.utils.advisor_intent import detect_intent, resolve_agent_mode
from frappe_pilot.utils.advisor_reply import finalize_advisor_reply
from frappe_pilot.utils.navigation import filter_self_nav_links, process_reply_navigation, try_context_navigation
from frappe_pilot.utils.settings import get_advisor_config, user_has_advisor_access
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

def _resolve_mode(message, mode=""):
	return resolve_agent_mode(message, mode)


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

	if not user_has_advisor_access():
		return _empty_response(reply="You do not have permission to use the Advisor tab.")

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
	intent_info = detect_intent(message, mode=mode)

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
	persist_chat = bool(advisor_cfg.get("persist_chat_on_route"))
	if not persist_chat and last_context != current_context:
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
		fast_result = try_calc_fast_path(
			doctype=doctype,
			docname=docname,
			message=message,
			intent_info=intent_info,
		)
		if fast_result:
			agent_result = fast_result
		else:
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
				intent_info=intent_info,
			)

		if agent_result.get("needs_api_setup"):
			return _empty_response(
				reply=None,
				needs_api_setup=True,
				context_summary=context_summary,
				evidence=agent_result.get("evidence") or {"tools_used": [], "checks_run": 0},
			)

		reply_text = agent_result.get("reply", "")
		advisor_card = agent_result.get("advisor_card")
		evidence = agent_result.get("evidence") or {"tools_used": [], "checks_run": 0}

		if resolved_mode == "diagnose" and not advisor_card and doctype and docname:
			advisor_card = _build_diagnose_card_from_checks(doctype, docname)
			evidence["checks_run"] = len((advisor_card or {}).get("findings") or [])

		reply_text = finalize_advisor_reply(
			reply_text,
			advisor_card=advisor_card,
			message=message,
			brief_replies_enabled=bool(advisor_cfg.get("brief_replies", 1)),
		)

		history.append({"role": "assistant", "content": reply_text})
		frappe.session[session_key] = history
		frappe.session["ai_advisor_last_intent"] = intent_info.get("intent")

		if agent_result.get("llm_exhausted"):
			return _empty_response(
				reply=reply_text,
				context_summary=context_summary,
				evidence=evidence,
				llm_exhausted=agent_result.get("llm_exhausted"),
				advisor_card=advisor_card,
			)

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

		nav_links = filter_self_nav_links(
			nav_result.get("nav_links") or [],
			doctype=doctype,
			docname=docname,
		)

		suggestions = _get_suggestions(
			doctype, docname, list_doctype, route, page_ctx,
			last_intent=intent_info.get("intent"),
			last_message=message,
		)
		return {
			"reply": nav_result["reply"],
			"chips": suggestions.get("chips") or [],
			"chip_meta": suggestions.get("chip_meta") or {},
			"chip_groups": suggestions.get("chip_groups") or [],
			"context_summary": context_summary,
			"context_bar": suggestions.get("context_bar") or {},
			"evidence": evidence,
			"nav_links": nav_links,
			"navigation_action": nav_result.get("navigation_action"),
			"reply_locale": resolved_locale,
			"advisor_card": advisor_card,
			"hide_evidence_hint": bool(advisor_cfg.get("show_context_bar", 1)),
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


def _build_diagnose_card_from_checks(doctype, docname):
	from frappe_pilot.api.doc_checks import run_document_checks
	from frappe_pilot.utils.advisor_card import build_diagnose_card

	checks = run_document_checks(doctype, docname)
	issues = checks.get("issues") or []
	evidence_lines = [
		f"{issue.get('code')}: {issue.get('message')}"
		for issue in issues[:6]
		if issue.get("message")
	]
	verify_lines = [
		issue.get("message")
		for issue in issues
		if issue.get("severity") == "high" and issue.get("message")
	][:3]
	if not verify_lines and issues:
		verify_lines = ["Review the flagged fields on this form."]
	return build_diagnose_card(
		title=f"Diagnose · {doctype}",
		findings=issues,
		evidence=evidence_lines,
		verify=verify_lines or ["No further action required."],
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


def _get_suggestions(doctype, docname, list_doctype, route, page_ctx=None, last_intent="", last_message=""):
	from frappe_pilot.api.suggestions import build_suggestions

	return build_suggestions(
		tab="advisor",
		doctype=doctype or "",
		docname=docname or "",
		route=route or "",
		list_doctype=list_doctype or "",
		page_ctx=page_ctx or {},
		last_intent=last_intent or "",
		last_message=last_message or "",
	)


@frappe.whitelist()
def get_context_bar(doctype="", docname="", route="", list_doctype="", page_context=""):
	"""Sticky context strip for Advisor tab."""
	from frappe_pilot.api.suggestions import build_context_bar

	doctype, docname, route = resolve_form_context(doctype, docname, route)
	page_ctx = parse_page_context(page_context)
	return build_context_bar(
		doctype=doctype or "",
		docname=docname or "",
		route=route or "",
		list_doctype=list_doctype or "",
		page_ctx=page_ctx,
	)


@frappe.whitelist()
def clear_history():
	frappe.session["ai_analyze_history"] = []
	frappe.session["ai_analyze_last_context"] = ""
	return {"status": "ok", "message": "Advisor conversation cleared."}
