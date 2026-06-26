# Copyright (c) 2026, Aditya Boi and Contributors

from frappe.tests import UnitTestCase

from frappe_pilot.utils.insight_link_graph import get_doctype_links


class TestInsightLinkGraph(UnitTestCase):
	def test_sales_invoice_has_customer_link(self):
		links = get_doctype_links("Sales Invoice")
		link_doctypes = {lnk["link_doctype"] for lnk in links if lnk.get("link_type") == "Link"}
		self.assertIn("Customer", link_doctypes)
