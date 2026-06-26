"""Safe expression evaluation for flow routing."""

import frappe
from frappe.utils.safe_exec import safe_eval


def safe_eval_expression(expression: str, context: dict | None = None) -> bool:
	if not expression:
		return True
	try:
		return bool(safe_eval(expression, None, context or {}))
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Pilot Flow Eval")
		return False
