"""Site DocType metadata indexing for RAG."""

import frappe
from frappe.utils import now_datetime

from frappe_pilot.ai.knowledge.backends import get_backend

SYSTEM_SOURCE_NAME = "Site DocType Metadata"
METADATA_INPUT_ID = "__site_metadata__"


def ensure_system_metadata_source() -> str:
	if not frappe.db.exists("DocType", "Pilot Knowledge Source"):
		return ""
	if frappe.db.exists("Pilot Knowledge Source", SYSTEM_SOURCE_NAME):
		return SYSTEM_SOURCE_NAME
	doc = frappe.get_doc({
		"doctype": "Pilot Knowledge Source",
		"source_name": SYSTEM_SOURCE_NAME,
		"description": "Auto-indexed DocType schema for all installed apps",
		"knowledge_type": "sqlite_fts",
		"scope": "Site",
		"status": "Pending",
		"chunk_size": 800,
		"chunk_overlap": 80,
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def build_metadata_chunks() -> list[dict]:
	chunks = []
	for dt in frappe.get_all("DocType", filters={"custom": 0, "istable": 0}, pluck="name"):
		meta = frappe.get_meta(dt)
		app = ""
		if meta.module:
			app = frappe.db.get_value("Module Def", meta.module, "app_name") or ""
		lines = [
			f"DocType: {dt}",
			f"App: {app}",
			f"Module: {meta.module}",
			f"Label: {dt}",
			"Fields:",
		]
		for field in meta.fields:
			if field.fieldtype in ("Section Break", "Column Break", "Tab Break"):
				continue
			line = f"- {field.fieldname} ({field.fieldtype})"
			if field.reqd:
				line += " [mandatory]"
			if field.options:
				line += f" options={field.options}"
			lines.append(line)
		chunks.append({
			"text": "\n".join(lines),
			"metadata": {"doctype": dt, "app": app, "module": meta.module},
		})
	return chunks


def refresh_source_stats(source_name: str) -> None:
	if not frappe.db.exists("Pilot Knowledge Source", source_name):
		return
	total_inputs = frappe.db.count(
		"Pilot Knowledge Input",
		{"knowledge_source": source_name, "status": "Indexed"},
	)
	total_chunks = frappe.db.sql(
		"SELECT COALESCE(SUM(chunks_created), 0) FROM `tabPilot Knowledge Input` WHERE knowledge_source = %s",
		source_name,
	)[0][0]
	frappe.db.set_value(
		"Pilot Knowledge Source",
		source_name,
		{"total_inputs": total_inputs, "total_chunks": total_chunks},
		update_modified=False,
	)


def reindex_site_metadata():
	source_name = ensure_system_metadata_source()
	if not source_name:
		return
	doc = frappe.get_doc("Pilot Knowledge Source", source_name)
	chunks = build_metadata_chunks()
	backend = get_backend(doc.knowledge_type or "sqlite_fts")
	backend.initialize(source_name, doc.as_dict())
	backend.delete_input(METADATA_INPUT_ID)
	created = backend.add_chunks(METADATA_INPUT_ID, chunks)
	backend.close()
	doc.total_chunks = created
	doc.total_inputs = 1
	doc.last_indexed_at = now_datetime()
	doc.status = "Ready"
	doc.error_message = None
	frappe.db.set_value(
		"Pilot Knowledge Source",
		source_name,
		{
			"total_chunks": created,
			"total_inputs": 1,
			"last_indexed_at": doc.last_indexed_at,
			"status": "Ready",
			"error_message": None,
		},
		update_modified=True,
	)
	frappe.db.commit()


def enqueue_metadata_reindex():
	if not frappe.db.exists("DocType", "Pilot Knowledge Source"):
		return
	frappe.enqueue(
		"frappe_pilot.ai.knowledge.metadata_indexer.reindex_site_metadata",
		queue="long",
		now=frappe.flags.in_install,
	)
