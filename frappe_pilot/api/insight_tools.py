# Insight read-only tools

from __future__ import annotations

import json

import time

import frappe

from frappe_pilot.api.analyze_tools import exec_get_doctype_meta as _analyze_get_doctype_meta
from frappe_pilot.utils.insight_fields import resolve_list_fields
from frappe_pilot.utils.insight_link_graph import get_related_doctypes
from frappe_pilot.utils.insight_permissions import (
	EXCLUDED_USER_MESSAGE,
	assert_insight_access,
	check_doctype_access,
	check_module_access,
)
from frappe_pilot.utils.insight_report_router import resolve_report_intent
from frappe_pilot.utils.insight_sql import exec_run_readonly_query
from frappe_pilot.utils.report_catalogue import discover_reports, resolve_report_docname
from frappe_pilot.utils.report_defaults import apply_report_filter_defaults, erpnext_installed, resolve_insight_context
from frappe_pilot.utils.settings import get_insight_config


def _limits():
	cfg = get_insight_config()
	return {
		"report_rows": cfg["max_report_rows"],
		"list_rows": cfg["max_list_rows"],
		"json_chars": cfg["max_tool_json_chars"],
	}


def _truncate_result(data: dict) -> dict:
	max_chars = _limits()["json_chars"]
	serialized = json.dumps(data, default=str)
	if len(serialized) <= max_chars:
		return data
	data = dict(data)
	data["_truncated"] = True
	if "rows" in data and isinstance(data["rows"], list):
		while data["rows"] and len(json.dumps(data, default=str)) > max_chars:
			data["rows"] = data["rows"][:-1]
	return data


def _permission_error(resource: str) -> dict:
	return {"error": "permission_denied", "resource": resource}


def exec_list_reports(module: str = "", search: str = ""):
	if not erpnext_installed():
		return {"error": "ERPNext is not installed."}
	if module and (err := check_module_access(module)):
		return err
	return discover_reports(module=module, search=search)


def exec_run_report(report_name: str = "", filters=None, limit=None):
	if not erpnext_installed():
		return {"error": "ERPNext is not installed."}
	if not report_name:
		return {"error": "report_name is required"}

	resolved = resolve_report_intent(report_name) or report_name
	report_name = resolved

	limit = limit or _limits()["report_rows"]
	filters = filters or {}
	if isinstance(filters, str):
		try:
			filters = json.loads(filters)
		except (TypeError, ValueError):
			filters = {}

	report_doc = resolve_report_docname(report_name)
	if not report_doc:
		return {"error": f"Report '{report_name}' not found.", "report_name": report_name}

	report_module = frappe.db.get_value("Report", report_doc, "module")
	if report_module and (err := check_module_access(report_module)):
		return err

	ref_doctype = frappe.db.get_value("Report", report_doc, "ref_doctype")
	if ref_doctype and (err := check_doctype_access(ref_doctype)):
		return err

	ctx = resolve_insight_context(filters)
	filters = apply_report_filter_defaults(filters, ctx)

	from frappe_pilot.utils.insight_cache import get_cached_report_result, set_cached_report_result

	cached, cache_key = get_cached_report_result(report_name, filters, company=ctx.get("company"))
	if cached:
		cached = dict(cached)
		cached["from_cache"] = True
		cached["kpi_snapshot_id"] = cache_key
		return _truncate_result(cached)

	try:
		from frappe.desk.query_report import run

		result = run(
			report_name=report_name,
			filters=filters,
			ignore_prepared_report=True,
		)
	except frappe.PermissionError:
		return _permission_error(report_name)
	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "Insight Report Run Error")
		return {"error": str(exc), "report_name": report_name, "filters": filters}

	columns = result.get("columns") or []
	rows = result.get("result") or []

	col_labels = []
	structured_columns = []
	for col in columns:
		if isinstance(col, dict):
			col_labels.append(col.get("label") or col.get("fieldname") or "")
			structured_columns.append(col)
		else:
			col_labels.append(str(col))
			structured_columns.append({"fieldname": str(col), "label": str(col), "fieldtype": "Data"})

	sample_rows = rows[:limit]
	formatted_rows = []
	for row in sample_rows:
		if isinstance(row, dict):
			formatted_rows.append(row)
		elif isinstance(row, (list, tuple)):
			formatted_rows.append(dict(zip(col_labels, row)))

	payload = {
		"report_name": report_name,
		"filters": filters,
		"columns": col_labels,
		"structured_columns": structured_columns,
		"total_rows": len(rows),
		"sample_row_count": len(formatted_rows),
		"rows": formatted_rows,
		"kpi_snapshot_id": set_cached_report_result(
			report_name,
			filters,
			{
				"report_name": report_name,
				"filters": filters,
				"columns": col_labels,
				"structured_columns": structured_columns,
				"total_rows": len(rows),
				"sample_row_count": len(formatted_rows),
				"rows": formatted_rows,
			},
			company=ctx.get("company"),
		),
	}
	return _truncate_result(payload)


