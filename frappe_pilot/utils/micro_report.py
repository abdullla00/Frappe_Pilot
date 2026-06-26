# Micro-report schema builder for Insight tab

from __future__ import annotations

import hashlib
import json
from typing import Any

import frappe

from frappe_pilot.utils.insights_link import attach_insights_links
from frappe_pilot.utils.report_defaults import get_company_currency, resolve_insight_context
from frappe_pilot.utils.settings import get_insight_config

# Voucher column hints → DocType for report table links
VOUCHER_COLUMN_DOCTYPES: dict[str, str] = {
	"voucher_no": "",
	"sales_invoice": "Sales Invoice",
	"purchase_invoice": "Purchase Invoice",
	"payment_entry": "Payment Entry",
	"journal_entry": "Journal Entry",
	"delivery_note": "Delivery Note",
	"purchase_receipt": "Purchase Receipt",
}


def report_desk_route(report_name: str, filters: dict | None = None) -> str:
	from urllib.parse import quote

	return f"/app/query-report/{quote(report_name)}"


def format_currency(value, currency: str | None = None) -> str:
	if value is None or value == "":
		return "—"
	try:
		num = float(value)
	except (TypeError, ValueError):
		return str(value)
	if currency:
		return frappe.format_value(num, {"fieldtype": "Currency", "options": currency})
	return frappe.format_value(num, {"fieldtype": "Float"})


def empty_micro_report(title: str = "Insight", error: str | None = None) -> dict:
	ctx = resolve_insight_context()
	return {
		"title": title,
		"period": "",
		"company": ctx.get("company") or "",
		"currency": ctx.get("currency") or "",
		"kpis": [],
		"tables": [],
		"sources": [],
		"warnings": [],
		"error": error,
	}


def build_table_columns(doctype: str, fieldnames: list[str]) -> list[dict]:
	meta = frappe.get_meta(doctype)
	field_map = {f.fieldname: f for f in meta.fields if f.fieldname}
	columns: list[dict] = []

	for fn in fieldnames:
		field = field_map.get(fn)
		if not field:
			if fn == "name":
				columns.append(
					{
						"fieldname": "name",
						"label": meta.get_label("name") or "ID",
						"fieldtype": "Data",
						"link_doctype": doctype,
					}
				)
			else:
				columns.append(
					{
						"fieldname": fn,
						"label": _LINK_FIELD_LABELS.get(fn) or fn.replace("_", " ").title(),
						"fieldtype": "Data",
					}
				)
			continue

		col: dict = {
			"fieldname": fn,
			"label": field.label or fn.replace("_", " ").title(),
			"fieldtype": field.fieldtype,
		}
		if fn == "name" or field.fieldtype == "Link":
			col["link_doctype"] = field.options if field.fieldtype == "Link" else doctype
		elif field.fieldtype in ("Dynamic Link",):
			col["link_doctype"] = None
		columns.append(col)

	return columns


def format_cell_value(value, fieldtype: str, currency: str | None = None) -> str:
	if value is None or value == "":
		return "—"
	if fieldtype == "Date":
		try:
			return frappe.utils.formatdate(value)
		except Exception:
			return str(value)
	if fieldtype == "Datetime":
		try:
			return frappe.utils.format_datetime(value)
		except Exception:
			return str(value)
	if fieldtype in ("Currency", "Float", "Int"):
		if fieldtype == "Currency":
			return format_currency(value, currency)
		try:
			return frappe.format_value(float(value), {"fieldtype": fieldtype})
		except (TypeError, ValueError):
			return str(value)
	return str(value)


def build_from_report_result(
	report_name: str,
	filters: dict,
	tool_result: dict,
	*,
	title: str | None = None,
	period: str | None = None,
	ref_doctype: str | None = None,
) -> dict:
	if tool_result.get("error"):
		return empty_micro_report(title or report_name, error=tool_result["error"])

	ctx = resolve_insight_context(filters)
	currency = ctx.get("currency") or get_company_currency(ctx.get("company"))
	rows = tool_result.get("rows") or []
	raw_columns = tool_result.get("columns") or []
	structured_columns = tool_result.get("structured_columns") or _parse_report_columns(
		raw_columns, ref_doctype=ref_doctype
	)

	kpis = _extract_kpis(rows, raw_columns, currency)
	tables = []
	if rows:
		formatted_rows = _format_report_rows(rows, structured_columns, currency, ref_doctype)
		if formatted_rows:
			tables.append(
				{
					"name": report_name,
					"title": title or report_name,
					"report_name": report_name,
					"columns": structured_columns,
					"rows": formatted_rows,
					"row_count": tool_result.get("total_rows") or len(rows),
				}
			)

	period_label = period or _period_from_filters(filters)
	sources = attach_insights_links(
		[
			{
				"type": "report",
				"name": report_name,
				"route": report_desk_route(report_name, filters),
				"filters": filters,
				"navigable": False,
			}
		]
	)
	return {
		"title": title or report_name,
		"period": period_label,
		"company": ctx.get("company") or filters.get("company") or "",
		"currency": currency or "",
		"kpis": kpis,
		"tables": tables,
		"sources": sources,
		"warnings": [],
		"error": None,
	}


