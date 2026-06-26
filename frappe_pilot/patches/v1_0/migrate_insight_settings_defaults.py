# Backfill Insight tab numeric defaults when fields were saved as 0 after migrate

import frappe

from frappe_pilot.utils.settings import DEFAULTS


INSIGHT_INT_FIELDS = (
	"insight_max_passes",
	"insight_max_tokens",
	"insight_max_tokens_final",
	"insight_max_report_rows",
	"insight_max_list_rows",
	"insight_max_tool_json_chars",
	"insight_kpi_cache_ttl",
)


def execute():
	if not frappe.db.exists("DocType", "Pilot Settings"):
		return
	if not frappe.db.exists("Pilot Settings", "Pilot Settings"):
		return

	doc = frappe.get_doc("Pilot Settings", "Pilot Settings")
	updated = False

	for fieldname in INSIGHT_INT_FIELDS:
		if not int(doc.get(fieldname) or 0):
			default = DEFAULTS.get(fieldname)
			if default:
				doc.set(fieldname, default)
				updated = True

	if not float(doc.get("insight_temperature") or 0):
		default = DEFAULTS.get("insight_temperature")
		if default:
			doc.set("insight_temperature", default)
			updated = True

	if not (doc.get("insight_model") or "").strip():
		default = DEFAULTS.get("insight_model")
		if default:
			doc.set("insight_model", default)
			updated = True

	if updated:
		doc.save(ignore_permissions=True)
		frappe.db.commit()
