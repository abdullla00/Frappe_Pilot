# Copyright (c) 2026, Frappe Pilot and contributors

import frappe


def before_uninstall():
	"""Remove desk branding before module/DocType cleanup."""
	try:
		from frappe_pilot.setup.desk import purge_pilot_desk_artifacts

		purge_pilot_desk_artifacts()
		frappe.db.commit()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Frappe Pilot before_uninstall")
		raise


def after_uninstall():
	"""Safety pass: scrub layouts and icons Frappe generic cleanup may miss."""
	try:
		from frappe_pilot.setup.desk import (
			_clear_desk_caches,
			_delete_pilot_desktop_icons,
			_purge_pilot_from_desktop_layouts,
		)

		_purge_pilot_from_desktop_layouts()
		_delete_pilot_desktop_icons()
		_clear_desk_caches()
		frappe.db.commit()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Frappe Pilot after_uninstall")
