# LLM client resolution — Pilot LLM Provider child rows + LLM Provider master catalog

import re
import time

import frappe

from frappe_pilot.utils.llm_catalog import get_llm_provider_master, resolve_row_model
from frappe_pilot.utils.settings import get_pilot_settings

SESSION_ROW_CACHE_PREFIX = "pilot_llm_row:"
EXHAUSTED_ROW_CACHE_PREFIX = "pilot_llm_exhausted:"
CURRENT_ROW_CACHE_KEY = "pilot_llm_current_row"
EXHAUSTED_DEFAULT_TTL = 3600


class ProviderExhaustedError(frappe.ValidationError):
	def __init__(self, message, *, payload=None):
		super().__init__(message)
		self.payload = payload or {}


def _parse_site_config_keys(raw):
	if not raw:
		return ()
	return tuple(k.strip() for k in str(raw).split(",") if k.strip())


def resolve_row_api_key(row, master=None):
	"""Return API key for a child row: password field, then master site_config keys."""
	master = master or get_llm_provider_master(row.llm_provider)
	try:
		key = row.get_password("api_key", raise_exception=False)
	except Exception:
		key = None
	if key:
		return key
	if not master:
		return None
	for conf_key in _parse_site_config_keys(master.site_config_keys):
		val = frappe.conf.get(conf_key)
		if val:
			return val
	return None


def _enrich_row(row):
	master = get_llm_provider_master(row.llm_provider)
	if not master:
		return None
	api_key = resolve_row_api_key(row, master)
	return {
		"name": row.name,
		"priority": int(row.priority or 0),
		"row_label": (row.row_label or "").strip(),
		"enabled": bool(int(row.enabled or 0)),
		"model": resolve_row_model(row, master),
		"provider_link": row.llm_provider,
		"provider_name": master.provider_name,
		"provider_code": master.provider_code,
		"supports_tool_calling": bool(int(master.supports_tool_calling or 0)),
		"api_key": api_key,
	}


def get_provider_rows(*, enabled_only=True, require_tool_calling=False):
	settings = get_pilot_settings()
	rows = []
	for row in settings.get("llm_providers") or []:
		if enabled_only and not int(row.enabled or 0):
			continue
		enriched = _enrich_row(row)
		if not enriched:
			continue
		if require_tool_calling and not enriched["supports_tool_calling"]:
			continue
		if enabled_only and not enriched["api_key"]:
			continue
		rows.append(enriched)
	rows.sort(key=lambda r: (r["priority"], r["name"] or ""))
	return rows


def _get_session_row_name():
	user = frappe.session.user if frappe.session else None
	if not user:
		return None
	return frappe.cache.get_value(f"{SESSION_ROW_CACHE_PREFIX}{user}")


def _row_public(row):
	if not row:
		return None
	return {
		"name": row["name"],
		"provider": row["provider_name"],
		"row_label": row["row_label"] or row["provider_name"],
		"priority": row["priority"],
		"model": row.get("model"),
	}


def _exhausted_cache_key(row_name):
	return f"{EXHAUSTED_ROW_CACHE_PREFIX}{row_name}"


def _parse_rate_limit_ttl(exc):
	"""Best-effort TTL from provider rate-limit error text."""
	exc_str = str(exc or "")
	wait = re.search(
		r"(?:try again in|retry in)\s+(\d+(?:\.\d+)?\s*(?:ms|s|m|h|d)?)",
		exc_str,
		re.I,
	)
	if not wait:
		return EXHAUSTED_DEFAULT_TTL
	chunk = wait.group(1).strip().lower()
	total = 0.0
	for amount, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(ms|s|m|h|d)", chunk):
		val = float(amount)
		if unit == "ms":
			total += val / 1000
		elif unit == "s":
			total += val
		elif unit == "m":
			total += val * 60
		elif unit == "h":
			total += val * 3600
		elif unit == "d":
			total += val * 86400
	if total <= 0:
		return EXHAUSTED_DEFAULT_TTL
	return int(max(60, min(total + 30, 86400)))


def mark_row_rate_limited(row, exc=None):
	ttl = _parse_rate_limit_ttl(exc)
	frappe.cache.set_value(
		_exhausted_cache_key(row["name"]),
		{
			"row_label": row.get("row_label") or row.get("provider_name"),
			"provider": row.get("provider_name"),
			"priority": row.get("priority"),
			"expires_at": time.time() + ttl,
		},
		expires_in_sec=ttl,
	)


