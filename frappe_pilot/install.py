import frappe

from frappe_pilot.utils.llm_catalog import ensure_llm_provider_catalog, ensure_pilot_llm_models
from frappe_pilot.utils.settings import DEFAULTS, ensure_pilot_english_language_row


SYSTEM_MANAGER_ROLE = "System Manager"


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


def ensure_system_manager_allowed_role():
	"""Ensure System Manager is in Allowed Roles with Advisor and Build tabs."""
	if not frappe.db.exists("DocType", "Pilot Settings"):
		return
	if not frappe.db.exists("Pilot Settings", "Pilot Settings"):
		return

	doc = frappe.get_doc("Pilot Settings", "Pilot Settings")
	updated = False
	for row in doc.get("allowed_roles") or []:
		if row.role == SYSTEM_MANAGER_ROLE:
			if not row.advisor_tab:
				row.advisor_tab = 1
				updated = True
			if not row.build_tab:
				row.build_tab = 1
				updated = True
			if not getattr(row, "insight_tab", 0):
				row.insight_tab = 1
				updated = True
			for f in ("agents_tab", "flows_tab", "knowledge_tab", "integrations_tab", "logs_tab"):
				if not getattr(row, f, 0):
					row.set(f, 1)
					updated = True
			break
	else:
		doc.append(
			"allowed_roles",
			{
				"role": SYSTEM_MANAGER_ROLE,
				"advisor_tab": 1,
				"insight_tab": 1,
				"build_tab": 1,
				"agents_tab": 1,
				"flows_tab": 1,
				"knowledge_tab": 1,
				"integrations_tab": 1,
				"logs_tab": 1,
			},
		)
		updated = True

	if updated:
		doc.save(ignore_permissions=True)
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


def ensure_default_llm_provider_row(doc=None):
	"""Seed one Groq child row on fresh Pilot Settings if table is empty."""
	if not frappe.db.exists("DocType", "Pilot Settings"):
		return False
	if doc is None:
		if not frappe.db.exists("Pilot Settings", "Pilot Settings"):
			return False
		doc = frappe.get_doc("Pilot Settings", "Pilot Settings")
	if doc.get("llm_providers"):
		return False
	ensure_llm_provider_catalog()
	doc.append(
		"llm_providers",
		{
			"enabled": 1,
			"priority": 1,
			"llm_provider": "Groq",
			"row_label": "",
			"model": "",
			"api_key": "",
		},
	)
	if not doc.get("llm_failover_mode"):
		doc.llm_failover_mode = "Both"
	return True


def seed_platform_data():
	"""Seed LLM providers, models, tool types, system agents, and pilot roles."""
	ensure_llm_provider_catalog()
	ensure_pilot_llm_models()
	try:
		from frappe_pilot.patches.v2_0.seed_platform import execute

		execute()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Pilot Platform Seed")


def after_install():
	ensure_kurdish_sorani_language()
	ensure_arabic_language()
	seed_platform_data()
	if frappe.db.exists("DocType", "Pilot Settings"):
		if not frappe.db.exists("Pilot Settings", "Pilot Settings"):
			doc = frappe.new_doc("Pilot Settings")
			for key, val in DEFAULTS.items():
				doc.set(key, val)
			doc.append("enabled_languages", {"language": "en", "enabled": 1})
			doc.append(
				"allowed_roles",
				{
					"role": SYSTEM_MANAGER_ROLE,
					"advisor_tab": 1,
					"insight_tab": 1,
					"build_tab": 1,
					"agents_tab": 1,
					"flows_tab": 1,
					"knowledge_tab": 1,
					"integrations_tab": 1,
					"logs_tab": 1,
				},
			)
			ensure_default_llm_provider_row(doc)
			doc.insert(ignore_permissions=True)
			frappe.db.commit()
		else:
			ensure_pilot_settings_english_row()
			doc = frappe.get_doc("Pilot Settings", "Pilot Settings")
			if ensure_default_llm_provider_row(doc):
				doc.save(ignore_permissions=True)
				frappe.db.commit()

	ensure_system_manager_allowed_role()
	from frappe_pilot.setup.desk import sync_desk_from_app

	sync_desk_from_app()
	frappe.db.commit()


def after_migrate():
	ensure_kurdish_sorani_language()
	ensure_arabic_language()
	ensure_pilot_settings_english_row()
	seed_platform_data()
	if frappe.db.exists("Pilot Settings", "Pilot Settings"):
		doc = frappe.get_doc("Pilot Settings", "Pilot Settings")
		if ensure_default_llm_provider_row(doc):
			doc.save(ignore_permissions=True)
			frappe.db.commit()
	ensure_system_manager_allowed_role()
	if frappe.db.exists("DocType", "Pilot Knowledge Source"):
		try:
			from frappe_pilot.ai.knowledge.metadata_indexer import enqueue_metadata_reindex

			enqueue_metadata_reindex()
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Pilot Metadata Reindex")
	from frappe_pilot.setup.desk import sync_desk_from_app

	sync_desk_from_app()
	frappe.db.commit()
