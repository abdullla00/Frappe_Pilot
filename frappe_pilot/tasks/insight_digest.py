# Daily Insight digest (scheduled)

from __future__ import annotations

import frappe

from frappe_pilot.api.insight_presets import run_preset
from frappe_pilot.utils.settings import get_insight_config, get_pilot_settings


def run_daily_insight_digest():
	cfg = get_pilot_settings()
	if not cfg.get("insight_enabled") or not cfg.get("insight_enable_daily_digest"):
		return

	recipients = frappe.get_all(
		"User",
		filters={"enabled": 1, "name": ("in", _digest_users())},
		pluck="name",
	)
	if not recipients:
		return

	preset_ids = ("pl_this_month", "cash_position", "ar_summary")
	for user in recipients:
		try:
			frappe.set_user(user)
			sections = []
			skipped = 0
			for preset_id in preset_ids:
				result = run_preset(preset_id)
				if result.get("error") and not result.get("micro_report"):
					skipped += 1
					continue
				mr = result.get("micro_report") or {}
				if mr.get("error") and not (mr.get("kpis") or mr.get("tables")):
					skipped += 1
					continue
				title = mr.get("title") or preset_id
				kpis = mr.get("kpis") or []
				kpi_lines = ", ".join(f"{k.get('label')}: {k.get('value')}" for k in kpis[:3])
				sections.append(f"<b>{title}</b><br>{kpi_lines or mr.get('error') or 'No data'}")
			if skipped:
				sections.append(
					f"<i>{skipped} section(s) unavailable (excluded or no permission).</i>"
				)
			if not sections:
				continue
			frappe.sendmail(
				recipients=[user],
				subject="Pilot Insight Daily Digest",
				message="<br><br>".join(sections),
				now=True,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Insight Digest Error ({user})")
		finally:
			frappe.set_user("Administrator")


def _digest_users():
	rows = frappe.get_all(
		"Has Role",
		filters={"role": "System Manager", "parenttype": "User"},
		pluck="parent",
	)
	return list(set(rows))
