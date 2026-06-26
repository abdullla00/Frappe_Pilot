"""Build LLM context snippets from retrieved knowledge."""

from .retriever import retrieve_for_agent


def build_knowledge_context(agent_name: str, query: str, token_budget: int = 2000) -> str:
	rows = retrieve_for_agent(agent_name, query)
	if not rows:
		return ""

	parts = []
	used = 0
	for row in rows:
		text = row.get("text") or ""
		if not text:
			continue
		if used + len(text) > token_budget * 4:
			break
		parts.append(text)
		used += len(text)
	return "\n\n".join(parts)
