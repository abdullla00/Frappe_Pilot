# Read-only tool executors for Analyze Agent

import json

import frappe

from frappe_pilot.api.context_utils import (
	format_doc_summary_block,
	format_field_value,
	format_meta_summary_block,
	get_doc_summary,
	get_meta_summary,
	is_sensitive_field,
)
from frappe_pilot.api.doc_checks import run_document_checks
from frappe_pilot.utils.settings import get_analyze_config


def _limits():
	cfg = get_analyze_config()
	return {
		"linked_docs": cfg["max_linked_docs"],
		"linked_fields": cfg["max_linked_fields"],
		"gl_rows": cfg["max_gl_rows"],
		"list_rows": cfg["max_list_rows"],
		"report_rows": cfg["max_report_rows"],
		"timeline": cfg["max_timeline_items"],
		"json_chars": cfg["max_tool_json_chars"],
	}


def parse_page_context(page_context_raw=""):
	if not page_context_raw:
		return {}
	try:
		ctx = json.loads(page_context_raw) if isinstance(page_context_raw, str) else page_context_raw
		return ctx if isinstance(ctx, dict) else {}
	except (TypeError, ValueError):
		return {}


def _truncate_result(data):
	lim = _limits()["json_chars"]
	text = json.dumps(data, default=str)
	if len(text) <= lim:
		return data
	return {
		"truncated": True,
		"preview": text[:lim] + "…",
	}


def _permission_error(doctype, docname=""):
	return {"permission_denied": True, "message": f"No read permission for {doctype} {docname}".strip()}


# ── Tool executors ──────────────────────────────────────────────


def exec_get_document(doctype="", docname="", user_message=""):
	if not doctype or not docname:
		return {"error": "doctype and docname are required"}

	summary = get_doc_summary(doctype, docname, user_message=user_message)
	if summary.get("permission_denied"):
		return summary
	if summary.get("error"):
		return summary

	return _truncate_result({
		"doctype": summary["doctype"],
		"name": summary["name"],
		"docstatus": summary["docstatus"],
		"fields": summary.get("fields", {}),
		"child_tables": summary.get("child_tables", {}),
	})


def exec_get_linked_documents(doctype="", docname="", max_links=None):
	max_links = max_links or _limits()["linked_docs"]
	if not doctype or not docname:
		return {"error": "doctype and docname are required"}

	if not frappe.has_permission(doctype, "read", docname):
		return _permission_error(doctype, docname)

	doc = frappe.get_doc(doctype, docname)
	meta = frappe.get_meta(doctype)
	linked = []

	for field in meta.fields:
		if field.fieldtype != "Link" or not field.fieldname:
			continue
		value = doc.get(field.fieldname)
		if not value:
			continue

		link_doctype = field.options
		if not link_doctype:
			continue

		if not frappe.has_permission(link_doctype, "read", value):
			linked.append({
				"field": field.label or field.fieldname,
				"link_doctype": link_doctype,
				"name": value,
				"permission_denied": True,
			})
			continue

		if not frappe.db.exists(link_doctype, value):
			linked.append({
				"field": field.label or field.fieldname,
				"link_doctype": link_doctype,
				"name": value,
				"error": "Document does not exist",
			})
			continue

		try:
			link_doc = frappe.get_doc(link_doctype, value)
		except frappe.PermissionError:
			linked.append({
				"field": field.label or field.fieldname,
				"link_doctype": link_doctype,
				"name": value,
				"permission_denied": True,
			})
			continue

		link_meta = frappe.get_meta(link_doctype)
		fields_out = {}
		for lf in link_meta.fields:
			if lf.fieldtype in ("Table", "Section Break", "Column Break", "HTML") or is_sensitive_field(lf.fieldname):
				continue
			fv = format_field_value(link_doc.get(lf.fieldname), lf.fieldtype)
			if fv is not None:
				fields_out[lf.label or lf.fieldname] = fv
			if len(fields_out) >= _limits()["linked_fields"]:
				break

		linked.append({
			"field": field.label or field.fieldname,
			"link_doctype": link_doctype,
			"name": value,
			"docstatus": link_doc.docstatus,
			"fields": fields_out,
		})

		if len(linked) >= max_links:
			break

	return _truncate_result({"linked_documents": linked, "count": len(linked)})


def exec_get_doctype_meta(doctype="", include_list_view=False):
	if not doctype:
		return {"error": "doctype is required"}

	if not frappe.has_permission(doctype, "read"):
		return _permission_error(doctype)

	summary = get_meta_summary(doctype, include_list_view=include_list_view)
	workflow_name = frappe.db.get_value(
		"Workflow", {"document_type": doctype, "is_active": 1}, "name"
	)
	if workflow_name:
		summary["workflow"] = workflow_name

	return _truncate_result(summary)


