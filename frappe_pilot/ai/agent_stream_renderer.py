"""SSE page renderer placeholder for agent streaming."""

import json

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer
from werkzeug.wrappers import Response


class AgentStreamRenderer(BaseRenderer):
	"""Minimal SSE renderer for /pilot/stream routes."""

	def can_render(self) -> bool:
		return self.path == "pilot/stream" or self.path.startswith("pilot/stream/")

	def render(self):
		if self.path == "pilot/stream/ping":
			return Response(json.dumps({"ok": True}), mimetype="application/json")
		if self.path.startswith("pilot/stream/"):
			return self._render_stream()
		return Response("<p>Pilot stream endpoint</p>", mimetype="text/html")

	def _render_stream(self):
		def generate():
			yield 'data: {"event": "ready"}\n\n'
			yield 'data: {"event": "done"}\n\n'

		return Response(generate(), mimetype="text/event-stream")
