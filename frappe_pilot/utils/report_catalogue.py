# Report discovery for Insight tab

from __future__ import annotations

import frappe

from frappe_pilot.utils.report_defaults import erpnext_installed
from frappe_pilot.utils.settings import get_insight_disallowed_modules

APP_MODULE_MAP = {
	"erpnext": [
		"Accounts",
		"Selling",
		"Buying",
		"Stock",
		"CRM",
		"Projects",
		"Manufacturing",
	],
	"hrms": ["HR"],
	"helpdesk": ["Helpdesk"],
}

# Fallback catalogue for chip preset validation (from HUF)
REPORT_CATALOGUE = {
	"Accounts": [
		"Balance Sheet",
		"Profit and Loss Statement",
		"Accounts Receivable Summary",
		"Accounts Payable",
		"Budget Variance Report",
	],
	"Selling": ["Sales Analytics", "Sales Order Analysis"],
	"Stock": ["Item Shortage Report", "Stock Balance"],
	"CRM": ["Opportunity Summary by Sales Stage"],
	"HR": ["Employee Analytics"],
	"Helpdesk": ["Ticket Summary"],
}


def _installed_apps() -> list[str]:
	try:
		return frappe.get_installed_apps() or []
	except Exception:
		return []


def _hook_modules() -> list[str]:
	modules = []
	for hook_modules in frappe.get_hooks("pilot_insight_modules") or []:
		if isinstance(hook_modules, (list, tuple)):
			modules.extend(hook_modules)
		elif isinstance(hook_modules, str):
			modules.append(hook_modules)
	return modules


def detect_insight_modules() -> set[str]:
	if not erpnext_installed():
		return set()

	modules: set[str] = set()
	installed = set(_installed_apps())

	for app, app_modules in APP_MODULE_MAP.items():
		if app in installed:
			modules.update(app_modules)

	modules.update(_hook_modules())

	disallowed = get_insight_disallowed_modules()
	if disallowed:
		modules -= disallowed

	return modules


def _user_can_access_report(report_name: str, user: str | None = None) -> bool:
	user = user or frappe.session.user
	try:
		from frappe.desk.query_report import get_report_doc

		get_report_doc(report_name)
		return True
	except Exception:
		return bool(frappe.db.exists("Report", report_name))


def discover_reports(
	module: str = "",
	search: str = "",
	user: str | None = None,
	limit: int = 50,
) -> dict:
	if not erpnext_installed():
		return {"error": "ERPNext is not installed.", "reports": []}

	effective_modules = detect_insight_modules()
	if not effective_modules:
		return {"error": "No report modules available.", "reports": []}

	filters: dict = {"disabled": 0, "report_type": ("in", ["Script Report", "Query Report", "Custom Report"])}
	if module:
		mod_key = next((m for m in effective_modules if m.lower() == module.lower()), None)
		if not mod_key:
			return {
				"error": f"Module '{module}' is not available or is excluded.",
				"available_modules": sorted(effective_modules),
				"reports": [],
			}
		filters["module"] = mod_key
	else:
		filters["module"] = ("in", list(effective_modules))

	rows = frappe.get_all(
		"Report",
		filters=filters,
		fields=["name", "report_name", "module", "ref_doctype"],
		order_by="module asc, name asc",
		limit=limit * 3,
	)

	search_l = (search or "").strip().lower()
	reports = []
	for row in rows:
		name = row.report_name or row.name
		if search_l and search_l not in name.lower() and search_l not in (row.module or "").lower():
			continue
		if not _user_can_access_report(row.name, user):
			continue
		reports.append(
			{
				"name": name,
				"report_doc": row.name,
				"module": row.module,
				"ref_doctype": row.ref_doctype,
			}
		)
		if len(reports) >= limit:
			break

	by_module: dict[str, list[str]] = {}
	for r in reports:
		by_module.setdefault(r["module"] or "Other", []).append(r["name"])

	return {"reports": reports, "by_module": by_module, "modules": sorted(effective_modules)}


def report_exists(report_name: str) -> bool:
	if frappe.db.exists("Report", report_name):
		return True
	return bool(
		frappe.db.exists("Report", {"report_name": report_name})
	)


def resolve_report_docname(report_name: str) -> str | None:
	if frappe.db.exists("Report", report_name):
		return report_name
	match = frappe.db.get_value("Report", {"report_name": report_name}, "name")
	return match