def exec_get_workflow_state(doctype="", docname=""):
	if not doctype or not docname:
		return {"error": "doctype and docname are required"}

	if not frappe.has_permission(doctype, "read", docname):
		return _permission_error(doctype, docname)

	from frappe.model.workflow import get_workflow, get_workflow_name

	workflow_name = get_workflow_name(doctype)
	if not workflow_name:
		return {"workflow": None, "message": f"No active workflow for {doctype}"}

	doc = frappe.get_doc(doctype, docname)
	workflow = get_workflow(doctype)
	state_field = workflow.workflow_state_field
	current_state = doc.get(state_field)

	transitions = []
	try:
		from frappe.model.workflow import get_transitions
		for t in get_transitions(doc, workflow) or []:
			transitions.append({
				"action": t.get("action"),
				"next_state": t.get("next_state"),
				"allowed": t.get("allowed"),
			})
	except Exception:
		pass

	return {
		"workflow": workflow_name,
		"state_field": state_field,
		"current_state": current_state,
		"available_transitions": transitions[:10],
	}


def exec_get_timeline(doctype="", docname="", limit=None):
	limit = limit or _limits()["timeline"]
	if not doctype or not docname:
		return {"error": "doctype and docname are required"}

	if not frappe.has_permission(doctype, "read", docname):
		return _permission_error(doctype, docname)

	versions = frappe.get_all(
		"Version",
		filters={"ref_doctype": doctype, "docname": docname},
		fields=["owner", "creation"],
		order_by="creation desc",
		limit=limit,
	)

	comments = frappe.get_all(
		"Comment",
		filters={
			"reference_doctype": doctype,
			"reference_name": docname,
			"comment_type": ["in", ["Comment", "Info", "Label"]],
		},
		fields=["owner", "creation", "content"],
		order_by="creation desc",
		limit=limit,
	)

	for c in comments:
		if c.get("content") and len(c["content"]) > 200:
			c["content"] = c["content"][:200] + "…"

	return _truncate_result({
		"versions": versions,
		"comments": comments,
	})


def exec_get_gl_entries(doctype="", docname="", limit=None):
	limit = limit or _limits()["gl_rows"]
	if not doctype or not docname:
		return {"error": "doctype and docname are required"}

	if doctype not in ("Sales Invoice", "Purchase Invoice", "Payment Entry", "Journal Entry"):
		return {"message": f"GL entries not applicable for {doctype}", "entries": []}

	if not frappe.has_permission(doctype, "read", docname):
		return _permission_error(doctype, docname)

	if not frappe.has_permission("GL Entry", "read"):
		return _permission_error("GL Entry")

	entries = frappe.get_all(
		"GL Entry",
		filters={"voucher_type": doctype, "voucher_no": docname, "is_cancelled": 0},
		fields=[
			"account", "debit", "credit", "debit_in_account_currency",
			"credit_in_account_currency", "posting_date", "cost_center", "party",
		],
		order_by="creation asc",
		limit=limit,
	)

	return _truncate_result({
		"voucher_type": doctype,
		"voucher_no": docname,
		"entry_count": len(entries),
		"entries": entries,
	})


def exec_get_list_sample(doctype="", filters=None, fields=None, limit=None):
	limit = limit or _limits()["list_rows"]
	if not doctype:
		return {"error": "doctype is required"}

	if not frappe.has_permission(doctype, "read"):
		return _permission_error(doctype)

	filters = filters or []
	fields = fields or ["name"]

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

	# Normalise field list for reportview
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

	return _truncate_result({
		"doctype": doctype,
		"filters": filters,
		"fields": fields,
		"row_count": len(rows),
		"rows": rows,
	})


def exec_get_list_count(doctype="", filters=None):
	if not doctype:
		return {"error": "doctype is required"}

	if not frappe.has_permission(doctype, "read"):
		return _permission_error(doctype)

	filters = filters or []
	if isinstance(filters, str):
		try:
			filters = json.loads(filters)
		except (TypeError, ValueError):
			filters = []

	try:
		count = frappe.db.count(doctype, filters)
	except Exception:
		count = None

	return {
		"doctype": doctype,
		"filters": filters,
		"count": count,
	}


def exec_run_report_sample(report_name="", filters=None, limit=None):
	limit = limit or _limits()["report_rows"]
	if not report_name:
		return {"error": "report_name is required"}

	filters = filters or {}
	if isinstance(filters, str):
		try:
			filters = json.loads(filters)
		except (TypeError, ValueError):
			filters = {}

	try:
		from frappe.desk.query_report import run
		result = run(report_name, filters=filters)
	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "Analyze Report Run Error")
		return {"error": str(exc), "report_name": report_name}

	columns = result.get("columns") or []
	rows = result.get("result") or []

	col_labels = []
	for col in columns:
		if isinstance(col, dict):
			col_labels.append(col.get("label") or col.get("fieldname") or "")
		else:
			col_labels.append(str(col))

	sample_rows = rows[:limit]
	# Convert rows to dicts if they are lists
	formatted_rows = []
	for row in sample_rows:
		if isinstance(row, dict):
			formatted_rows.append(row)
		elif isinstance(row, (list, tuple)):
			formatted_rows.append(dict(zip(col_labels, row)))

	return _truncate_result({
		"report_name": report_name,
		"filters": filters,
		"columns": col_labels,
		"total_rows": len(rows),
		"sample_row_count": len(formatted_rows),
		"rows": formatted_rows,
		"add_total_row": result.get("add_total_row"),
	})


