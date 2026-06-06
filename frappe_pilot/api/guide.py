# Guide API — deprecated; forwards to Advisor (analyze.chat)

import frappe

from frappe_pilot.api.advisor_prompts import GUIDE_SYSTEM_PROMPT


@frappe.whitelist()
def chat(message, doctype="", docname="", mode="guide", route="", list_doctype="", reply_locale=""):
	"""Deprecated — use frappe_pilot.api.analyze.chat (Advisor)."""
	from frappe_pilot.api.analyze import chat as advisor_chat

	return advisor_chat(
		message=message,
		doctype=doctype,
		docname=docname,
		route=route,
		list_doctype=list_doctype,
		mode=mode if mode in ("explain", "diagnose") else "explain",
		reply_locale=reply_locale,
	)
