# Copyright (c) 2026, Frappe Pilot and contributors

import frappe
from frappe.model.document import Document

from frappe_pilot.utils.llm import resolve_row_api_key
from frappe_pilot.utils.llm_catalog import get_llm_provider_master, resolve_row_model
from frappe_pilot.utils.settings import (
	DEFAULTS,
	_language_link_code,
	cint,
	ensure_pilot_english_language_row,
)

VALID_FAILOVER_MODES = frozenset({"Manual", "Auto", "Both"})
KNOWN_ANALYZE_TOOLS = frozenset({
	"get_document",
	"get_linked_documents",
	"get_doctype_meta",
	"get_workflow_state",
	"get_timeline",
	"get_gl_entries",
	"get_list_sample",
	"get_list_count",
	"run_report_sample",
	"run_document_checks",
})
KNOWN_INSIGHT_TOOLS = frozenset({
	"list_reports",
	"run_report",
	"run_multi_report",
	"get_list_count",
	"get_list_sample",
	"get_doctype_meta",
	"get_related_doctypes",
	"get_child_table_sample",
	"get_budget_summary",
	"get_financial_snapshot",
	"compare_periods",
	"get_list_aggregate",
	"run_readonly_query",
})


class PilotSettings(Document):
	def validate(self):
		self._clamp_int("analyze_max_passes", 1, 10)
		self._clamp_int("max_list_rows", 1, 100)
		self._clamp_int("max_report_rows", 1, 100)
		self._clamp_int("context_char_budget", 1000, 20000)
		self._clamp_int("max_tool_json_chars", 1000, 20000)
		self._clamp_int("insight_max_passes", 1, 10)
		self._clamp_int("insight_max_tokens", 100, 8000)
		self._clamp_int("insight_max_tokens_final", 100, 8000)
		self._clamp_int("insight_max_report_rows", 1, 100)
		self._clamp_int("insight_max_list_rows", 1, 100)
		self._clamp_int("insight_max_tool_json_chars", 1000, 20000)
		self._clamp_int("insight_max_tools_per_turn", 1, 5)
		self._clamp_int("insight_max_tables_per_card", 1, 10)
		self._clamp_int("insight_kpi_cache_ttl", 60, 86400)
		self._clamp_int("preview_expiry_minutes", 1, 60)
		self._clamp_float("analyze_temperature", 0.0, 1.0)
		self._clamp_float("diagnose_temperature", 0.0, 1.0)
		self._clamp_float("guide_temperature", 0.0, 1.0)
		self._clamp_float("build_temperature", 0.0, 1.0)
		self._clamp_float("build_temperature_fallback", 0.0, 1.0)
		self._clamp_float("insight_temperature", 0.0, 1.0)
		self._ensure_insight_defaults()

		mode = (self.llm_failover_mode or "Both").strip()
		if mode not in VALID_FAILOVER_MODES:
			frappe.throw(f"Invalid LLM failover mode: {mode}")

		self._validate_llm_providers()

		if self.disabled_analyze_tools:
			for name in self._parse_disabled_tools():
				if name not in KNOWN_ANALYZE_TOOLS:
					frappe.throw(f"Unknown analyze tool: {name}")

		if self.disabled_insight_tools:
			for name in self._parse_disabled_insight_tools():
				if name not in KNOWN_INSIGHT_TOOLS:
					frappe.throw(f"Unknown insight tool: {name}")

		self._dedupe_insight_disallow_rows()

		ensure_pilot_english_language_row(self)

		seen_langs = set()
		for row in self.get("enabled_languages") or []:
			if not row.language:
				continue
			lang_code = _language_link_code(row.language)
			if lang_code == "en":
				if not cint(row.enabled):
					frappe.throw("English must stay enabled in Pilot.")
				continue
			if row.language in seen_langs:
				frappe.throw(f"Duplicate language: {row.language}")
			seen_langs.add(row.language)

		tab = (self.default_tab or "").strip()
		if tab in ("Analyze", "Guide"):
			self.default_tab = "Advisor"

	def on_update(self):
		frappe.clear_cache(doctype="Pilot Settings")

	def _clamp_int(self, fieldname, low, high):
		val = int(self.get(fieldname) or 0)
		if not val or val < low or val > high:
			default = DEFAULTS.get(fieldname)
			try:
				default_int = int(default)
			except (TypeError, ValueError):
				default_int = low
			if not val:
				val = default_int if default_int >= low else low
			self.set(fieldname, max(low, min(high, val)))

	def _clamp_float(self, fieldname, low, high):
		val = float(self.get(fieldname) or 0)
		if val < low or val > high:
			self.set(fieldname, max(low, min(high, val)))

	def _ensure_insight_defaults(self):
		for fieldname in (
			"insight_max_passes",
			"insight_max_tokens",
			"insight_max_tokens_final",
			"insight_max_report_rows",
			"insight_max_list_rows",
			"insight_max_tool_json_chars",
			"insight_kpi_cache_ttl",
		):
			if not int(self.get(fieldname) or 0):
				default = DEFAULTS.get(fieldname)
				if default:
					self.set(fieldname, default)
		if not float(self.get("insight_temperature") or 0):
			default = DEFAULTS.get("insight_temperature")
			if default:
				self.set("insight_temperature", default)
		if not (self.get("insight_model") or "").strip():
			self.set("insight_model", DEFAULTS.get("insight_model"))

	def _parse_disabled_tools(self):
		return [t.strip() for t in (self.disabled_analyze_tools or "").split(",") if t.strip()]

	def _parse_disabled_insight_tools(self):
		return [t.strip() for t in (self.disabled_insight_tools or "").split(",") if t.strip()]

	def _dedupe_insight_disallow_rows(self):
		seen_modules: set[str] = set()
		for row in self.get("insight_disallowed_modules") or []:
			if not row.module or row.module in seen_modules:
				continue
			seen_modules.add(row.module)
		seen_doctypes: set[str] = set()
		for row in self.get("insight_disallowed_doctypes") or []:
			if not row.doctype or row.doctype in seen_doctypes:
				continue
			seen_doctypes.add(row.doctype)

	def _validate_llm_providers(self):
		if frappe.flags.in_install or frappe.flags.in_migrate:
			return
		for row in self.get("llm_providers") or []:
			row.limited = ""
			link = row.get("llm_provider") or row.get("provider")
			if link:
				master = get_llm_provider_master(link)
				if master:
					row.model = resolve_row_model(row, master)

		rows = [r for r in (self.get("llm_providers") or []) if cint(r.enabled)]
		seen_priority = set()
		for row in rows:
			link = row.get("llm_provider") or row.get("provider")
			if not link:
				frappe.throw("Each enabled LLM provider row must link to an LLM Provider.")
			master = get_llm_provider_master(link)
			if not master or not cint(master.is_active):
				frappe.throw(f"LLM Provider {link} is not active.")
			priority = int(row.priority or 0)
			if priority in seen_priority:
				frappe.throw(f"Duplicate priority {priority} among enabled LLM provider rows.")
			seen_priority.add(priority)
			if not resolve_row_api_key(row, master):
				frappe.throw(
					f"No API key for enabled row {row.row_label or link} "
					f"(priority {priority}). Add a key or site_config fallback."
				)
