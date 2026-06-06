import frappe

from frappe_pilot.install import ensure_kurdish_sorani_language


def execute():
	ensure_kurdish_sorani_language()

	legacy_map = {
		"Kurdish Sorani": "ckb",
	}

	for row in frappe.db.sql(
		"""
		SELECT name, language, enabled
		FROM `tabPilot Enabled Language`
		""",
		as_dict=True,
	):
		lang = (row.language or "").strip()
		if not lang:
			continue

		new_link = legacy_map.get(lang, lang)
		if new_link == lang and not frappe.db.exists("Language", lang):
			code = frappe.db.get_value("Language", {"language_name": lang}, "name")
			if code:
				new_link = code

		updates = {}
		if new_link != lang:
			updates["language"] = new_link
		if row.enabled is None:
			updates["enabled"] = 1

		if updates:
			frappe.db.set_value("Pilot Enabled Language", row.name, updates, update_modified=False)

	frappe.db.commit()
