# Copyright (c) 2026, Frappe Pilot and contributors

import frappe
from frappe.model.document import Document

from frappe_pilot.utils.settings import (
	_language_link_code,
	cint,
	ensure_pilot_english_language_row,
)

VALID_PROVIDERS = frozenset({"Groq", "OpenAI", "Gemini"})
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


class PilotSettings(Document):
	def validate(self):
		self._clamp_int("analyze_max_passes", 1, 10)
		self._clamp_int("max_list_rows", 1, 100)
		self._clamp_int("max_report_rows", 1, 100)
		self._clamp_int("context_char_budget", 1000, 20000)
		self._clamp_int("max_tool_json_chars", 1000, 20000)
		self._clamp_int("preview_expiry_minutes", 1, 60)
		self._clamp_float("analyze_temperature", 0.0, 1.0)
		self._clamp_float("diagnose_temperature", 0.0, 1.0)
		self._clamp_float("guide_temperature", 0.0, 1.0)
		self._clamp_float("build_temperature", 0.0, 1.0)
		self._clamp_float("build_temperature_fallback", 0.0, 1.0)

		if self.llm_provider and self.llm_provider not in VALID_PROVIDERS:
			frappe.throw(f"Invalid LLM provider: {self.llm_provider}")

		if self.disabled_analyze_tools:
			for name in self._parse_disabled_tools():
				if name not in KNOWN_ANALYZE_TOOLS:
					frappe.throw(f"Unknown analyze tool: {name}")

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
		if val and (val < low or val > high):
			self.set(fieldname, max(low, min(high, val)))

	def _clamp_float(self, fieldname, low, high):
		val = float(self.get(fieldname) or 0)
		if val < low or val > high:
			self.set(fieldname, max(low, min(high, val)))

	def _parse_disabled_tools(self):
		return [t.strip() for t in (self.disabled_analyze_tools or "").split(",") if t.strip()]
