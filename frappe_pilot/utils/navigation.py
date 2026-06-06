# Desk navigation helpers for Advisor replies

import re

import frappe

NAV_TOKEN_RE = re.compile(
	r"\[\[nav:(form|list|report|workspace|setup|page)\|([^\]|]+)(?:\|([^\]|]+))?(?:\|([^\]]+))?\]\]",
	re.IGNORECASE,
)

NAV_INTENT_RE = re.compile(
	r"\b(go\s+to|open|nav\w*|navigate\s+to|take\s+me\s+to|show\s+me|bring\s+me\s+to)\b",
	re.IGNORECASE,
)

DOCNAME_RE = re.compile(r"\b([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)\b")

DOC_PREFIX_DOCTYPE = (
	("ACC-SINV", "Sales Invoice"),
	("ACC-PINV", "Purchase Invoice"),
	("ACC-SORD", "Sales Order"),
	("ACC-PORD", "Purchase Order"),
	("ACC-DN", "Delivery Note"),
	("ACC-PR", "Purchase Receipt"),
	("ACC-PAY", "Payment Entry"),
	("ACC-JV", "Journal Entry"),
)

DOCNAME_LOOKUP_DOCTYPES = (
	"Sales Invoice",
	"Purchase Invoice",
	"Sales Order",
	"Purchase Order",
	"Delivery Note",
	"Purchase Receipt",
	"Payment Entry",
	"Journal Entry",
	"Quotation",
	"Customer",
	"Supplier",
	"Employee",
	"Lead",
	"Opportunity",
)

KURDISH_NAV_INTENT_RE = re.compile(
	r"(بڕۆ\s*بۆ|بکەرەوە|بگەڕێ\s*بۆ|بمبە|پیشان\s*بدە|بچۆ\s*بۆ)",
)

REFERENCED_INTENT_RE = re.compile(
	r"\b(referenced?|linked|related|associated)\b",
	re.IGNORECASE,
)

REFERENCE_ABBREV = {
	"si": "Sales Invoice",
	"sinv": "Sales Invoice",
	"invoice": "Sales Invoice",
	"invoices": "Sales Invoice",
	"rt": "Return Ticket",
	"dt": "Delivery Ticket",
	"st": "Service Ticket",
	"so": "Sales Order",
	"qtn": "Quotation",
	"jp": "Job Performance",
	"dn": "Delivery Note",
}

EXPLAIN_REFERENCE_RE = re.compile(
	r"\b(what is|what are|what's|show|list|explain|tell me|which)\b",
	re.I,
)

REFERENCE_SHORT_RE = re.compile(
	r"\b(si|sinv|rt|dt|st|so|qtn|jp)\s+refs?\b",
	re.I,
)

REFERENCE_TYPE_PATTERNS = (
	(re.compile(r"sales\s+invoices?", re.I), "Sales Invoice"),
	(re.compile(r"\binvoices?\b", re.I), "Sales Invoice"),
	(re.compile(r"sales\s+orders?", re.I), "Sales Order"),
	(re.compile(r"quotations?", re.I), "Quotation"),
	(re.compile(r"delivery\s+tickets?", re.I), "Delivery Ticket"),
	(re.compile(r"return\s+tickets?", re.I), "Return Ticket"),
	(re.compile(r"service\s+tickets?", re.I), "Service Ticket"),
	(re.compile(r"job\s+performances?", re.I), "Job Performance"),
	(re.compile(r"delivery\s+notes?", re.I), "Delivery Note"),
)

BLOCKED_DOCTYPES = frozenset({
	"User", "Role", "DocType", "DocField", "Has Role", "DocPerm",
})


