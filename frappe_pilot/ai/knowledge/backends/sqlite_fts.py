"""SQLite FTS5 backend for keyword search."""

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager

import frappe
from frappe.utils import get_files_path

from .base import KnowledgeBackend


class SQLiteFTSBackend(KnowledgeBackend):
	SCHEMA = """
	CREATE TABLE IF NOT EXISTS chunks (
		chunk_id TEXT PRIMARY KEY,
		input_id TEXT NOT NULL,
		chunk_index INTEGER NOT NULL,
		text TEXT NOT NULL,
		metadata TEXT,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	);
	CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
		text,
		content='chunks',
		content_rowid='rowid',
		tokenize='porter unicode61'
	);
	CREATE INDEX IF NOT EXISTS idx_chunks_input_id ON chunks(input_id);
	"""

	def __init__(self):
		self.knowledge_source = None
		self.db_path = None

	def initialize(self, knowledge_source: str, config: dict) -> None:
		self.knowledge_source = knowledge_source
		files_path = get_files_path(is_private=True)
		knowledge_dir = os.path.join(files_path, "pilot_knowledge")
		os.makedirs(knowledge_dir, exist_ok=True)
		safe_name = frappe.scrub(knowledge_source)
		self.db_path = os.path.join(knowledge_dir, f"{safe_name}.sqlite")
		with self._connect() as conn:
			conn.executescript(self.SCHEMA)

	@contextmanager
	def _connect(self):
		conn = sqlite3.connect(self.db_path)
		conn.row_factory = sqlite3.Row
		try:
			yield conn
			conn.commit()
		finally:
			conn.close()

	def add_chunks(self, input_id: str, chunks: list[dict]) -> int:
		count = 0
		with self._connect() as conn:
			for idx, chunk in enumerate(chunks):
				chunk_id = str(uuid.uuid4())
				conn.execute(
					"INSERT INTO chunks (chunk_id, input_id, chunk_index, text, metadata) VALUES (?, ?, ?, ?, ?)",
					(
						chunk_id,
						input_id,
						idx,
						chunk.get("text", ""),
						json.dumps(chunk.get("metadata") or {}),
					),
				)
				count += 1
		return count

	def delete_input(self, input_id: str) -> None:
		with self._connect() as conn:
			conn.execute("DELETE FROM chunks WHERE input_id = ?", (input_id,))

	def search(self, query: str, limit: int = 5) -> list[dict]:
		if not query:
			return []
		with self._connect() as conn:
			rows = conn.execute(
				"""
				SELECT c.input_id, c.text, c.metadata
				FROM chunks_fts f
				JOIN chunks c ON c.rowid = f.rowid
				WHERE chunks_fts MATCH ?
				LIMIT ?
				""",
				(query, limit),
			).fetchall()
		return [dict(row) for row in rows]
