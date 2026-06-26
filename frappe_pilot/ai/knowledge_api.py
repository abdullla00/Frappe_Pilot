"""Whitelisted knowledge API endpoints."""

import frappe
from frappe import _

from .context_builder import build_knowledge_context
from .indexer import process_knowledge_input
from .retriever import search_knowledge_source


@frappe.whitelist()
def index_input(name: str):
	frappe.only_for("System Manager")
	return process_knowledge_input(name)


@frappe.whitelist()
def search(source: str, query: str, limit: int = 5):
	frappe.only_for("System Manager")
	return search_knowledge_source(source, query, limit=int(limit or 5))


@frappe.whitelist()
def agent_context(agent: str, query: str):
	frappe.only_for("System Manager")
	return build_knowledge_context(agent, query)
