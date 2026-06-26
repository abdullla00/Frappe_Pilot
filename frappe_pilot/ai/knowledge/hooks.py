"""Knowledge DocType event handlers."""

import frappe

from .indexer import process_knowledge_input
from .metadata_indexer import refresh_source_stats


def on_knowledge_source_created(doc, method=None):
	if doc.status != "Pending":
		doc.db_set("status", "Pending")


def on_knowledge_source_updated(doc, method=None):
	refresh_source_stats(doc.name)


def on_knowledge_source_deleted(doc, method=None):
	inputs = frappe.get_all("Pilot Knowledge Input", filters={"knowledge_source": doc.name}, pluck="name")
	for name in inputs:
		frappe.delete_doc("Pilot Knowledge Input", name, ignore_permissions=True)


def on_knowledge_input_saved(doc, method=None):
	if doc.flags.get("skip_index"):
		return
	if doc.input_type and doc.status in (None, "", "Pending"):
		frappe.enqueue(
			"frappe_pilot.ai.knowledge.indexer.process_knowledge_input",
			knowledge_input=doc.name,
			queue="long",
		)


def on_knowledge_input_deleted(doc, method=None):
	from .backends import get_backend

	source = frappe.get_doc("Pilot Knowledge Source", doc.knowledge_source)
	backend = get_backend(source.knowledge_type)
	backend.initialize(source.name, {})
	backend.delete_input(doc.name)
	backend.close()
	refresh_source_stats(source.name)