def exec_run_multi_report(reports: list | None = None):
	reports = reports or []
	if not reports:
		return {"error": "reports list is required"}
	if len(reports) > 3:
		reports = reports[:3]

	results = []
	for spec in reports:
		if not isinstance(spec, dict):
			continue
		name = spec.get("report_name") or spec.get("name")
		if not name:
			results.append({"error": "report_name required", "report_name": ""})
			continue
		result = exec_run_report(name, filters=spec.get("filters"))
		if spec.get("title"):
			result["title"] = spec["title"]
		results.append(result)

	return _truncate_result({"reports": results, "multi": True})


def exec_get_list_count(doctype: str = "", filters=None):
	if not doctype:
		return {"error": "doctype is required"}

	if err := check_doctype_access(doctype):
		return err

	filters = filters or []
	if isinstance(filters, str):
		try:
			filters = json.loads(filters)
		except (TypeError, ValueError):
			filters = []

	try:
		count = frappe.db.count(doctype, filters)
	except Exception as exc:
		return {"error": str(exc), "doctype": doctype}

	return {
		"doctype": doctype,
		"filters": filters,
		"count": count,
	}


def exec_get_list_sample(
	doctype: str = "",
	filters=None,
	fields=None,
	limit: int | None = None,
	user_message: str = "",
	title: str = "",
):
	if not doctype:
		return {"error": "doctype is required"}

	if err := check_doctype_access(doctype):
		return err

	limit = limit or _limits()["list_rows"]
	filters = filters or []

	if isinstance(fields, str):
		try:
			fields = json.loads(fields)
		except (TypeError, ValueError):
			fields = [f.strip() for f in fields.split(",") if f.strip()]

	if isinstance(filters, str):
		try:
			filters = json.loads(filters)
		except (TypeError, ValueError):
			filters = []

	fields = resolve_list_fields(doctype, fields, user_message=user_message)

	field_list = []
	for f in fields[:15]:
		if f == "name":
			field_list.append(f"`tab{doctype}`.name as name")
		elif "." not in f:
			field_list.append(f"`tab{doctype}`.`{f}` as `{f}`")
		else:
			field_list.append(f)

	if not field_list:
		field_list = [f"`tab{doctype}`.name as name"]

	try:
		from frappe.desk.reportview import execute

		rows = execute(
			doctype=doctype,
			fields=field_list,
			filters=filters,
			limit_page_length=limit,
			limit_start=0,
		)
	except Exception as exc:
		return {"error": str(exc), "rows": []}

	return _truncate_result(
		{
			"doctype": doctype,
			"filters": filters,
			"fields": fields,
			"title": title or None,
			"row_count": len(rows),
			"rows": rows,
		}
	)


def exec_get_doctype_meta(doctype: str = "", include_list_view: bool = False):
	if err := check_doctype_access(doctype):
		if err.get("error") == "doctype_excluded":
			return {"error": "doctype_excluded", "doctype": doctype, "message": EXCLUDED_USER_MESSAGE}
		return err
	return _analyze_get_doctype_meta(doctype=doctype, include_list_view=include_list_view)


def exec_get_related_doctypes(doctype: str = "", target_doctype: str = "", depth: int = 1):
	return get_related_doctypes(doctype, target_doctype or None, depth=int(depth or 1))


def exec_get_child_table_sample(
	parent_doctype: str = "",
	parent_filters=None,
	child_table: str = "",
	fields=None,
	limit: int | None = None,
):
	if not parent_doctype or not child_table:
		return {"error": "parent_doctype and child_table are required"}

	if err := check_doctype_access(parent_doctype):
		return err
	if err := check_doctype_access(child_table):
		return err

	limit = limit or _limits()["list_rows"]
	parent_filters = parent_filters or []
	if isinstance(parent_filters, str):
		try:
			parent_filters = json.loads(parent_filters)
		except (TypeError, ValueError):
			parent_filters = []

	parent_names = frappe.get_all(
		parent_doctype,
		filters=parent_filters,
		pluck="name",
		limit=limit,
	)
	if not parent_names:
		return {
			"parent_doctype": parent_doctype,
			"child_table": child_table,
			"rows": [],
			"row_count": 0,
		}

	field_list = fields or ["name", "parent", "idx"]
	if isinstance(field_list, str):
		field_list = [f.strip() for f in field_list.split(",") if f.strip()]

	rows = frappe.get_all(
		child_table,
		filters={"parent": ("in", parent_names)},
		fields=field_list,
		limit=limit,
	)

	return _truncate_result(
		{
			"doctype": child_table,
			"parent_doctype": parent_doctype,
			"child_table": child_table,
			"filters": parent_filters,
			"fields": field_list,
			"row_count": len(rows),
			"rows": rows,
		}
	)


