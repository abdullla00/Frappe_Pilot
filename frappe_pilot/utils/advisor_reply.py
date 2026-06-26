# Advisor brief reply composer and reply formatting.

import re

from frappe_pilot.utils.advisor_intent import (
	INTENT_CALCULATION,
	INTENT_DIAGNOSE,
	INTENT_SUMMARY,
	detect_intent,
)

_TOOL_PLANNING_MARKERS = (
	"get_list_sample",
	"get_document",
	"get_domain_calc_context",
	"submit_advisor_card",
	"run_document_checks",
	"i will fetch",
	"let me fetch",
	"let me use",
	"let me proceed",
	"let me start",
	"let me run",
	"i'll fetch",
	"i will use",
)

_READ_ONLY_OFFER_RE = re.compile(
	r"\b(i('ll| will)|let me)\s+(update|change|modify|edit|set)\b",
	re.I,
)


def looks_like_tool_planning(text: str) -> bool:
	if not text or len(text) < 80:
		return False
	lower = (text or "").lower()
	return sum(1 for marker in _TOOL_PLANNING_MARKERS if marker in lower) >= 2


def strip_read_only_offers(text: str) -> str:
	if not text:
		return text
	if _READ_ONLY_OFFER_RE.search(text):
		lines = [ln for ln in text.splitlines() if not _READ_ONLY_OFFER_RE.search(ln)]
		cleaned = "\n".join(lines).strip()
		return cleaned or "I can explain what to change — you will need to update the form manually."
	return text


def _format_currency(amount, currency=""):
	if amount is None:
		return ""
	try:
		import frappe

		return frappe.format_value(float(amount), {"fieldtype": "Currency", "options": currency or None})
	except Exception:
		return f"{amount:,.2f}" + (f" {currency}" if currency else "")


def compose_brief_advisor_reply(advisor_card: dict | None) -> str | None:
	"""One-line headline from a validated advisor card."""
	if not advisor_card or advisor_card.get("error"):
		return None

	card_type = advisor_card.get("type") or advisor_card.get("card_type")
	currency = advisor_card.get("currency") or ""

	if card_type == "calculation":
		total = advisor_card.get("total")
		days = advisor_card.get("days")
		if total is not None:
			formatted = _format_currency(total, currency)
			if days:
				return f"Total for {days} days: **{formatted}** — see breakdown below."
			return f"Estimated total: **{formatted}** — see breakdown below."
		headline = advisor_card.get("headline")
		if headline:
			return headline

	if card_type == "summary":
		headline = advisor_card.get("headline") or advisor_card.get("title")
		if headline:
			return headline
		status = advisor_card.get("status")
		if status:
			return f"**{status}** — see summary below."

	if card_type == "diagnose":
		issues = advisor_card.get("issues") or advisor_card.get("findings") or []
		count = len(issues)
		if count == 0:
			return "No issues detected — see details below."
		return f"**{count} issue{'s' if count != 1 else ''} found** — see findings below."

	return advisor_card.get("headline") or advisor_card.get("title")


def format_advisor_markdown(text: str, *, max_words: int = 120) -> str:
	"""Trim and clean LLM markdown for Advisor chat."""
	if not text:
		return text
	clean = strip_read_only_offers(text.strip())
	words = clean.split()
	if len(words) > max_words:
		clean = " ".join(words[:max_words]).rstrip(".,;:") + "…"
	return clean


def finalize_advisor_reply(
	raw_reply: str,
	*,
	advisor_card: dict | None = None,
	message: str = "",
	brief_replies_enabled: bool = True,
) -> str:
	"""Degradation ladder: card brief → cleaned LLM → formatted fallback."""
	if brief_replies_enabled and advisor_card:
		brief = compose_brief_advisor_reply(advisor_card)
		if brief:
			return brief

	intent = detect_intent(message).get("intent")
	if advisor_card and not brief_replies_enabled:
		brief = compose_brief_advisor_reply(advisor_card)
		if brief:
			return brief

	if looks_like_tool_planning(raw_reply):
		if advisor_card:
			brief = compose_brief_advisor_reply(advisor_card)
			if brief:
				return brief
		if intent in (INTENT_CALCULATION, INTENT_SUMMARY, INTENT_DIAGNOSE):
			return "See the card below for details."

	clean = strip_read_only_offers(raw_reply or "")
	if intent in (INTENT_CALCULATION, INTENT_SUMMARY):
		return format_advisor_markdown(clean, max_words=120)
	return format_advisor_markdown(clean, max_words=150)