def _parse_report_columns(columns: list, ref_doctype: str | None = None) -> list[dict]:
	parsed: list[dict] = []
	for col in columns:
		if isinstance(col, dict):
			fn = col.get("fieldname") or col.get("label") or ""
			ft = col.get("fieldtype") or "Data"
			entry = {
				"fieldname": fn,
				"label": col.get("label") or fn,
				"fieldtype": ft,
			}
			if col.get("options"):
				entry["link_doctype"] = col.get("options")
			elif ref_doctype and fn in ("name", "voucher_no", "voucher"):
				entry["link_doctype"] = ref_doctype
			elif fn.lower() in VOUCHER_COLUMN_DOCTYPES and VOUCHER_COLUMN_DOCTYPES[fn.lower()]:
				entry["link_doctype"] = VOUCHER_COLUMN_DOCTYPES[fn.lower()]
			parsed.append(entry)
		else:
			label = str(col)
			fn = label.lower().replace(" ", "_")
			entry = {"fieldname": fn, "label": label, "fieldtype": "Data"}
			if ref_doctype and fn in ("voucher_no", "name"):
				entry["link_doctype"] = ref_doctype
			parsed.append(entry)
	return parsed


def _format_report_rows(
	rows: list,
	columns: list[dict],
	currency: str | None,
	ref_doctype: str | None,
) -> list[dict]:
	formatted: list[dict] = []
	col_fns = [c.get("fieldname") for c in columns if c.get("fieldname")]
	if not col_fns and rows:
		if isinstance(rows[0], dict):
			col_fns = list(rows[0].keys())
		elif isinstance(rows[0], (list, tuple)):
			col_fns = [c.get("fieldname") or f"col_{i}" for i, c in enumerate(columns)]

	for row in rows[:25]:
		if isinstance(row, dict):
			out: dict = {}
			for col in columns:
				fn = col.get("fieldname") or ""
				raw = row.get(fn)
				if raw is None:
					for key in row:
						if key.lower() == fn.lower() or key.lower().replace(" ", "_") == fn:
							raw = row[key]
							break
				ft = col.get("fieldtype") or "Data"
				out[fn] = format_cell_value(raw, ft, currency)
				out[f"_{fn}"] = raw
			formatted.append(out)
		elif isinstance(row, (list, tuple)):
			out = {}
			for idx, col in enumerate(columns):
				fn = col.get("fieldname") or f"col_{idx}"
				raw = row[idx] if idx < len(row) else None
				ft = col.get("fieldtype") or "Data"
				out[fn] = format_cell_value(raw, ft, currency)
				out[f"_{fn}"] = raw
			formatted.append(out)
	return formatted


def build_from_count_result(
	doctype: str,
	filters: list,
	count: int | None,
	*,
	title: str,
	label: str | None = None,
) -> dict:
	ctx = resolve_insight_context()
	kpi_label = label or f"{doctype} count"
	return {
		"title": title,
		"period": frappe.utils.formatdate(frappe.utils.today()),
		"company": ctx.get("company") or "",
		"currency": ctx.get("currency") or "",
		"kpis": [
			{
				"label": kpi_label,
				"value": str(count if count is not None else "—"),
				"raw_value": count,
			}
		],
		"tables": [],
		"sources": [],
		"warnings": [],
		"error": None if count is not None else "Could not count records",
	}


_LINK_FIELD_LABELS = {
	"job_order": "Job Order",
	"rental_order": "Rental Order",
}


def _normalize_list_filter(raw) -> tuple[str, str, Any] | None:
	if not isinstance(raw, (list, tuple)) or len(raw) < 3:
		return None
	if len(raw) >= 4 and isinstance(raw[0], str):
		field, op, val = raw[1], raw[2], raw[3] if len(raw) > 3 else None
	else:
		field, op, val = raw[0], raw[1], raw[2] if len(raw) > 2 else None
	if not isinstance(field, str):
		return None
	return field.split(".")[-1], str(op).lower(), val


