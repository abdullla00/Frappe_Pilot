"""Knowledge ingestion pipeline."""

import frappe
from frappe import _
from frappe.utils import now_datetime

from .backends import get_backend
from .extractors import TextExtractor, URLExtractor


def _chunk_text(text: str, chunk_size: int = 512, chunk_overlap: int = 50) -> list[dict]:
	if not text:
		return []
	chunks = []
	start = 0
	while start < len(text):
		end = min(len(text), start + chunk_size)
		chunks.append({"text": text[start:end], "metadata": {"char_start": start, "char_end": end}})
		if end >= len(text):
			break
		start = max(end - chunk_overlap, start + 1)
	return chunks


def process_knowledge_input(knowledge_input: str) -> dict:
	"""Index a Pilot Knowledge Input document."""
	if not frappe.db.exists("DocType", "Pilot Knowledge Input"):
		return {"ok": False, "error": "DocType missing"}

	doc = frappe.get_doc("Pilot Knowledge Input", knowledge_input)
	source = frappe.get_doc("Pilot Knowledge Source", doc.knowledge_source)
	extractor = TextExtractor()
	url_extractor = URLExtractor()

	try:
		doc.status = "Processing"
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		if doc.input_type == "Text":
			extracted = extractor.extract_from_text(doc.text or "")
		elif doc.input_type == "File":
			extracted = extractor.extract_from_file(doc.file)
		elif doc.input_type == "URL":
			extracted = url_extractor.extract(doc.url)
		else:
			raise ValueError(_("Unsupported input type"))

		chunks = _chunk_text(extracted.text, source.chunk_size or 512, source.chunk_overlap or 50)
		backend = get_backend(source.knowledge_type)
		backend.initialize(source.name, {})
		backend.delete_input(doc.name)
		created = backend.add_chunks(doc.name, chunks)
		backend.close()

		doc.status = "Indexed"
		doc.source_hash = extracted.source_hash
		doc.chunks_created = created
		doc.character_count = len(extracted.text)
		doc.processed_at = now_datetime()
		doc.error_message = None
		doc.save(ignore_permissions=True)

		source.status = "Ready"
		source.last_indexed_at = now_datetime()
		source.total_inputs = frappe.db.count("Pilot Knowledge Input", {"knowledge_source": source.name, "status": "Indexed"})
		source.total_chunks = frappe.db.sql(
			"SELECT COALESCE(SUM(chunks_created), 0) FROM `tabPilot Knowledge Input` WHERE knowledge_source = %s",
			source.name,
		)[0][0]
		source.save(ignore_permissions=True)
		frappe.db.commit()
		return {"ok": True, "chunks": created}
	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "Pilot Knowledge Index")
		doc.status = "Error"
		doc.error_message = str(exc)
		doc.save(ignore_permissions=True)
		source.status = "Error"
		source.error_message = str(exc)
		source.save(ignore_permissions=True)
		frappe.db.commit()
		return {"ok": False, "error": str(exc)}