def get_reply_locale_instruction(reply_locale, enabled_langs):
	"""Per-turn language override for the agent system prompt."""
	from frappe_pilot.utils.i18n import _language_display_name

	if reply_locale == "en":
		return "\n\n## Language\nReply in English. Keep DocType names and document IDs in English."
	if reply_locale not in enabled_langs or reply_locale == "en":
		return ""
	if reply_locale == "ckb":
		return (
			"\n\n## Language\n"
			"Reply in Kurdish Sorani (Central Kurdish, Arabic script). "
			"Keep ERPNext DocType names, field names, and document IDs in English."
		)
	if reply_locale == "ar":
		return (
			"\n\n## Language\n"
			"Reply in Modern Standard Arabic (العربية). "
			"Keep ERPNext DocType names, field names, and document IDs in English."
		)
	name = _language_display_name(reply_locale)
	return (
		f"\n\n## Language\n"
		f"Reply in {name}. Keep ERPNext DocType names, field names, and document IDs in English."
	)


def build_route(nav_type, target, name=None):
	nav_type = (nav_type or "").lower()
	target = (target or "").strip()
	name = (name or "").strip() if name else None

	if nav_type == "form":
		if not target or not name:
			return None
		return ["Form", target, name]
	if nav_type == "list":
		if not target:
			return None
		return ["List", target]
	if nav_type == "report":
		if not target:
			return None
		return ["query-report", target]
	if nav_type == "workspace":
		if not target:
			return None
		slug = frappe.utils.cstr(target).lower().replace(" ", "-")
		return ["Workspaces", "private", slug]
	if nav_type == "setup":
		if not target:
			return None
		if name:
			return ["Form", target, name]
		return ["List", target]
	if nav_type == "page" and target:
		parts = [p.strip() for p in target.split(">") if p.strip()]
		if len(parts) >= 3 and parts[0].lower() == "form":
			return ["Form", parts[1], parts[2]]
		if len(parts) >= 2 and parts[0].lower() == "list":
			return ["List", parts[1]]
		if parts and parts[0].lower() in ("query-report", "report"):
			return ["query-report", parts[-1]]
		return None
	return None


def validate_nav_item(nav_type, target, name=None, label=""):
	nav_type = (nav_type or "").lower()
	target = (target or "").strip()
	name = (name or "").strip() if name else None
	label = (label or target or name or "Open").strip()

	if nav_type == "form":
		if target in BLOCKED_DOCTYPES:
			return None
		if not frappe.db.exists("DocType", target):
			return None
		if not name or not frappe.db.exists(target, name):
			return None
		if not frappe.has_permission(target, "read", name):
			return None
		route = build_route("form", target, name)
	elif nav_type == "list":
		if target in BLOCKED_DOCTYPES:
			return None
		if not frappe.db.exists("DocType", target):
			return None
		if not frappe.has_permission(target, "read"):
			return None
		route = build_route("list", target)
	elif nav_type == "report":
		if not frappe.db.exists("Report", target):
			return None
		route = build_route("report", target)
	elif nav_type == "workspace":
		route = build_route("workspace", target)
		if not route:
			return None
	elif nav_type == "setup":
		if not frappe.db.exists("DocType", target):
			return None
		if name and not frappe.db.exists(target, name):
			return None
		route = build_route("setup", target, name)
	elif nav_type == "page":
		route = build_route("page", target)
	else:
		return None

	if not route:
		return None

	return {
		"type": nav_type,
		"doctype": target if nav_type in ("form", "list", "setup") else "",
		"name": name or "",
		"report": target if nav_type == "report" else "",
		"label": label,
		"route": route,
		"primary": False,
	}


