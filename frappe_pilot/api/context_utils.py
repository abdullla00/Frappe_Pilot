# Shared context helpers for Guide and Analyze APIs

import frappe

LAYOUT_FIELDTYPES = frozenset({
	"Column Break", "Section Break", "HTML", "Tab Break", "Heading",
})

SKIP_PARENT_FIELDTYPES = frozenset({
	"Attach", "Attach Image", "Table",
})

LONG_TEXT_FIELDTYPES = frozenset({
	"Text Editor", "Long Text", "Code", "Markdown Editor",
})

SENSITIVE_FIELD_PATTERNS = (
	"password", "secret", "api_key", "token", "private_key",
)

DOCSTATUS_LABELS = {0: "Draft", 1: "Submitted", 2: "Cancelled"}

CONTEXT_CHAR_BUDGET = 7000
LONG_FIELD_TRUNCATE = 300


def get_context_key(doctype="", docname="", list_doctype="", route=""):
	return f"{doctype}|{docname}|{list_doctype}|{route}"


def parse_form_route(route=""):
	"""Parse 'Form > Sales Invoice > ACC-SINV-2026-00020' into (doctype, docname)."""
	if not route:
		return None

	parts = [p.strip() for p in route.split(">") if p.strip()]
	if len(parts) >= 3 and parts[0].lower() == "form":
		return parts[1], parts[2]
	return None


def build_context_prefix(doctype="", docname="", route="", list_doctype=""):
	if list_doctype:
		return f"[Context: I am currently on the {list_doctype} List page in ERPNext] "
	if doctype and docname:
		return f"[Context: I am on the {doctype} form, document: {docname}] "
	if doctype:
		return f"[Context: I am on a new {doctype} form in ERPNext] "
	if route:
		return f"[Context: My current page route is '{route}'] "
	return "[Context: I am on the ERPNext home dashboard] "


def parse_route_description(route=""):
	if not route:
		return "The user is on the ERPNext home dashboard."

	lines = [
		f"Current route: **{route}**",
		"Route translation guide:",
		"  'Form > X > name'       → X document form",
		"  'List > X > List'       → X List page",
		"  'query-report > X'      → X Report page",
		"  'Report > X'            → X Report page",
		f"Translate route '{route}' using this logic.",
	]
	return "\n".join(lines)


def is_sensitive_field(fieldname):
	name = (fieldname or "").lower()
	return any(pattern in name for pattern in SENSITIVE_FIELD_PATTERNS)


def format_field_value(value, fieldtype=None, *, max_len=200):
	if value is None or value == "":
		return None
	if fieldtype == "Password":
		return "[redacted]"
	if fieldtype in ("Check",):
		return "Yes" if value else "No"
	if fieldtype in ("Currency", "Float", "Percent"):
		try:
			return str(round(float(value), 2))
		except (TypeError, ValueError):
			return str(value)
	if fieldtype == "Date" and hasattr(value, "isoformat"):
		return value.isoformat()
	if isinstance(value, (list, dict)):
		return None

	limit = LONG_FIELD_TRUNCATE if fieldtype in LONG_TEXT_FIELDTYPES else max_len
	text = str(value).strip()
	if len(text) > limit:
		return text[:limit] + "…"
	return text


def _extract_row_fields(row, child_meta):
	row_data = {}
	for field in child_meta.fields:
		if field.fieldtype in LAYOUT_FIELDTYPES or not field.fieldname:
			continue
		if is_sensitive_field(field.fieldname):
			continue
		value = format_field_value(row.get(field.fieldname), field.fieldtype)
		if value is not None:
			row_data[field.label or field.fieldname] = value
	return row_data


def _row_matches_message(row_data, message):
	if not message:
		return False
	msg = message.lower()
	for val in row_data.values():
		if val and str(val).lower() in msg:
			return True
	# Also check common item identifiers in message
	for key in ("item_code", "Item", "item name"):
		if key in row_data and row_data[key].lower() in msg:
			return True
	return False


