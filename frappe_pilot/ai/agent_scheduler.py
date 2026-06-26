"""Scheduled trigger runner."""

import frappe
from frappe.utils import add_to_date, now_datetime

from .agent_hooks import run_trigger


def run_scheduled_agents():
	if not frappe.db.exists("DocType", "Pilot Agent Trigger"):
		return

	now = now_datetime().replace(microsecond=0)
	triggers = frappe.get_all(
		"Pilot Agent Trigger",
		filters={"trigger_type": "Schedule", "disabled": 0, "next_execution": ("<=", now)},
		fields=["name", "scheduled_interval", "interval_count"],
	)

	for row in triggers:
		try:
			run_trigger(row.name, payload={"scheduled": True})
			doc = frappe.get_doc("Pilot Agent Trigger", row.name)
			doc.last_execution = now
			interval = doc.interval_count or 1
			si = (doc.scheduled_interval or "Daily").lower()
			doc.next_execution = add_to_date(
				now,
				hours=interval if si == "hourly" else 0,
				days=interval if si == "daily" else 0,
				weeks=interval if si == "weekly" else 0,
				months=interval if si == "monthly" else 0,
				years=interval if si == "yearly" else 0,
			)
			doc.save(ignore_permissions=True)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Pilot Schedule Trigger: {row.name}")
	frappe.db.commit()
