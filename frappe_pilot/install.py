import frappe

from frappe_pilot.utils.settings import DEFAULTS, ensure_pilot_english_language_row


def ensure_kurdish_sorani_language():
	"""Ensure Kurdish Sorani exists in Frappe Language list (code ckb)."""
	if frappe.db.exists("Language", "ckb"):
		return
	frappe.get_doc(
		{
			"doctype": "Language",
			"language_code": "ckb",
			"language_name": "Kurdish Sorani",
			"enabled": 1,
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()


def ensure_arabic_language():
	"""Ensure Arabic exists in Frappe Language list (code ar)."""
	if frappe.db.exists("Language", "ar"):
		return
	frappe.get_doc(
		{
			"doctype": "Language",
			"language_code": "ar",
			"language_name": "Arabic",
			"enabled": 1,
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()


def ensure_pilot_settings_english_row():
	"""Seed or repair the required English row on Pilot Settings."""
	if not frappe.db.exists("DocType", "Pilot Settings"):
		return
	if not frappe.db.exists("Pilot Settings", "Pilot Settings"):
		return
	doc = frappe.get_doc("Pilot Settings", "Pilot Settings")
	if ensure_pilot_english_language_row(doc):
		doc.save(ignore_permissions=True)
		frappe.db.commit()


def after_install():
	ensure_kurdish_sorani_language()
	ensure_arabic_language()
	if frappe.db.exists("DocType", "Pilot Settings"):
		if not frappe.db.exists("Pilot Settings", "Pilot Settings"):
			doc = frappe.new_doc("Pilot Settings")
			for key, val in DEFAULTS.items():
				doc.set(key, val)
			doc.append("enabled_languages", {"language": "en", "enabled": 1})
			doc.insert(ignore_permissions=True)
			frappe.db.commit()
		else:
			ensure_pilot_settings_english_row()


def after_migrate():
	ensure_kurdish_sorani_language()
	ensure_arabic_language()
	ensure_pilot_settings_english_row()