def get_meta_summary(doctype, include_list_view=False, field_limit=40):
	if not doctype:
		return {"error": "No DocType specified"}

	try:
		meta = frappe.get_meta(doctype)
	except Exception as exc:
		return {"error": str(exc)}

	fields = []
	mandatory = []
	list_columns = []

	for f in meta.fields:
		if f.fieldtype in LAYOUT_FIELDTYPES or not f.fieldname:
			continue

		entry = {
			"fieldname": f.fieldname,
			"label": f.label or f.fieldname,
			"fieldtype": f.fieldtype,
			"reqd": bool(f.reqd),
		}
		if f.options:
			entry["options"] = f.options

		fields.append(entry)
		if f.reqd:
			mandatory.append(f.label or f.fieldname)
		if include_list_view and f.in_list_view:
			list_columns.append(f.label or f.fieldname)

		if len(fields) >= field_limit:
			break

	result = {
		"doctype": doctype,
		"total_fields": len(meta.fields),
		"fields": fields,
		"mandatory_fields": mandatory[:20],
	}
	if include_list_view:
		result["list_columns"] = list_columns[:15] or [f["label"] for f in fields[:8]]
	return result


def get_doc_summary(doctype, docname, user_message=""):
	if not doctype or not docname:
		return {"error": "DocType and document name are required"}

	if not frappe.db.exists(doctype, docname):
		return {"error": f"Document {doctype} {docname} does not exist"}

	if not frappe.has_permission(doctype, "read", docname):
		return {
			"permission_denied": True,
			"doctype": doctype,
			"docname": docname,
			"message": f"You do not have permission to read {doctype} {docname}.",
		}

	try:
		doc = frappe.get_doc(doctype, docname)
	except frappe.PermissionError:
		return {
			"permission_denied": True,
			"doctype": doctype,
			"docname": docname,
			"message": f"You do not have permission to read {doctype} {docname}.",
		}

	meta = frappe.get_meta(doctype)

	summary = {
		"doctype": doctype,
		"name": doc.name,
		"docstatus": DOCSTATUS_LABELS.get(doc.docstatus, str(doc.docstatus)),
		"modified": str(doc.modified) if doc.get("modified") else None,
		"owner": doc.get("owner"),
		"fields": {},
		"child_tables": {},
	}

	for field in meta.fields:
		if field.fieldtype in LAYOUT_FIELDTYPES or not field.fieldname:
			continue
		if field.fieldtype in SKIP_PARENT_FIELDTYPES or is_sensitive_field(field.fieldname):
			continue
		value = format_field_value(doc.get(field.fieldname), field.fieldtype)
		if value is not None:
			summary["fields"][field.label or field.fieldname] = value

	for field in meta.fields:
		if field.fieldtype != "Table" or not field.fieldname or not field.options:
			continue
		rows = doc.get(field.fieldname) or []
		if not rows:
			continue

		try:
			child_meta = frappe.get_meta(field.options)
		except Exception:
			continue

		table_rows = []
		for row in rows:
			row_data = _extract_row_fields(row, child_meta)
			if row_data:
				row_label = (
					row_data.get("Item")
					or row_data.get("item_code")
					or row_data.get("Item Code")
					or f"Row {len(table_rows) + 1}"
				)
				table_rows.append({"label": str(row_label), "fields": row_data})

		# Prioritize rows mentioned in the user message when budget is tight
		if user_message:
			table_rows.sort(
				key=lambda r: 0 if _row_matches_message(r["fields"], user_message) else 1
			)

		summary["child_tables"][field.label or field.fieldname] = {
			"row_count": len(rows),
			"rows": table_rows,
			"fieldname": field.fieldname,
		}

	summary["child_tables"] = _order_child_tables(summary)
	try:
		from frappe_pilot.utils.advisor_profile import get_greet_facts, get_profile_status

		profile = get_advisor_profile(doctype)
		if profile:
			summary["profile_status"] = get_profile_status(doc, profile)
			summary["greet_facts"] = get_greet_facts(doc, profile)
	except Exception:
		pass

	summary["fields"] = _order_summary_fields(summary, meta)
	return summary


def get_advisor_profile(doctype):
	from frappe_pilot.utils.advisor_profile import get_advisor_profile as _get

	return _get(doctype)


def _order_summary_fields(summary, meta):
	fields = dict(summary.get("fields") or {})
	profile = get_advisor_profile(summary.get("doctype") or "")
	if not profile or not fields:
		return fields

	priority_labels = []
	for fieldname in list(profile.get("greet_fields") or []):
		if meta.has_field(fieldname):
			label = meta.get_label(fieldname) or fieldname
			if label in fields:
				priority_labels.append(label)
	status_field = profile.get("status_field")
	if status_field and meta.has_field(status_field):
		label = meta.get_label(status_field) or status_field
		if label in fields and label not in priority_labels:
			priority_labels.insert(0, label)

	ordered = {}
	for label in priority_labels:
		ordered[label] = fields[label]
	for label, value in fields.items():
		if label not in ordered:
			ordered[label] = value
	return ordered


