# Guarded read-only SQL for Insight (SM-only, last resort)

from __future__ import annotations

import re

import frappe
from frappe.model import get_permitted_fields

from frappe_pilot.utils.insight_permissions import check_doctype_access
from frappe_pilot.utils.report_defaults import resolve_insight_context
from frappe_pilot.utils.settings import get_insight_config

_FORBIDDEN = re.compile(
	r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE)\b",
	re.IGNORECASE,
)
_TAB_PATTERN = re.compile(r"`?tab([A-Za-z0-9_ ]+)`?", re.IGNORECASE)
_COMPANY_FILTER_PATTERN = re.compile(r"\bcompany\b", re.IGNORECASE)


def _is_sql_allowed() -> bool:
	cfg = get_insight_config()
	if not cfg.get("enable_readonly_sql"):
		return False
	roles = set(frappe.get_roles())
	return frappe.session.user == "Administrator" or "System Manager" in roles


def _doctype_from_tab(tab_name: str) -> str:
	clean = (tab_name or "").strip().strip("`").strip('"')
	if clean.lower().startswith("tab"):
		clean = clean[3:]
	return clean.replace("_", " ") if "_" in clean else clean


def _parse_tab_doctypes(query: str) -> list[str]:
	doctypes: list[str] = []
	seen: set[str] = set()
	for match in _TAB_PATTERN.finditer(query or ""):
		dt = _doctype_from_tab(match.group(1))
		if dt not in seen and frappe.db.exists("DocType", dt):
			seen.add(dt)
			doctypes.append(dt)
	return doctypes


def _validate_query(query: str) -> dict | None:
	q = (query or "").strip()
	if not q:
		return {"error": "query_required"}
	if _FORBIDDEN.search(q):
		return {"error": "sql_forbidden_statement"}
	inner = q.rstrip(";").strip()
	if ";" in inner:
		return {"error": "sql_single_statement_only"}
	if not re.match(r"^\s*(SELECT|WITH)\b", q, re.IGNORECASE):
		return {"error": "sql_select_only"}
	return None


def _doctype_has_company(doctype: str) -> bool:
	meta = frappe.get_meta(doctype)
	return any(f.fieldname == "company" for f in meta.fields)


def _requires_company_filter(doctypes: list[str]) -> bool:
	return any(_doctype_has_company(dt) for dt in doctypes)


def _inject_company_filters(query: str, doctypes: list[str], company: str) -> str | dict:
	"""Append company predicates for each referenced doctype that has a company field."""
	if not company:
		if _requires_company_filter(doctypes):
			return {"error": "company_required", "message": "Company context is required for this query."}
		return query

	if _COMPANY_FILTER_PATTERN.search(query):
		return query

	predicates: list[str] = []
	escaped_company = frappe.db.escape(company)
	for dt in doctypes:
		if not _doctype_has_company(dt):
			continue
		tab = f"`tab{dt}`"
		if tab.lower() in query.lower() or f"tab{dt.replace(' ', '_')}".lower() in query.lower():
			predicates.append(f"{tab}.company = {escaped_company}")

	if not predicates:
		return query

	q = query.strip().rstrip(";")
	joiner = " AND "
	if re.search(r"\bWHERE\b", q, re.IGNORECASE):
		return f"{q}{joiner}{joiner.join(predicates)}"
	return f"{q} WHERE {joiner.join(predicates)}"


def _permission_names_subquery(doctype: str, *, parent_doctype: str | None = None) -> str | None:
	if not frappe.has_permission(doctype, "read"):
		return None
	try:
		return str(
			frappe.get_list(
				doctype,
				fields=["name"],
				order_by=None,
				parent_doctype=parent_doctype,
				run=False,
			)
		)
	except Exception:
		return None


def _primary_doctype(doctypes: list[str]) -> str | None:
	if len(doctypes) == 1:
		return doctypes[0]
	return doctypes[0] if doctypes else None


