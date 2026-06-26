# Insight tab API — business micro-reports via chat

from __future__ import annotations

import json
import time

import frappe

from frappe_pilot.api.insight_agent import EVIDENCE_SESSION_KEY, narrate_micro_report, run_insight_agent
from frappe_pilot.api.insight_presets import run_preset
from frappe_pilot.api.suggestions import build_insight_followup_chips, build_suggestions
from frappe_pilot.utils.insight_log import log_insight_turn
from frappe_pilot.utils.micro_report import empty_micro_report
from frappe_pilot.utils.report_defaults import erpnext_installed
from frappe_pilot.utils.settings import get_insight_config, get_enabled_languages, user_has_insight_access


SESSION_KEY = "ai_insight_history"
# Context bar (FRAI.insightContext in localStorage) = user filter defaults.
# EVIDENCE_SESSION_KEY = prior answer metadata for follow-up turns (session-only).


def _empty_response(**extra):
	base = {
		"reply": "",
		"micro_report": None,
		"evidence": {"tools_used": [], "reports_used": [], "filters_applied": [], "preset_id": ""},
		"nav_links": [],
		"kpi_snapshot_id": "",
		"chips": [],
		"chip_meta": {},
		"llm_exhausted": None,
		"reply_locale": "en",
	}
	base.update(extra)
	return base


def _resolve_log_status(base_status: str, micro_report: dict | None, tools_used) -> str:
	if base_status == "Error":
		return "Error"
	micro_report = micro_report or {}
	warnings = micro_report.get("warnings") or []
	has_data = bool(micro_report.get("tables") or micro_report.get("kpis"))
	if warnings and has_data:
		return "Partial"
	if warnings and tools_used:
		return "Partial"
	return "Success"


def _extract_sql_query(evidence: dict | None) -> str:
	for entry in (evidence or {}).get("filters_applied") or []:
		if entry.get("tool") == "run_readonly_query" and entry.get("query"):
			return entry["query"]
	return ""


def _parse_context(context):
	if not context:
		return {}
	if isinstance(context, dict):
		return context
	try:
		return json.loads(context) if context else {}
	except (TypeError, ValueError):
		return {}


def _resolve_reply_locale(reply_locale, message, langs):
	if reply_locale and reply_locale in langs:
		return reply_locale
	from frappe_pilot.utils.i18n import detect_user_locale

	return detect_user_locale(message, langs) or "en"


def _get_suggestions(reply_locale="en", *, message="", micro_report=None, evidence=None):
	if message or micro_report:
		from frappe_pilot.api.suggestions import _normalize_insight_chips
		from frappe_pilot.utils.i18n import build_chip_meta

		raw = build_insight_followup_chips(message, micro_report, evidence, limit=3)
		structured = _normalize_insight_chips(raw)
		return structured, build_chip_meta(structured)

	result = build_suggestions(
		tab="insight",
		doctype="",
		docname="",
		route="",
		list_doctype="",
		page_ctx={},
		sidebar_locale=reply_locale,
	)
	return result.get("chips") or [], result.get("chip_meta") or {}


