# Copyright (c) 2026, Aditya Boi and Contributors

from frappe.tests import UnitTestCase

from frappe_pilot.utils.insight_fields import resolve_list_fields


class TestInsightFields(UnitTestCase):
	def test_name_always_included(self):
		fields = resolve_list_fields("User", user_message="show email addresses")
		self.assertEqual(fields[0], "name")
		self.assertIn("name", fields)

	def test_doctype_meta_hint_adds_label_match(self):
		meta = {
			"fields": [
				{"fieldname": "email", "label": "Email Address"},
			]
		}
		fields = resolve_list_fields(
			"User",
			user_message="list email address for users",
			doctype_meta=meta,
		)
		self.assertEqual(fields[0], "name")