def get_row_rate_limit_retry_sec(row_name):
	data = frappe.cache.get_value(_exhausted_cache_key(row_name))
	if not data or not isinstance(data, dict):
		return None
	expires_at = data.get("expires_at")
	if not expires_at:
		return None
	return max(0, int(expires_at - time.time()))


def is_row_rate_limited(row_name):
	return bool(frappe.cache.get_value(_exhausted_cache_key(row_name)))


def get_rate_limited_rows():
	rows = get_provider_rows()
	out = []
	for row in rows:
		if is_row_rate_limited(row["name"]):
			out.append(_row_public(row))
	return out


def record_successful_row(row):
	frappe.cache.set_value(
		CURRENT_ROW_CACHE_KEY,
		_row_public(row),
		expires_in_sec=86400 * 7,
	)


def get_recorded_current_row():
	data = frappe.cache.get_value(CURRENT_ROW_CACHE_KEY)
	if not data or not isinstance(data, dict):
		return None
	rows = {r["name"]: r for r in get_provider_rows()}
	return rows.get(data.get("name"))


def get_runtime_provider_row():
	"""Row Pilot is using or will try next (respects pin, cooldowns, last success)."""
	rows = get_provider_rows()
	if not rows:
		return None

	pinned = _get_session_row_name()
	if pinned:
		return next((r for r in rows if r["name"] == pinned), rows[0])

	rate_limited = {r["name"] for r in get_rate_limited_rows()}
	recorded = get_recorded_current_row()
	if recorded and recorded["name"] not in rate_limited:
		return recorded

	for row in rows:
		if row["name"] not in rate_limited:
			return row
	return rows[0]


def _build_row_states():
	"""Per child-row status for Pilot Settings grid coloring."""
	settings = get_pilot_settings()
	recorded = get_recorded_current_row()
	active_name = recorded["name"] if recorded else None
	if not active_name:
		current = get_runtime_provider_row()
		active_name = current["name"] if current else None
	rate_limited_names = {r["name"] for r in get_rate_limited_rows()}
	row_states = {}

	for child in settings.get("llm_providers") or []:
		if not child.name:
			continue
		enriched = _enrich_row(child)
		base = {
			"priority": int(child.priority or 0),
			"row_label": (child.row_label or "").strip() or (child.llm_provider or ""),
			"provider": child.llm_provider or "",
		}
		if enriched:
			base["row_label"] = enriched["row_label"]
			base["provider"] = enriched["provider_name"]
			base["priority"] = enriched["priority"]

		if not int(child.enabled or 0):
			row_states[child.name] = {**base, "status": "disabled"}
		elif child.name in rate_limited_names:
			entry = {**base, "status": "rate_limited"}
			retry = get_row_rate_limit_retry_sec(child.name)
			if retry is not None:
				entry["retry_in_sec"] = retry
			row_states[child.name] = entry
		elif child.name == active_name:
			row_states[child.name] = {**base, "status": "active"}
		else:
			row_states[child.name] = {**base, "status": "idle"}

	return row_states


def get_llm_runtime_status():
	"""Structured LLM status for Pilot Settings and sidebar config."""
	rows = get_provider_rows()
	settings = get_pilot_settings()
	mode = (settings.get("llm_failover_mode") or "Both").strip()
	primary = rows[0] if rows else None
	current = get_runtime_provider_row()
	rate_limited = get_rate_limited_rows()
	pinned = _get_session_row_name()
	recorded = get_recorded_current_row()
	last_success_row = _row_public(recorded) if recorded else None

	is_failover = bool(
		primary and current and primary["name"] != current["name"]
	)
	is_using_failover = is_failover or bool(rate_limited)

	status_summary = ""
	if not rows:
		status_summary = "No enabled LLM provider rows."
	elif not current:
		status_summary = "Not configured."
	else:
		cur = _row_public(current)
		status_summary = (
			f"Active: {cur['row_label']} ({cur['provider']} · P{cur['priority']})"
		)
		if rate_limited:
			parts = ", ".join(f"P{r['priority']} {r['row_label']}" for r in rate_limited)
			status_summary += f". Rate limited: {parts}"
		if pinned:
			status_summary += ". Session row pinned."

	return {
		"primary_row": _row_public(primary),
		"current_row": _row_public(current),
		"last_success_row": last_success_row,
		"is_failover_active": is_using_failover,
		"is_session_pinned": bool(pinned),
		"rate_limited_rows": rate_limited,
		"row_states": _build_row_states(),
		"status_summary": status_summary,
		"llm_failover_mode": mode,
		"enabled_row_count": len(rows),
	}


