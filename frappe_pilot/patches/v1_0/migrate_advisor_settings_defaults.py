# Backfill Advisor tab UX defaults

import frappe

from frappe_pilot.utils.settings import DEFAULTS

ADVISOR_CHECK_FIELDS = (
	"advisor_brief_replies",
	"advisor_show_context_bar",
	"advisor_group_chips",
	"advisor_followup_chips",
)


def execute():
	if not frappe.db.exists("DocType", "Pilot Settings"):
		return
	if not frappe.db.exists("Pilot Settings", "Pilot Settings"):
		return

	doc = frappe.get_doc("Pilot Settings", "Pilot Settings")
	updated = False

	for fieldname in ADVISOR_CHECK_FIELDS:
		if doc.get(fieldname) is None:
			doc.set(fieldname, DEFAULTS.get(fieldname, 1))
			updated = True

	if doc.get("advisor_persist_chat_on_route") is None:
		doc.set("advisor_persist_chat_on_route", DEFAULTS.get("advisor_persist_chat_on_route", 0))
		updated = True

	if updated:
		doc.save(ignore_permissions=True)
		frappe.db.commit()
