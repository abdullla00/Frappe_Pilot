# LLM client resolution — Pilot Settings + site_config fallback

import frappe

from frappe_pilot.utils.settings import get_pilot_settings

PROVIDER_SETTINGS_FIELDS = {
	"Groq": ("groq_api_key", "groq_api_key_backup"),
	"OpenAI": ("openai_api_key",),
	"Gemini": ("gemini_api_key",),
}

PROVIDER_SITE_CONFIG_KEYS = {
	"Groq": ("groq_api_key", "groq_api_key_2"),
	"OpenAI": ("openai_api_key", "gpt_api_key"),
	"Gemini": ("gemini_api_key",),
}

DEFAULT_MODELS = {
	"Groq": "llama-3.3-70b-versatile",
	"OpenAI": "gpt-4o-mini",
	"Gemini": "gemini-1.5-flash",
}


def get_active_provider():
	settings = get_pilot_settings()
	return settings.get("llm_provider") or "Groq"


def get_effective_api_key(provider=None, *, use_backup=False):
	provider = provider or get_active_provider()
	settings = get_pilot_settings()

	field_names = PROVIDER_SETTINGS_FIELDS.get(provider, ())
	site_keys = PROVIDER_SITE_CONFIG_KEYS.get(provider, ())

	if provider == "Groq" and use_backup:
		field_names = ("groq_api_key_backup",)
		site_keys = ("groq_api_key_2",)

	for fieldname in field_names:
		try:
			key = settings.get_password(fieldname, raise_exception=False)
		except Exception:
			key = None
		if key:
			return key

	for conf_key in site_keys:
		key = frappe.conf.get(conf_key)
		if key:
			return key

	return None


def has_api_key(provider=None):
	provider = provider or get_active_provider()
	if get_effective_api_key(provider):
		return True
	if provider == "Groq" and get_effective_api_key(provider, use_backup=True):
		return True
	return False


def get_llm_client(provider=None):
	"""Return (client, provider_label) or (None, None)."""
	provider = provider or get_active_provider()
	primary_key = get_effective_api_key(provider)
	backup_key = None
	if provider == "Groq":
		backup_key = get_effective_api_key(provider, use_backup=True)

	if not primary_key and not backup_key:
		return None, None

	if provider == "Groq":
		from groq import Groq
		key = primary_key or backup_key
		label = "primary" if primary_key else "backup"
		return Groq(api_key=key), label

	if provider == "OpenAI":
		try:
			from openai import OpenAI
		except ImportError:
			return None, "missing_sdk"
		return OpenAI(api_key=primary_key), "openai"

	if provider == "Gemini":
		try:
			import google.generativeai as genai
		except ImportError:
			return None, "missing_sdk"
		genai.configure(api_key=primary_key)
		return genai, "gemini"

	return None, None


def chat_completion(*, messages, model=None, max_tokens=600, temperature=0.25, tools=None, tool_choice=None):
	"""
	Unified chat completion across providers.
	Returns (response_object, provider, key_label) or raises.
	"""
	provider = get_active_provider()
	client, key_label = get_llm_client(provider)

	if not client:
		raise frappe.ValidationError(_no_key_message(provider))

	model = model or _resolve_model(provider)

	if provider == "Groq":
		kwargs = dict(model=model, messages=messages, max_tokens=max_tokens, temperature=temperature)
		if tools:
			kwargs["tools"] = tools
			kwargs["tool_choice"] = tool_choice or "auto"
		try:
			return client.chat.completions.create(**kwargs), provider, key_label
		except Exception as exc:
			if _is_rate_limit(exc) and key_label == "primary":
				primary_key = get_effective_api_key("Groq")
				backup = get_effective_api_key("Groq", use_backup=True)
				if backup and backup != primary_key:
					from groq import Groq
					try:
						backup_client = Groq(api_key=backup)
						return backup_client.chat.completions.create(**kwargs), provider, "backup"
					except Exception as backup_exc:
						if _is_rate_limit(backup_exc):
							raise frappe.ValidationError(
								groq_rate_limit_message(backup_exc, used_backup=True)
							) from backup_exc
						raise
				elif _is_rate_limit(exc):
					raise frappe.ValidationError(groq_rate_limit_message(exc)) from exc
			raise

	if provider == "OpenAI":
		kwargs = dict(model=model, messages=messages, max_tokens=max_tokens, temperature=temperature)
		if tools:
			kwargs["tools"] = tools
			kwargs["tool_choice"] = tool_choice or "auto"
		return client.chat.completions.create(**kwargs), provider, key_label

	if provider == "Gemini":
		import google.generativeai as genai
		system = next((m["content"] for m in messages if m["role"] == "system"), "")
		history = [m for m in messages if m["role"] != "system"]
		prompt_parts = []
		if system:
			prompt_parts.append(f"System:\n{system}\n")
		for m in history:
			prompt_parts.append(f"{m['role']}: {m.get('content', '')}")
		model_obj = genai.GenerativeModel(model)
		response = model_obj.generate_content(
			"\n".join(prompt_parts),
			generation_config=genai.types.GenerationConfig(
				max_output_tokens=max_tokens,
				temperature=temperature,
			),
		)
		return _GeminiResponseAdapter(response), provider, key_label

	raise frappe.ValidationError(f"Unsupported provider: {provider}")




def groq_rate_limit_message(exc, *, used_backup=False):
	exc_str = str(exc)
	wait = __import__("re").search(r"try again in ([^.,']+)", exc_str)
	wait_msg = f" Try again in {wait.group(1)}." if wait else ""
	org_note = (
		" Groq daily token limits are per **organization**, not per API key — "
		"a backup key in the same Groq account shares the same quota."
	)
	if used_backup:
		return (
			"Groq rate limit reached on both primary and backup API keys."
			+ wait_msg
			+ org_note
			+ " Wait for reset, use a key from a different Groq org, or switch LLM provider in Pilot Settings."
		)
	return (
		"Groq rate limit reached on the primary API key."
		+ wait_msg
		+ org_note
		+ " Backup key will be tried automatically if configured."
	)

def _resolve_model(provider):
	settings = get_pilot_settings()
	if provider == "Groq":
		return settings.get("analyze_model") or DEFAULT_MODELS["Groq"]
	if provider == "OpenAI":
		return settings.get("analyze_model") or DEFAULT_MODELS["OpenAI"]
	return settings.get("analyze_model") or DEFAULT_MODELS["Gemini"]


def _is_rate_limit(exc):
	exc_str = str(exc)
	return "rate_limit" in exc_str.lower() or "429" in exc_str


def _no_key_message(provider):
	return (
		f"No API key configured for {provider}. "
		"Open Pilot Settings and add your key, or set it in site_config.json."
	)


class _GeminiResponseAdapter:
	"""Minimal adapter so Gemini responses resemble OpenAI message objects."""

	def __init__(self, gemini_response):
		text = ""
		try:
			text = gemini_response.text or ""
		except Exception:
			text = str(gemini_response)
		self.choices = [_GeminiChoice(text)]


class _GeminiChoice:
	def __init__(self, text):
		self.message = _GeminiMessage(text)
		self.tool_calls = None


class _GeminiMessage:
	def __init__(self, text):
		self.content = text