def get_active_provider_row():
	"""Primary row (priority 1) unless session-pinned."""
	return get_runtime_provider_row()


def get_active_provider():
	row = get_active_provider_row()
	return row["provider_name"] if row else None


def get_active_provider_label():
	row = get_active_provider_row()
	if not row:
		return None
	return row["row_label"] or row["provider_name"]


def has_api_key():
	return bool(get_provider_rows())


def has_tool_calling_provider():
	return bool(get_provider_rows(require_tool_calling=True))


def set_session_llm_row(row_name=None):
	"""Pin LLM child row for current user session (or clear pin)."""
	if "System Manager" not in frappe.get_roles():
		frappe.throw("Only System Manager can override the active LLM row.", frappe.PermissionError)
	user = frappe.session.user
	cache_key = f"{SESSION_ROW_CACHE_PREFIX}{user}"
	if not row_name:
		frappe.cache.delete_value(cache_key)
		return {"ok": True, "row_name": None}
	rows = get_provider_rows()
	match = next((r for r in rows if r["name"] == row_name), None)
	if not match:
		frappe.throw("Invalid or disabled LLM provider row.")
	frappe.cache.set_value(cache_key, row_name)
	return {"ok": True, "row_name": row_name, "label": match["row_label"] or match["provider_name"]}


def get_effective_api_key(provider=None):
	"""Backward-compatible helper — returns key for active or named provider row."""
	row = get_active_provider_row()
	if provider:
		rows = get_provider_rows()
		for candidate in rows:
			if candidate["provider_name"] == provider or candidate["provider_code"] == provider:
				row = candidate
				break
	return row["api_key"] if row else None


def _get_failover_chain(*, require_tool_calling=False):
	settings = get_pilot_settings()
	mode = (settings.get("llm_failover_mode") or "Both").strip()
	rows = get_provider_rows(require_tool_calling=require_tool_calling)
	pinned = _get_session_row_name()
	if pinned:
		rows = [r for r in rows if r["name"] == pinned] or rows
	elif mode == "Manual":
		rows = rows[:1]
	return rows, mode


def chat_completion(
	*,
	messages,
	model=None,
	max_tokens=600,
	temperature=0.25,
	tools=None,
	tool_choice=None,
	require_tool_calling=False,
):
	"""
	Walk enabled LLM provider rows by priority (per failover mode).
	Returns (response_object, provider_name, row_label_or_key_label).
	"""
	chain, mode = _get_failover_chain(require_tool_calling=require_tool_calling)
	if not chain:
		if require_tool_calling:
			raise frappe.ValidationError(
				"No enabled LLM provider with tool-calling support. "
				"Enable Groq, OpenAI, or Mistral in Pilot Settings > API Keys."
			)
		raise frappe.ValidationError(_no_key_message())

	exhausted = []
	last_exc = None

	for idx, row in enumerate(chain):
		if mode != "Manual" and is_row_rate_limited(row["name"]):
			continue
		# Per-row model (from child row or LLM Provider catalog) wins over Advisor/Build tab model.
		call_model = row["model"] or model
		try:
			response = call_provider(
				row,
				messages=messages,
				model=call_model,
				max_tokens=max_tokens,
				temperature=temperature,
				tools=tools,
				tool_choice=tool_choice,
			)
			record_successful_row(row)
			label = row["row_label"] or row["provider_name"]
			return response, row["provider_name"], label
		except Exception as exc:
			last_exc = exc
			if _is_rate_limit(exc):
				mark_row_rate_limited(row, exc)
				exhausted.append(
					{
						"name": row["name"],
						"provider": row["provider_name"],
						"row_label": row["row_label"] or row["provider_name"],
						"priority": row["priority"],
						"model": call_model,
					}
				)
				if mode == "Manual":
					raise frappe.ValidationError(
						llm_rate_limit_message(row, exc, manual_mode=True, next_rows=chain[idx + 1 :])
					) from exc
				continue
			raise

	suggestions = chain[len(exhausted) :] if exhausted else []
	payload = {
		"exhausted_rows": exhausted,
		"suggested_rows": [
			{
				"name": r["name"],
				"provider": r["provider_name"],
				"row_label": r["row_label"] or r["provider_name"],
				"priority": r["priority"],
			}
			for r in suggestions
		],
		"failover_mode": mode,
	}
	msg = llm_rate_limit_message(
		exhausted[-1] if exhausted else chain[-1],
		last_exc,
		all_exhausted=True,
		next_rows=suggestions,
	)
	raise ProviderExhaustedError(msg, payload=payload)


