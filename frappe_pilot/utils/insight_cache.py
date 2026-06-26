# KPI snapshot cache for Insight report runs

from __future__ import annotations

import hashlib
import json

import frappe

from frappe_pilot.utils.settings import get_insight_config


def _cache_key(user: str, report_name: str, filters: dict, company: str = "") -> str:
	payload = json.dumps(
		{"user": user, "company": company or "", "report": report_name, "filters": filters},
		sort_keys=True,
		default=str,
	)
	digest = hashlib.sha256(payload.encode()).hexdigest()[:32]
	return f"pilot_insight_kpi:{digest}"


def get_cached_report_result(
	report_name: str,
	filters: dict | None,
	user: str | None = None,
	company: str | None = None,
):
	cfg = get_insight_config()
	ttl = int(cfg.get("kpi_cache_ttl") or 0)
	if ttl <= 0:
		return None, ""

	user = user or frappe.session.user
	company = company or (filters or {}).get("company") or ""
	key = _cache_key(user, report_name, filters or {}, company)
	cached = frappe.cache.get_value(key)
	if cached:
		return cached, key
	return None, key


def set_cached_report_result(
	report_name: str,
	filters: dict | None,
	result: dict,
	user: str | None = None,
	company: str | None = None,
) -> str:
	cfg = get_insight_config()
	ttl = int(cfg.get("kpi_cache_ttl") or 0)
	if ttl <= 0:
		return ""

	user = user or frappe.session.user
	company = company or (filters or {}).get("company") or ""
	key = _cache_key(user, report_name, filters or {}, company)
	frappe.cache.set_value(key, result, expires_in_sec=ttl)
	return key
