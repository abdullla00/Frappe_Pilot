# Insight chip presets — deterministic tool execution

from __future__ import annotations

import frappe

from frappe_pilot.api.insight_tools import exec_get_list_count, exec_run_report
from frappe_pilot.utils.micro_report import build_from_count_result, build_from_report_result
from frappe_pilot.utils.report_defaults import current_month_range, resolve_insight_context, week_date_range


def _mtd_filters(context: dict | None = None) -> dict:
	ctx = resolve_insight_context(context)
	from_date, to_date = current_month_range()
	filters = {
		"company": ctx.get("company"),
		"from_date": str(from_date),
		"to_date": str(to_date),
		"period_start_date": str(from_date),
		"period_end_date": str(to_date),
		"periodicity": "Monthly",
		"filter_based_on": "Date Range",
	}
	if ctx.get("fiscal_year"):
		filters["fiscal_year"] = ctx["fiscal_year"]
	return {k: v for k, v in filters.items() if v}


def _week_filters(context: dict | None = None) -> dict:
	ctx = resolve_insight_context(context)
	from_date, to_date = week_date_range()
	filters = {
		"company": ctx.get("company"),
		"from_date": str(from_date),
		"to_date": str(to_date),
	}
	return {k: v for k, v in filters.items() if v}


INSIGHT_CHIP_PRESETS = {
	"pl_this_month": {
		"label": "P&L this month",
		"tool": "run_report",
		"report_name": "Profit and Loss Statement",
		"filters_fn": _mtd_filters,
		"title": "Profit & Loss — This Month",
	},
	"cash_position": {
		"label": "Cash position",
		"tool": "run_report",
		"report_name": "Balance Sheet",
		"filters_fn": lambda ctx: {
			"company": resolve_insight_context(ctx).get("company"),
			"periodicity": "Yearly",
			"filter_based_on": "Fiscal Year",
			"fiscal_year": resolve_insight_context(ctx).get("fiscal_year"),
		},
		"title": "Cash Position",
	},
	"stock_shortage": {
		"label": "Stock below reorder",
		"tool": "run_report",
		"report_name": "Item Shortage Report",
		"filters_fn": lambda ctx: {"company": resolve_insight_context(ctx).get("company")},
		"title": "Stock Below Reorder",
	},
	"overdue_so": {
		"label": "Overdue sales orders",
		"tool": "get_list_count",
		"doctype": "Sales Order",
		"filters_fn": lambda ctx: [
			["Sales Order", "delivery_date", "<", frappe.utils.today()],
			["Sales Order", "status", "not in", ["Completed", "Cancelled", "Closed"]],
		],
		"title": "Overdue Sales Orders",
		"kpi_label": "Overdue orders",
	},
	"ar_summary": {
		"label": "AR summary",
		"tool": "run_report",
		"report_name": "Accounts Receivable Summary",
		"filters_fn": lambda ctx: {"company": resolve_insight_context(ctx).get("company")},
		"title": "Accounts Receivable Summary",
	},
	"ap_due_week": {
		"label": "Bills due this week",
		"tool": "run_report",
		"report_name": "Accounts Payable",
		"filters_fn": _week_filters,
		"title": "Bills Due This Week",
	},
	"budget_variance": {
		"label": "Budget vs actual",
		"tool": "run_report",
		"report_name": "Budget Variance Report",
		"filters_fn": _mtd_filters,
		"title": "Budget vs Actual",
	},
	"top_customers_ytd": {
		"label": "Top 5 customers",
		"tool": "run_report",
		"report_name": "Sales Analytics",
		"filters_fn": lambda ctx: {
			"company": resolve_insight_context(ctx).get("company"),
			"tree_type": "Customer",
			"doc_type": "Sales Invoice",
		},
		"title": "Top Customers YTD",
	},
}


def get_preset(preset_id: str) -> dict | None:
	return INSIGHT_CHIP_PRESETS.get(preset_id)


def run_preset(preset_id: str, context: dict | None = None) -> dict:
	preset = get_preset(preset_id)
	if not preset:
		return {"error": f"Unknown preset: {preset_id}", "preset_id": preset_id}

	context = context or {}
	tool = preset.get("tool")
	filters_fn = preset.get("filters_fn")
	filters = filters_fn(context) if callable(filters_fn) else {}

	tools_used = []
	reports_used = []
	filters_applied = filters

	if tool == "run_report":
		report_name = preset["report_name"]
		result = exec_run_report(report_name, filters=filters)
		tools_used.append("run_report")
		reports_used.append(report_name)
		filters_applied = result.get("filters") or filters
		micro_report = build_from_report_result(
			report_name,
			filters_applied,
			result,
			title=preset.get("title"),
		)
		tool_result = result
	elif tool == "get_list_count":
		doctype = preset["doctype"]
		result = exec_get_list_count(doctype, filters=filters)
		tools_used.append("get_list_count")
		filters_applied = result.get("filters") or filters
		micro_report = build_from_count_result(
			doctype,
			filters_applied,
			result.get("count"),
			title=preset.get("title") or doctype,
			label=preset.get("kpi_label"),
		)
		if result.get("error"):
			micro_report["error"] = result["error"]
		tool_result = result
	else:
		return {"error": f"Unsupported preset tool: {tool}", "preset_id": preset_id}

	return {
		"preset_id": preset_id,
		"tool_result": tool_result,
		"micro_report": micro_report,
		"tools_used": tools_used,
		"reports_used": reports_used,
		"filters_applied": filters_applied,
		"error": micro_report.get("error"),
	}
