# Copyright (c) 2026, Frappe Pilot and contributors

from frappe.model.document import Document


class PilotAgent(Document):
	def validate(self):
		if self.execution_mode_locked and self.execution_mode != "Safe":
			self.execution_mode = "Safe"
		if self.is_system_agent and self.system_agent_key == "build":
			self.execution_mode = "Safe"
			self.execution_mode_locked = 1

		from frappe_pilot.ai.site_tool_sync import sync_agent_tools

		sync_agent_tools(self)
