# Pilot Settings helpers

import frappe

from frappe_pilot.utils.i18n import (
	PILOT_LOCALE_LABELS,
	RTL_LOCALE_CODES,
	UI_STRINGS,
	pilot_locale_label,
)

DEFAULTS = {
	"enable_pilot": 1,
	"default_tab": "Advisor",
	"auto_navigate": 0,
	"close_sidebar_on_navigate": 0,
	"show_evidence_line": 1,
	"llm_failover_mode": "Both",
	"analyze_enabled": 1,
	"analyze_model": "llama-3.3-70b-versatile",
	"analyze_max_passes": 5,
	"analyze_max_tokens": 900,
	"analyze_max_tokens_final": 600,
	"analyze_temperature": 0.25,
	"diagnose_temperature": 0.2,
	"context_char_budget": 7000,
	"enable_document_checks": 1,
	"advisor_brief_replies": 1,
	"advisor_show_context_bar": 1,
	"advisor_group_chips": 1,
	"advisor_followup_chips": 1,
	"advisor_persist_chat_on_route": 0,
	"max_linked_docs": 3,
	"max_linked_fields": 8,
	"max_gl_rows": 15,
	"max_list_rows": 25,
	"max_report_rows": 30,
	"max_timeline_items": 5,
	"max_tool_json_chars": 6000,
	"guide_enabled": 1,
	"guide_model": "llama-3.3-70b-versatile",
	"guide_max_tokens": 600,
	"guide_temperature": 0.7,
	"guide_history_limit": 20,
	"build_enabled": 1,
	"build_model": "llama-3.3-70b-versatile",
	"build_max_tokens": 1400,
	"build_max_tokens_fallback": 500,
	"build_temperature": 0.15,
	"build_temperature_fallback": 0.3,
	"preview_expiry_minutes": 5,
	"debug_log_tool_calls": 0,
	"chip_locale_scope": "all_enabled",
	"enable_doc_event_triggers": 0,
	"engine_tabs_enabled": 1,
	"insight_enabled": 0,
	"insight_model": "llama-3.3-70b-versatile",
	"insight_max_passes": 5,
	"insight_max_tokens": 900,
	"insight_max_tokens_final": 600,
	"insight_temperature": 0.2,
	"insight_max_report_rows": 30,
	"insight_max_list_rows": 25,
	"insight_max_tool_json_chars": 6000,
	"insight_max_tools_per_turn": 3,
	"insight_max_tables_per_card": 4,
	"insight_enable_readonly_sql": 0,
	"insight_followup_context": "compact",
	"insight_show_evidence": 1,
	"insight_enable_save_snapshot": 1,
	"insight_enable_logging": 1,
	"insight_kpi_cache_ttl": 600,
}

VALID_CHIP_LOCALE_SCOPES = frozenset({"all_enabled", "active_locale", "active_plus_en"})


def get_pilot_settings():
	try:
		return frappe.get_cached_doc("Pilot Settings")
	except frappe.DoesNotExistError:
		return _default_settings_doc()


def _default_settings_doc():
	"""In-memory defaults before first migrate/save."""
	doc = frappe.new_doc("Pilot Settings")
	for key, val in DEFAULTS.items():
		doc.set(key, val)
	return doc


def _setting(name):
	settings = get_pilot_settings()
	val = settings.get(name)
	if val is None or val == "":
		return DEFAULTS.get(name)
	return val


def _setting_int(name, *, minimum=1, maximum=None):
	default = DEFAULTS.get(name)
	val = _setting(name)
	try:
		n = int(val)
	except (TypeError, ValueError):
		try:
			n = int(default)
		except (TypeError, ValueError):
			n = minimum
	if n <= 0:
		try:
			d = int(default)
			n = d if d > 0 else minimum
		except (TypeError, ValueError):
			n = minimum
	if minimum is not None and n < minimum:
		n = minimum
	if maximum is not None and n > maximum:
		n = maximum
	return n


