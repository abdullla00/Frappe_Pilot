# Pilot bootstrap config for sidebar (non-secret)

import frappe

from frappe_pilot.utils.llm import get_active_provider, has_api_key
from frappe_pilot.utils.i18n import get_ui_bundle
from frappe_pilot.utils.settings import (
	cint,
	get_advisor_config,
	get_chip_locale_scope,
	get_enabled_languages,
	get_pilot_language_options,
	get_pilot_settings,
	user_has_build_access,
	user_has_pilot_access,
)


def _normalize_default_tab(raw):
	val = (raw or "Advisor").strip().lower()
	if val in ("analyze", "guide"):
		return "advisor"
	if val == "build":
		return "build"
	return "advisor"


def _normalize_sidebar_position(raw):
	val = (raw or "Right").strip().lower()
	if val in ("left", "bottom"):
		return val
	return "right"


@frappe.whitelist()
def get_pilot_config():
	settings = get_pilot_settings()
	langs = get_enabled_languages()
	language_options = get_pilot_language_options()
	advisor_cfg = get_advisor_config()
	return {
		"enabled": bool(cint(settings.get("enable_pilot"))),
		"languages": langs,
		"language_options": language_options,
		"chip_locale_scope": get_chip_locale_scope(),
		"primary_locale": "en",
		"ui_strings": get_ui_bundle(langs),
		"has_api_key": has_api_key(),
		"active_provider": get_active_provider(),
		"can_configure_api": "System Manager" in frappe.get_roles(),
		"api_setup_route": ["Form", "Pilot Settings", "Pilot Settings"],
		"default_tab": _normalize_default_tab(settings.get("default_tab")),
		"sidebar_position": _normalize_sidebar_position(settings.get("sidebar_position")),
		"advisor_enabled": bool(advisor_cfg.get("enabled")),
		"analyze_enabled": bool(advisor_cfg.get("enabled")),
		"guide_enabled": bool(advisor_cfg.get("enabled")),
		"build_enabled": bool(cint(settings.get("build_enabled"))),
		"show_evidence": bool(cint(settings.get("show_evidence_line"))),
		"auto_navigate": bool(cint(settings.get("auto_navigate"))),
		"close_sidebar_on_navigate": bool(cint(settings.get("close_sidebar_on_navigate"))),
		"can_access_pilot": user_has_pilot_access(),
		"can_access_build": user_has_build_access(),
		"is_system_manager": "System Manager" in frappe.get_roles(),
	}


@frappe.whitelist()
def test_api_connection():
	if "System Manager" not in frappe.get_roles():
		frappe.throw("Only System Manager can test the API connection.", frappe.PermissionError)

	if not has_api_key():
		return {"ok": False, "message": "No API key configured for the active provider."}

	from frappe_pilot.utils.llm import chat_completion, get_active_provider, get_effective_api_key

	provider = get_active_provider()
	settings = get_pilot_settings()
	model = settings.get("analyze_model") or "llama-3.3-70b-versatile"
	primary = get_effective_api_key(provider)
	backup = get_effective_api_key(provider, use_backup=True) if provider == "Groq" else None
	lines = []
	reply = ""

	try:
		response, _, label = chat_completion(
			messages=[
				{"role": "system", "content": "Reply with exactly: ok"},
				{"role": "user", "content": "ping"},
			],
			model=model,
			max_tokens=10,
			temperature=0,
		)
		reply = response.choices[0].message.content or ""
		lines.append(f"Primary key: OK ({label})")
	except Exception as exc:
		lines.append(f"Primary key: failed — {exc}")

	if provider == "Groq" and backup:
		if backup == primary:
			lines.append("Backup key: skipped (same as primary)")
		else:
			try:
				from groq import Groq
				Groq(api_key=backup).chat.completions.create(
					model=model,
					messages=[{"role": "user", "content": "ping"}],
					max_tokens=5,
					temperature=0,
				)
				lines.append(
					"Backup key: OK (separate key; same Groq org shares daily token quota)"
				)
			except Exception as exc:
				lines.append(f"Backup key: failed — {exc}")

	ok = any("OK" in line for line in lines)
	return {
		"ok": ok,
		"message": "\n".join(lines),
		"reply_preview": (reply or "")[:80] if ok else "",
	}
