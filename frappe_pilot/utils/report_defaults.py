# Insight report filter defaults (company, fiscal year, dates)

from __future__ import annotations

from datetime import date
from typing import Any

import frappe


def erpnext_installed() -> bool:
	try:
		return "erpnext" in frappe.get_installed_apps()
	except Exception:
		return False


def resolve_company(context: dict | None = None) -> str | None:
	context = context or {}
	company = context.get("company")
	if company:
		return company
	return (
		frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
	)


def resolve_fiscal_year(context: dict | None = None) -> str | None:
	context = context or {}
	fy = context.get("fiscal_year")
	if fy:
		return fy
	user_fy = frappe.defaults.get_user_default("Fiscal Year")
	if user_fy:
		return user_fy
	if erpnext_installed():
		try:
			from erpnext.accounts.utils import get_fiscal_year

			fy_row = get_fiscal_year(frappe.utils.today(), as_dict=True, raise_on_missing=False)
			if fy_row:
				return fy_row.name
		except Exception:
			pass
	return None


def get_fiscal_year_doc(fiscal_year: str | None):
	if not fiscal_year:
		return None
	try:
		if frappe.db.exists("Fiscal Year", fiscal_year):
			return frappe.get_doc("Fiscal Year", fiscal_year)
		fy_list = frappe.get_all(
			"Fiscal Year",
			filters={"name": ("like", f"%{fiscal_year}%")},
			limit=1,
		)
		if fy_list:
			return frappe.get_doc("Fiscal Year", fy_list[0].name)
	except Exception:
		return None
	return None


def month_to_date_range(year: int, month: int) -> tuple[date, date]:
	from calendar import monthrange

	last_day = monthrange(year, month)[1]
	return date(year, month, 1), date(year, month, last_day)


def current_month_range() -> tuple[date, date]:
	today = frappe.utils.getdate()
	return month_to_date_range(today.year, today.month)


def week_date_range() -> tuple[date, date]:
	today = frappe.utils.getdate()
	from frappe.utils import add_days

	return today, add_days(today, 7)


def apply_report_filter_defaults(filters: dict | None, context: dict | None = None) -> dict:
	filters = dict(filters or {})
	context = context or {}

	if not filters.get("company"):
		company = resolve_company(context)
		if company:
			filters["company"] = company

	if not filters.get("from_date") and not filters.get("to_date"):
		if context.get("from_date"):
			filters["from_date"] = context["from_date"]
		if context.get("to_date"):
			filters["to_date"] = context["to_date"]

		if not filters.get("from_date") and not filters.get("to_date"):
			fy_name = filters.get("fiscal_year") or resolve_fiscal_year(context)
			fy_doc = get_fiscal_year_doc(fy_name)
			if fy_doc:
				filters["from_date"] = str(fy_doc.year_start_date)
				filters["to_date"] = str(fy_doc.year_end_date)
				filters["period_start_date"] = fy_doc.year_start_date
				filters["period_end_date"] = fy_doc.year_end_date
				filters["fiscal_year"] = fy_doc.name

	if not filters.get("periodicity"):
		filters["periodicity"] = "Yearly"

	return _normalize_erpnext_financial_filters(filters, context)


def _normalize_erpnext_financial_filters(filters: dict, context: dict | None = None) -> dict:
	"""Map Insight generic date keys to ERPNext financial report filter fields."""
	if filters.get("from_date") and not filters.get("period_start_date"):
		filters["period_start_date"] = filters["from_date"]
	if filters.get("to_date") and not filters.get("period_end_date"):
		filters["period_end_date"] = filters["to_date"]

	has_period = bool(filters.get("period_start_date") and filters.get("period_end_date"))
	fy_name = filters.get("fiscal_year") or filters.get("from_fiscal_year") or resolve_fiscal_year(context or filters)

	if not filters.get("filter_based_on"):
		periodicity = filters.get("periodicity") or "Yearly"
		if periodicity in ("Monthly", "Quarterly", "Half-Yearly") and has_period:
			filters["filter_based_on"] = "Date Range"
		elif periodicity == "Yearly" and fy_name and (not has_period or not _is_month_bound_range(filters)):
			filters["filter_based_on"] = "Fiscal Year"
		elif has_period:
			filters["filter_based_on"] = "Date Range"
		elif fy_name:
			filters["filter_based_on"] = "Fiscal Year"
		else:
			filters["filter_based_on"] = "Date Range"

	if filters["filter_based_on"] == "Fiscal Year":
		if not fy_name and has_period:
			try:
				from erpnext.accounts.utils import get_fiscal_year

				fy_name = get_fiscal_year(filters["period_start_date"], company=filters.get("company"))[0]
			except Exception:
				fy_name = resolve_fiscal_year(context or filters)
		if fy_name:
			filters.setdefault("fiscal_year", fy_name)
			filters.setdefault("from_fiscal_year", fy_name)
			filters.setdefault("to_fiscal_year", filters.get("to_fiscal_year") or fy_name)
			fy_doc = get_fiscal_year_doc(fy_name)
			if fy_doc and not has_period:
				filters["period_start_date"] = fy_doc.year_start_date
				filters["period_end_date"] = fy_doc.year_end_date
				filters["from_date"] = str(fy_doc.year_start_date)
				filters["to_date"] = str(fy_doc.year_end_date)

	return filters


def _is_month_bound_range(filters: dict) -> bool:
	"""True when period looks like a partial month range (e.g. MTD), not full FY."""
	try:
		from frappe.utils import getdate

		start = getdate(filters.get("period_start_date"))
		end = getdate(filters.get("period_end_date"))
		return (end - start).days < 300
	except Exception:
		return False


def resolve_insight_context(context: dict | None = None) -> dict[str, Any]:
	context = dict(context or {})
	company = resolve_company(context)
	fy = resolve_fiscal_year(context)
	result = {
		"company": company,
		"fiscal_year": fy,
		"from_date": context.get("from_date"),
		"to_date": context.get("to_date"),
	}
	if not result.get("from_date") or not result.get("to_date"):
		fy_doc = get_fiscal_year_doc(fy)
		if fy_doc:
			result["from_date"] = str(fy_doc.year_start_date)
			result["to_date"] = str(fy_doc.year_end_date)
	if company and frappe.db.exists("Company", company):
		result["currency"] = frappe.db.get_value("Company", company, "default_currency")
	return result


def get_company_currency(company: str | None) -> str | None:
	if not company or not frappe.db.exists("Company", company):
		return None
	return frappe.db.get_value("Company", company, "default_currency")
