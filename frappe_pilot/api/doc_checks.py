# Deterministic document issue checks for Analyze Agent

import frappe

from frappe_pilot.api.context_utils import DOCSTATUS_LABELS

SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

GL_VOUCHER_DOCTYPES = frozenset({
	"Sales Invoice",
	"Purchase Invoice",
	"Payment Entry",
	"Journal Entry",
})


def _issue(severity, code, message, evidence=None):
	return {
		"severity": severity,
		"code": code,
		"message": message,
		"evidence": evidence or {},
	}


def run_document_checks(doctype, docname):
	"""Run all registered checks for a document. Returns list of issue dicts."""
	from frappe_pilot.utils.settings import get_analyze_config

	if not get_analyze_config().get("enable_document_checks"):
		return {
			"doctype": doctype,
			"docname": docname,
			"issue_count": 0,
			"issues": [],
			"checks_disabled": True,
		}

	if not doctype or not docname:
		return {"error": "doctype and docname are required"}

	if not frappe.db.exists(doctype, docname):
		return {"error": f"Document {doctype} {docname} does not exist"}

	if not frappe.has_permission(doctype, "read", docname):
		return {"permission_denied": True, "issues": []}

	try:
		doc = frappe.get_doc(doctype, docname)
	except frappe.PermissionError:
		return {"permission_denied": True, "issues": []}

	issues = []
	for check_fn in GENERIC_CHECKS:
		issues.extend(check_fn(doc) or [])

	for check_fn in CHECK_REGISTRY.get(doctype, []):
		issues.extend(check_fn(doc) or [])

	for hook_fn_path in frappe.get_hooks("advisor_document_checks") or []:
		try:
			hook_fn = frappe.get_attr(hook_fn_path)
			issues.extend(hook_fn(doc) or [])
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Advisor document check hook failed: {hook_fn_path}")

	return {
		"doctype": doctype,
		"docname": docname,
		"docstatus": DOCSTATUS_LABELS.get(doc.docstatus, str(doc.docstatus)),
		"issue_count": len(issues),
		"issues": issues,
	}


# ── Generic checks ──────────────────────────────────────────────


def check_mandatory_on_submitted(doc):
	if doc.docstatus != 1:
		return []

	issues = []
	meta = frappe.get_meta(doc.doctype)
	for field in meta.fields:
		if not field.reqd or field.fieldtype in ("Table", "Section Break", "Column Break"):
			continue
		value = doc.get(field.fieldname)
		if value is None or value == "" or value == 0 and field.fieldtype not in ("Check",):
			issues.append(_issue(
				SEVERITY_HIGH,
				"MANDATORY_EMPTY_ON_SUBMIT",
				f"Submitted document has empty mandatory field: {field.label or field.fieldname}",
				{"fieldname": field.fieldname, "label": field.label},
			))
	return issues


def check_broken_links(doc):
	issues = []
	meta = frappe.get_meta(doc.doctype)

	for field in meta.fields:
		if field.fieldtype != "Link" or not field.fieldname:
			continue
		value = doc.get(field.fieldname)
		if not value:
			continue

		link_doctype = field.options
		if not link_doctype or not frappe.db.exists("DocType", link_doctype):
			continue

		if not frappe.db.exists(link_doctype, value):
			issues.append(_issue(
				SEVERITY_HIGH,
				"BROKEN_LINK",
				f"Link field '{field.label or field.fieldname}' points to missing {link_doctype}: {value}",
				{"fieldname": field.fieldname, "link_doctype": link_doctype, "value": value},
			))
			continue

		if frappe.get_meta(link_doctype).is_submittable:
			link_docstatus = frappe.db.get_value(link_doctype, value, "docstatus")
			if link_docstatus == 2:
				issues.append(_issue(
					SEVERITY_MEDIUM,
					"LINK_CANCELLED",
					f"Link field '{field.label or field.fieldname}' points to cancelled {link_doctype}: {value}",
					{"fieldname": field.fieldname, "link_doctype": link_doctype, "value": value},
				))

	return issues


def check_empty_item_tables_on_submitted(doc):
	if doc.docstatus != 1:
		return []

	meta = frappe.get_meta(doc.doctype)
	issues = []
	item_table_fields = ("items", "packed_items", "taxes", "payment_schedule")

	for fieldname in item_table_fields:
		if not meta.has_field(fieldname):
			continue
		rows = doc.get(fieldname) or []
		if not rows and fieldname == "items":
			issues.append(_issue(
				SEVERITY_HIGH,
				"EMPTY_ITEMS_ON_SUBMIT",
				f"Submitted {doc.doctype} has no rows in the items table.",
				{"table": fieldname},
			))
	return issues


GENERIC_CHECKS = [
	check_mandatory_on_submitted,
	check_broken_links,
	check_empty_item_tables_on_submitted,
]


# ── ERPNext core checks ─────────────────────────────────────────


def check_gl_after_submit(doc):
	if doc.docstatus != 1 or doc.doctype not in ("Sales Invoice", "Purchase Invoice"):
		return []

	if not frappe.has_permission("GL Entry", "read"):
		return []

	count = frappe.db.count(
		"GL Entry",
		{"voucher_type": doc.doctype, "voucher_no": doc.name, "is_cancelled": 0},
	)
	if count == 0:
		return [_issue(
			SEVERITY_HIGH,
			"NO_GL_AFTER_SUBMIT",
			f"Submitted {doc.doctype} has no GL Entry rows — accounting may not have posted.",
			{"gl_entry_count": 0},
		)]
	return []


