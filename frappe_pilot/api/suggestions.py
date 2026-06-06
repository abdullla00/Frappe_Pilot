# Context-aware suggestion chips and Build quick actions

import json

import frappe

from frappe_pilot.api.doc_checks import CHECK_REGISTRY
from frappe_pilot.utils.i18n import (
	apply_chip_locale_scope,
	build_chip_meta,
	expand_split_chips,
	format_greet,
	localize_actions,
)
from frappe_pilot.utils.settings import get_chip_locale_scope, get_enabled_languages

MAX_CHIPS = 4
MAX_ACTIONS = 4

DIAGNOSE_CHIP_LABELS = frozenset({
	"Diagnose this record",
	"Flag anything unusual",
	"Why are these records here?",
	"Why is this total high?",
	"Diagnose rental status",
	"Diagnose posting issues",
	"Check Job Order linkage",
})

# ── Guide: form DocType chips (migrated from ai_sidebar.js) ───────────────

GUIDE_FORM_CHIPS = {
	"Customer": [
		"How do I add a GSTIN field?",
		"How do I set a credit limit?",
		"How do I link contacts?",
		"How do I create a Sales Order?",
	],
	"Supplier": [
		"How do I track outstanding payments?",
		"How do I set payment terms?",
		"How do I add a PAN field?",
		"How do I block a supplier?",
	],
	"Sales Invoice": [
		"What happens when I submit this?",
		"How do I apply a discount?",
		"How do I create a credit note?",
		"How do I record a partial payment?",
	],
	"Purchase Invoice": [
		"How do I match this to a PO?",
		"How do I record a partial payment?",
		"What is Save vs Submit?",
		"How do I handle a debit note?",
	],
	"Sales Order": [
		"How do I create an invoice from this?",
		"How do I check delivery status?",
		"How do I add an approval workflow?",
		"How do I handle partial delivery?",
	],
	"Purchase Order": [
		"How do I receive goods against this?",
		"How do I set up approval workflow?",
		"How do I create a Purchase Invoice?",
		"How do I cancel and amend?",
	],
	"Employee": [
		"How do I set up payroll?",
		"How do I assign a leave policy?",
		"How do I add an emergency contact?",
		"How do I track attendance?",
	],
	"Item": [
		"How do I add item variants?",
		"How do I set a reorder level?",
		"How do I track in multiple warehouses?",
		"Stock vs non-stock items?",
	],
	"Payment Entry": [
		"How do I reconcile against an invoice?",
		"How do I handle foreign currency?",
		"How do I reverse this payment?",
		"What accounts does this affect?",
	],
	"Stock Entry": [
		"Material Transfer vs Issue?",
		"How do I do a stock reconciliation?",
		"How do I track batch numbers?",
		"How do I move stock between warehouses?",
	],
	"Delivery Note": [
		"How do I create an invoice from this?",
		"How do I track the Sales Order?",
		"How do I handle a return?",
		"How do I print a packing slip?",
	],
	"Journal Entry": [
		"When to use this vs Payment Entry?",
		"How do I reverse this entry?",
		"How do I reconcile with bank?",
		"Debit vs credit here?",
	],
	"Warehouse": [
		"How do I transfer stock here?",
		"How do I check stock levels?",
		"How do I set a default warehouse?",
		"How do I create a child warehouse?",
	],
	"Lead": [
		"How do I convert to a customer?",
		"How do I assign to a salesperson?",
		"How do I schedule a follow-up?",
		"How do I track lead source?",
	],
	"Quotation": [
		"How do I convert to Sales Order?",
		"How do I apply a discount?",
		"How do I send by email?",
		"How do I set an expiry date?",
	],
	"Social Login Key": [
		"What is a Social Login Key?",
		"How do I set up Google login?",
		"How do I get a Client ID and Secret?",
		"How do I enable OAuth for ERPNext?",
	],
}

