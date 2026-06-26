"""Seed Pilot definitions from app pilot/ folders."""

import json
from dataclasses import dataclass, field
from pathlib import Path

import frappe

from .scanner import _seed_dirs_for_app, find_seed_dirs, get_seed_files


@dataclass
class SeedResult:
	app: str
	seeded: int = 0
	skipped: int = 0
	errors: list[str] = field(default_factory=list)


def _upsert_doc(doctype: str, key_field: str, key_value: str, data: dict) -> tuple[bool, str | None]:
	try:
		if frappe.db.exists(doctype, key_value):
			doc = frappe.get_doc(doctype, key_value)
			for k, v in data.items():
				if k not in ("doctype", key_field):
					doc.set(k, v)
			doc.save(ignore_permissions=True)
		else:
			payload = {"doctype": doctype, key_field: key_value, **data}
			frappe.get_doc(payload).insert(ignore_permissions=True)
		return True, None
	except Exception as exc:
		return False, str(exc)


def seed_app(app_name: str, seed_dir: Path) -> SeedResult:
	result = SeedResult(app=app_name)
	loaders = {
		"agents": ("Pilot Agent", "agent_name"),
		"tools": ("Pilot Agent Tool Function", "tool_name"),
		"knowledge": ("Pilot Knowledge Source", "source_name"),
		"triggers": ("Pilot Agent Trigger", "trigger_name"),
	}
	for folder, (doctype, key_field) in loaders.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		for file_path in get_seed_files(seed_dir, folder):
			try:
				with open(file_path, encoding="utf-8") as handle:
					data = json.load(handle)
				items = data if isinstance(data, list) else [data]
				for item in items:
					key = item.get(key_field)
					if not key:
						result.skipped += 1
						continue
					ok, err = _upsert_doc(doctype, key_field, key, item)
					if ok:
						result.seeded += 1
					else:
						result.skipped += 1
						result.errors.append(f"{key}: {err}")
			except Exception as exc:
				result.skipped += 1
				result.errors.append(f"{file_path.name}: {exc}")
	return result


def seed_all() -> list[SeedResult]:
	return [seed_app(app, path) for app, path in find_seed_dirs().items()]


def on_app_installed(app_name: str):
	try:
		dirs = _seed_dirs_for_app(app_name)
		if not dirs:
			return
		seed_dir = next((d for d in dirs if d.name == "pilot"), dirs[0])
		res = seed_app(app_name, seed_dir)
		if res.errors:
			frappe.log_error(str(res.errors), f"Pilot seed errors: {app_name}")
	except Exception as exc:
		frappe.log_error(str(exc), f"Pilot seed failed: {app_name}")


@frappe.whitelist()
def seed_all_apps():
	frappe.only_for("System Manager")
	results = seed_all()
	return {
		"seeded": sum(r.seeded for r in results),
		"skipped": sum(r.skipped for r in results),
		"results": [r.__dict__ for r in results],
	}
