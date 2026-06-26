# Copyright (c) 2026, Frappe Pilot and contributors

import frappe

from frappe_pilot.api.config import user_has_pilot_access


@frappe.whitelist()
def get_pilot_stats():
	"""Live KPIs for /pilot SPA home (mirrors desk number cards)."""
	if not user_has_pilot_access():
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

	total_runs = frappe.db.count("Pilot Agent Run")
	success_count = frappe.db.count("Pilot Agent Run", {"status": "Success"})
	success_rate = round((success_count / total_runs) * 100, 1) if total_runs else 0
	total_cost = frappe.db.sql(
		"SELECT COALESCE(SUM(total_cost), 0) FROM `tabPilot Agent Run`",
	)[0][0]
	currency = frappe.defaults.get_global_default("currency") or "USD"

	return {
		"total_runs": total_runs,
		"success_count": success_count,
		"success_rate": success_rate,
		"total_cost": float(total_cost or 0),
		"currency": currency,
	}