GUIDE_LIST_CHIPS = {
	"Customer": [
		"How do I create a new customer?",
		"How do I filter by territory?",
		"How do I export this list?",
		"How do I bulk update?",
	],
	"Item": [
		"How do I create a new item?",
		"How do I check stock levels?",
		"How do I set item prices?",
		"How do I add variants?",
	],
	"Sales Invoice": [
		"How do I create a new invoice?",
		"How do I filter unpaid invoices?",
		"How do I see overdue invoices?",
		"How do I bulk send by email?",
	],
	"Purchase Order": [
		"How do I create a PO?",
		"How do I check pending orders?",
		"How do I filter by supplier?",
		"How do I close a PO?",
	],
	"Stock Entry": [
		"How do I create a stock transfer?",
		"How do I do a reconciliation?",
		"How do I filter by warehouse?",
		"What are the entry types?",
	],
	"Employee": [
		"How do I add a new employee?",
		"How do I filter by department?",
		"How do I export employee data?",
		"How do I check attendance?",
	],
	"Payment Entry": [
		"How do I record a payment?",
		"How do I reconcile payments?",
		"How do I filter unreconciled?",
		"How do I handle advances?",
	],
	"Supplier": [
		"How do I add a supplier?",
		"How do I check outstanding payables?",
		"How do I filter by group?",
		"How do I block a supplier?",
	],
	"Social Login Key": [
		"What is a Social Login Key?",
		"How do I add a new provider?",
		"How do I set up Google OAuth?",
		"How do I get a Client Secret?",
	],
}

GUIDE_ROUTE_CHIPS = {
	"stock": [
		"How do I do a stock transfer?",
		"How do I check stock levels?",
		"What is a Stock Entry?",
		"How do I set a reorder level?",
	],
	"selling": [
		"How do I create a Sales Order?",
		"How do I apply a discount?",
		"How do I create a quotation?",
		"How do I track outstanding invoices?",
	],
	"buying": [
		"How do I create a Purchase Order?",
		"How do I record goods received?",
		"How do I set payment terms?",
		"How do I create a Purchase Invoice?",
	],
	"account": [
		"How do I reconcile a bank statement?",
		"How do I create a Journal Entry?",
		"How do I record a payment?",
		"How do I view the general ledger?",
	],
	"hr": [
		"How do I run payroll?",
		"How do I mark attendance?",
		"How do I set up leave policies?",
		"How do I create an employee?",
	],
	"integrat": [
		"What is a Social Login Key?",
		"How do I set up OAuth?",
		"How do I connect to third-party apps?",
		"How do I use REST API?",
	],
	"report": [
		"How do I filter this report?",
		"How do I export report data?",
		"How do I save filters?",
		"How do I schedule by email?",
	],
}

# ── Analyze: per-DocType chips (saved document) ─────────────────────────────

ANALYZE_SAVED_CHIPS = {
	"Sales Invoice": [
		"Check payment status",
		"Verify GL entries",
		"Diagnose this record",
		"Summarize this record",
	],
	"Purchase Invoice": [
		"Check payment status",
		"Verify GL entries",
		"Diagnose this record",
		"Summarize this record",
	],
	"Payment Entry": [
		"Check unallocated amount",
		"Diagnose this record",
		"Summarize this record",
		"What should I do next?",
	],
	"Sales Order": [
		"Check fulfillment status",
		"Diagnose this record",
		"Summarize this record",
		"What should I do next?",
	],
	"Purchase Order": [
		"Check fulfillment status",
		"Diagnose this record",
		"Summarize this record",
		"What should I do next?",
	],
	"Rental Order": [
		"Check Job Order linkage",
		"Diagnose rental status",
		"Summarize this order",
		"What should I do next?",
	],
	"Pilot Settings": [
		"Explain each settings tab",
		"How do API keys work here?",
		"What should I configure first?",
		"Summarize current settings",
	],
	"Customer": [
		"Summarize this customer",
		"Check outstanding balance",
		"Diagnose this record",
		"What should I do next?",
	],
	"Item": [
		"Summarize this item",
		"Check stock levels",
		"Diagnose this record",
		"What should I do next?",
	],
}

ANALYZE_NEW_FORM_CHIPS = {
	"Sales Invoice": [
		"What fields are required?",
		"Walk me through filling this in",
		"Pre-submit checklist",
	],
	"Purchase Invoice": [
		"What fields are required?",
		"Walk me through filling this in",
		"Pre-submit checklist",
	],
	"Pilot Settings": [
		"What is Pilot Settings for?",
		"How do API keys work here?",
		"What should I configure first?",
	],
}