def _filter_implies_field_set(op: str, val) -> bool:
	if op == "is" and val == "set":
		return True
	if op == "!=" and val in ("", None):
		return True
	if op == "not in" and val in ([], "", None):
		return True
	return False


def infer_list_sample_title(
	doctype: str,
	filters=None,
	fields=None,
	*,
	explicit_title: str | None = None,
) -> str:
	if explicit_title and str(explicit_title).strip():
		return str(explicit_title).strip()

	filters = filters or []
	fields = fields or []
	has_unpaid = False
	link_hints: list[str] = []

	for raw in filters:
		parsed = _normalize_list_filter(raw)
		if not parsed:
			continue
		fn, op, val = parsed
		if fn == "outstanding_amount" and op in (">", ">="):
			has_unpaid = True
		if fn in _LINK_FIELD_LABELS and _filter_implies_field_set(op, val):
			label = _LINK_FIELD_LABELS[fn]
			if label not in link_hints:
				link_hints.append(label)
		if fn in _LINK_FIELD_LABELS and op == "=" and val:
			label = _LINK_FIELD_LABELS[fn]
			if label not in link_hints:
				link_hints.append(label)

	for fn in fields:
		if fn in _LINK_FIELD_LABELS:
			label = _LINK_FIELD_LABELS[fn]
			if label not in link_hints:
				link_hints.append(label)

	base = f"Unpaid {doctype}" if has_unpaid else doctype
	if len(link_hints) == 1:
		return f"{base} · {link_hints[0]} linked"
	if link_hints:
		return f"{base} · {' & '.join(link_hints)} linked"
	return base


def _cell_has_value(raw) -> bool:
	if raw is None:
		return False
	if isinstance(raw, str) and not raw.strip():
		return False
	return True


def _prune_sparse_columns(fieldnames: list[str], rows: list[dict]) -> list[str]:
	if not fieldnames or not rows:
		return fieldnames or ["name"]

	kept: list[str] = []
	for fn in fieldnames:
		if fn == "name":
			kept.append(fn)
			continue
		if any(_cell_has_value(row.get(fn)) for row in rows if isinstance(row, dict)):
			kept.append(fn)

	if not kept:
		return ["name"] if "name" in fieldnames else fieldnames[:1]
	if "name" not in kept and "name" in fieldnames:
		kept.insert(0, "name")
	return kept


def _filters_fingerprint(filters) -> str:
	if not filters:
		return ""
	payload = json.dumps(filters, sort_keys=True, default=str)
	return hashlib.sha256(payload.encode()).hexdigest()[:12]


def build_from_list_sample_result(
	doctype: str,
	filters: list,
	tool_result: dict,
	*,
	title: str | None = None,
) -> dict:
	if tool_result.get("error"):
		return empty_micro_report(title or doctype, error=tool_result["error"])

	ctx = resolve_insight_context()
	currency = ctx.get("currency") or get_company_currency(ctx.get("company"))
	rows = tool_result.get("rows") or []
	fieldnames = tool_result.get("fields") or []
	if rows and isinstance(rows[0], dict) and not fieldnames:
		fieldnames = list(rows[0].keys())
	if not fieldnames:
		fieldnames = ["name"]

	fieldnames = _prune_sparse_columns(fieldnames, rows)

	columns = build_table_columns(doctype, fieldnames)
	col_map = {c["fieldname"]: c for c in columns}

	formatted_rows: list[dict] = []
	for row in rows[:25]:
		if not isinstance(row, dict):
			continue
		out_row: dict = {}
		for fn in fieldnames:
			raw = row.get(fn)
			ft = col_map.get(fn, {}).get("fieldtype", "Data")
			out_row[fn] = format_cell_value(raw, ft, currency)
			out_row[f"_{fn}"] = raw
		formatted_rows.append(out_row)

	row_count = tool_result.get("row_count", len(rows))
	display_title = infer_list_sample_title(
		doctype,
		filters,
		fieldnames,
		explicit_title=title or tool_result.get("title"),
	)

	return {
		"title": display_title,
		"period": frappe.utils.formatdate(frappe.utils.today()),
		"company": ctx.get("company") or "",
		"currency": currency or "",
		"kpis": [],
		"row_count": row_count,
		"tables": [
			{
				"doctype": doctype,
				"title": display_title,
				"name": doctype,
				"filters": filters,
				"columns": columns,
				"rows": formatted_rows,
				"row_count": row_count,
			}
		]
		if formatted_rows
		else [],
		"sources": [],
		"warnings": [],
		"error": None,
	}


