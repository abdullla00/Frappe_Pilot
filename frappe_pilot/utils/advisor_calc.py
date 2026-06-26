# Advisor calculation fast path — deterministic card without LLM when hook is unambiguous.

from frappe_pilot.utils.advisor_intent import INTENT_CALCULATION
from frappe_pilot.utils.advisor_reply import compose_brief_advisor_reply


def try_calc_fast_path(*, doctype="", docname="", message="", intent_info=None):
	"""Return advisor response dict when domain hook provides a complete suggested_card."""
	intent_info = intent_info or {}
	if intent_info.get("intent") != INTENT_CALCULATION:
		return None
	if not doctype or not docname:
		return None

	days = intent_info.get("days")
	if not days:
		return None

	from frappe_pilot.api.analyze_tools import exec_get_domain_calc_context

	result = exec_get_domain_calc_context(doctype=doctype, docname=docname, days=days)
	if not isinstance(result, dict) or result.get("error"):
		return None

	card = result.get("suggested_card")
	if not card or not card.get("rows"):
		return None

	reply = compose_brief_advisor_reply(card)
	if not reply:
		return None

	return {
		"reply": reply,
		"advisor_card": card,
		"evidence": {
			"tools_used": ["get_domain_calc_context"],
			"checks_run": 0,
			"fast_path": True,
			"calc_evidence": {
				"lines": result.get("lines") or [],
				"currency": result.get("currency"),
				"days": days,
			},
		},
	}