ANALYZE_LIST_CHIPS = {
	"Sales Invoice": [
		"Why are these invoices here?",
		"Show unpaid invoices",
		"What do the columns mean?",
	],
	"Customer": [
		"Why are these customers here?",
		"What do the columns mean?",
		"What can I do on this list?",
	],
}

# ── Report chips ───────────────────────────────────────────────────────────

REPORT_CHIP_REGISTRY = {
	"General Ledger": [
		"Explain this balance",
		"Why is this total high?",
		"Explain the filters",
		"Flag anything unusual",
	],
	"Accounts Receivable": [
		"Who owes the most?",
		"Why is this total high?",
		"Explain the filters",
		"Flag anything unusual",
	],
	"Accounts Payable": [
		"What do we owe?",
		"Why is this total high?",
		"Explain the filters",
		"Flag anything unusual",
	],
	"Stock Balance": [
		"Which items are low?",
		"Why is this total high?",
		"Explain the filters",
		"What does this report show?",
	],
	"Sales Register": [
		"What does this report show?",
		"Why is this total high?",
		"Explain the filters",
	],
	"Purchase Register": [
		"What does this report show?",
		"Why is this total high?",
		"Explain the filters",
	],
}

# ── Module fallbacks for Analyze ─────────────────────────────────────────────

MODULE_ANALYZE_CHIPS = {
	"Selling": [
		"What can I analyze on this page?",
		"Summarize selling activity",
		"What should I check?",
	],
	"Buying": [
		"What can I analyze on this page?",
		"Summarize buying activity",
		"What should I check?",
	],
	"Stock": [
		"What can I analyze on this page?",
		"Check stock implications",
		"What should I check?",
	],
	"Accounts": [
		"What can I analyze on this page?",
		"Check accounting impact",
		"What should I check?",
	],
	"HR": [
		"What can I analyze on this page?",
		"What should I check?",
	],
}


@frappe.whitelist()
def get_context_suggestions(
	tab,
	doctype="",
	docname="",
	route="",
	list_doctype="",
	page_context=None,
	sidebar_locale="en",
):
	"""Return context-aware chips/actions for Advisor or Build."""
	page_ctx = _parse_page_context(page_context)
	return build_suggestions(
		tab=(tab or "advisor").lower(),
		doctype=doctype or "",
		docname=docname or "",
		route=route or "",
		list_doctype=list_doctype or "",
		page_ctx=page_ctx,
		sidebar_locale=sidebar_locale or "en",
	)


def suggest_chips(doctype="", docname="", list_doctype="", route="", page_ctx=None):
	"""Shortcut for advisor post-reply chips."""
	result = build_suggestions(
		tab="advisor",
		doctype=doctype or "",
		docname=docname or "",
		route=route or "",
		list_doctype=list_doctype or "",
		page_ctx=page_ctx or {},
	)
	return result.get("chips") or []


def build_suggestions(*, tab, doctype, docname, route, list_doctype, page_ctx, sidebar_locale="en"):
	tab = (tab or "advisor").lower()
	if tab in ("analyze", "guide"):
		tab = "advisor"
	ctx = _resolve_context(doctype, docname, route, list_doctype, page_ctx)
	langs = get_enabled_languages()
	chip_scope = get_chip_locale_scope()

	if tab == "build":
		raw_chips = []
		greet_en = _build_build_greet(ctx)
		actions = _build_build_actions(ctx)[:MAX_ACTIONS]
	else:
		raw_chips = _build_advisor_chips(ctx)
		greet_en = _build_analyze_greet(ctx)
		actions = []

	structured = expand_split_chips(raw_chips, langs, max_en=MAX_CHIPS)
	structured = apply_chip_locale_scope(structured, langs, sidebar_locale, chip_scope)
	localized_actions = localize_actions(actions, langs)
	localized_actions = apply_chip_locale_scope(
		localized_actions, langs, sidebar_locale, chip_scope
	)
	greet_out = format_greet(greet_en, ctx, tab, langs, sidebar_locale=sidebar_locale)
	return {
		"greet": greet_out["greet"],
		"greet_locale": greet_out.get("greet_locale") or "en",
		"chips": structured,
		"chip_meta": build_chip_meta(structured),
		"actions": localized_actions,
	}


