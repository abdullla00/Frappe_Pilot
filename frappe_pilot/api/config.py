# Pilot bootstrap config for sidebar (non-secret)

import frappe

from frappe_pilot.utils.llm import (
	get_active_provider,
	get_active_provider_label,
	get_active_provider_row,
	get_llm_runtime_status,
	get_provider_rows,
	has_api_key,
	has_tool_calling_provider,
	set_session_llm_row as _set_session_llm_row,
)
from frappe_pilot.utils.i18n import get_ui_bundle
from frappe_pilot.utils.settings import (
	cint,
	get_advisor_config,
	get_chip_locale_scope,
	get_enabled_languages,
	get_insight_config,
	get_pilot_language_options,
	get_pilot_settings,
	user_has_advisor_access,
	user_has_build_access,
	user_has_engine_tab_access,
	user_has_insight_access,
	user_has_pilot_access,
)


def _normalize_default_tab(raw):
	val = (raw or "Advisor").strip().lower()
	if val in ("analyze", "guide"):
		return "advisor"
	if val == "build":
		return "build"
	if val == "insight":
		return "insight"
	return "advisor"


def _normalize_sidebar_position(raw):
	val = (raw or "Right").strip().lower()
	if val in ("left", "bottom"):
		return val
	return "right"


def _llm_provider_options():
	options = []
	for row in get_provider_rows():
		options.append(
			{
				"name": row["name"],
				"provider": row["provider_name"],
				"row_label": row["row_label"] or row["provider_name"],
				"priority": row["priority"],
				"model": row["model"],
			}
		)
	return options


@frappe.whitelist()
def get_pilot_config():
	settings = get_pilot_settings()
	langs = get_enabled_languages()
	language_options = get_pilot_language_options()
	advisor_cfg = get_advisor_config()
	insight_cfg = get_insight_config()
	active_row = get_active_provider_row()
	llm_status = get_llm_runtime_status()
	current_row = llm_status.get("current_row") or {}
	return {
		"enabled": bool(cint(settings.get("enable_pilot"))),
		"languages": langs,
		"language_options": language_options,
		"chip_locale_scope": get_chip_locale_scope(),
		"primary_locale": "en",
		"ui_strings": get_ui_bundle(langs),
		"has_api_key": has_api_key(),
		"has_tool_calling_provider": has_tool_calling_provider(),
		"active_provider": current_row.get("provider") or get_active_provider(),
		"active_provider_label": current_row.get("row_label") or get_active_provider_label(),
		"active_llm_row": current_row.get("name") or (active_row["name"] if active_row else None),
		"primary_llm_row": llm_status.get("primary_row"),
		"llm_runtime_status": llm_status,
		"llm_failover_mode": settings.get("llm_failover_mode") or "Both",
		"llm_provider_options": _llm_provider_options(),
		"can_configure_api": "System Manager" in frappe.get_roles(),
		"api_setup_route": ["Form", "Pilot Settings", "Pilot Settings"],
		"default_tab": _normalize_default_tab(settings.get("default_tab")),
		"sidebar_position": _normalize_sidebar_position(settings.get("sidebar_position")),
		"advisor_enabled": bool(advisor_cfg.get("enabled")),
		"analyze_enabled": bool(advisor_cfg.get("enabled")),
		"guide_enabled": bool(advisor_cfg.get("enabled")),
		"build_enabled": bool(cint(settings.get("build_enabled"))),
		"insight_enabled": bool(insight_cfg.get("enabled")),
		"insight_show_evidence": bool(insight_cfg.get("show_evidence")),
		"insight_enable_save_snapshot": bool(insight_cfg.get("enable_save_snapshot")),
		"insight_enable_logging": bool(insight_cfg.get("enable_logging")),
		"show_evidence": bool(cint(settings.get("show_evidence_line"))),
        "advisor_show_context_bar": bool(advisor_cfg.get("show_context_bar", 1)),
        "advisor_group_chips": bool(advisor_cfg.get("group_chips", 1)),
        "advisor_followup_chips": bool(advisor_cfg.get("followup_chips", 1)),
        "advisor_persist_chat_on_route": bool(advisor_cfg.get("persist_chat_on_route")),
		"auto_navigate": bool(cint(settings.get("auto_navigate"))),
		"close_sidebar_on_navigate": bool(cint(settings.get("close_sidebar_on_navigate"))),
		"can_access_pilot": user_has_pilot_access(),
		"can_access_advisor": user_has_advisor_access(),
		"can_access_build": user_has_build_access(),
		"can_access_insight": user_has_insight_access(),
		"engine_tabs_enabled": bool(cint(settings.get("engine_tabs_enabled"))),
		"enable_doc_event_triggers": bool(cint(settings.get("enable_doc_event_triggers"))),
		"can_access_agents": user_has_engine_tab_access(tab="agents"),
		"can_access_flows": user_has_engine_tab_access(tab="flows"),
		"can_access_knowledge": user_has_engine_tab_access(tab="knowledge"),
		"can_access_integrations": user_has_engine_tab_access(tab="integrations"),
		"can_access_logs": user_has_engine_tab_access(tab="logs"),
		"is_system_manager": "System Manager" in frappe.get_roles(),
		"platform_url": "/pilot",
	}


@frappe.whitelist()
def set_session_llm_row(row_name=None):
	return _set_session_llm_row(row_name or None)


@frappe.whitelist()
def test_api_connection(row_name=None):
	if "System Manager" not in frappe.get_roles():
		frappe.throw("Only System Manager can test the API connection.", frappe.PermissionError)

	rows = get_provider_rows()
	if not rows:
		return {"ok": False, "message": "No enabled LLM provider rows configured."}

	settings = get_pilot_settings()
	results = []
	any_ok = False
	reply = ""

	target_rows = rows
	if row_name:
		target_rows = [r for r in rows if r["name"] == row_name]
		if not target_rows:
			return {"ok": False, "message": f"Row {row_name} not found or not enabled.", "results": []}

	for row in target_rows:
		label = row["row_label"] or row["provider_name"]
		call_model = row["model"]
		entry = {
			"name": row["name"],
			"label": label,
			"provider": row["provider_name"],
			"priority": row["priority"],
			"model": call_model,
			"ok": False,
			"error": "",
		}
		try:
			from frappe_pilot.utils.llm import (
				_is_rate_limit,
				call_provider,
				mark_row_rate_limited,
				record_successful_row,
			)

			response = call_provider(
				row,
				messages=[
					{"role": "system", "content": "Reply with exactly: ok"},
					{"role": "user", "content": "ping"},
				],
				model=call_model,
				max_tokens=10,
				temperature=0,
			)
			reply = response.choices[0].message.content or ""
			record_successful_row(row)
			entry["ok"] = True
			any_ok = True
		except Exception as exc:
			entry["error"] = str(exc)
			if _is_rate_limit(exc):
				mark_row_rate_limited(row, exc)
				entry["rate_limited"] = True
		results.append(entry)

	all_ok = bool(results) and all(r["ok"] for r in results)
	return {
		"ok": any_ok,
		"all_ok": all_ok,
		"results": results,
		"message": "\n".join(
			f"{r['label']} (priority {r['priority']}): "
			+ ("OK" if r["ok"] else f"failed — {r['error']}")
			for r in results
		),
		"reply_preview": (reply or "")[:80] if any_ok else "",
	}


def has_app_permission():
	"""Apps screen permission hook."""
	return user_has_pilot_access()