def parse_nav_tokens(text):
	"""Extract nav tokens from LLM reply text."""
	if not text:
		return [], text

	links = []
	clean = text

	for match in NAV_TOKEN_RE.finditer(text):
		nav_type = match.group(1).lower()
		a = (match.group(2) or "").strip()
		b = (match.group(3) or "").strip() if match.group(3) else ""
		label = (match.group(4) or "").strip() if match.group(4) else ""

		if nav_type == "form":
			item = validate_nav_item("form", a, b, label or f"Open {b}")
		elif nav_type == "list":
			item = validate_nav_item("list", a, "", label or f"{a} list")
		elif nav_type == "report":
			item = validate_nav_item("report", a, "", label or a)
		elif nav_type == "workspace":
			item = validate_nav_item("workspace", a, "", label or a)
		elif nav_type == "setup":
			item = validate_nav_item("setup", a, b or None, label or a)
		else:
			item = validate_nav_item("page", a, "", label or "Open page")

		if item:
			links.append(item)
		clean = clean.replace(match.group(0), "")

	return links, clean.strip()


def enrich_nav_from_context(doctype="", docname="", list_doctype="", report_name=""):
	"""Seed nav links from current page context."""
	links = []
	if doctype and docname:
		item = validate_nav_item("form", doctype, docname, docname)
		if item:
			links.append(item)
	elif list_doctype:
		item = validate_nav_item("list", list_doctype, "", f"{list_doctype} list")
		if item:
			links.append(item)
	elif report_name:
		item = validate_nav_item("report", report_name, "", report_name)
		if item:
			links.append(item)
	return links


def dedupe_nav_links(links):
	seen = set()
	out = []
	for item in links:
		key = tuple(item.get("route") or [])
		if not key or key in seen:
			continue
		seen.add(key)
		out.append(item)
	return out


def detect_nav_intent(message):
	text = (message or "").strip()
	if not text:
		return False
	if NAV_INTENT_RE.search(text):
		return True
	if KURDISH_NAV_INTENT_RE.search(text):
		return True
	return False


def _guess_doctype_for_docname(docname):
	for prefix, doctype in DOC_PREFIX_DOCTYPE:
		if docname.startswith(prefix + "-") or docname == prefix:
			if frappe.db.exists(doctype, docname):
				return doctype
	for doctype in DOCNAME_LOOKUP_DOCTYPES:
		if frappe.db.exists(doctype, docname):
			return doctype
	return None


def try_resolve_document_nav(message):
	"""Resolve a desk form route from messages like 'navigate ACC-SINV-2026-00020'."""
	text = (message or "").strip()
	if not text:
		return None

	docnames = DOCNAME_RE.findall(text)
	if not docnames:
		return None

	docname = docnames[-1]
	words = text.split()
	has_nav_cue = bool(detect_nav_intent(text)) or len(words) <= 2
	if not has_nav_cue:
		return None

	doctype = _guess_doctype_for_docname(docname)
	if not doctype:
		return None

	return validate_nav_item("form", doctype, docname, docname)


def _apply_nav_button_labels(links, reply_locale="en"):
	from frappe_pilot.utils.i18n import UI_STRINGS

	locale = reply_locale if reply_locale in UI_STRINGS else "en"
	strings = UI_STRINGS.get(locale, UI_STRINGS["en"])
	nav_tpl = strings.get("nav_go_to", "Go to {label}")
	for item in links:
		if not item.get("label"):
			item["label"] = "Open"
		item["button_label"] = nav_tpl.replace("{label}", item["label"])
	return links


def try_direct_document_navigation(message, *, auto_navigate=False, reply_locale="en"):
	"""Bypass LLM for simple open-document requests when the name exists."""
	item = try_resolve_document_nav(message)
	if not item:
		return None

	links = _apply_nav_button_labels([item], reply_locale=reply_locale)
	links[0]["primary"] = True
	action = build_navigation_action(message, links, auto_navigate=auto_navigate)
	doctype = item.get("doctype") or "document"
	reply = f"Opening **{item.get('name') or item.get('label')}** ({doctype})."
	return {
		"reply": reply,
		"nav_links": links,
		"navigation_action": action,
	}




def detect_referenced_nav_intent(message):
	return bool(REFERENCED_INTENT_RE.search(message or ""))


def _parse_referenced_doctype(message):
	for pattern, doctype in REFERENCE_TYPE_PATTERNS:
		if pattern.search(message or ""):
			return doctype
	return None