def _parse_page_context(page_context):
	if not page_context:
		return {}
	if isinstance(page_context, dict):
		return page_context
	try:
		return json.loads(page_context) if page_context else {}
	except (TypeError, ValueError):
		return {}


def _resolve_context(doctype, docname, route, list_doctype, page_ctx):
	ctx = {
		"doctype": doctype,
		"docname": docname,
		"route": route,
		"list_doctype": list_doctype or page_ctx.get("list_doctype") or "",
		"page_type": page_ctx.get("page_type") or "",
		"report_name": page_ctx.get("report_name") or "",
		"is_new": bool(doctype and not docname),
		"has_saved_doc": bool(doctype and docname),
		"docstatus": None,
		"module": "",
		"has_checks": False,
		"outstanding_amount": None,
		"has_rental_order_link": False,
	}

	if ctx["has_saved_doc"]:
		doc_info = _load_doc_signals(doctype, docname)
		ctx.update(doc_info)

	if doctype and not ctx["module"]:
		ctx["module"] = _get_doctype_module(doctype)
	elif ctx["list_doctype"]:
		ctx["module"] = _get_doctype_module(ctx["list_doctype"])

	if doctype in CHECK_REGISTRY:
		ctx["has_checks"] = True

	if not ctx["page_type"]:
		if ctx["has_saved_doc"] or (doctype and ctx["is_new"]):
			ctx["page_type"] = "form"
		elif ctx["list_doctype"]:
			ctx["page_type"] = "list"
		elif ctx["report_name"] or (route and "report" in route.lower()):
			ctx["page_type"] = "report"
		elif route:
			ctx["page_type"] = "other"
		else:
			ctx["page_type"] = "dashboard"

	return ctx


def _load_doc_signals(doctype, docname):
	info = {
		"docstatus": None,
		"outstanding_amount": None,
		"has_rental_order_link": False,
	}

	if not frappe.db.exists(doctype, docname):
		return info

	if not frappe.has_permission(doctype, "read", docname):
		return info

	try:
		doc = frappe.get_doc(doctype, docname)
	except frappe.PermissionError:
		return info

	info["docstatus"] = doc.docstatus

	if doc.meta.has_field("outstanding_amount"):
		info["outstanding_amount"] = doc.get("outstanding_amount")

	if doc.meta.has_field("rental_order"):
		info["has_rental_order_link"] = bool(doc.get("rental_order"))

	return info


def _get_doctype_module(doctype):
	try:
		return frappe.db.get_value("DocType", doctype, "module") or ""
	except Exception:
		return ""


def _dedupe_cap(items, limit=MAX_CHIPS):
	seen = set()
	result = []
	for item in items:
		if not item or item in seen:
			continue
		seen.add(item)
		result.append(item)
		if len(result) >= limit:
			break
	return result


def _build_chip_meta(chips):
	meta = {}
	for chip in chips:
		if chip in DIAGNOSE_CHIP_LABELS:
			meta[chip] = {"mode": "diagnose"}
	return meta


# ── Advisor (merged Analyze + Guide) ─────────────────────────────────────────


def _build_advisor_chips(ctx):
	analyze = _build_analyze_chips(ctx)
	guide = _build_guide_chips(ctx)
	seen = set()
	merged = []
	for chip in analyze + guide:
		key = (chip or "").strip().lower()
		if not key or key in seen:
			continue
		seen.add(key)
		merged.append(chip)
	return merged[:MAX_CHIPS]


# ── Analyze ──────────────────────────────────────────────────────────────────


def _build_analyze_chips(ctx):
	chips = []

	if ctx["has_saved_doc"]:
		chips.extend(_analyze_saved_doc_chips(ctx))
	elif ctx["doctype"]:
		chips.extend(ANALYZE_NEW_FORM_CHIPS.get(ctx["doctype"], [
			"What fields are required?",
			"What is this form for?",
			"Walk me through filling this in",
		]))
	elif ctx["page_type"] == "list" or ctx["list_doctype"]:
		dt = ctx["list_doctype"]
		chips.extend(ANALYZE_LIST_CHIPS.get(dt, [
			"Why are these records here?",
			"What do the columns mean?",
			"What can I do on this list?",
		]))
	elif ctx["page_type"] == "report" or ctx["report_name"]:
		report = ctx["report_name"]
		chips.extend(_report_chips(report))
	elif ctx["route"]:
		chips.extend(_route_analyze_chips(ctx))
	else:
		chips.extend([
			"What page am I on?",
			"Where should I go to analyze a document?",
		])

	return _dedupe_cap(chips)