def build_from_financial_snapshot(tool_result: dict, *, title: str = "Financial Snapshot") -> dict:
	pl = tool_result.get("profit_and_loss") or {}
	bs = tool_result.get("balance_sheet") or {}
	filters = tool_result.get("filters") or {}
	warnings: list[dict] = []

	if pl.get("error"):
		warnings.append({"tool": "get_financial_snapshot", "error": pl["error"], "part": "profit_and_loss"})
	if bs.get("error"):
		warnings.append({"tool": "get_financial_snapshot", "error": bs["error"], "part": "balance_sheet"})

	ctx = resolve_insight_context(filters)
	currency = ctx.get("currency") or get_company_currency(ctx.get("company"))
	kpis: list[dict] = []

	for label, result in (("P&L", pl), ("Balance Sheet", bs)):
		if result.get("error"):
			continue
		for kpi in _extract_kpis(result.get("rows") or [], result.get("columns") or [], currency)[:3]:
			kpi = dict(kpi)
			kpi["label"] = f"{label}: {kpi.get('label', '')}"
			kpis.append(kpi)

	tables: list[dict] = []
	for report_label, result in (("Profit & Loss", pl), ("Balance Sheet", bs)):
		if result.get("error") or not result.get("rows"):
			continue
		partial = build_from_report_result(
			result.get("report_name") or report_label,
			result.get("filters") or filters,
			result,
			title=report_label,
		)
		for tbl in partial.get("tables") or []:
			tables.append(tbl)

	return _assemble_micro_report(
		kpis[:6],
		tables[:2],
		{
			"title": title,
			"period": _period_from_filters(filters),
			"company": ctx.get("company") or "",
			"currency": currency or "",
		},
		warnings=warnings,
	)


def build_from_compare_periods(tool_result: dict, *, title: str | None = None) -> dict:
	report_name = tool_result.get("report_name") or "Report"
	current = tool_result.get("current") or {}
	previous = tool_result.get("previous") or {}
	warnings: list[dict] = []

	if current.get("error"):
		warnings.append({"tool": "compare_periods", "error": current["error"], "part": "current"})
	if previous.get("error"):
		warnings.append({"tool": "compare_periods", "error": previous["error"], "part": "previous"})

	ctx = resolve_insight_context(current.get("filters") or {})
	currency = ctx.get("currency") or get_company_currency(ctx.get("company"))
	kpis: list[dict] = []

	cur_rows = current.get("rows") or []
	prev_rows = previous.get("rows") or []
	columns = current.get("columns") or previous.get("columns") or []

	cur_kpis = _extract_kpis(cur_rows, columns, currency)
	prev_kpis = _extract_kpis(prev_rows, columns, currency)
	prev_map = {k.get("label"): k.get("raw_value") for k in prev_kpis}

	for kpi in cur_kpis[:5]:
		label = kpi.get("label") or ""
		cur_val = kpi.get("raw_value")
		prev_val = prev_map.get(label)
		delta_str = ""
		if cur_val is not None and prev_val is not None:
			try:
				prev_f = float(prev_val)
				cur_f = float(cur_val)
				if prev_f:
					pct = ((cur_f - prev_f) / abs(prev_f)) * 100
					sign = "+" if pct >= 0 else ""
					delta_str = f" ({sign}{pct:.0f}% vs prior)"
			except (TypeError, ValueError):
				pass
		kpis.append(
			{
				"label": label,
				"value": str(kpi.get("value", "")),
				"delta": delta_str.strip(" ()") if delta_str else "",
				"raw_value": cur_val,
			}
		)

	display_title = title or f"{report_name} — Period Comparison"
	return _assemble_micro_report(
		kpis,
		[],
		{
			"title": display_title,
			"period": _period_from_filters(current.get("filters") or {}),
			"company": ctx.get("company") or "",
			"currency": currency or "",
		},
		warnings=warnings,
	)


