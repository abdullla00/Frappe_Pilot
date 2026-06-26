"""Webhook and manual trigger endpoints."""

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def webhook(slug: str, key: str | None = None):
	"""Invoke a webhook trigger by slug/key."""
	if not frappe.db.exists("DocType", "Pilot Agent Trigger"):
		frappe.throw(_("Triggers are not configured"), frappe.DoesNotExistError)

	filters = {"trigger_type": "Webhook", "disabled": 0, "webhook_slug": slug}
	if key:
		filters["webhook_key"] = key
	trigger_name = frappe.db.get_value("Pilot Agent Trigger", filters, "name")
	if not trigger_name:
		frappe.throw(_("Invalid webhook"), frappe.PermissionError)

	trigger = frappe.get_doc("Pilot Agent Trigger", trigger_name)
	payload = frappe.request.get_json(silent=True) or {}
	frappe.enqueue(
		"frappe_pilot.ai.agent_hooks.run_trigger",
		trigger_name=trigger.name,
		payload=payload,
		queue="long",
	)
	return {"ok": True, "trigger": trigger.name}


@frappe.whitelist()
def run_manual_trigger(trigger_name: str):
	frappe.only_for("System Manager")
	return frappe.get_attr("frappe_pilot.ai.agent_hooks.run_trigger")(trigger_name=trigger_name, payload={})
