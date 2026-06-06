import frappe

from frappe_pilot.install import ensure_arabic_language


def execute():
	ensure_arabic_language()