def build_from_list_aggregate(tool_result: dict, *, title: str | None = None) -> dict:
	if tool_result.get("error"):
		return empty_micro_report(title or tool_result.get("doctype", "Aggregate"), error=tool_result["error"])

	doctype = tool_result.get("doctype") or "Records"
	group_by = tool_result.get("group_by") or "name"
	rows = tool_result.get("rows") or []
	ctx = resolve_insight_context()
	currency = ctx.get("currency") or get_company_currency(ctx.get("company"))

	columns = [
		{"fieldname": group_by, "label": group_by.replace("_", " ").title(), "fieldtype": "Data"},
	]
	if rows and "total" in (rows[0] if rows else {}):
		columns.append({"fieldname": "total", "label": "Total", "fieldtype": "Currency"})

	formatted_rows: list[dict] = []
	for row in rows[:25]:
		if not isinstance(row, dict):
			continue
		out: dict = {}
		for col in columns:
			fn = col["fieldname"]
			raw = row.get(fn)
			out[fn] = format_cell_value(raw, col.get("fieldtype", "Data"), currency)
			out[f"_{fn}"] = raw
		formatted_rows.append(out)

	return _assemble_micro_report(
		[],
		[
			{
				"doctype": doctype,
				"title": title or f"{doctype} by {group_by}",
				"columns": columns,
				"rows": formatted_rows,
				"row_count": len(rows),
			}
		]
		if formatted_rows
		else [],
		{
			"title": title or f"{doctype} Summary",
			"company": ctx.get("company") or "",
			"currency": currency or "",
		},
	)


def build_from_query_result(tool_result: dict) -> dict:
	if tool_result.get("error"):
		return empty_micro_report(tool_result.get("title") or "Query", error=tool_result["error"])

	ctx = resolve_insight_context()
	currency = ctx.get("currency") or get_company_currency(ctx.get("company"))
	col_names = tool_result.get("columns") or []
	rows = tool_result.get("rows") or []

	columns = [
		{"fieldname": str(c), "label": str(c).replace("_", " ").title(), "fieldtype": "Data"}
		for c in col_names
	]
	if not columns and rows and isinstance(rows[0], dict):
		col_names = list(rows[0].keys())
		columns = [
			{"fieldname": c, "label": c.replace("_", " ").title(), "fieldtype": "Data"}
			for c in col_names
		]

	formatted_rows: list[dict] = []
	for row in rows[:25]:
		if not isinstance(row, dict):
			continue
		out: dict = {}
		for col in columns:
			fn = col["fieldname"]
			raw = row.get(fn)
			out[fn] = format_cell_value(raw, col.get("fieldtype", "Data"), currency)
			out[f"_{fn}"] = raw
		formatted_rows.append(out)

	return _assemble_micro_report(
		[],
		[
			{
				"title": tool_result.get("title") or "Query Results",
				"columns": columns,
				"rows": formatted_rows,
				"row_count": tool_result.get("row_count") or len(rows),
			}
		]
		if formatted_rows
		else [],
		{
			"title": tool_result.get("title") or "Query Results",
			"company": ctx.get("company") or tool_result.get("company") or "",
			"currency": currency or "",
		},
	)


def _build_partial_from_tool_result(result: dict, context: dict | None = None) -> dict | None:
	if not result:
		return None

	if result.get("error") and not any(
		k in result for k in ("rows", "count", "profit_and_loss", "current", "reports")
	):
		return empty_micro_report(error=result["error"])

	if result.get("micro_report"):
		return result["micro_report"]

	if result.get("multi") and result.get("reports"):
		kpis, tables, warnings = [], [], []
		for sub in result["reports"]:
			if sub.get("error"):
				warnings.append(
					{
						"tool": "run_multi_report",
						"error": sub["error"],
						"report": sub.get("report_name"),
					}
				)
				continue
			partial = _build_partial_from_tool_result(sub, context)
			if not partial:
				continue
			if partial.get("error") and not (partial.get("tables") or partial.get("kpis")):
				warnings.append({"tool": "run_report", "error": partial["error"]})
				continue
			kpis.extend(partial.get("kpis") or [])
			tables.extend(partial.get("tables") or [])
			warnings.extend(partial.get("warnings") or [])
		return _assemble_micro_report(kpis, tables, {}, warnings=warnings)

	if result.get("profit_and_loss") is not None or result.get("balance_sheet") is not None:
		return build_from_financial_snapshot(result)

	if result.get("current") is not None and result.get("previous") is not None:
		return build_from_compare_periods(result)

	if result.get("query") and result.get("rows") is not None:
		return build_from_query_result(result)

	if result.get("report_name"):
		ref_dt = None
		try:
			ref_dt = frappe.db.get_value("Report", result["report_name"], "ref_doctype")
		except Exception:
			pass
		return build_from_report_result(
			result["report_name"],
			result.get("filters") or {},
			result,
			title=result.get("title"),
			period=result.get("period"),
			ref_doctype=ref_dt,
		)

	if result.get("doctype") and "count" in result and "rows" not in result:
		return build_from_count_result(
			result["doctype"],
			result.get("filters") or [],
			result.get("count"),
			title=result.get("title") or result["doctype"],
			label=result.get("kpi_label"),
		)

	if result.get("doctype") and result.get("group_by"):
		return build_from_list_aggregate(result, title=result.get("title"))

	if result.get("doctype") and result.get("rows") is not None:
		return build_from_list_sample_result(
			result["doctype"],
			result.get("filters") or [],
			result,
			title=result.get("title") or result["doctype"],
		)

	if result.get("error"):
		return empty_micro_report(error=result["error"])

	return None


