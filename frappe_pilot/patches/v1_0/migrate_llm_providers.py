# Migrate flat API key fields to Pilot LLM Provider child table

import frappe

from frappe_pilot.utils.llm_catalog import ensure_llm_provider_catalog, resolve_provider_link


def execute():
	ensure_llm_provider_catalog()

	if not frappe.db.exists("DocType", "Pilot Settings"):
		return
	if not frappe.db.exists("Pilot Settings", "Pilot Settings"):
		return

	doc = frappe.get_doc("Pilot Settings", "Pilot Settings")
	if doc.get("llm_providers"):
		return

	meta = frappe.get_meta("Pilot Settings")
	legacy_provider = doc.get("llm_provider") or "Groq"
	rows = []
	priority = 1

	primary_link = resolve_provider_link(legacy_provider) or "Groq"
	primary_key = _read_password(doc, "groq_api_key") if primary_link == "Groq" else None
	if primary_link == "OpenAI":
		primary_key = _read_password(doc, "openai_api_key")
	elif primary_link == "Gemini":
		primary_key = _read_password(doc, "gemini_api_key")
	elif not primary_key:
		primary_key = _read_password(doc, "groq_api_key")

	if primary_key or _has_site_key(primary_link):
		rows.append(
			{
				"enabled": 1,
				"priority": priority,
				"llm_provider": primary_link,
				"row_label": "",
				"model": "",
				"api_key": primary_key or "",
			}
		)
		priority += 1

	backup_key = _read_password(doc, "groq_api_key_backup")
	if backup_key:
		rows.append(
			{
				"enabled": 1,
				"priority": priority,
				"llm_provider": "Groq",
				"row_label": "Groq — Backup",
				"model": "",
				"api_key": backup_key,
			}
		)
		priority += 1

	for field, provider_name in (
		("groq_api_key", "Groq"),
		("openai_api_key", "OpenAI"),
		("gemini_api_key", "Gemini"),
	):
		if field == "groq_api_key" and primary_link == "Groq":
			continue
		if field == "openai_api_key" and primary_link == "OpenAI":
			continue
		if field == "gemini_api_key" and primary_link == "Gemini":
			continue
		key = _read_password(doc, field)
		if key or _has_site_key(provider_name):
			rows.append(
				{
					"enabled": 1,
					"priority": priority,
					"llm_provider": provider_name,
					"row_label": "",
					"model": "",
					"api_key": key or "",
				}
			)
			priority += 1

	if not rows:
		rows.append(
			{
				"enabled": 1,
				"priority": 1,
				"llm_provider": "Groq",
				"row_label": "",
				"model": "",
				"api_key": "",
			}
		)

	doc.set("llm_providers", [])
	for row in rows:
		doc.append("llm_providers", row)

	doc.llm_failover_mode = doc.get("llm_failover_mode") or "Both"
	doc.save(ignore_permissions=True)

	for fieldname in (
		"llm_provider",
		"groq_api_key",
		"groq_api_key_backup",
		"openai_api_key",
		"gemini_api_key",
	):
		if meta.has_field(fieldname):
			frappe.db.set_value("Pilot Settings", "Pilot Settings", fieldname, None)

	frappe.db.commit()


def _read_password(doc, fieldname):
	try:
		return doc.get_password(fieldname, raise_exception=False)
	except Exception:
		return None


def _has_site_key(provider_name):
	from frappe_pilot.utils.llm_catalog import LLM_PROVIDER_CATALOG

	for entry in LLM_PROVIDER_CATALOG:
		if entry["provider_name"] != provider_name:
			continue
		for key in entry.get("site_config_keys", "").split(","):
			key = key.strip()
			if key and frappe.conf.get(key):
				return True
	return False