@frappe.whitelist()
def chat(message, reply_locale="", context=None, preset_id="", page_context=""):
	if not user_has_insight_access():
		return _empty_response(reply="You do not have permission to use the Insight tab.")

	cfg = get_insight_config()
	if not cfg.get("enabled"):
		return _empty_response(reply="The Insight tab is disabled in Pilot Settings.")

	if not erpnext_installed():
		return _empty_response(
			reply="Insight requires ERPNext to be installed on this site.",
			micro_report=empty_micro_report(error="ERPNext is not installed."),
		)

	langs = get_enabled_languages()
	resolved_locale = _resolve_reply_locale(reply_locale, message, langs)
	ctx = _parse_context(context)
	preset_id = (preset_id or "").strip()

	start = time.time()
	history = frappe.session.get(SESSION_KEY) or []
	if len(history) > 16:
		history = history[-16:]

	user_turn = message or (preset_id and f"[preset:{preset_id}]") or ""
	history.append({"role": "user", "content": user_turn})

	agent_result = {}
	status = "Success"
	error_message = ""

	try:
		if preset_id:
			preset_result = run_preset(preset_id, ctx)
			if preset_result.get("error") and not preset_result.get("micro_report"):
				micro_report = empty_micro_report(
					title=preset_id,
					error=preset_result["error"],
				)
				agent_result = {
					"reply": preset_result["error"],
					"micro_report": micro_report,
					"evidence": {
						"tools_used": preset_result.get("tools_used") or [],
						"reports_used": preset_result.get("reports_used") or [],
						"filters_applied": preset_result.get("filters_applied") or [],
						"preset_id": preset_id,
					},
				}
				status = "Error"
				error_message = preset_result["error"]
			else:
				micro_report = preset_result.get("micro_report") or empty_micro_report()
				narrate = narrate_micro_report(
					micro_report,
					message or user_turn,
					reply_locale=resolved_locale,
					history=history[:-1],
				)
				if narrate.get("needs_api_setup"):
					return _empty_response(needs_api_setup=True, reply_locale=resolved_locale)
				agent_result = {
					"reply": narrate.get("reply") or "",
					"micro_report": micro_report,
					"tool_result": preset_result.get("tool_result"),
					"kpi_snapshot_id": (preset_result.get("tool_result") or {}).get("kpi_snapshot_id"),
					"evidence": {
						"tools_used": preset_result.get("tools_used") or [],
						"reports_used": preset_result.get("reports_used") or [],
						"filters_applied": preset_result.get("filters_applied") or [],
						"preset_id": preset_id,
					},
					"provider": narrate.get("provider"),
					"model": narrate.get("model"),
					"prompt_tokens": narrate.get("prompt_tokens"),
					"completion_tokens": narrate.get("completion_tokens"),
					"llm_exhausted": narrate.get("llm_exhausted"),
				}
		else:
			agent_result = run_insight_agent(
				message,
				history=history[:-1],
				reply_locale=resolved_locale,
				context=ctx,
			)
			if agent_result.get("needs_api_setup"):
				return _empty_response(needs_api_setup=True, reply_locale=resolved_locale)
	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "Insight Chat Error")
		status = "Error"
		error_message = str(exc)
		agent_result = {
			"reply": f"An error occurred: {exc}",
			"micro_report": empty_micro_report(error=str(exc)),
			"evidence": {"tools_used": [], "reports_used": [], "filters_applied": [], "preset_id": preset_id},
		}

	duration_ms = int((time.time() - start) * 1000)
	evidence = agent_result.get("evidence") or {}
	micro_report = agent_result.get("micro_report")
	status = _resolve_log_status(status, micro_report, evidence.get("tools_used"))

	log_insight_turn(
		status=status,
		message=message or preset_id,
		preset_id=preset_id or evidence.get("preset_id") or "",
		reports_used=evidence.get("reports_used"),
		tools_used=evidence.get("tools_used"),
		filters_applied=evidence.get("filters_applied"),
		sub_queries_json=evidence.get("sub_queries"),
		sql_query=_extract_sql_query(evidence),
		provider=agent_result.get("provider") or "",
		model=agent_result.get("model") or "",
		prompt_tokens=agent_result.get("prompt_tokens"),
		completion_tokens=agent_result.get("completion_tokens"),
		duration_ms=duration_ms,
		error_message=error_message,
	)

	reply = agent_result.get("reply") or ""
	if reply:
		history.append({"role": "assistant", "content": reply})
	frappe.session[SESSION_KEY] = history

	chips, chip_meta = _get_suggestions(
		resolved_locale,
		message=message or preset_id,
		micro_report=agent_result.get("micro_report"),
		evidence=evidence,
	)

	kpi_snapshot_id = ""
	if agent_result.get("kpi_snapshot_id"):
		kpi_snapshot_id = agent_result["kpi_snapshot_id"]
	elif isinstance(agent_result.get("micro_report"), dict):
		tool_res = agent_result.get("tool_result") or {}
		kpi_snapshot_id = tool_res.get("kpi_snapshot_id") or ""

	return _empty_response(
		reply=reply,
		micro_report=agent_result.get("micro_report"),
		evidence=evidence,
		chips=chips,
		chip_meta=chip_meta,
		llm_exhausted=agent_result.get("llm_exhausted"),
		reply_locale=resolved_locale,
		kpi_snapshot_id=kpi_snapshot_id,
	)


@frappe.whitelist()
def get_defaults():
	"""Return user company/FY defaults for Insight context bar."""
	from frappe_pilot.utils.report_defaults import get_fiscal_year_doc, resolve_company, resolve_fiscal_year

	company = resolve_company()
	fy = resolve_fiscal_year()
	result = {"company": company or "", "fiscal_year": fy or ""}
	fy_doc = get_fiscal_year_doc(fy)
	if fy_doc:
		result["from_date"] = str(fy_doc.year_start_date)
		result["to_date"] = str(fy_doc.year_end_date)
	return result


@frappe.whitelist()
def clear_history():
	frappe.session[SESSION_KEY] = []
	frappe.session[EVIDENCE_SESSION_KEY] = {}
	return {"ok": True}


@frappe.whitelist()
def save_snapshot(micro_report=None, reply="", title=""):
	cfg = get_insight_config()
	if not cfg.get("enable_save_snapshot"):
		frappe.throw("Save snapshot is disabled in Pilot Settings.")

	if not user_has_insight_access():
		frappe.throw("You do not have permission to save Insight snapshots.", frappe.PermissionError)

	if isinstance(micro_report, str):
		try:
			micro_report = json.loads(micro_report)
		except (TypeError, ValueError):
			micro_report = {}

	micro_report = micro_report or {}
	from frappe_pilot.utils.micro_report import build_snapshot_sources

	sources = micro_report.get("sources") or build_snapshot_sources(micro_report.get("tables") or [])
	# Frappe JSON fields accept dicts, not bare lists — serialize for storage.
	if isinstance(sources, list):
		sources = json.dumps(sources, default=str)
	elif isinstance(sources, dict):
		sources = json.dumps(sources, default=str)

	doc = frappe.get_doc(
		{
			"doctype": "Pilot Insight Snapshot",
			"title": title or micro_report.get("title") or "Insight Snapshot",
			"period": micro_report.get("period") or "",
			"company": micro_report.get("company") or "",
			"narrative": reply or "",
			"micro_report": micro_report,
			"sources": sources,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {
		"name": doc.name,
		"route": f"/app/pilot-insight-snapshot/{doc.name}",
	}