def _dedupe_tables(tables: list[dict]) -> list[dict]:
	"""Drop duplicate table sections from repeated tool calls."""
	seen: set[tuple] = set()
	unique: list[dict] = []
	for table in tables or []:
		key = (
			table.get("report_name") or "",
			table.get("doctype") or "",
			table.get("title") or table.get("name") or "",
			_filters_fingerprint(table.get("filters")),
			table.get("row_count") or len(table.get("rows") or []),
		)
		if key in seen:
			continue
		seen.add(key)
		unique.append(table)
	return unique


def _filter_redundant_count_kpis(kpis: list[dict], tables: list[dict]) -> list[dict]:
	"""Drop count KPIs when a list table already covers the same DocType."""
	table_doctypes = {t.get("doctype") for t in tables if t.get("doctype")}
	if not table_doctypes:
		return kpis

	filtered: list[dict] = []
	for kpi in kpis or []:
		label = (kpi.get("label") or "").strip()
		if not label:
			filtered.append(kpi)
			continue
		skip = False
		for dt in table_doctypes:
			if label == f"{dt} count" or label.endswith(f" {dt} count"):
				skip = True
				break
		if skip:
			continue
		filtered.append(kpi)
	return filtered


def _dedupe_kpis(kpis: list[dict]) -> list[dict]:
	seen: set[tuple] = set()
	unique: list[dict] = []
	for kpi in kpis or []:
		key = (kpi.get("label") or "", kpi.get("value") or "")
		if key in seen:
			continue
		seen.add(key)
		unique.append(kpi)
	return unique


def _assemble_micro_report(
	kpis: list,
	tables: list,
	meta: dict,
	context: dict | None = None,
	*,
	warnings: list | None = None,
) -> dict:
	ctx = resolve_insight_context(context)
	cfg = get_insight_config()
	max_tables = cfg.get("max_tables_per_card") or 4

	company = meta.get("company") or ctx.get("company") or ""
	currency = meta.get("currency") or ctx.get("currency") or get_company_currency(company)
	title = meta.get("title") or (context or {}).get("query_title") or ""
	period = meta.get("period") or ctx.get("period") or ""

	if not title and len(tables) > 1:
		dt = tables[0].get("doctype") or "Results"
		title = f"{dt} ({len(tables)} sections)"
	elif not title and tables:
		title = tables[0].get("title") or tables[0].get("name") or "Insight"
	if not title and kpis:
		title = "Insight Summary"
	if not title:
		title = "Insight"

	warn_list = list(warnings or [])
	tables = _dedupe_tables(tables)
	kpis = _dedupe_kpis(_filter_redundant_count_kpis(kpis, tables))
	if len(tables) > max_tables:
		overflow = len(tables) - max_tables
		tables = tables[:max_tables]
		warn_list.append(
			{
				"tool": "build_micro_report",
				"error": f"{overflow} additional table section(s) omitted (limit {max_tables}).",
			}
		)

	sources = build_snapshot_sources(tables)

	return {
		"title": title,
		"period": period,
		"company": company,
		"currency": currency,
		"kpis": kpis[:6],
		"tables": tables,
		"sources": sources,
		"warnings": warn_list,
		"error": None if (tables or kpis) else (warn_list[0]["error"] if warn_list else None),
	}


