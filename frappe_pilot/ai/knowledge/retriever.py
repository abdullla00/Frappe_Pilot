"""Knowledge retrieval helpers."""

import frappe

from .backends import get_backend


def search_knowledge_source(source_name: str, query: str, limit: int = 5) -> list[dict]:
	if not source_name or not query:
		return []
	source = frappe.get_doc("Pilot Knowledge Source", source_name)
	backend = get_backend(source.knowledge_type)
	backend.initialize(source.name, {})
	try:
		return backend.search(query, limit=limit)
	finally:
		backend.close()


def retrieve_for_agent(agent_name: str, query: str) -> list[dict]:
	agent = frappe.get_doc("Pilot Agent", agent_name)
	results = []
	for row in agent.get("agent_knowledge") or []:
		if not row.knowledge_source:
			continue
		max_chunks = row.max_chunks or 5
		rows = search_knowledge_source(row.knowledge_source, query, limit=max_chunks)
		for item in rows:
			item["knowledge_source"] = row.knowledge_source
			item["injection_mode"] = row.injection_mode
		results.extend(rows)
	return results