def _load_order_reference_rows(parent_doctype, parent_name, reference_doctype):
	if not parent_doctype or not parent_name or not reference_doctype:
		return []
	if not frappe.db.exists("DocType", "Order Reference"):
		return []
	if not frappe.db.exists(parent_doctype, parent_name):
		return []
	if not frappe.has_permission(parent_doctype, "read", parent_name):
		return []
	return frappe.get_all(
		"Order Reference",
		filters={
			"parenttype": parent_doctype,
			"parent": parent_name,
			"reference_doctype": reference_doctype,
		},
		fields=["reference_id", "reference_status"],
		order_by="idx asc",
	)


def try_referenced_document_navigation(
	message,
	parent_doctype,
	parent_name,
	*,
	auto_navigate=False,
	reply_locale="en",
):
	"""Open linked docs from order_reference — disambiguate when multiple matches."""
	if not parent_doctype or not parent_name:
		return None
	if not (detect_nav_intent(message) or detect_referenced_nav_intent(message)):
		return None

	target_dt = _parse_referenced_doctype(message)
	if not target_dt:
		return None

	rows = _load_order_reference_rows(parent_doctype, parent_name, target_dt)
	if not rows:
		return {
			"reply": f"No **{target_dt}** found in Order Reference on this {parent_doctype}.",
			"nav_links": [],
			"navigation_action": None,
		}

	links = []
	for row in rows:
		ref_id = (row.get("reference_id") or "").strip()
		if not ref_id:
			continue
		status = (row.get("reference_status") or "").strip()
		label = f"{ref_id} ({status})" if status else ref_id
		item = validate_nav_item("form", target_dt, ref_id, label)
		if item:
			links.append(item)

	if not links:
		return None

	links = _apply_nav_button_labels(links, reply_locale=reply_locale)

	if len(links) == 1:
		links[0]["primary"] = True
		action = build_navigation_action(message, links, auto_navigate=auto_navigate)
		reply = f"Opening **{links[0].get('name') or links[0].get('label')}** ({target_dt})."
	else:
		action = None
		reply = (
			f"This {parent_doctype} has **{len(links)}** linked **{target_dt}** records. "
			"Choose which one to open:"
		)

	return {
		"reply": reply,
		"nav_links": links,
		"navigation_action": action,
	}




def detect_explain_reference_intent(message):
	text = message or ""
	if REFERENCE_SHORT_RE.search(text):
		return True
	if EXPLAIN_REFERENCE_RE.search(text) and re.search(r"\bref(erence)?s?\b", text, re.I):
		return True
	return bool(re.search(r"\bref(erence)?s?\b", text, re.I) and _parse_reference_abbrev(text))


def _should_enrich_nav_from_context(message):
	if detect_referenced_nav_intent(message) or detect_explain_reference_intent(message):
		return False
	if re.search(r"\b(what is|what are|what's|explain|which)\b", message or "", re.I):
		return False
	return True


def _parse_reference_abbrev(message):
	text = (message or "").lower()
	for abbrev in sorted(REFERENCE_ABBREV.keys(), key=len, reverse=True):
		if re.search(rf"\b{re.escape(abbrev)}\b", text):
			return REFERENCE_ABBREV[abbrev]
	return _parse_referenced_doctype(message)


def _rows_to_nav_links(rows, target_dt):
	links = []
	for row in rows:
		ref_id = (row.get("reference_id") or "").strip()
		if not ref_id:
			continue
		status = (row.get("reference_status") or "").strip()
		label = f"{ref_id} ({status})" if status else ref_id
		item = validate_nav_item("form", target_dt, ref_id, label)
		if item:
			links.append(item)
	return links