def _setting_float(name, *, minimum=None, maximum=None):
	default = DEFAULTS.get(name)
	val = _setting(name)
	try:
		n = float(val)
	except (TypeError, ValueError):
		try:
			n = float(default)
		except (TypeError, ValueError):
			n = 0.0
	if n == 0.0 and default not in (None, "", 0, 0.0):
		try:
			d = float(default)
			if d != 0.0:
				n = d
		except (TypeError, ValueError):
			pass
	if minimum is not None and n < minimum:
		n = minimum
	if maximum is not None and n > maximum:
		n = maximum
	return n


def _allowed_role_rows():
	settings = get_pilot_settings()
	return [r for r in (settings.get("allowed_roles") or []) if r.role]


def _matching_allowed_rows(user=None):
	user = user or frappe.session.user
	rows = _allowed_role_rows()
	if not rows:
		return None
	user_roles = set(frappe.get_roles(user))
	return [r for r in rows if r.role in user_roles]


def user_has_advisor_access(user=None):
	user = user or frappe.session.user
	if user == "Guest":
		return False
	if not cint(_setting("enable_pilot")):
		return False
	if not (cint(_setting("analyze_enabled")) or cint(_setting("guide_enabled"))):
		return False

	matching = _matching_allowed_rows(user)
	if matching is None:
		return True
	return any(cint(r.advisor_tab) for r in matching)


def user_has_build_access(user=None):
	user = user or frappe.session.user
	if user == "Guest":
		return False
	if not cint(_setting("build_enabled")):
		return False

	matching = _matching_allowed_rows(user)
	if matching is None:
		return "System Manager" in frappe.get_roles(user)
	return any(cint(r.build_tab) for r in matching)


def user_has_insight_access(user=None):
	user = user or frappe.session.user
	if user == "Guest":
		return False
	if not cint(_setting("enable_pilot")):
		return False
	if not cint(_setting("insight_enabled")):
		return False

	matching = _matching_allowed_rows(user)
	if matching is None:
		return "System Manager" in frappe.get_roles(user)
	return any(cint(getattr(r, "insight_tab", 0)) for r in matching)


def user_has_pilot_access(user=None):
	return (
		user_has_advisor_access(user)
		or user_has_build_access(user)
		or user_has_insight_access(user)
		or user_has_engine_tab_access(user)
	)


def user_has_engine_tab_access(user=None, tab=None):
	"""Any engine tab (agents, flows, knowledge, integrations, logs)."""
	user = user or frappe.session.user
	if user == "Guest":
		return False
	if not cint(_setting("engine_tabs_enabled")):
		return False
	if not frappe.db.exists("DocType", "Agent"):
		return False

	matching = _matching_allowed_rows(user)
	if matching is None:
		return "System Manager" in frappe.get_roles(user)

	tab_field = {
		"agents": "agents_tab",
		"flows": "flows_tab",
		"knowledge": "knowledge_tab",
		"integrations": "integrations_tab",
		"logs": "logs_tab",
	}.get(tab)

	if tab_field:
		return any(cint(getattr(r, tab_field, 0)) for r in matching)

	return any(
		cint(getattr(r, f, 0))
		for r in matching
		for f in ("agents_tab", "flows_tab", "knowledge_tab", "integrations_tab", "logs_tab")
	)


def get_disabled_analyze_tools():
	raw = _setting("disabled_analyze_tools") or ""
	if not raw:
		return frozenset()
	return frozenset(t.strip() for t in str(raw).split(",") if t.strip())


