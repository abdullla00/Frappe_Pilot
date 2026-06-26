"""Scan installed apps for pilot/ seed directories."""

from pathlib import Path

import frappe


def _seed_dirs_for_app(app_name: str) -> list[Path]:
	app_path = frappe.get_app_path(app_name)
	candidates = [Path(app_path) / "pilot", Path(app_path) / "huf"]
	return [p for p in candidates if p.is_dir()]


def find_seed_dirs() -> dict[str, Path]:
	result = {}
	for app in frappe.get_installed_apps():
		dirs = _seed_dirs_for_app(app)
		if not dirs:
			continue
		pilot_dirs = [d for d in dirs if d.name == "pilot"]
		result[app] = pilot_dirs[0] if pilot_dirs else dirs[0]
	return result


def get_seed_files(seed_dir: Path, type_folder: str):
	folder = seed_dir / type_folder
	if not folder.is_dir():
		return []
	return sorted(folder.glob("*.json"))