def call_provider(
	row,
	*,
	messages,
	model,
	max_tokens=600,
	temperature=0.25,
	tools=None,
	tool_choice=None,
):
	code = row["provider_code"]
	api_key = row["api_key"]
	if not api_key:
		raise frappe.ValidationError(_no_key_message(row["provider_name"]))

	if code == "groq":
		from groq import Groq

		client = Groq(api_key=api_key)
		kwargs = dict(model=model, messages=messages, max_tokens=max_tokens, temperature=temperature)
		if tools:
			kwargs["tools"] = tools
			kwargs["tool_choice"] = tool_choice or "auto"
		return client.chat.completions.create(**kwargs)

	if code == "openai":
		try:
			from openai import OpenAI
		except ImportError:
			raise frappe.ValidationError("OpenAI SDK is not installed.") from None
		client = OpenAI(api_key=api_key)
		kwargs = dict(model=model, messages=messages, max_tokens=max_tokens, temperature=temperature)
		if tools:
			kwargs["tools"] = tools
			kwargs["tool_choice"] = tool_choice or "auto"
		return client.chat.completions.create(**kwargs)

	if code == "gemini":
		try:
			import google.generativeai as genai
		except ImportError:
			raise frappe.ValidationError("Google Generative AI SDK is not installed.") from None
		genai.configure(api_key=api_key)
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
		return _GeminiResponseAdapter(response)

	if code == "mistral":
		try:
			from mistralai.client import Mistral
		except ImportError:
			raise frappe.ValidationError("Mistral AI SDK is not installed.") from None
		client = Mistral(api_key=api_key)
		kwargs = dict(
			model=model,
			messages=messages,
			max_tokens=max_tokens,
			temperature=temperature,
		)
		if tools:
			kwargs["tools"] = tools
			kwargs["tool_choice"] = tool_choice or "auto"
		return client.chat.complete(**kwargs)

	raise frappe.ValidationError(f"Unsupported provider code: {code}")


def llm_rate_limit_message(row, exc=None, *, manual_mode=False, all_exhausted=False, next_rows=None):
	exc_str = str(exc or "")
	wait = __import__("re").search(r"try again in ([^.,']+)", exc_str)
	wait_msg = f" Try again in {wait.group(1)}." if wait else ""
	label = row.get("row_label") or row.get("provider_name") or row.get("provider") or "LLM"
	provider_code = row.get("provider_code") or ""

	org_note = ""
	if provider_code == "groq":
		org_note = (
			" Groq daily token limits are per **organization**, not per API key — "
			"multiple keys in the same Groq org share the same quota."
		)

	next_hint = ""
	if next_rows:
		labels = [r.get("row_label") or r.get("provider_name") or r.get("provider") for r in next_rows]
		labels = [l for l in labels if l]
		if labels:
			next_hint = f" Next available: {', '.join(labels)}."

	if all_exhausted:
		return (
			f"Rate limit reached on all configured LLM provider rows."
			+ wait_msg
			+ org_note
			+ next_hint
			+ " Add another row in Pilot Settings or switch provider."
		)
	if manual_mode:
		return (
			f"{label} rate limit reached."
			+ wait_msg
			+ org_note
			+ next_hint
			+ " Failover is Manual — enable Auto/Both or select another row."
		)
	return f"{label} rate limit reached." + wait_msg + org_note + next_hint


def groq_rate_limit_message(exc, *, used_backup=False):
	"""Backward-compatible alias."""
	row = {"provider_name": "Groq", "provider_code": "groq", "row_label": "Groq"}
	if used_backup:
		return llm_rate_limit_message(row, exc, all_exhausted=True)
	return llm_rate_limit_message(row, exc)


def _is_rate_limit(exc):
	exc_str = str(exc).lower()
	return (
		"rate_limit" in exc_str
		or "rate limit" in exc_str
		or "429" in exc_str
		or "quota exceeded" in exc_str
	)


def _no_key_message(provider=None):
	if provider:
		return (
			f"No API key configured for {provider}. "
			"Open Pilot Settings > API Keys and add a provider row, or set site_config fallback keys."
		)
	return (
		"No LLM provider configured. "
		"Open Pilot Settings > API Keys and add at least one enabled provider row."
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
