"""Knowledge backend base class."""


class KnowledgeBackend:
	def initialize(self, knowledge_source: str, config: dict) -> None:
		raise NotImplementedError

	def add_chunks(self, input_id: str, chunks: list[dict]) -> int:
		raise NotImplementedError

	def delete_input(self, input_id: str) -> None:
		raise NotImplementedError

	def search(self, query: str, limit: int = 10) -> list[dict]:
		raise NotImplementedError

	def close(self) -> None:
		return None
