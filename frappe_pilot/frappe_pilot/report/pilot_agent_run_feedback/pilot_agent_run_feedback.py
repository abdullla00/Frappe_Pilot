# Copyright (c) 2026, Frappe Pilot and contributors

import frappe


def execute(filters=None):
	columns = [
		{"label": "Agent", "fieldname": "agent", "fieldtype": "Link", "options": "Pilot Agent", "width": 140},
		{"label": "Rating", "fieldname": "rating", "fieldtype": "Int", "width": 80},
		{"label": "Feedback", "fieldname": "feedback", "fieldtype": "Data", "width": 200},
		{"label": "Run", "fieldname": "run", "fieldtype": "Link", "options": "Pilot Agent Run", "width": 140},
	]
	if not frappe.db.exists("DocType", "Pilot Agent Run Feedback"):
		return columns, []
	data = frappe.get_all(
		"Pilot Agent Run Feedback",
		fields=["agent", "rating", "feedback", "run"],
		order_by="creation desc",
		limit=200,
	)
	return columns, data