def build_micro_report(tool_results: list[dict], context: dict | None = None) -> dict:
	if not tool_results:
		return empty_micro_report(error="No data returned")

	kpis: list = []
	tables: list = []
	warnings: list = []
	meta: dict = {}
	companies_seen: set[str] = set()
	periods_seen: set[str] = set()

	deferred_counts: list[dict] = []

	for result in tool_results:
		if result.get("company"):
			companies_seen.add(str(result["company"]))
		if result.get("period"):
			periods_seen.add(str(result["period"]))

		if result.get("doctype") and "count" in result and "rows" not in result:
			deferred_counts.append(result)
			continue

		if result.get("error") and not any(
			k in result for k in ("rows", "count", "profit_and_loss", "current", "reports", "report_name")
		):
			warnings.append(
				{
					"tool": result.get("tool") or "unknown",
					"error": result.get("error") or result.get("message") or "Unknown error",
				}
			)
			continue

		partial = _build_partial_from_tool_result(result, context)
		if not partial:
			if result.get("error"):
				warnings.append({"tool": result.get("tool") or "unknown", "error": result["error"]})
			continue

		if partial.get("error") and not (partial.get("tables") or partial.get("kpis")):
			warnings.append({"tool": result.get("tool") or "unknown", "error": partial["error"]})
			continue

		kpis.extend(partial.get("kpis") or [])
		tables.extend(partial.get("tables") or [])
		warnings.extend(partial.get("warnings") or [])

		for key in ("company", "currency", "period", "title"):
			val = partial.get(key)
			if val and key not in meta:
				meta[key] = val
			if key == "company" and val:
				companies_seen.add(str(val))
			if key == "period" and val:
				periods_seen.add(str(val))

	table_doctypes = {t.get("doctype") for t in tables if t.get("doctype")}
	for result in deferred_counts:
		if result.get("doctype") in table_doctypes:
			continue
		partial = _build_partial_from_tool_result(result, context)
		if not partial:
			continue
		kpis.extend(partial.get("kpis") or [])

	ctx_company = (context or {}).get("company") or resolve_insight_context(context).get("company") or ""
	if len(companies_seen) > 1:
		warnings.append(
			{
				"tool": "build_micro_report",
				"error": f"Merged results span multiple companies ({', '.join(sorted(companies_seen))}). "
				f"Showing context company: {ctx_company or 'unknown'}.",
			}
		)
	if len(periods_seen) > 1:
		warnings.append(
			{
				"tool": "build_micro_report",
				"error": f"Merged results span multiple periods ({', '.join(sorted(periods_seen))}).",
			}
		)

	if not tables and not kpis:
		err_msg = warnings[0]["error"] if warnings else "Unable to build micro-report"
		report = empty_micro_report(
			title=meta.get("title") or (context or {}).get("query_title") or "Insight",
			error=err_msg,
		)
		report["warnings"] = warnings
		return report

	return _assemble_micro_report(kpis, tables, meta, context, warnings=warnings)


def build_snapshot_sources(tables: list[dict]) -> list[dict]:
	sources: list[dict] = []
	for tbl in tables or []:
		if tbl.get("report_name") or tbl.get("name") and not tbl.get("doctype"):
			sources.append(
				{
					"type": "report",
					"name": tbl.get("report_name") or tbl.get("name") or tbl.get("title"),
					"row_count": tbl.get("row_count"),
				}
			)
		elif tbl.get("doctype"):
			sources.append(
				{
					"type": "list",
					"doctype": tbl.get("doctype"),
					"name": tbl.get("title") or tbl.get("doctype"),
					"row_count": tbl.get("row_count"),
				}
			)
	return sources


def compact_micro_report_digest(micro_report: dict) -> str:
	if not micro_report:
		return ""
	parts: list[str] = []
	for tbl in micro_report.get("tables") or []:
		label = tbl.get("title") or tbl.get("doctype") or tbl.get("name") or "Table"
		count = tbl.get("row_count") or len(tbl.get("rows") or [])
		dt = tbl.get("doctype") or tbl.get("report_name") or ""
		parts.append(f"{label} ({count} rows{f', {dt}' if dt else ''})")
	for kpi in (micro_report.get("kpis") or [])[:3]:
		parts.append(f"{kpi.get('label')}: {kpi.get('value')}")
	if not parts:
		return ""
	return "[Context: " + "; ".join(parts) + "]"


def build_last_insight_evidence(micro_report: dict, evidence: dict | None = None) -> dict:
	evidence = evidence or {}
	tables_meta = []
	for tbl in micro_report.get("tables") or []:
		cols = tbl.get("columns") or []
		col_names = [c.get("fieldname") if isinstance(c, dict) else c for c in cols]
		tables_meta.append(
			{
				"title": tbl.get("title"),
				"doctype": tbl.get("doctype"),
				"report_name": tbl.get("report_name"),
				"row_count": tbl.get("row_count"),
				"columns": col_names,
			}
		)
	return {
		"tables": tables_meta,
		"kpis": micro_report.get("kpis") or [],
		"tools_used": evidence.get("tools_used") or [],
		"filters_applied": evidence.get("filters_applied") or [],
		"reports_used": evidence.get("reports_used") or [],
		"company": micro_report.get("company") or "",
		"period": micro_report.get("period") or "",
	}


