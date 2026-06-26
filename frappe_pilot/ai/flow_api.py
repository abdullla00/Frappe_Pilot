"""Whitelisted flow API endpoints."""

import json

import frappe
from frappe import _

from .flow_engine import create_flow_run, execute_flow_run, load_definition


@frappe.whitelist()
def start_flow(flow_id: str, payload: str | None = None):
	frappe.only_for("System Manager")
	data = json.loads(payload) if payload else {}
	run = create_flow_run(flow_id, payload=data)
	return {"run": run.name, "status": run.status}


@frappe.whitelist()
def resume_flow(run_name: str):
	frappe.only_for("System Manager")
	return execute_flow_run(run_name)


@frappe.whitelist()
def get_flow_definition(flow_id: str):
	frappe.only_for("System Manager")
	return load_definition(flow_id)
