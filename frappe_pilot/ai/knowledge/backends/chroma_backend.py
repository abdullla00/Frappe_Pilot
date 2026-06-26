"""Chroma vector backend (simplified)."""

import json
import os

import frappe
from frappe.utils import get_files_path

from .base import KnowledgeBackend


class ChromaBackend(KnowledgeBackend):
	def __init__(self):
		self.collection = None
		self.knowledge_source = None

	def initialize(self, knowledge_source: str, config: dict) -> None:
		self.knowledge_source = knowledge_source
		try:
			import chromadb
		except ImportError as exc:
			raise ImportError("chromadb is required for Chroma knowledge sources") from exc

		files_path = get_files_path(is_private=True)
		persist_dir = os.path.join(files_path, "pilot_knowledge", frappe.scrub(knowledge_source))
		os.makedirs(persist_dir, exist_ok=True)
		client = chromadb.PersistentClient(path=persist_dir)
		self.collection = client.get_or_create_collection(name=frappe.scrub(knowledge_source))

	def add_chunks(self, input_id: str, chunks: list[dict]) -> int:
		if not self.collection or not chunks:
			return 0
		ids = [f"{input_id}-{idx}" for idx in range(len(chunks))]
		docs = [c.get("text", "") for c in chunks]
		metas = [{"input_id": input_id, **(c.get("metadata") or {})} for c in chunks]
		self.collection.add(ids=ids, documents=docs, metadatas=metas)
		return len(chunks)

	def delete_input(self, input_id: str) -> None:
		if not self.collection:
			return
		try:
			self.collection.delete(where={"input_id": input_id})
		except Exception:
			pass

	def search(self, query: str, limit: int = 5) -> list[dict]:
		if not self.collection or not query:
			return []
		result = self.collection.query(query_texts=[query], n_results=limit)
		docs = result.get("documents") or [[]]
		metas = result.get("metadatas") or [[]]
		rows = []
		for doc, meta in zip(docs[0], metas[0]):
			rows.append({"text": doc, "metadata": json.dumps(meta or {}), "input_id": (meta or {}).get("input_id")})
		return rows
