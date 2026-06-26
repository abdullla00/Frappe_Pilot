# Copyright (c) 2026, Frappe Pilot and contributors

"""LLM cost calculation from Pilot LLM Model pricing with LiteLLM fallback."""

import frappe

_PRICING_CACHE_TTL = 600


def get_model_pricing(model_name: str) -> dict | None:
	"""Return pricing from Pilot LLM Model, cached in Redis."""
	if not model_name:
		return None

	cache_key = f"pilot_model_pricing:{model_name}"
	try:
		cached = frappe.cache().get_value(cache_key)
		if cached is not None:
			return cached if cached else None
	except Exception:
		pass

	if not frappe.db.exists("Pilot LLM Model", model_name):
		return None

	model_doc = frappe.db.get_value(
		"Pilot LLM Model",
		model_name,
		["input_cost_per_million", "output_cost_per_million"],
		as_dict=True,
	)
	if not model_doc:
		return None

	input_price = model_doc.get("input_cost_per_million")
	output_price = model_doc.get("output_cost_per_million")
	if input_price is None and output_price is None:
		try:
			frappe.cache().set_value(cache_key, {}, expires_in_sec=_PRICING_CACHE_TTL)
		except Exception:
			pass
		return None

	pricing = {
		"input_cost_per_1m_tokens": float(input_price or 0),
		"output_cost_per_1m_tokens": float(output_price or 0),
	}
	try:
		frappe.cache().set_value(cache_key, pricing, expires_in_sec=_PRICING_CACHE_TTL)
	except Exception:
		pass
	return pricing


def _calculate_from_custom_pricing(pricing: dict, input_tokens: int, output_tokens: int) -> float:
	cost = (input_tokens / 1_000_000) * pricing["input_cost_per_1m_tokens"]
	cost += (output_tokens / 1_000_000) * pricing["output_cost_per_1m_tokens"]
	return round(cost, 10)


def calculate_cost(
	model_name: str,
	input_tokens: int,
	output_tokens: int,
	cached_tokens: int = 0,
	litellm_response=None,
) -> tuple[float, str]:
	"""Return (cost_usd, source) where source is custom | litellm | unknown."""
	try:
		pricing = get_model_pricing(model_name)
		if pricing is not None:
			return _calculate_from_custom_pricing(
				pricing,
				int(input_tokens or 0),
				int(output_tokens or 0),
			), "custom"
	except Exception as e:
		frappe.log_error(f"Pilot custom cost failed for '{model_name}': {e}", "Cost Calculator")

	if litellm_response is not None:
		try:
			from litellm import completion_cost

			litellm_cost = completion_cost(completion_response=litellm_response)
			if litellm_cost and float(litellm_cost) > 0:
				return float(litellm_cost), "litellm"
		except Exception:
			pass

	return 0.0, "unknown"


def invalidate_model_pricing_cache(model_name: str):
	if not model_name:
		return
	try:
		frappe.cache().delete_value(f"pilot_model_pricing:{model_name}")
	except Exception:
		pass
