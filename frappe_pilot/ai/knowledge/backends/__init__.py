"""Knowledge storage backends."""

from .base import KnowledgeBackend
from .chroma_backend import ChromaBackend
from .sqlite_fts import SQLiteFTSBackend


def get_backend(backend_type: str) -> KnowledgeBackend:
	if backend_type == "chroma":
		return ChromaBackend()
	return SQLiteFTSBackend()


__all__ = ["KnowledgeBackend", "ChromaBackend", "SQLiteFTSBackend", "get_backend"]
