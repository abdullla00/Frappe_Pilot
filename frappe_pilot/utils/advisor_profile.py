# Advisor DocType profiles — hook merge + generic ERPNext fallback.

import frappe

DEFAULT_GREET_FIELDS = [
	"customer",
	"customer_name",
	"party_name",
	"supplier",
	"company",
	"grand_total",
	"total",
	"currency",
]

DEFAULT_ANALYZE_CHIPS = [
	"Summarize this record",
	"What should I do next?",
	"Diagnose this record",
]

DEFAULT_GUIDE_CHIPS = [
	"What is this form for?",
	"How do I fill this in?",
	"What happens on submit?",
]

_PROFILE_CACHE_KEY = "advisor_profiles_merged"


def _profile_cache():
	if not hasattr(frappe.local, _PROFILE_CACHE_KEY):
		frappe.local.advisor_profiles_merged = {}
	return frappe.local.advisor_profiles_merged


def _load_hook_profiles() -> dict:
	cache = _profile_cache()
	if cache.get("_loaded"):
		return cache.get("profiles") or {}

	profiles = {}
	for provider in frappe.get_hooks("advisor_doctype_profiles") or []:
		try:
			data = frappe.get_attr(provider)()
			if isinstance(data, dict):
				for dt, profile in data.items():
					if dt in profiles:
						profiles[dt] = _merge_profiles(profiles[dt], profile)
					else:
						profiles[dt] = dict(profile)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Advisor profile hook failed: {provider}")

	cache["profiles"] = profiles
	cache["_loaded"] = True
	return profiles


def _merge_profiles(base: dict, extra: dict) -> dict:
	merged = dict(base)
	for key, value in (extra or {}).items():
		if key in ("analyze_chips", "guide_chips", "greet_fields", "link_fields", "summary_child_tables"):
			existing = list(merged.get(key) or [])
			for item in value or []:
				if item and item not in existing:
					existing.append(item)
			merged[key] = existing
		elif key not in merged or merged[key] is None:
			merged[key] = value
	return merged


def _auto_profile_from_meta(doctype: str) -> dict:
	if not frappe.db.exists("DocType", doctype):
		return {}
	meta = frappe.get_meta(doctype)
	if meta.issingle or meta.istable:
		return {}

	greet_fields = []
	link_fields = []
	status_field = None
	for field in meta.fields:
		if field.fieldtype == "Link" and field.options and field.options not in link_fields:
			link_fields.append(field.fieldname)
		if field.fieldname in ("status", "workflow_state") and not status_field:
			status_field = field.fieldname
		if field.fieldname in DEFAULT_GREET_FIELDS and field.fieldname not in greet_fields:
			greet_fields.append(field.fieldname)

	child_tables = [df.fieldname for df in meta.fields if df.fieldtype == "Table"][:5]

	return {
		"category": "auto",
		"status_field": status_field,
		"greet_fields": greet_fields or list(DEFAULT_GREET_FIELDS[:4]),
		"link_fields": link_fields[:8],
		"summary_child_tables": child_tables,
		"analyze_chips": list(DEFAULT_ANALYZE_CHIPS),
		"guide_chips": list(DEFAULT_GUIDE_CHIPS),
	}


def get_advisor_profile(doctype: str) -> dict:
	if not doctype:
		return {}
	cache = _profile_cache()
	if doctype in cache:
		return cache[doctype]

	profiles = _load_hook_profiles()
	profile = dict(profiles.get(doctype) or {})

	if not profile:
		module = frappe.db.get_value("DocType", doctype, "module") if frappe.db.exists("DocType", doctype) else ""
		if module == "Frappe Trs":
			profile = _auto_profile_from_meta(doctype)

	cache[doctype] = profile
	return profile


def get_profile_status(doc, profile: dict | None = None) -> str:
	profile = profile or get_advisor_profile(doc.doctype)
	parts = []

	docstatus_labels = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
	if doc.docstatus is not None:
		parts.append(docstatus_labels.get(doc.docstatus, str(doc.docstatus)))

	workflow = None
	if doc.meta.has_field("workflow_state"):
		workflow = doc.get("workflow_state")
	status_field = (profile or {}).get("status_field")
	profile_status = doc.get(status_field) if status_field and doc.meta.has_field(status_field) else None

	for label in (workflow, profile_status):
		if label and label not in parts:
			parts.append(str(label))

	return " · ".join(parts) if parts else ""


def get_greet_facts(doc, profile: dict | None = None) -> list[str]:
	profile = profile or get_advisor_profile(doc.doctype)
	facts = []
	seen = set()

	status = get_profile_status(doc, profile)
	if status:
		facts.append(status)
		seen.add(status.lower())

	field_names = list(profile.get("greet_fields") or DEFAULT_GREET_FIELDS)
	for fieldname in field_names:
		if not doc.meta.has_field(fieldname):
			continue
		value = doc.get(fieldname)
		if value in (None, ""):
			continue
		label = doc.meta.get_label(fieldname) or fieldname.replace("_", " ").title()
		text = f"{label}: {value}"
		key = text.lower()
		if key in seen:
			continue
		seen.add(key)
		facts.append(text)
		if len(facts) >= 5:
			break

	if doc.meta.has_field("items") and doc.get("items"):
		count = len(doc.get("items") or [])
		facts.append(f"{count} item{'s' if count != 1 else ''}")

	if doc.docstatus == 2:
		facts.insert(0, "Cancelled")
	elif doc.meta.has_field("amended_from") and doc.get("amended_from"):
		facts.append(f"Amended from {doc.get('amended_from')}")

	return facts[:6]


def get_profile_analyze_chips(doctype: str) -> list[str]:
	profile = get_advisor_profile(doctype)
	chips = list(profile.get("analyze_chips") or [])
	for provider in frappe.get_hooks("advisor_chip_providers") or []:
		try:
			extra = frappe.get_attr(provider)(doctype=doctype, kind="analyze") or []
			for chip in extra:
				if chip and chip not in chips:
					chips.append(chip)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Advisor chip provider failed: {provider}")
	return chips


def get_profile_guide_chips(doctype: str) -> list[str]:
	profile = get_advisor_profile(doctype)
	chips = list(profile.get("guide_chips") or [])
	for provider in frappe.get_hooks("advisor_chip_providers") or []:
		try:
			extra = frappe.get_attr(provider)(doctype=doctype, kind="guide") or []
			for chip in extra:
				if chip and chip not in chips:
					chips.append(chip)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Advisor chip provider failed: {provider}")
	return chips


def get_context_enrichments(doctype: str, docname: str) -> list[str]:
	"""Optional extra context bar / greet facts from advisor_context_enrichers hooks."""
	if not doctype or not docname or not frappe.db.exists(doctype, docname):
		return []
	if not frappe.has_permission(doctype, "read", docname):
		return []
	try:
		doc = frappe.get_doc(doctype, docname)
	except frappe.PermissionError:
		return []

	facts = []
	for provider in frappe.get_hooks("advisor_context_enrichers") or []:
		try:
			extra = frappe.get_attr(provider)(doc=doc, doctype=doctype, docname=docname) or []
			for fact in extra:
				if fact and fact not in facts:
					facts.append(str(fact))
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Advisor context enricher failed: {provider}")
	return facts[:4]
