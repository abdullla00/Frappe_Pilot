# Reconcile Pilot LLM Provider child-table columns after schema rename

import frappe


def execute():
	if not frappe.db.table_exists("tabPilot LLM Provider"):
		return

	columns = {row[0] for row in frappe.db.sql("SHOW COLUMNS FROM `tabPilot LLM Provider`")}

	if "provider" in columns and "llm_provider" in columns:
		frappe.db.sql(
			"""
			UPDATE `tabPilot LLM Provider`
			SET llm_provider = provider
			WHERE (llm_provider IS NULL OR llm_provider = '')
			  AND provider IS NOT NULL AND provider != ''
			"""
		)

	if "failover_mode" in columns:
		frappe.db.sql_ddl("ALTER TABLE `tabPilot LLM Provider` DROP COLUMN `failover_mode`")

	frappe.db.commit()
