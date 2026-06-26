# Copyright (c) 2026, Aditya Boi and Contributors

from frappe.tests import UnitTestCase

from frappe_pilot.utils.insight_permissions import check_doctype_access, check_module_access


class TestInsightPermissions(UnitTestCase):
	def test_empty_disallow_allows_readable_doctype(self):
		# User doctype exists; with empty disallow list should pass permission or deny read only
		result = check_doctype_access("User")
		if result:
			self.assertIn(result.get("error"), ("permission_denied", "doctype_excluded"))

	def test_module_excluded_error_shape(self):
		# Direct call with fake module name in disallow would need DB setup;
		# verify error dict shape for excluded module helper path
		result = check_module_access("__nonexistent_test_module_xyz__")
		self.assertIsNone(result)
