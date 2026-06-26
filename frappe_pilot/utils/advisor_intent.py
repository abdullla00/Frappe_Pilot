# Advisor intent router — single source of truth for message classification.

import re

DIAGNOSE_TRIGGERS = frozenset({
	"diagnose this record",
	"flag anything unusual",
	"why are these records here?",
	"why is this total high?",
	"دەستنیشانکردنی کێشەکان",
})

INTENT_CALCULATION = "calculation"
INTENT_SUMMARY = "summary"
INTENT_DIAGNOSE = "diagnose"
INTENT_HOWTO = "howto"
INTENT_NAVIGATE = "navigate"
INTENT_EXPLAIN = "explain"

_CALC_RE = re.compile(
	r"\b("
	r"how much|total|rent|rental|cost|price|amount|calculate|calculation|"
	r"days|day rate|per day|grand total|estimate|estimated|"
	r"چەند|کۆی|کرێ|ڕۆژ"
	r")\b",
	re.I,
)
_SUMMARY_RE = re.compile(
	r"\b(summarize|summary|overview|status|what is this|what's on|"
	r"what is on|give me a summary|brief overview)\b",
	re.I,
)
_HOWTO_RE = re.compile(
	r"\b(how do i|how to|where do i|where to click|where can i|"
	r"walk me through|what fields|what is required|help me fill)\b",
	re.I,
)
_NAV_RE = re.compile(
	r"\b(open|go to|take me to|navigate|show me the|show me this)\b",
	re.I,
)
_DAYS_RE = re.compile(r"(\d+)\s*(?:days?|d\b|ڕۆژ)", re.I)


def extract_days(message: str) -> int | None:
	if not message:
		return None
	match = _DAYS_RE.search(message)
	if match:
		try:
			return int(match.group(1))
		except (TypeError, ValueError):
			return None
	return None


def _is_diagnose(message: str) -> bool:
	normalised = (message or "").strip().lower()
	if normalised in DIAGNOSE_TRIGGERS or normalised.startswith("diagnose "):
		return True
	if "what's wrong" in normalised or "what is wrong" in normalised:
		return True
	if "flag anything unusual" in normalised:
		return True
	return False


def detect_intent(message: str, *, mode: str = "") -> dict:
	"""Classify user message → intent, agent mode, and output hints."""
	text = (message or "").strip()
	lower = text.lower()

	if mode == "diagnose" or _is_diagnose(text):
		return {
			"intent": INTENT_DIAGNOSE,
			"mode": "diagnose",
			"wants_card": True,
			"card_type": "diagnose",
			"days": extract_days(text),
		}

	if _NAV_RE.search(text) and not _CALC_RE.search(text) and not _SUMMARY_RE.search(text):
		return {
			"intent": INTENT_NAVIGATE,
			"mode": "explain",
			"wants_card": False,
			"card_type": None,
			"days": extract_days(text),
		}

	if _HOWTO_RE.search(text) and not _CALC_RE.search(text):
		return {
			"intent": INTENT_HOWTO,
			"mode": "explain",
			"wants_card": False,
			"card_type": None,
			"days": extract_days(text),
		}

	if _CALC_RE.search(text) or extract_days(text):
		return {
			"intent": INTENT_CALCULATION,
			"mode": "explain",
			"wants_card": True,
			"card_type": "calculation",
			"days": extract_days(text),
		}

	if _SUMMARY_RE.search(text):
		return {
			"intent": INTENT_SUMMARY,
			"mode": "explain",
			"wants_card": True,
			"card_type": "summary",
			"days": None,
		}

	return {
		"intent": INTENT_EXPLAIN,
		"mode": mode if mode in ("explain", "diagnose") else "explain",
		"wants_card": False,
		"card_type": None,
		"days": extract_days(text),
	}


def resolve_agent_mode(message: str, mode: str = "") -> str:
	"""Extend analyze._resolve_mode using intent router."""
	intent = detect_intent(message, mode=mode)
	return intent.get("mode") or "explain"


def is_analytical_message(message: str) -> bool:
	"""True when message is calculation/summary/diagnose — skip nav enrichment."""
	intent = detect_intent(message).get("intent")
	return intent in (INTENT_CALCULATION, INTENT_SUMMARY, INTENT_DIAGNOSE)