def try_explain_order_references(message, parent_doctype, parent_name, reply_locale="en"):
	"""Answer 'what is si ref' / 'rt refs' from order_reference without LLM."""
	if not detect_explain_reference_intent(message):
		return None
	if not parent_doctype or not parent_name:
		return None

	target_dt = _parse_reference_abbrev(message)
	if not target_dt:
		return None

	rows = _load_order_reference_rows(parent_doctype, parent_name, target_dt)
	if not rows:
		return {
			"reply": f"No **{target_dt}** rows in Order Reference on this {parent_doctype}.",
			"nav_links": [],
			"navigation_action": None,
		}

	links = _apply_nav_button_labels(_rows_to_nav_links(rows, target_dt), reply_locale=reply_locale)
	lines = [f"**{target_dt}** in Order Reference on **{parent_name}**:"]
	for idx, row in enumerate(rows, start=1):
		ref_id = row.get("reference_id") or ""
		status = row.get("reference_status") or ""
		lines.append(f"{idx}. **{ref_id}**" + (f" — {status}" if status else ""))

	if len(rows) == 1:
		reply = (
			f"**{target_dt}** reference: **{rows[0].get('reference_id')}**"
			+ (f" ({rows[0].get('reference_status')})" if rows[0].get("reference_status") else "")
			+ "."
		)
	else:
		reply = "\n".join(lines) + "\n\nChoose one to open:"

	return {
		"reply": reply,
		"nav_links": links,
		"navigation_action": None,
	}

def try_context_navigation(message, parent_doctype, parent_name, *, auto_navigate=False, reply_locale="en"):
	"""Explicit doc id nav, then order_reference nav — no LLM."""
	explicit = try_direct_document_navigation(
		message,
		auto_navigate=auto_navigate,
		reply_locale=reply_locale,
	)
	if explicit:
		return explicit
	explain = try_explain_order_references(
		message,
		parent_doctype,
		parent_name,
		reply_locale=reply_locale,
	)
	if explain:
		return explain
	return try_referenced_document_navigation(
		message,
		parent_doctype,
		parent_name,
		auto_navigate=auto_navigate,
		reply_locale=reply_locale,
	)

def build_navigation_action(message, nav_links, auto_navigate=False):
	if not detect_nav_intent(message) or not nav_links:
		return None
	# Multiple targets: always require explicit user choice (ignore auto_navigate).
	if len(nav_links) > 1:
		return None

	primary = None
	for item in nav_links:
		if item.get("primary"):
			primary = item
			break
	if not primary:
		primary = nav_links[0]

	return {
		"route": primary["route"],
		"label": primary.get("label") or "Open",
		"mode": "auto" if auto_navigate else "confirm",
	}


def process_reply_navigation(
	reply_text,
	*,
	message="",
	doctype="",
	docname="",
	list_doctype="",
	report_name="",
	auto_navigate=False,
	reply_locale="en",
):
	"""Parse tokens, enrich links, build optional navigation_action."""
	from frappe_pilot.utils.i18n import UI_STRINGS

	links, clean_reply = parse_nav_tokens(reply_text or "")
	if _should_enrich_nav_from_context(message):
		links.extend(enrich_nav_from_context(
			doctype=doctype,
			docname=docname,
			list_doctype=list_doctype,
			report_name=report_name,
		))
	links = dedupe_nav_links(links)

	if links and detect_nav_intent(message) and len(links) == 1:
		links[0]["primary"] = True

	locale = reply_locale if reply_locale in UI_STRINGS else "en"
	nav_label_key = "nav_go_to"
	strings = UI_STRINGS.get(locale, UI_STRINGS["en"])
	nav_tpl = strings.get(nav_label_key, "Go to {label}")

	for item in links:
		if not item.get("label"):
			item["label"] = "Open"
		item["button_label"] = nav_tpl.replace("{label}", item["label"])

	action = build_navigation_action(message, links, auto_navigate=auto_navigate)
	return {
		"reply": clean_reply or reply_text,
		"nav_links": links,
		"navigation_action": action,
	}