def exec_get_budget_summary(company: str = "", fiscal_year: str = "", cost_center: str = ""):
	filters = {}
	if company:
		filters["company"] = company
	if fiscal_year:
		filters["fiscal_year"] = fiscal_year
	if cost_center:
		filters["cost_center"] = cost_center
	result = exec_run_report("Budget Variance Report", filters=filters)
	result["title"] = "Budget vs Actual"
	return result


def exec_get_financial_snapshot(company: str = "", from_date: str = "", to_date: str = ""):
	filters = {}
	if company:
		filters["company"] = company
	if from_date:
		filters["from_date"] = from_date
	if to_date:
		filters["to_date"] = to_date
	pl = exec_run_report("Profit and Loss Statement", filters=dict(filters))
	bs = exec_run_report("Balance Sheet", filters=dict(filters))
	return {
		"profit_and_loss": pl,
		"balance_sheet": bs,
		"filters": filters,
	}


def exec_compare_periods(report_name: str, current_filters=None, previous_filters=None):
	resolved = resolve_report_intent(report_name) or report_name
	current = exec_run_report(resolved, filters=current_filters or {})
	previous = exec_run_report(resolved, filters=previous_filters or {})
	return {
		"report_name": resolved,
		"current": current,
		"previous": previous,
	}


def exec_get_list_aggregate(
	doctype: str = "",
	filters=None,
	group_by: str = "",
	sum_field: str = "",
	limit: int = 5,
):
	if not doctype:
		return {"error": "doctype is required"}
	if err := check_doctype_access(doctype):
		return err

	filters = filters or []
	fields = [group_by] if group_by else ["name"]
	if sum_field:
		fields.append(f"sum(`{sum_field}`) as total")

	try:
		rows = frappe.get_all(
			doctype,
			filters=filters,
			fields=fields,
			group_by=group_by or None,
			order_by="total desc" if sum_field else None,
			limit=limit,
		)
	except Exception as exc:
		return {"error": str(exc)}

	return _truncate_result({"doctype": doctype, "group_by": group_by, "rows": rows})


TOOL_HANDLERS = {
	"list_reports": exec_list_reports,
	"run_report": exec_run_report,
	"run_multi_report": exec_run_multi_report,
	"get_list_count": exec_get_list_count,
	"get_list_sample": exec_get_list_sample,
	"get_doctype_meta": exec_get_doctype_meta,
	"get_related_doctypes": exec_get_related_doctypes,
	"get_child_table_sample": exec_get_child_table_sample,
	"get_budget_summary": exec_get_budget_summary,
	"get_financial_snapshot": exec_get_financial_snapshot,
	"compare_periods": exec_compare_periods,
	"get_list_aggregate": exec_get_list_aggregate,
	"run_readonly_query": exec_run_readonly_query,
}


def get_insight_tool_handlers():
	handlers = dict(TOOL_HANDLERS)
	for hook_tools in frappe.get_hooks("pilot_insight_tools") or []:
		if isinstance(hook_tools, dict):
			handlers.update(hook_tools)
	return handlers


def execute_insight_tool(tool_name: str, tool_args: dict | None = None):
	cfg = get_insight_config()
	disabled = cfg.get("disabled_tools") or frozenset()
	if tool_name in disabled:
		return {"error": f"Tool '{tool_name}' is disabled.", "tool": tool_name}

	handlers = get_insight_tool_handlers()
	handler = handlers.get(tool_name)
	if not handler:
		return {"error": f"Unknown tool: {tool_name}", "tool": tool_name}

	args = dict(tool_args or {})
	start = time.monotonic()
	try:
		result = handler(**args)
		if isinstance(result, dict):
			result.setdefault("tool", tool_name)
			result.setdefault("duration_ms", int((time.monotonic() - start) * 1000))
		return result
	except TypeError:
		import inspect

		sig = inspect.signature(handler)
		filtered = {k: v for k, v in args.items() if k in sig.parameters}
		result = handler(**filtered)
		if isinstance(result, dict):
			result.setdefault("tool", tool_name)
			result.setdefault("duration_ms", int((time.monotonic() - start) * 1000))
		return result
	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), f"Insight Tool Error: {tool_name}")
		return {
			"error": str(exc),
			"tool": tool_name,
			"duration_ms": int((time.monotonic() - start) * 1000),
		}
