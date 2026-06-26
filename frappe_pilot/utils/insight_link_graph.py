# DocField link graph for multi-doctype Insight planning (Insights-inspired, no Insights dependency)

from __future__ import annotations

import frappe

from frappe_pilot.utils.insight_permissions import check_doctype_access

_LINK_GRAPH_CACHE_TTL = 86400


def get_doctype_links(doctype: str) -> list[dict]:
	"""Return Link and Table field relationships for a DocType."""
	if not doctype or not frappe.db.exists("DocType", doctype):
		return []

	cache_key = f"pilot_insight_link_graph:{doctype}"
	cached = frappe.cache.get_value(cache_key)
	if cached is not None:
		return cached

	links: list[dict] = []
	seen: set[tuple[str, str, str]] = set()

	for source, parentfield in (("DocField", "parent"), ("Custom Field", "dt")):
		rows = frappe.get_all(
			source,
			filters={
				parentfield: doctype,
				"fieldtype": ("in", ["Link", "Table"]),
			},
			fields=["fieldname", "fieldtype", "options", "label"],
		)
		for row in rows:
			if row.fieldtype == "Link" and row.options:
				key = (doctype, row.fieldname, row.options)
				if key in seen:
					continue
				seen.add(key)
				links.append(
					{
						"doctype": doctype,
						"fieldname": row.fieldname,
						"label": row.label or row.fieldname,
						"link_doctype": row.options,
						"link_type": "Link",
						"join_hint": f"{doctype}.{row.fieldname} → {row.options}.name",
					}
				)
			elif row.fieldtype == "Table" and row.options:
				child = row.options
				key = (doctype, row.fieldname, child)
				if key in seen:
					continue
				seen.add(key)
				links.append(
					{
						"doctype": doctype,
						"fieldname": row.fieldname,
						"label": row.label or row.fieldname,
						"link_doctype": child,
						"link_type": "Table",
						"join_hint": f"{doctype}.name → {child}.parent",
					}
				)

	frappe.cache.set_value(cache_key, links, expires_in_sec=_LINK_GRAPH_CACHE_TTL)
	return links


def get_related_doctypes(
	doctype: str,
	target_doctype: str | None = None,
	*,
	depth: int = 1,
) -> dict:
	if err := check_doctype_access(doctype):
		return err

	links = get_doctype_links(doctype)
	if target_doctype:
		target_l = target_doctype.strip()
		links = [lnk for lnk in links if lnk["link_doctype"] == target_l]

	related: list[dict] = []
	for lnk in links:
		link_dt = lnk["link_doctype"]
		if check_doctype_access(link_dt):
			continue
		entry = dict(lnk)
		if depth > 1 and lnk["link_type"] == "Link":
			entry["children"] = [
				c
				for c in get_doctype_links(link_dt)
				if not check_doctype_access(c["link_doctype"])
			]
		related.append(entry)

	return {"doctype": doctype, "links": related, "count": len(related)}
