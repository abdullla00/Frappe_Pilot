"""Seed platform data for Frappe Pilot v2.x."""

import frappe

from frappe_pilot.ai.permissions_api import DEFAULT_ROLE_CAPABILITIES, seed_capabilities
from frappe_pilot.utils.llm_catalog import ensure_llm_provider_catalog, ensure_pilot_llm_models


SYSTEM_AGENTS = (
	{
		"agent_name": "advisor",
		"description": "Default Advisor system agent (read-only desk copilot).",
		"provider": "Groq",
		"model": "Groq-llama-3.3-70b-versatile",
		"system_agent_key": "advisor",
		"is_system_agent": 1,
		"execution_mode": "Direct",
		"execution_mode_locked": 0,
		"temperature": 0.2,
	},
	{
		"agent_name": "build",
		"description": "Default Build system agent (safe-mode ERPNext customizations).",
		"provider": "Groq",
		"model": "Groq-llama-3.3-70b-versatile",
		"system_agent_key": "build",
		"is_system_agent": 1,
		"execution_mode": "Safe",
		"execution_mode_locked": 1,
		"temperature": 0.1,
	},
)


def _ensure_frappe_roles():
	for role_name in ("Pilot Operator", "Pilot Viewer"):
		if not frappe.db.exists("Role", role_name):
			frappe.get_doc({"doctype": "Role", "role_name": role_name, "desk_access": 1}).insert(
				ignore_permissions=True
			)


def _ensure_pilot_roles():
	if not frappe.db.exists("DocType", "Pilot Role"):
		return
	for role_name, capabilities in DEFAULT_ROLE_CAPABILITIES.items():
		if frappe.db.exists("Pilot Role", role_name):
			doc = frappe.get_doc("Pilot Role", role_name)
		else:
			doc = frappe.get_doc({
				"doctype": "Pilot Role",
				"role_name": role_name,
				"description": f"Default {role_name} role",
			})
		existing = {row.capability for row in doc.permissions}
		for cap in capabilities:
			if cap not in existing:
				doc.append("permissions", {"capability": cap})
		if doc.is_new():
			doc.insert(ignore_permissions=True)
		elif doc.has_value_changed("permissions") or doc.has_value_changed("description"):
			doc.save(ignore_permissions=True)


def _ensure_admin_pilot_role():
	if not frappe.db.exists("DocType", "Pilot User Role"):
		return
	if frappe.db.exists("Pilot User Role", {"user": "Administrator"}):
		return
	if not frappe.db.exists("Pilot Role", "Pilot Admin"):
		return
	frappe.get_doc({
		"doctype": "Pilot User Role",
		"user": "Administrator",
		"pilot_role": "Pilot Admin",
	}).insert(ignore_permissions=True)


def _ensure_system_agents():
	if not frappe.db.exists("DocType", "Pilot Agent"):
		return
	for entry in SYSTEM_AGENTS:
		if frappe.db.exists("Pilot Agent", entry["agent_name"]):
			doc = frappe.get_doc("Pilot Agent", entry["agent_name"])
			changed = False
			for key, val in entry.items():
				if doc.get(key) != val:
					doc.set(key, val)
					changed = True
			if changed:
				doc.save(ignore_permissions=True)
			continue
		frappe.get_doc({"doctype": "Pilot Agent", **entry}).insert(ignore_permissions=True)


def execute():
	ensure_llm_provider_catalog()
	ensure_pilot_llm_models()
	_ensure_frappe_roles()
	seed_capabilities()
	_ensure_pilot_roles()
	_ensure_admin_pilot_role()
	_ensure_system_agents()
	frappe.db.commit()
