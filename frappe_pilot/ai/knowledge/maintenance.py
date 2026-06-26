"""Scheduled maintenance for knowledge indexes."""

import os

import frappe
from frappe.utils import get_files_path


def cleanup_orphaned_files():
	"""Remove sqlite files for deleted knowledge sources."""
	if not frappe.db.exists("DocType", "Pilot Knowledge Source"):
		return
	dir_path = os.path.join(get_files_path(is_private=True), "pilot_knowledge")
	if not os.path.isdir(dir_path):
		return
	valid = {frappe.scrub(name) for name in frappe.get_all("Pilot Knowledge Source", pluck="name")}
	for fname in os.listdir(dir_path):
		base = fname.replace(".sqlite", "")
		if base not in valid and fname.endswith(".sqlite"):
			try:
				os.remove(os.path.join(dir_path, fname))
			except OSError:
				pass


def optimize_indexes():
	"""Placeholder for future index optimization."""
	cleanup_orphaned_files()
