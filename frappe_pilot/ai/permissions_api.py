# Copyright (c) 2026, Frappe Pilot and contributors

"""Pilot Role capability checks and seed catalogue."""

import frappe
from frappe import _

CAPABILITIES: dict[str, str] = {
	"agent.use": "Use Agents",
	"agent.create": "Create Agents",
	"agent.edit": "Edit Agents",
	"agent.delete": "Delete Agents",
	"agent.view_all": "View All Agents",
	"chat.use": "Use Chat",
	"chat.view_own": "View Own Conversations",
	"chat.view_all": "View All Conversations",
	"tools.use": "Use Tools",
	"tools.manage": "Manage Tools",
	"system.providers.manage": "Manage LLM Providers",
	"system.settings.manage": "Manage Pilot Settings",
	"users.manage": "Manage Pilot Users",
	"roles.manage": "Manage Pilot Roles",
}

DEFAULT_ROLE_CAPABILITIES: dict[str, list[str]] = {
	"Pilot Admin": list(CAPABILITIES.keys()),
	"Pilot Operator": [
		"agent.use",
		"agent.create",
		"agent.edit",
		"chat.use",
		"chat.view_own",
		"tools.use",
	],
	"Pilot Viewer": [
		"agent.use",
		"chat.use",
		"chat.view_own",
	],
}

_CACHE_KEY_PREFIX = "pilot_user_capabilities"


def _cache_key(user: str) -> str:
	return f"{_CACHE_KEY_PREFIX}::{user}"


def bust_capabilities_cache(user: str):
	frappe.cache().delete_value(_cache_key(user))


def get_user_pilot_role(user: str | None = None) -> str | None:
	if not user:
		user = frappe.session.user
	if user == "Administrator":
		return "Pilot Admin"
	return frappe.db.get_value("Pilot User Role", {"user": user}, "pilot_role")


def get_user_capabilities(user: str | None = None) -> list[str]:
	if not user:
		user = frappe.session.user

	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return list(CAPABILITIES.keys())

	cached = frappe.cache().get_value(_cache_key(user))
	if cached is not None:
		return cached

	role_name = get_user_pilot_role(user)
	if not role_name:
		capabilities = ["agent.use", "chat.use", "chat.view_own", "tools.use"]
	else:
		capabilities = frappe.get_all(
			"Pilot Role Permission",
			filters={"parent": role_name},
			pluck="capability",
		) or DEFAULT_ROLE_CAPABILITIES.get(role_name, [])

	frappe.cache().set_value(_cache_key(user), capabilities, expires_in_sec=300)
	return capabilities


def has_capability(user: str | None, capability: str) -> bool:
	if not capability:
		return False
	return capability in get_user_capabilities(user)


def seed_capabilities():
	"""Seed default Pilot Roles and tool types if missing."""
	for role_name, capabilities in DEFAULT_ROLE_CAPABILITIES.items():
		if frappe.db.exists("Pilot Role", role_name):
			continue
		doc = frappe.get_doc({
			"doctype": "Pilot Role",
			"role_name": role_name,
			"description": f"Default {role_name} role",
		})
		for cap in capabilities:
			doc.append("permissions", {"capability": cap})
		doc.insert(ignore_permissions=True)

	for type_name, is_mutating in [
		("Get Document", 0),
		("Get List", 0),
		("Create Document", 1),
		("Update Document", 1),
		("Delete Document", 1),
	]:
		if frappe.db.exists("Pilot Agent Tool Type", type_name):
			continue
		frappe.get_doc({
			"doctype": "Pilot Agent Tool Type",
			"name1": type_name,
			"is_mutating": is_mutating,
		}).insert(ignore_permissions=True)

	frappe.db.commit()


@frappe.whitelist()
def get_capabilities_catalogue():
	if not has_capability(frappe.session.user, "roles.manage"):
		frappe.throw(_("You don't have permission to view capabilities."), frappe.PermissionError)
	return CAPABILITIES