def exec_run_document_checks(doctype="", docname=""):
	return _truncate_result(run_document_checks(doctype, docname))


def exec_get_domain_calc_context(doctype="", docname="", days=None):
	if not doctype or not docname:
		return {"error": "doctype and docname are required"}

	from frappe_pilot.utils.advisor_profile import get_advisor_profile

	profile = get_advisor_profile(doctype)
	context = {"doctype": doctype, "docname": docname, "days": days, "lines": [], "notes": []}

	for provider in frappe.get_hooks("advisor_calc_context") or []:
		try:
			hook_result = frappe.get_attr(provider)(
				doctype=doctype,
				docname=docname,
				days=days,
				profile=profile,
			)
			if isinstance(hook_result, dict):
				for line in hook_result.get("lines") or []:
					context["lines"].append(line)
				context["notes"].extend(hook_result.get("notes") or [])
				if hook_result.get("currency"):
					context["currency"] = hook_result.get("currency")
				suggested = hook_result.get("suggested_card") or hook_result.get("card")
				if suggested:
					context["suggested_card"] = suggested
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Advisor calc hook failed: {provider}")

	if context.get("lines") or context.get("suggested_card"):
		frappe.local.advisor_calc_evidence = {
			"lines": context.get("lines") or [],
			"days": days,
			"currency": context.get("currency"),
		}

	if not context["lines"] and not context.get("suggested_card"):
		summary = get_doc_summary(doctype, docname)
		if summary.get("child_tables"):
			items = summary.get("child_tables", {}).get("items") or []
			for row in items[:30]:
				context["lines"].append({
					"item_code": row.get("item_code") or row.get("item_name"),
					"role": "unknown",
					"rate": row.get("rate"),
					"qty": row.get("qty"),
				})

	return _truncate_result(context)


def exec_submit_advisor_card(card=None):
	from frappe_pilot.utils.advisor_card import normalize_advisor_card, validate_advisor_card

	if not card or not isinstance(card, dict):
		return {"error": "card object is required", "accepted": False}

	evidence = getattr(frappe.local, "advisor_calc_evidence", None)
	validated = validate_advisor_card(card, evidence=evidence)
	if validated.get("error"):
		return {"error": validated.get("error"), "accepted": False}

	normalized = normalize_advisor_card(validated, evidence=evidence)
	if normalized.get("error"):
		return {"error": normalized.get("error"), "accepted": False}

	return {"accepted": True, "card": normalized, "warnings": normalized.get("warnings") or []}


TOOL_HANDLERS = {
	"get_document": exec_get_document,
	"get_linked_documents": exec_get_linked_documents,
	"get_doctype_meta": exec_get_doctype_meta,
	"get_workflow_state": exec_get_workflow_state,
	"get_timeline": exec_get_timeline,
	"get_gl_entries": exec_get_gl_entries,
	"get_list_sample": exec_get_list_sample,
	"get_list_count": exec_get_list_count,
	"run_report_sample": exec_run_report_sample,
	"run_document_checks": exec_run_document_checks,
	"get_domain_calc_context": exec_get_domain_calc_context,
	"submit_advisor_card": exec_submit_advisor_card,
}


def execute_tool(tool_name, tool_args, *, page_context=None, default_doctype="", default_docname=""):
	"""Dispatch a tool call, filling in doctype/docname from page context when omitted."""
	handler = TOOL_HANDLERS.get(tool_name)
	if not handler:
		return {"error": f"Unknown tool: {tool_name}"}

	args = dict(tool_args or {})
	page_context = page_context or {}

	if not args.get("doctype") and default_doctype:
		args["doctype"] = default_doctype
	if not args.get("docname") and default_docname:
		args["docname"] = default_docname

	# Inject list/report context from page_context when relevant
	if tool_name == "get_list_sample" and page_context.get("page_type") == "list":
		args.setdefault("doctype", page_context.get("list_doctype"))
		args.setdefault("filters", page_context.get("list_filters"))
		args.setdefault("fields", page_context.get("list_fields"))

	if tool_name == "get_list_count" and page_context.get("page_type") == "list":
		args.setdefault("doctype", page_context.get("list_doctype"))
		args.setdefault("filters", page_context.get("list_filters"))

	if tool_name == "run_report_sample" and page_context.get("page_type") == "report":
		args.setdefault("report_name", page_context.get("report_name"))
		args.setdefault("filters", page_context.get("report_filters"))

	try:
		return handler(**args)
	except TypeError:
		# Fallback: pass only recognised kwargs
		import inspect
		sig = inspect.signature(handler)
		filtered = {k: v for k, v in args.items() if k in sig.parameters}
		return handler(**filtered)
	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), f"Analyze Tool Error: {tool_name}")
		return {"error": str(exc), "tool": tool_name}