def _analyze_saved_doc_chips(ctx):
	doctype = ctx["doctype"]
	docstatus = ctx["docstatus"]
	chips = list(ANALYZE_SAVED_CHIPS.get(doctype, []))

	if not chips:
		if ctx["has_checks"]:
			chips = [
				"Diagnose this record",
				"Summarize this record",
				"What should I do next?",
			]
		else:
			chips = [
				"Summarize this record",
				"What should I do next?",
				"Flag anything unusual",
			]

	if docstatus == 0 and doctype not in ("Pilot Settings",):
		chips = [
			c for c in chips
			if c not in ("Verify GL entries", "Check payment status", "Diagnose posting issues")
		]
		chips = ["What to fix before submit?", "Can I submit this?"] + chips

	if docstatus == 1 and doctype in ("Sales Invoice", "Purchase Invoice"):
		if ctx["outstanding_amount"] and float(ctx["outstanding_amount"] or 0) > 0:
			chips = ["Check payment status"] + [c for c in chips if c != "Check payment status"]

	if ctx["has_rental_order_link"] and doctype == "Sales Invoice":
		chips = ["Check Rental Order link"] + [c for c in chips if c != "Check Rental Order link"]

	if ctx["has_checks"] and "Diagnose this record" not in chips:
		chips.insert(0, "Diagnose this record")

	return chips


def _report_chips(report_name):
	if report_name in REPORT_CHIP_REGISTRY:
		return list(REPORT_CHIP_REGISTRY[report_name])
	for key, chips in REPORT_CHIP_REGISTRY.items():
		if key.lower() in (report_name or "").lower():
			return list(chips)
	return [
		"What does this report show?",
		"Why is this total high?",
		"Explain the filters",
	]


def _route_analyze_chips(ctx):
	route = (ctx["route"] or "").lower()
	if "report" in route:
		return _report_chips(ctx["report_name"])
	module = ctx["module"]
	if module in MODULE_ANALYZE_CHIPS:
		return list(MODULE_ANALYZE_CHIPS[module])
	return [
		"What is this page for?",
		"What can I do here?",
	]


def _build_analyze_greet(ctx):
	if ctx["has_saved_doc"]:
		return (
			f"I can analyze <strong>{ctx['doctype']}: {ctx['docname']}</strong> "
			"using live data and automated checks. Ask me anything or tap a suggestion:"
		)
	if ctx["doctype"]:
		return (
			f"You're on a new <strong>{ctx['doctype']}</strong> form. "
			"I can explain the fields and what to fill in:"
		)
	if ctx["page_type"] == "list" or ctx["list_doctype"]:
		dt = ctx["list_doctype"]
		return (
			f"You're on the <strong>{dt} list</strong>. "
			"I can fetch filtered rows and explain why records appear here:"
		)
	if ctx["page_type"] == "report" or ctx["report_name"]:
		rn = ctx["report_name"] or "this report"
		return (
			f"You're on report <strong>{rn}</strong>. "
			"I can run it with your current filters and explain the results:"
		)
	if ctx["route"]:
		return (
			f"You're on <strong>{ctx['route']}</strong>. "
			"I can fetch page data and explain what you are seeing:"
		)
	return "Navigate to a document, list, or report to analyze it — or ask a general question:"


# ── Guide ────────────────────────────────────────────────────────────────────


def _build_guide_chips(ctx):
	if ctx["doctype"] and ctx["doctype"] in GUIDE_FORM_CHIPS:
		return list(GUIDE_FORM_CHIPS[ctx["doctype"]])

	if ctx["list_doctype"] and ctx["list_doctype"] in GUIDE_LIST_CHIPS:
		return list(GUIDE_LIST_CHIPS[ctx["list_doctype"]])

	route = (ctx["route"] or "").lower()
	for key, chips in GUIDE_ROUTE_CHIPS.items():
		if key in route:
			return list(chips)

	return [
		"What is a DocType?",
		"How do I add a custom field?",
		"How do workflows work?",
		"How do I set up permissions?",
	]


