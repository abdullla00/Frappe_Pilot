# Insight access control — allow-all minus disallow child tables + Frappe permissions

from __future__ import annotations

import frappe

from frappe_pilot.utils.settings import get_insight_disallowed_doctypes, get_insight_disallowed_modules

EXCLUDED_USER_MESSAGE = "This DocType/module is excluded from Insight in Pilot Settings."


def check_module_access(module: str) -> dict | None:
	if not module:
		return None
	if module in get_insight_disallowed_modules():
		return {"error": "module_excluded", "module": module, "message": EXCLUDED_USER_MESSAGE}
	return None


def check_doctype_access(doctype: str) -> dict | None:
	if not doctype:
		return {"error": "doctype_required"}
	if doctype in get_insight_disallowed_doctypes():
		return {"error": "doctype_excluded", "doctype": doctype, "message": EXCLUDED_USER_MESSAGE}
	if not frappe.has_permission(doctype, "read"):
		return {"error": "permission_denied", "doctype": doctype}
	return None


def assert_insight_access(*, module: str | None = None, doctype: str | None = None) -> dict | None:
	if module:
		err = check_module_access(module)
		if err:
			return err
	if doctype:
		return check_doctype_access(doctype)
	return None
