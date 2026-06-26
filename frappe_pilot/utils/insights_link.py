# Optional Frappe Insights workbook links for Insight micro-reports

from __future__ import annotations

import frappe

from frappe_pilot.utils.settings import cint, get_pilot_settings


def insights_app_installed() -> bool:
	try:
		return "insights" in frappe.get_installed_apps()
	except Exception:
		return False


def attach_insights_links(sources: list | None) -> list:
	if not sources:
		return []
	if not insights_app_installed():
		return sources
	settings = get_pilot_settings()
	if not cint(settings.get("insight_link_insights_app")):
		return sources

	out = []
	for src in sources:
		item = dict(src)
		name = (item.get("name") or "").strip()
		if name and frappe.db.exists("Insights Query", {"title": name}):
			item["insights_workbook"] = f"/insights/query/{frappe.db.get_value('Insights Query', {'title': name}, 'name')}"
		out.append(item)
	return out