def _build_guide_greet(ctx):
	if ctx["doctype"]:
		return (
			f"I can see you're on the <strong>{ctx['doctype']}</strong> form. "
			"Here are some things I can help you with:"
		)
	if ctx["list_doctype"]:
		return (
			f"I can see you're on the <strong>{ctx['list_doctype']} list</strong>. "
			"Here are some things I can help you with:"
		)
	if ctx["route"]:
		return (
			f"I can see you're on <strong>{ctx['route']}</strong>. "
			"Here are some things I can help you with:"
		)
	return "Hi! I'm your ERPNext Guide. Pick a question below or ask anything:"


# ── Build ────────────────────────────────────────────────────────────────────


def _build_build_greet(ctx):
	target = ctx["doctype"] or ctx["list_doctype"] or ""
	if target:
		return (
			f"I'm <strong>Frappe Pilot</strong> — I make real changes to ERPNext from plain English. "
			f"You're on <strong>{target}</strong>. Every change goes through "
			"<strong>Review &rarr; Confirm</strong> before it's applied.<br><br>"
			"What do you want to build?"
		)
	return (
		"I'm <strong>Frappe Pilot</strong> — I make real changes to ERPNext from plain English. "
		"Every change goes through <strong>Review &rarr; Confirm</strong> before it's applied."
		"<br><br>What do you want to build?"
	)


def _build_build_actions(ctx):
	doctype = ctx["doctype"] or ctx["list_doctype"] or ""
	route = (ctx["route"] or "").lower()

	if doctype:
		return [
			{
				"icon": "⚙️",
				"label": "Custom Field",
				"desc": f"Add a field to {doctype}",
				"prompt": f"Add a custom field to {doctype} for ",
			},
			{
				"icon": "⚡",
				"label": "Server Script",
				"desc": f"Python automation on {doctype}",
				"prompt": f"Create a server script on {doctype} that ",
			},
			{
				"icon": "📜",
				"label": "Client Script",
				"desc": f"Form behaviour on {doctype}",
				"prompt": f"Create a client script on {doctype} that ",
			},
			{
				"icon": "🔀",
				"label": "Workflow",
				"desc": f"Approval flow for {doctype}",
				"prompt": f"Create an approval workflow for {doctype} ",
			},
		]

	if "stock" in route:
		return [
			{
				"icon": "⚙️",
				"label": "Reorder Level",
				"desc": "Custom field on Item",
				"prompt": "Add a reorder level custom field to Item for ",
			},
			{
				"icon": "⚡",
				"label": "Stock Script",
				"desc": "Automate Stock Entry",
				"prompt": "Write a server script on Stock Entry that ",
			},
			{
				"icon": "📄",
				"label": "New DocType",
				"desc": "Create a new table",
				"prompt": "Create a new DocType called ",
			},
			{
				"icon": "🔀",
				"label": "Workflow",
				"desc": "Approval flows",
				"prompt": "Create an approval workflow for ",
			},
		]

	if "account" in route:
		return [
			{
				"icon": "⚡",
				"label": "Payment Script",
				"desc": "Automate Payment Entry",
				"prompt": "Write a server script on Payment Entry that ",
			},
			{
				"icon": "⚙️",
				"label": "Custom Field",
				"desc": "Add to any form",
				"prompt": "Add a custom field to ",
			},
			{
				"icon": "📄",
				"label": "New DocType",
				"desc": "Create a new table",
				"prompt": "Create a new DocType called ",
			},
			{
				"icon": "🔀",
				"label": "Workflow",
				"desc": "Approval flows",
				"prompt": "Create an approval workflow for ",
			},
		]

	return [
		{
			"icon": "⚙️",
			"label": "Custom Fields",
			"desc": "Add fields to any existing form",
			"prompt": "Add a custom field to ",
		},
		{
			"icon": "📄",
			"label": "New DocType",
			"desc": "Create a new table from scratch",
			"prompt": "Create a new DocType called ",
		},
		{
			"icon": "⚡",
			"label": "Scripts",
			"desc": "Python and JS automation",
			"prompt": "Write a server script that ",
		},
		{
			"icon": "🔀",
			"label": "Workflows",
			"desc": "Approval flows with roles",
			"prompt": "Create an approval workflow for ",
		},
	]
