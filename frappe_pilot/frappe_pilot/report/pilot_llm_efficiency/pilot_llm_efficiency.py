# Copyright (c) 2026, Frappe Pilot and contributors

import frappe


def execute(filters=None):
	columns = [
		{"label": "Agent", "fieldname": "agent", "fieldtype": "Link", "options": "Pilot Agent", "width": 140},
		{"label": "Runs", "fieldname": "runs", "fieldtype": "Int", "width": 80},
		{"label": "Avg Latency (ms)", "fieldname": "avg_latency", "fieldtype": "Float", "width": 120},
		{"label": "Total Cost", "fieldname": "total_cost", "fieldtype": "Currency", "width": 120},
	]
	rows = frappe.db.sql(
		"""
		SELECT agent AS agent, COUNT(*) AS runs,
			AVG(latency_ms) AS avg_latency, SUM(total_cost) AS total_cost
		FROM `tabPilot Agent Run`
		GROUP BY agent
		ORDER BY runs DESC
		""",
		as_dict=True,
	)
	return columns, rows