def get_advisor_config():
	enabled = cint(_setting("analyze_enabled")) or cint(_setting("guide_enabled"))
	return {
		"enabled": enabled,
		"model": _setting("analyze_model"),
		"max_passes": int(_setting("analyze_max_passes")),
		"max_tokens": int(_setting("analyze_max_tokens")),
		"max_tokens_final": int(_setting("analyze_max_tokens_final")),
		"temperature": float(_setting("analyze_temperature")),
		"diagnose_temperature": float(_setting("diagnose_temperature")),
		"context_char_budget": int(_setting("context_char_budget")),
		"enable_document_checks": cint(_setting("enable_document_checks")),
		"max_linked_docs": int(_setting("max_linked_docs")),
		"max_linked_fields": int(_setting("max_linked_fields")),
		"max_gl_rows": int(_setting("max_gl_rows")),
		"max_list_rows": int(_setting("max_list_rows")),
		"max_report_rows": int(_setting("max_report_rows")),
		"max_timeline_items": int(_setting("max_timeline_items")),
		"max_tool_json_chars": int(_setting("max_tool_json_chars")),
		"custom_analyze_prompt": _setting("custom_analyze_prompt") or "",
		"disabled_tools": get_disabled_analyze_tools(),
		"debug_log_tool_calls": cint(_setting("debug_log_tool_calls")),
		"auto_navigate": cint(_setting("auto_navigate")),
		"close_sidebar_on_navigate": cint(_setting("close_sidebar_on_navigate")),
		"brief_replies": cint(_setting("advisor_brief_replies")) if _setting("advisor_brief_replies") is not None else 1,
		"show_context_bar": cint(_setting("advisor_show_context_bar")) if _setting("advisor_show_context_bar") is not None else 1,
		"group_chips": cint(_setting("advisor_group_chips")) if _setting("advisor_group_chips") is not None else 1,
		"followup_chips": cint(_setting("advisor_followup_chips")) if _setting("advisor_followup_chips") is not None else 1,
		"persist_chat_on_route": cint(_setting("advisor_persist_chat_on_route")),
	}


def get_analyze_config():
	return {
		"enabled": cint(_setting("analyze_enabled")) or cint(_setting("guide_enabled")),
		"model": _setting("analyze_model"),
		"max_passes": int(_setting("analyze_max_passes")),
		"max_tokens": int(_setting("analyze_max_tokens")),
		"max_tokens_final": int(_setting("analyze_max_tokens_final")),
		"temperature": float(_setting("analyze_temperature")),
		"diagnose_temperature": float(_setting("diagnose_temperature")),
		"context_char_budget": int(_setting("context_char_budget")),
		"enable_document_checks": cint(_setting("enable_document_checks")),
		"max_linked_docs": int(_setting("max_linked_docs")),
		"max_linked_fields": int(_setting("max_linked_fields")),
		"max_gl_rows": int(_setting("max_gl_rows")),
		"max_list_rows": int(_setting("max_list_rows")),
		"max_report_rows": int(_setting("max_report_rows")),
		"max_timeline_items": int(_setting("max_timeline_items")),
		"max_tool_json_chars": int(_setting("max_tool_json_chars")),
		"custom_analyze_prompt": _setting("custom_analyze_prompt") or "",
		"disabled_tools": get_disabled_analyze_tools(),
		"debug_log_tool_calls": cint(_setting("debug_log_tool_calls")),
	}


def get_guide_config():
	return {
		"enabled": cint(_setting("guide_enabled")),
		"model": _setting("guide_model"),
		"max_tokens": int(_setting("guide_max_tokens")),
		"temperature": float(_setting("guide_temperature")),
		"history_limit": int(_setting("guide_history_limit")),
	}


def get_build_config():
	return {
		"enabled": cint(_setting("build_enabled")),
		"model": _setting("build_model"),
		"max_tokens": int(_setting("build_max_tokens")),
		"max_tokens_fallback": int(_setting("build_max_tokens_fallback")),
		"temperature": float(_setting("build_temperature")),
		"temperature_fallback": float(_setting("build_temperature_fallback")),
		"preview_expiry_minutes": int(_setting("preview_expiry_minutes")),
	}


def get_disabled_insight_tools():
	raw = _setting("disabled_insight_tools") or ""
	if not raw:
		return frozenset()
	return frozenset(t.strip() for t in str(raw).split(",") if t.strip())


def get_insight_disallowed_doctypes() -> frozenset[str]:
	settings = get_pilot_settings()
	return frozenset(
		row.doctype
		for row in (settings.get("insight_disallowed_doctypes") or [])
		if getattr(row, "doctype", None)
	)


def get_insight_disallowed_modules() -> frozenset[str]:
	settings = get_pilot_settings()
	return frozenset(
		row.module
		for row in (settings.get("insight_disallowed_modules") or [])
		if getattr(row, "module", None)
	)


