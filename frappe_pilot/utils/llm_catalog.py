# LLM Provider master catalog — seed and lookup helpers

import frappe

LLM_PROVIDER_CATALOG = (
	{
		"provider_name": "Groq",
		"provider_code": "groq",
		"default_model": "llama-3.3-70b-versatile",
		"supports_tool_calling": 1,
		"site_config_keys": "groq_api_key,groq_api_key_2",
		"sort_order": 1,
	},
	{
		"provider_name": "OpenAI",
		"provider_code": "openai",
		"default_model": "gpt-4o-mini",
		"supports_tool_calling": 1,
		"site_config_keys": "openai_api_key,gpt_api_key",
		"sort_order": 2,
	},
	{
		"provider_name": "Gemini",
		"provider_code": "gemini",
		"default_model": "gemini-flash-latest",
		"supports_tool_calling": 0,
		"site_config_keys": "gemini_api_key",
		"sort_order": 3,
	},
	{
		"provider_name": "Mistral",
		"provider_code": "mistral",
		"default_model": "mistral-small-latest",
		"supports_tool_calling": 1,
		"site_config_keys": "mistral_api_key",
		"sort_order": 4,
	},
)

PILOT_LLM_MODELS = (
	{"model_name": "llama-3.3-70b-versatile", "llm_provider": "Groq", "supports_tool_calling": 1},
	{"model_name": "gpt-4o-mini", "llm_provider": "OpenAI", "supports_tool_calling": 1},
	{"model_name": "gemini-flash-latest", "llm_provider": "Gemini", "supports_tool_calling": 0},
	{"model_name": "mistral-small-latest", "llm_provider": "Mistral", "supports_tool_calling": 1},
)

LEGACY_PROVIDER_MAP = {
	"Groq": "Groq",
	"OpenAI": "OpenAI",
	"Gemini": "Gemini",
	"Mistral": "Mistral",
	"groq": "Groq",
	"openai": "OpenAI",
	"gemini": "Gemini",
	"mistral": "Mistral",
}


def ensure_llm_provider_catalog():
	"""Insert or update standard LLM Provider master records."""
	if not frappe.db.exists("DocType", "LLM Provider"):
		return

	for entry in LLM_PROVIDER_CATALOG:
		name = entry["provider_name"]
		if frappe.db.exists("LLM Provider", name):
			doc = frappe.get_doc("LLM Provider", name)
			changed = False
			for key, val in entry.items():
				if doc.get(key) != val:
					doc.set(key, val)
					changed = True
			if not doc.get("is_active"):
				doc.is_active = 1
				changed = True
			if changed:
				doc.save(ignore_permissions=True)
		else:
			frappe.get_doc({"doctype": "LLM Provider", "is_active": 1, **entry}).insert(ignore_permissions=True)

	frappe.db.commit()


def get_llm_provider_master(link_name):
	if not link_name:
		return None
	try:
		return frappe.get_cached_doc("LLM Provider", link_name)
	except frappe.DoesNotExistError:
		return None


PROVIDER_MODEL_HINTS = {
	"groq": ("llama", "mixtral", "gemma", "qwen", "deepseek", "compound", "moonshot"),
	"mistral": ("mistral", "codestral", "pixtral", "ministral", "open-mistral"),
	"openai": ("gpt-", "o1-", "o3-", "o4-", "chatgpt"),
	"gemini": ("gemini",),
}


def model_matches_provider(model, provider_code):
	if not model or not provider_code:
		return True
	model_l = str(model).lower()
	hints = PROVIDER_MODEL_HINTS.get(str(provider_code).lower(), ())
	if not hints:
		return True
	return any(h in model_l for h in hints)


def resolve_row_model(row, master=None):
	"""Return a model name valid for the row's linked LLM Provider."""
	link = row.get("llm_provider") if isinstance(row, dict) else row.llm_provider
	master = master or get_llm_provider_master(link)
	stored = ""
	if isinstance(row, dict):
		stored = (row.get("model") or "").strip()
	else:
		stored = (row.model or "").strip()

	if not master:
		return stored or "llama-3.3-70b-versatile"

	default = (master.default_model or "").strip()
	if not stored:
		return default
	if model_matches_provider(stored, master.provider_code):
		return stored
	return default or stored


def ensure_pilot_llm_models():
	"""Seed default Pilot LLM Model rows."""
	if not frappe.db.exists("DocType", "Pilot LLM Model"):
		return

	for entry in PILOT_LLM_MODELS:
		name = f"{entry['llm_provider']}-{entry['model_name']}"
		if frappe.db.exists("Pilot LLM Model", name):
			continue
		frappe.get_doc({"doctype": "Pilot LLM Model", **entry}).insert(ignore_permissions=True)

	frappe.db.commit()


def resolve_provider_link(provider_name_or_code):
	"""Map legacy provider string to LLM Provider link name."""
	if not provider_name_or_code:
		return None
	mapped = LEGACY_PROVIDER_MAP.get(provider_name_or_code, provider_name_or_code)
	if frappe.db.exists("LLM Provider", mapped):
		return mapped
	return frappe.db.get_value(
		"LLM Provider",
		{"provider_code": str(provider_name_or_code).lower()},
		"name",
	)
