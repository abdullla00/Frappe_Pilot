# Copyright (c) 2026, Frappe Pilot and contributors

import frappe
from frappe import _


class RunProvider:
	@staticmethod
	def run(agent, enhanced_prompt, provider, model, context=None):
		try:
			from frappe_pilot.ai.providers import litellm

			return litellm.run(agent, enhanced_prompt, provider, model, context=context)
		except ImportError as e:
			if "litellm" in str(e):
				msg = (
					"LiteLLM is required but not installed. "
					"Run bench setup requirements and restart the site."
				)
				frappe.log_error(str(e), "Pilot LiteLLM Import")
				frappe.throw(_(msg))
			raise
