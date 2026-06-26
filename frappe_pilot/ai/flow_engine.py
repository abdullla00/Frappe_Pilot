"""Simplified flow execution engine."""

import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from .flow_eval import safe_eval_expression

DEFAULT_MAX_HOPS = 100


def load_definition(flow_id: str) -> dict:
	doc = frappe.get_doc("Pilot Flow Definition", flow_id)
	if doc.status != "Active":
		frappe.throw(_("Flow '{0}' is not active").format(flow_id))
	return json.loads(doc.definition_json) if isinstance(doc.definition_json, str) else doc.definition_json


def create_flow_run(flow_id: str, payload: dict | None = None, trigger_type: str = "Manual"):
	defn_doc = frappe.get_doc("Pilot Flow Definition", flow_id)
	run = frappe.new_doc("Pilot Flow Run")
	run.flow_definition = defn_doc.name
	run.flow_id = defn_doc.flow_id
	run.flow_version = defn_doc.version or 1
	run.mode = "Normal"
	run.status = "Queued"
	run.trigger_type = trigger_type
	run.context_json = json.dumps(payload or {})
	run.trigger_payload = json.dumps(payload or {})
	run.max_hops = DEFAULT_MAX_HOPS
	run.started_at = now_datetime()
	run.insert(ignore_permissions=True)
	frappe.db.commit()
	return run


def execute_flow_run(run_name: str) -> dict:
	run = frappe.get_doc("Pilot Flow Run", run_name)
	defn = load_definition(run.flow_definition)
	context = json.loads(run.context_json or "{}")
	nodes = {n["id"]: n for n in defn.get("nodes", []) if n.get("id")}
	start_id = defn.get("start") or (defn.get("nodes") or [{}])[0].get("id")
	current = run.current_node_id or start_id
	hops = run.hop_count or 0

	run.status = "Running"
	run.save(ignore_permissions=True)

	while current and hops < (run.max_hops or DEFAULT_MAX_HOPS):
		hops += 1
		node = nodes.get(current) or {}
		node_type = node.get("type", "end")
		if node_type == "end":
			current = None
			break
		if node_type == "condition":
			current = _next_edge(defn, current, success=safe_eval_expression(node.get("expression", ""), context))
			continue
		context.setdefault("steps", []).append({"node": current, "type": node_type})
		current = _next_edge(defn, current, success=True)

	run.hop_count = hops
	run.current_node_id = current
	run.context_json = json.dumps(context)
	run.status = "Success" if not current else "Failed"
	run.completed_at = now_datetime()
	run.save(ignore_permissions=True)
	frappe.db.commit()
	return {"status": run.status, "hops": hops}


def _next_edge(defn: dict, node_id: str, success: bool = True) -> str | None:
	for edge in defn.get("edges", []):
		if edge.get("from") != node_id:
			continue
		when = edge.get("when", "always")
		if when == "always" or (success and when == "on_success") or ((not success) and when == "on_failure"):
			return edge.get("to")
	return None