def get_insight_config():
	return {
		"enabled": cint(_setting("insight_enabled")),
		"model": _setting("insight_model"),
		"max_passes": _setting_int("insight_max_passes", minimum=1, maximum=10),
		"max_tokens": _setting_int("insight_max_tokens", minimum=100, maximum=8000),
		"max_tokens_final": _setting_int("insight_max_tokens_final", minimum=100, maximum=8000),
		"temperature": _setting_float("insight_temperature", minimum=0.0, maximum=1.0),
		"max_report_rows": _setting_int("insight_max_report_rows", minimum=1, maximum=100),
		"max_list_rows": _setting_int("insight_max_list_rows", minimum=1, maximum=100),
		"max_tool_json_chars": _setting_int("insight_max_tool_json_chars", minimum=1000, maximum=20000),
		"max_tools_per_turn": _setting_int("insight_max_tools_per_turn", minimum=1, maximum=5),
		"max_tables_per_card": _setting_int("insight_max_tables_per_card", minimum=1, maximum=10),
		"enable_readonly_sql": cint(_setting("insight_enable_readonly_sql")),
		"followup_context": (_setting("insight_followup_context") or "compact").strip(),
		"disallowed_modules": get_insight_disallowed_modules(),
		"disallowed_doctypes": get_insight_disallowed_doctypes(),
		"disabled_tools": get_disabled_insight_tools(),
		"show_evidence": cint(_setting("insight_show_evidence")),
		"enable_save_snapshot": cint(_setting("insight_enable_save_snapshot")),
		"enable_logging": cint(_setting("insight_enable_logging")),
		"kpi_cache_ttl": _setting_int("insight_kpi_cache_ttl", minimum=60, maximum=86400),
	}


def cint(val):
	return int(val or 0)


def get_pilot_language_options():
	"""English always first, then enabled Additional Languages rows."""
	options = [
		{
			"code": "en",
			"label": PILOT_LOCALE_LABELS.get("en", "EN"),
			"name": "English",
			"rtl": False,
			"has_ui": True,
		}
	]
	settings = get_pilot_settings()
	seen = {"en"}
	for row in settings.get("enabled_languages") or []:
		if not cint(row.get("enabled")) or not row.language:
			continue
		lang = frappe.db.get_value(
			"Language",
			row.language,
			["language_code", "language_name"],
			as_dict=True,
		)
		if not lang or not lang.language_code:
			continue
		code = lang.language_code
		if code in seen:
			continue
		seen.add(code)
		options.append(
			{
				"code": code,
				"label": pilot_locale_label(code, lang.language_name),
				"name": lang.language_name or code,
				"rtl": code in RTL_LOCALE_CODES,
				"has_ui": code in UI_STRINGS,
			}
		)
	return options


def get_enabled_languages():
	return [opt["code"] for opt in get_pilot_language_options()]


def _language_link_code(link):
	if not link:
		return None
	return frappe.db.get_value("Language", link, "language_code") or link


def ensure_pilot_english_language_row(doc):
	"""Ensure English is the first, enabled row in enabled_languages. Returns True if mutated."""
	if not frappe.db.exists("Language", "en"):
		return False

	rows = list(doc.get("enabled_languages") or [])
	other = []
	seen_other = set()
	for row in rows:
		code = _language_link_code(row.language)
		if code == "en":
			continue
		if not row.language or row.language in seen_other:
			continue
		seen_other.add(row.language)
		other.append({"language": row.language, "enabled": cint(row.get("enabled"))})

	needs_update = True
	if rows:
		first_code = _language_link_code(rows[0].language)
		en_rows = [r for r in rows if _language_link_code(r.language) == "en"]
		if (
			len(en_rows) == 1
			and first_code == "en"
			and cint(en_rows[0].enabled)
			and len(rows) == 1 + len(other)
		):
			needs_update = False

	if not needs_update:
		return False

	doc.set("enabled_languages", [])
	doc.append("enabled_languages", {"language": "en", "enabled": 1})
	for row in other:
		doc.append("enabled_languages", row)
	return True


def get_chip_locale_scope():
	scope = (_setting("chip_locale_scope") or "all_enabled").strip()
	if scope not in VALID_CHIP_LOCALE_SCOPES:
		return "all_enabled"
	return scope