def _order_child_tables(summary):
	child_tables = summary.get("child_tables") or {}
	if not child_tables:
		return child_tables

	profile = get_advisor_profile(summary.get("doctype") or "")
	priority = list(profile.get("summary_child_tables") or [])
	if not priority:
		return child_tables

	meta = frappe.get_meta(summary["doctype"])
	label_by_field = {}
	for field in meta.fields:
		if field.fieldtype == "Table":
			label_by_field[field.fieldname] = field.label or field.fieldname

	ordered = {}
	for fieldname in priority:
		label = label_by_field.get(fieldname)
		if label and label in child_tables:
			ordered[label] = child_tables[label]
	for label, data in child_tables.items():
		if label not in ordered:
			ordered[label] = data
	return ordered


def format_doc_summary_block(summary, *, char_budget=CONTEXT_CHAR_BUDGET):
	if summary.get("permission_denied"):
		return (
			f"## Document access\n"
			f"The user does NOT have read permission for **{summary.get('doctype')}** "
			f"document **{summary.get('docname')}**.\n"
			f"Tell them clearly they cannot analyze this record."
		)

	if summary.get("error"):
		return f"## Document access\nError loading document: {summary['error']}"

	lines = [
		"## Open document data",
		f"DocType: **{summary['doctype']}**",
		f"Document: **{summary['name']}**",
	]
	status_line = summary.get("profile_status") or summary.get("docstatus")
	lines.append(f"Status: **{status_line}**")
	if summary.get("greet_facts"):
		lines.append("Key facts: " + " · ".join(summary["greet_facts"][:5]))
	if summary.get("owner"):
		lines.append(f"Owner: {summary['owner']}")
	if summary.get("modified"):
		lines.append(f"Last modified: {summary['modified']}")

	if summary.get("fields"):
		lines.append("")
		lines.append("Field values:")
		for label, value in summary["fields"].items():
			lines.append(f"  - {label}: {value}")

	if summary.get("child_tables"):
		lines.append("")
		lines.append("Child tables:")
		for table_label, table_data in summary["child_tables"].items():
			lines.append(f"  - {table_label}: {table_data['row_count']} row(s)")
			for row in table_data.get("rows", []):
				lines.append(f"    {row['label']}:")
				for label, value in row["fields"].items():
					lines.append(f"      - {label}: {value}")

	lines.append("")
	lines.append(
		"Use ONLY the field values above. Never invent values not listed here."
	)

	block = "\n".join(lines)
	if len(block) > char_budget:
		block = block[:char_budget] + "\n… (context truncated to fit token budget)"
	return block


def format_meta_summary_block(meta_summary, *, new_document=False):
	if meta_summary.get("error"):
		return f"## Form schema\nError: {meta_summary['error']}"

	lines = [
		"## Form schema (no saved document yet)" if new_document else "## Form schema",
		f"DocType: **{meta_summary['doctype']}**",
		f"Total fields: {meta_summary['total_fields']}",
	]

	if meta_summary.get("mandatory_fields"):
		lines.append(
			"Mandatory fields: " + ", ".join(meta_summary["mandatory_fields"])
		)

	if meta_summary.get("list_columns"):
		lines.append(
			"List view columns: " + ", ".join(meta_summary["list_columns"])
		)

	if meta_summary.get("fields"):
		lines.append("")
		lines.append("Key fields:")
		for f in meta_summary["fields"][:20]:
			req = " (required)" if f.get("reqd") else ""
			opts = f" [{f['options']}]" if f.get("options") else ""
			lines.append(
				f"  - {f['label']} ({f['fieldtype']}){req}{opts}"
			)

	return "\n".join(lines)


def resolve_form_context(doctype="", docname="", route=""):
	"""Resolve doctype/docname from route if not already provided."""
	if doctype and docname:
		return doctype, docname, ""
	parsed = parse_form_route(route)
	if parsed:
		return parsed[0], parsed[1], ""
	return doctype, docname, route
