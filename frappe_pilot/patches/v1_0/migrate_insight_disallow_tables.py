# Migrate Insight from allowlist text fields to disallow child tables

from __future__ import annotations

import frappe


def execute():
	if not frappe.db.exists("DocType", "Pilot Settings"):
		return

	doc = frappe.get_single("Pilot Settings")
	changed = False

	for field in ("insight_allowed_modules", "insight_allowed_doctypes"):
		if doc.meta.has_field(field) and doc.get(field):
			doc.set(field, "")
			changed = True

	if changed:
		doc.flags.ignore_validate = True
		doc.save(ignore_permissions=True)
		frappe.db.commit()
