# Merge build_allowed_roles into unified allowed_roles table

import frappe

from frappe_pilot.install import ensure_system_manager_allowed_role


def execute():
	if not frappe.db.exists("DocType", "Pilot Settings"):
		return
	if not frappe.db.exists("Pilot Settings", "Pilot Settings"):
		return

	doc = frappe.get_doc("Pilot Settings", "Pilot Settings")
	meta = frappe.get_meta("Pilot Settings")
	updated = False

	if meta.has_field("build_allowed_roles"):
		build_roles = {row.role for row in (doc.get("build_allowed_roles") or []) if row.role}
		allowed_by_role = {row.role: row for row in (doc.get("allowed_roles") or []) if row.role}

		for role in build_roles:
			if role in allowed_by_role:
				row = allowed_by_role[role]
				if not cint(row.get("build_tab")):
					row.build_tab = 1
					updated = True
			else:
				doc.append(
					"allowed_roles",
					{
						"role": role,
						"advisor_tab": 1,
						"build_tab": 1,
					},
				)
				updated = True

	for row in doc.get("allowed_roles") or []:
		if row.advisor_tab is None:
			row.advisor_tab = 1
			updated = True
		if not cint(row.advisor_tab) and not cint(row.get("build_tab")):
			for tab in ("agents_tab", "flows_tab", "knowledge_tab", "integrations_tab", "logs_tab"):
				if cint(row.get(tab)):
					break
			else:
				row.advisor_tab = 1
				updated = True

	if updated:
		doc.save(ignore_permissions=True)
		frappe.db.commit()

	ensure_system_manager_allowed_role()


def cint(val):
	try:
		return int(val or 0)
	except (TypeError, ValueError):
		return 0
