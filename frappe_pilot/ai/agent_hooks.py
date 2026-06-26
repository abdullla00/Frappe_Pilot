"""Document event and trigger dispatch for Pilot agents."""

import json

import frappe
from frappe.utils.background_jobs import enqueue
from frappe.utils.safe_exec import safe_eval

CACHE_KEY = "pilot:doc_event_triggers"
SKIP_DOCTYPES = frozenset({
	"User",
	"Error Log",
	"Activity Log",
	"Access Log",
	"Version",
	"Comment",
	"Communication",
})


def clear_doc_event_agents_cache(doc=None, method=None):
	frappe.cache().delete_key(CACHE_KEY)


def _triggers_enabled() -> bool:
	if frappe.flags.in_install or frappe.flags.in_migrate:
		return False
	try:
		if not frappe.db.exists("Pilot Settings", "Pilot Settings"):
			return False
		settings = frappe.get_single("Pilot Settings")
		if not settings.get("enable_pilot"):
			return False
		if settings.meta.has_field("enable_doc_event_triggers"):
			return bool(settings.get("enable_doc_event_triggers"))
		return False
	except Exception:
		return False


def get_doc_event_triggers(event: str) -> list[dict]:
	if not frappe.db.exists("DocType", "Pilot Agent Trigger"):
		return []
	cached = frappe.cache().hget(CACHE_KEY, event)
	if cached:
		return frappe.parse_json(cached)

	rows = frappe.get_all(
		"Pilot Agent Trigger",
		filters={"trigger_type": "Doc Event", "disabled": 0, "doc_event": event},
		fields=["name", "agent", "reference_doctype", "condition", "prompt_field"],
		ignore_permissions=True,
	)
	frappe.cache().hset(CACHE_KEY, event, json.dumps(rows))
	return rows


def run_hooked_agents(doc, method=None):
	if not _triggers_enabled() or not method:
		return
	if doc.doctype.startswith("Pilot ") or doc.doctype in SKIP_DOCTYPES:
		return

	for trigger in get_doc_event_triggers(method):
		if trigger.get("reference_doctype") and trigger["reference_doctype"] != doc.doctype:
			continue
		condition = trigger.get("condition")
		if condition:
			try:
				if not safe_eval(condition, None, {"doc": doc}):
					continue
			except Exception:
				continue
		enqueue(
			"frappe_pilot.ai.agent_hooks.run_trigger",
			trigger_name=trigger["name"],
			payload={"doctype": doc.doctype, "name": doc.name, "event": method},
			queue="long",
		)


def run_trigger(trigger_name: str, payload: dict | None = None):
	"""Execute a trigger by running the linked Pilot Agent."""
	trigger = frappe.get_doc("Pilot Agent Trigger", trigger_name)
	if trigger.disabled:
		return {"ok": False, "reason": "disabled"}

	agent_name = trigger.agent
	if not agent_name or not frappe.db.exists("Pilot Agent", agent_name):
		return {"ok": False, "reason": "missing agent"}

	payload = payload or {}
	prompt_parts = [f"Document event: {payload.get('event')} on {payload.get('doctype')} {payload.get('name')}"]
	if trigger.get("prompt_field") and payload.get("doctype") and payload.get("name"):
		try:
			doc = frappe.get_doc(payload["doctype"], payload["name"])
			field_val = doc.get(trigger.prompt_field)
			if field_val:
				prompt_parts.append(str(field_val))
		except Exception:
			pass
	message = "\n".join(prompt_parts)

	from frappe_pilot.ai.agent_integration import run_agent_sync

	previous_user = frappe.session.user
	try:
		frappe.set_user("Administrator")
		result = run_agent_sync(agent_name=agent_name, message=message)
		return {"ok": True, **result}
	finally:
		frappe.set_user(previous_user)