def _period_from_filters(filters: dict) -> str:
	fd = filters.get("from_date")
	td = filters.get("to_date")
	if fd and td:
		return f"{frappe.utils.formatdate(fd)} → {frappe.utils.formatdate(td)}"
	if filters.get("fiscal_year"):
		return str(filters["fiscal_year"])
	return ""


def _extract_kpis(rows: list, columns: list, currency: str | None) -> list[dict]:
	kpis = []
	if not rows:
		return kpis

	candidates = rows[-3:] if len(rows) >= 3 else rows
	for row in reversed(candidates):
		if isinstance(row, dict):
			for col in columns:
				col_key = col.get("fieldname") if isinstance(col, dict) else col
				val = row.get(col_key) if col_key else None
				if val is None and isinstance(col, str):
					val = row.get(col)
				if _is_numeric(val):
					label = col.get("label") if isinstance(col, dict) else col
					kpis.append(
						{
							"label": label,
							"value": format_currency(val, currency),
							"raw_value": float(val),
						}
					)
					if len(kpis) >= 5:
						return kpis
		elif isinstance(row, (list, tuple)):
			for idx, val in enumerate(row):
				if idx >= len(columns):
					break
				if _is_numeric(val):
					label = columns[idx]
					if isinstance(label, dict):
						label = label.get("label") or label.get("fieldname")
					kpis.append(
						{
							"label": label,
							"value": format_currency(val, currency),
							"raw_value": float(val),
						}
					)
					if len(kpis) >= 5:
						return kpis
	return kpis[:5]


def _is_numeric(val) -> bool:
	if val is None or val == "":
		return False
	try:
		float(val)
		return True
	except (TypeError, ValueError):
		return False


def micro_report_json(micro_report: dict) -> str:
	"""Truncated JSON for narrate LLM — KPIs + table summaries only."""
	summary = {
		"title": micro_report.get("title"),
		"company": micro_report.get("company"),
		"period": micro_report.get("period"),
		"kpis": micro_report.get("kpis") or [],
		"tables": [
			{
				"title": t.get("title"),
				"row_count": t.get("row_count") or len(t.get("rows") or []),
				"columns": [
					c.get("label") if isinstance(c, dict) else c for c in (t.get("columns") or [])
				],
			}
			for t in (micro_report.get("tables") or [])
		],
		"warnings": micro_report.get("warnings") or [],
	}
	return json.dumps(summary, default=str)


def compose_brief_insight_reply(micro_report: dict) -> str | None:
	"""Deterministic reply when the UI table already shows row details."""
	if not micro_report or (micro_report.get("error") and not micro_report.get("tables")):
		return None

	tables = micro_report.get("tables") or []
	kpis = micro_report.get("kpis") or []
	warnings = micro_report.get("warnings") or []
	company = micro_report.get("company") or ""

	partial_note = ""
	if warnings:
		partial_note = " Partial results — see card for details."

	if len(tables) > 1:
		total_rows = sum(t.get("row_count") or len(t.get("rows") or []) for t in tables)
		sections = "; ".join(
			f"{t.get('title') or 'Section'} ({t.get('row_count') or len(t.get('rows') or [])})"
			for t in tables[:4]
		)
		return (
			f"Found {total_rows} records across {len(tables)} lists — {sections}."
			f"{partial_note} See the card below."
		)

	if tables and tables[0].get("rows"):
		table = tables[0]
		rows = table.get("rows") or []
		count = table.get("row_count") or len(rows)
		title = micro_report.get("title") or table.get("title") or "records"

		highlight = ""
		columns = table.get("columns") or []
		col_names = [
			(c.get("fieldname") if isinstance(c, dict) else c) for c in columns
		]
		if "customer" in col_names:
			customers = []
			for row in rows:
				if isinstance(row, dict):
					val = row.get("customer") or row.get("_customer")
					if val:
						customers.append(str(val))
			if customers:
				top_name = max(set(customers), key=customers.count)
				top_count = customers.count(top_name)
				highlight = f" {top_count} are from {top_name}."
		elif "due_date" in col_names:
			dates = []
			for row in rows:
				if isinstance(row, dict):
					val = row.get("_due_date") or row.get("due_date")
					if val:
						dates.append(str(val))
			if dates:
				highlight = f" Earliest due date: {min(dates)}."

		company_part = f" for {company}" if company else ""
		return (
			f"Found {count} {title.lower()}{company_part}.{highlight}{partial_note} "
			"See the table below for the full list."
		)

	if kpis:
		summary = ", ".join(f"{k.get('label')}: {k.get('value')}" for k in kpis[:3])
		return f"{summary}.{partial_note} See the card below for details."

	return None
