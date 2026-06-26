# Grant insight_tab on System Manager allowed-role rows

import frappe

from frappe_pilot.install import ensure_system_manager_allowed_role


def execute():
	if not frappe.db.exists("DocType", "Pilot Settings"):
		return
	if not frappe.db.exists("Pilot Settings", "Pilot Settings"):
		return

	doc = frappe.get_doc("Pilot Settings", "Pilot Settings")
	updated = False

	for row in doc.get("allowed_roles") or []:
		if row.role == "System Manager":
			if not cint(getattr(row, "insight_tab", 0)):
				row.insight_tab = 1
				updated = True
			break

	if updated:
		doc.save(ignore_permissions=True)
		frappe.db.commit()

	ensure_system_manager_allowed_role()


def cint(val):
	try:
		return int(val or 0)
	except (TypeError, ValueError):
		return 0