def check_invoice_payment_consistency(doc):
	if doc.docstatus != 1 or doc.doctype not in ("Sales Invoice", "Purchase Invoice"):
		return []

	issues = []
	outstanding = float(doc.get("outstanding_amount") or 0)
	grand_total = float(doc.get("grand_total") or 0)
	paid = float(doc.get("paid_amount") or 0)

	if grand_total > 0 and outstanding < 0:
		issues.append(_issue(
			SEVERITY_MEDIUM,
			"NEGATIVE_OUTSTANDING",
			f"Outstanding amount is negative ({outstanding}) while grand total is {grand_total}.",
			{"outstanding_amount": outstanding, "grand_total": grand_total, "paid_amount": paid},
		))

	if paid > grand_total and grand_total > 0:
		issues.append(_issue(
			SEVERITY_MEDIUM,
			"OVERPAID",
			f"Paid amount ({paid}) exceeds grand total ({grand_total}).",
			{"outstanding_amount": outstanding, "grand_total": grand_total, "paid_amount": paid},
		))

	return issues


def check_payment_entry_unallocated(doc):
	if doc.docstatus != 1 or doc.doctype != "Payment Entry":
		return []

	unallocated = float(doc.get("unallocated_amount") or 0)
	if unallocated > 0:
		return [_issue(
			SEVERITY_MEDIUM,
			"UNALLOCATED_PAYMENT",
			f"Payment Entry has unallocated amount of {unallocated}.",
			{"unallocated_amount": unallocated},
		)]
	return []


def check_order_fulfillment(doc):
	if doc.docstatus != 1:
		return []

	issues = []
	if doc.doctype == "Sales Order":
		per_delivered = float(doc.get("per_delivered") or 0)
		per_billed = float(doc.get("per_billed") or 0)
		if per_delivered == 0 and per_billed > 0:
			issues.append(_issue(
				SEVERITY_LOW,
				"BILLED_NOT_DELIVERED",
				f"Sales Order is {per_billed}% billed but 0% delivered.",
				{"per_delivered": per_delivered, "per_billed": per_billed},
			))
	elif doc.doctype == "Purchase Order":
		per_received = float(doc.get("per_received") or 0)
		per_billed = float(doc.get("per_billed") or 0)
		if per_received == 0 and per_billed > 0:
			issues.append(_issue(
				SEVERITY_LOW,
				"BILLED_NOT_RECEIVED",
				f"Purchase Order is {per_billed}% billed but 0% received.",
				{"per_received": per_received, "per_billed": per_billed},
			))
	return issues


# ── Custom / frappe_trs checks ──────────────────────────────────


def check_sales_invoice_rental_order(doc):
	if doc.doctype != "Sales Invoice":
		return []

	meta = frappe.get_meta(doc.doctype)
	rental_field = None
	for field in meta.fields:
		label = (field.label or "").lower()
		fname = (field.fieldname or "").lower()
		if "rental" in label and "order" in label and field.fieldtype == "Link":
			rental_field = field
			break
		if fname in ("rental_order", "custom_rental_order"):
			rental_field = field
			break

	if not rental_field:
		return []

	value = doc.get(rental_field.fieldname)
	if not value:
		return []

	link_doctype = rental_field.options or "Rental Order"
	if not frappe.db.exists(link_doctype, value):
		return [_issue(
			SEVERITY_HIGH,
			"RENTAL_ORDER_MISSING",
			f"Rental Order reference '{value}' does not exist.",
			{"fieldname": rental_field.fieldname, "value": value},
		)]

	ro_docstatus = frappe.db.get_value(link_doctype, value, "docstatus")
	if ro_docstatus == 2:
		return [_issue(
			SEVERITY_MEDIUM,
			"RENTAL_ORDER_CANCELLED",
			f"Linked Rental Order '{value}' is cancelled.",
			{"fieldname": rental_field.fieldname, "value": value},
		)]
	return []


def check_rental_order_job_order(doc):
	if doc.doctype != "Rental Order":
		return []

	if not frappe.db.exists("DocType", "Job Order"):
		return []

	# Light check: active rental order with no linked job orders
	status = (doc.get("status") or "").lower()
	if status in ("active", "in progress", "ongoing") and meta_has_field("Job Order", "rental_order"):
		job_count = frappe.db.count(
			"Job Order",
			{"rental_order": doc.name, "docstatus": ["<", 2]},
		)
		if job_count == 0:
			return [_issue(
				SEVERITY_LOW,
				"NO_JOB_ORDER",
				f"Rental Order status is '{doc.get('status')}' but no active Job Orders are linked.",
				{"status": doc.get("status"), "job_order_count": 0},
			)]
	return []


def meta_has_field(doctype, fieldname):
	return frappe.get_meta(doctype).has_field(fieldname)


CHECK_REGISTRY = {
	"Sales Invoice": [
		check_gl_after_submit,
		check_invoice_payment_consistency,
		check_sales_invoice_rental_order,
	],
	"Purchase Invoice": [
		check_gl_after_submit,
		check_invoice_payment_consistency,
	],
	"Payment Entry": [check_payment_entry_unallocated],
	"Sales Order": [check_order_fulfillment],
	"Purchase Order": [check_order_fulfillment],
	"Rental Order": [check_rental_order_job_order],
}