def _can_enforce_row_permissions(query: str, doctype: str) -> bool:
	if len(_parse_tab_doctypes(query)) != 1:
		return False
	if re.search(r"\b(GROUP BY|UNION|JOIN)\b", query, re.IGNORECASE):
		return False
	meta = frappe.get_meta(doctype)
	if meta.istable:
		return False
	return True


def _wrap_with_row_permissions(query: str, doctype: str) -> str | dict:
	if not _can_enforce_row_permissions(query, doctype):
		return {
			"error": "sql_permission_unenforceable",
			"message": "Row-level permissions cannot be applied safely to this query.",
		}

	perm_sql = _permission_names_subquery(doctype)
	if not perm_sql:
		return {"error": "permission_denied", "doctype": doctype}

	q = query.strip().rstrip(";")
	tab = f"`tab{doctype}`"
	if tab.lower() in q.lower() or f"tab{doctype.replace(' ', '_')}".lower() in q.lower():
		if re.search(r"\bWHERE\b", q, re.IGNORECASE):
			return f"{q} AND {tab}.name IN ({perm_sql})"
		return f"{q} WHERE {tab}.name IN ({perm_sql})"

	# Fallback: wrap entire query and filter on name column in result set.
	if not re.search(r"\bname\b", q, re.IGNORECASE):
		return {
			"error": "sql_permission_unenforceable",
			"message": "Include the name column or query a single DocType table directly.",
		}
	return (
		f"SELECT _insight.* FROM ({q}) AS _insight "
		f"WHERE _insight.name IN ({perm_sql})"
	)


def _permitted_columns_for_doctypes(doctypes: list[str]) -> dict[str, set[str]]:
	perms: dict[str, set[str]] = {}
	for dt in doctypes:
		try:
			perms[dt] = set(get_permitted_fields(dt, ignore_virtual=True))
		except Exception:
			perms[dt] = set()
	return perms


def _strip_disallowed_columns(rows: list[dict], doctypes: list[str]) -> list[dict]:
	if not rows or not doctypes:
		return rows

	perms = _permitted_columns_for_doctypes(doctypes)
	allowed: set[str] = set()
	for fields in perms.values():
		allowed |= fields

	if not allowed:
		return rows

	filtered: list[dict] = []
	for row in rows:
		filtered.append({k: v for k, v in row.items() if k in allowed or k == "name"})
	return filtered


def exec_run_readonly_query(query: str = "", title: str = "", columns: list | None = None):
	if not _is_sql_allowed():
		return {
			"error": "sql_not_allowed",
			"message": "Read-only SQL is restricted to System Managers.",
		}

	err = _validate_query(query)
	if err:
		return err

	cfg = get_insight_config()
	limit = cfg.get("max_list_rows") or 25
	ctx = resolve_insight_context()
	company = ctx.get("company")

	doctypes = _parse_tab_doctypes(query)
	if not doctypes:
		return {"error": "sql_no_tables_found"}

	for dt in doctypes:
		if blocked := check_doctype_access(dt):
			return blocked

	company_result = _inject_company_filters(query, doctypes, company)
	if isinstance(company_result, dict):
		return company_result
	q = company_result

	primary = _primary_doctype(doctypes)
	if primary:
		perm_result = _wrap_with_row_permissions(q, primary)
		if isinstance(perm_result, dict):
			return perm_result
		q = perm_result

	if not re.search(r"\bLIMIT\b", q, re.IGNORECASE):
		q = f"{q} LIMIT {int(limit)}"

	try:
		rows = frappe.db.sql(q, as_dict=True, timeout=10)
	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "Insight SQL Error")
		return {"error": str(exc), "query": query}

	filtered_rows = _strip_disallowed_columns(rows, doctypes)
	col_names = list(filtered_rows[0].keys()) if filtered_rows else (columns or [])

	return {
		"query": query,
		"executed_query": q,
		"title": title or "Query Results",
		"columns": col_names,
		"rows": filtered_rows,
		"row_count": len(filtered_rows),
		"doctypes": doctypes,
		"company": company,
	}
