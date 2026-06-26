# Copyright (c) 2026, Frappe Pilot and contributors
"""Desk / workspace / desktop icon setup — runs on after_install and after_migrate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frappe

LOGO_URL = "/assets/frappe_pilot/images/frappe-pilot-logo.svg"
HOME_LINK = "/desk/pilot"
DESKTOP_ICON_NAME = "Frappe Pilot"
WORKSPACE_NAME = "Pilot"
SIDEBAR_TITLE = "Frappe Pilot"
LEGACY_SIDEBAR_TITLE = "Pilot"
HERO_BLOCK_NAME = "Frappe Pilot Hero"
APP_NAME = "frappe_pilot"

APP_PATH = Path(frappe.get_app_path("frappe_pilot"))

CUSTOM_BLOCK_FIXTURES = ("custom_html_block/pilot_hero/pilot_hero.json",)

WORKSPACE_FIXTURE = ("Pilot", "frappe_pilot/workspace/pilot/pilot.json")

SIDEBAR_FIXTURE = "workspace_sidebar/frappe_pilot.json"

DESKTOP_ICON_FIXTURE = "desktop_icon/frappe_pilot.json"

PILOT_LAYOUT_LABELS = frozenset({DESKTOP_ICON_NAME, WORKSPACE_NAME})


def after_migrate():
	sync_desk_from_app()


def sync_desk_from_app():
	"""Idempotent desk sync from app fixtures (install + every migrate)."""
	_upgrade_cleanup()
	_sync_custom_html_blocks()
	_ensure_workspace_exists()
	_sync_workspace_from_fixture()
	_sync_workspace_sidebar_from_fixture()
	_sync_desktop_icon_from_fixture()
	_dedupe_desktop_icons()
	_ensure_workspace_app_field()
	_refresh_pilot_desk_logo()
	_repair_pilot_icon_in_layouts()
	frappe.clear_cache()


def purge_pilot_desk_artifacts(*, include_workspace: bool = True) -> None:
	"""Remove every Pilot desk surface; safe to call from before_uninstall."""
	_purge_pilot_from_desktop_layouts()
	_delete_pilot_desktop_icons()
	_delete_pilot_sidebars()
	_delete_pilot_hero_block()
	_scrub_my_workspaces_pins()
	if include_workspace and frappe.db.exists("Workspace", WORKSPACE_NAME):
		frappe.delete_doc("Workspace", WORKSPACE_NAME, force=True, ignore_permissions=True)
	_clear_desk_caches()


def _app_path(*parts: str) -> Path:
	return APP_PATH.joinpath(*parts)


def _load_json(relative_path: str) -> dict:
	return json.loads(_app_path(relative_path).read_text())


def _upgrade_cleanup():
	_migrate_pilot_sidebar_title()


def _migrate_pilot_sidebar_title():
	"""Align sidebar doc name with the desktop icon label for routing and header logo."""
	if frappe.db.exists("Workspace Sidebar", SIDEBAR_TITLE):
		return
	if frappe.db.exists("Workspace Sidebar", LEGACY_SIDEBAR_TITLE):
		frappe.rename_doc("Workspace Sidebar", LEGACY_SIDEBAR_TITLE, SIDEBAR_TITLE, force=True)


def _upsert_custom_block(relative_fixture: str):
	fixture = _app_path(relative_fixture)
	if not fixture.exists():
		return

	data = json.loads(fixture.read_text())
	name = data["name"]
	if frappe.db.exists("Custom HTML Block", name):
		doc = frappe.get_doc("Custom HTML Block", name)
		doc.html = data.get("html")
		doc.style = data.get("style")
		doc.script = data.get("script") or ""
		doc.private = 0
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc(data).insert(ignore_permissions=True)


def _sync_custom_html_blocks():
	for relative in CUSTOM_BLOCK_FIXTURES:
		_upsert_custom_block(relative)


def _ensure_workspace_exists():
	workspace_name, relative_fixture = WORKSPACE_FIXTURE
	fixture_path = _app_path(relative_fixture)
	if not fixture_path.exists():
		return
	if frappe.db.exists("Workspace", workspace_name):
		return
	fixture = json.loads(fixture_path.read_text())
	frappe.get_doc(fixture).insert(ignore_permissions=True)


def _sync_workspace_from_fixture():
	workspace_name, relative_fixture = WORKSPACE_FIXTURE
	fixture_path = _app_path(relative_fixture)
	if not fixture_path.exists() or not frappe.db.exists("Workspace", workspace_name):
		return

	fixture = json.loads(fixture_path.read_text())
	ws = frappe.get_doc("Workspace", workspace_name)
	ws.content = fixture["content"]
	ws.icon = fixture.get("icon") or ws.icon
	ws.indicator_color = fixture.get("indicator_color") or ws.indicator_color
	# Desk icon routing (desktop.js get_route) slugs workspaces.title, not name — keep in sync.
	ws.title = workspace_name
	if fixture.get("app"):
		ws.app = fixture["app"]

	ws.shortcuts = []
	ws.number_cards = []
	ws.quick_lists = []
	ws.links = []
	ws.custom_blocks = []

	for row in fixture.get("shortcuts", []):
		ws.append("shortcuts", row)
	for row in fixture.get("number_cards", []):
		ws.append("number_cards", row)
	for row in fixture.get("quick_lists", []):
		ws.append("quick_lists", row)
	for row in fixture.get("links", []):
		ws.append("links", row)
	for row in fixture.get("custom_blocks", []):
		ws.append("custom_blocks", row)

	ws.save(ignore_permissions=True)


def _sync_workspace_sidebar_from_fixture():
	fixture_path = _app_path(SIDEBAR_FIXTURE)
	if not fixture_path.exists():
		return

	data = json.loads(fixture_path.read_text())
	title = data.get("title") or SIDEBAR_TITLE

	if frappe.db.exists("Workspace Sidebar", title):
		doc = frappe.get_doc("Workspace Sidebar", title)
	else:
		doc = frappe.new_doc("Workspace Sidebar")

	for field in ("app", "module", "header_icon", "standard", "title"):
		if field in data:
			doc.set(field, data[field])

	doc.items = []
	for item in data.get("items", []):
		doc.append("items", item)

	doc.save(ignore_permissions=True)


def _sync_desktop_icon_from_fixture():
	fixture_path = _app_path(DESKTOP_ICON_FIXTURE)
	if not fixture_path.exists():
		return

	data = json.loads(fixture_path.read_text())
	name = data.get("name") or DESKTOP_ICON_NAME

	if frappe.db.exists("Desktop Icon", name):
		doc = frappe.get_doc("Desktop Icon", name)
		for field in (
			"label",
			"link",
			"link_type",
			"link_to",
			"sidebar",
			"app",
			"icon_type",
			"logo_url",
			"bg_color",
			"standard",
			"hidden",
		):
			if field in data:
				doc.set(field, data[field])
		if data.get("link_type") == "Workspace Sidebar":
			doc.link = None
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc(data).insert(ignore_permissions=True)


def _dedupe_desktop_icons():
	"""Keep canonical Frappe Pilot App icon; remove duplicate auto-generated rows."""
	canonical = None
	if frappe.db.exists("Desktop Icon", DESKTOP_ICON_NAME):
		canonical = DESKTOP_ICON_NAME

	duplicates = frappe.get_all(
		"Desktop Icon",
		filters={"app": APP_NAME, "icon_type": "App"},
		pluck="name",
	)
	for name in duplicates:
		if name != canonical:
			frappe.delete_doc("Desktop Icon", name, force=True, ignore_permissions=True)


def _ensure_workspace_app_field():
	if not frappe.db.exists("Workspace", WORKSPACE_NAME):
		return
	current = frappe.db.get_value("Workspace", WORKSPACE_NAME, "app")
	if current != APP_NAME:
		frappe.db.set_value("Workspace", WORKSPACE_NAME, "app", APP_NAME, update_modified=False)


def _refresh_pilot_desk_logo():
	if frappe.db.exists("Desktop Icon", DESKTOP_ICON_NAME):
		frappe.db.set_value(
			"Desktop Icon",
			DESKTOP_ICON_NAME,
			{
				"logo_url": LOGO_URL,
				"icon_image": None,
				"link_type": "Workspace Sidebar",
				"link_to": SIDEBAR_TITLE,
				"sidebar": SIDEBAR_TITLE,
				"link": None,
			},
			update_modified=False,
		)

	for row in frappe.get_all("Desktop Layout", fields=["name", "layout"]):
		if not row.layout or DESKTOP_ICON_NAME not in row.layout:
			continue
		layout = json.loads(row.layout)
		if _patch_pilot_logo_in_layout(layout):
			frappe.db.set_value(
				"Desktop Layout",
				row.name,
				"layout",
				json.dumps(layout),
				update_modified=False,
			)


def _patch_pilot_logo_in_layout(obj: Any) -> bool:
	changed = False
	if isinstance(obj, list):
		for item in obj:
			if _patch_pilot_logo_in_layout(item):
				changed = True
	elif isinstance(obj, dict):
		if obj.get("label") == DESKTOP_ICON_NAME:
			if obj.get("icon_image"):
				obj["icon_image"] = None
				changed = True
			if obj.get("logo_url") != LOGO_URL:
				obj["logo_url"] = LOGO_URL
				changed = True
			if obj.get("link") != HOME_LINK:
				obj["link"] = HOME_LINK
				changed = True
		for key in ("child_icons",):
			if obj.get(key) and _patch_pilot_logo_in_layout(obj[key]):
				changed = True
	return changed


def _repair_pilot_icon_in_layouts():
	if not frappe.db.exists("Desktop Icon", DESKTOP_ICON_NAME):
		return

	icon = frappe.get_doc("Desktop Icon", DESKTOP_ICON_NAME)
	canonical = {
		"label": icon.label,
		"logo_url": LOGO_URL,
		"link": HOME_LINK,
		"link_type": icon.link_type,
		"icon_type": icon.icon_type,
		"app": icon.app,
		"bg_color": icon.bg_color,
		"name": icon.name,
	}

	for row in frappe.get_all("Desktop Layout", fields=["name", "layout"]):
		if not row.layout:
			continue
		layout = json.loads(row.layout)
		if _merge_pilot_icon_in_layout(layout, canonical):
			frappe.db.set_value(
				"Desktop Layout",
				row.name,
				"layout",
				json.dumps(layout),
				update_modified=False,
			)


def _merge_pilot_icon_in_layout(obj: Any, canonical: dict) -> bool:
	changed = False
	if isinstance(obj, list):
		for i, item in enumerate(obj):
			if isinstance(item, dict) and item.get("label") == DESKTOP_ICON_NAME:
				obj[i] = {**item, **{k: v for k, v in canonical.items() if v is not None}}
				changed = True
			elif _merge_pilot_icon_in_layout(item, canonical):
				changed = True
	elif isinstance(obj, dict):
		for key in ("child_icons",):
			if obj.get(key) and _merge_pilot_icon_in_layout(obj[key], canonical):
				changed = True
	return changed


def _layout_entry_matches_pilot(entry: dict) -> bool:
	if not isinstance(entry, dict):
		return False
	if entry.get("label") in PILOT_LAYOUT_LABELS:
		return True
	if entry.get("app") == APP_NAME:
		return True
	if entry.get("parent_icon") == DESKTOP_ICON_NAME:
		return True
	if entry.get("link_to") == WORKSPACE_NAME and entry.get("icon_type") == "Link":
		return True
	return False


def _purge_pilot_from_desktop_layouts():
	for row in frappe.get_all("Desktop Layout", fields=["name", "layout"]):
		if not row.layout:
			continue
		try:
			layout = json.loads(row.layout)
		except json.JSONDecodeError:
			frappe.log_error(title="Pilot Uninstall Layout Parse", message=row.name)
			continue
		if not isinstance(layout, list):
			continue
		new_layout = _filter_pilot_from_layout_list(layout)
		if new_layout != layout:
			frappe.db.set_value(
				"Desktop Layout",
				row.name,
				"layout",
				json.dumps(new_layout),
				update_modified=False,
			)


def _filter_pilot_from_layout_list(layout: list) -> list:
	result = []
	for item in layout:
		if not isinstance(item, dict):
			result.append(item)
			continue
		if _layout_entry_matches_pilot(item):
			continue
		if item.get("child_icons"):
			item = {**item, "child_icons": _filter_pilot_from_layout_list(item["child_icons"])}
		result.append(item)
	return result


def _delete_pilot_desktop_icons():
	names = set(
		frappe.get_all(
			"Desktop Icon",
			or_filters=[
				["name", "=", DESKTOP_ICON_NAME],
				["label", "=", DESKTOP_ICON_NAME],
				["app", "=", APP_NAME],
				["parent_icon", "=", DESKTOP_ICON_NAME],
			],
			pluck="name",
		)
	)
	link_icons = frappe.get_all(
		"Desktop Icon",
		filters={"link_to": WORKSPACE_NAME, "icon_type": "Link"},
		pluck="name",
	)
	names.update(link_icons)

	for name in names:
		if frappe.db.exists("Desktop Icon", name):
			frappe.delete_doc("Desktop Icon", name, force=True, ignore_permissions=True)


def _delete_pilot_sidebars():
	for title in (SIDEBAR_TITLE, LEGACY_SIDEBAR_TITLE, DESKTOP_ICON_NAME):
		if frappe.db.exists("Workspace Sidebar", title):
			frappe.delete_doc("Workspace Sidebar", title, force=True, ignore_permissions=True)


def _delete_pilot_hero_block():
	if frappe.db.exists("Custom HTML Block", HERO_BLOCK_NAME):
		frappe.delete_doc("Custom HTML Block", HERO_BLOCK_NAME, force=True, ignore_permissions=True)


def _scrub_my_workspaces_pins():
	for sidebar in frappe.get_all("Workspace Sidebar", filters={"title": ["like", "My Workspaces%"]}, pluck="name"):
		if not frappe.db.exists("Workspace Sidebar", sidebar):
			continue
		doc = frappe.get_doc("Workspace Sidebar", sidebar)
		original_len = len(doc.items or [])
		doc.items = [
			item
			for item in (doc.items or [])
			if not (
				(item.link_type == "Workspace" and item.link_to == WORKSPACE_NAME)
				or item.label in PILOT_LAYOUT_LABELS
			)
		]
		if len(doc.items) != original_len:
			doc.save(ignore_permissions=True)


def _clear_desk_caches():
	from frappe.desk.doctype.desktop_icon.desktop_icon import clear_desktop_icons_cache

	clear_desktop_icons_cache()
	frappe.clear_cache()
