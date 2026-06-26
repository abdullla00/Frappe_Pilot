app_name = "frappe_pilot"
app_title = "Frappe Pilot"
app_publisher = "Aditya Boi"
app_description = "AI Assistant for ERPNext"
app_email = "as0742004@gmail.com"
app_license = "mit"

app_logo_url = "/assets/frappe_pilot/images/frappe-pilot-logo.svg"
app_home = "/desk/pilot"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "frappe_pilot",
# 		"logo": "/assets/frappe_pilot/logo.png",
# 		"title": "Frappe Pilot",
# 		"route": "/frappe_pilot",
# 		"has_permission": "frappe_pilot.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/frappe_pilot/css/frappe_pilot.css"
app_include_js = "/assets/frappe_pilot/js/ai_sidebar.js"

# include js, css files in header of web template
# web_include_css = "/assets/frappe_pilot/css/frappe_pilot.css"
# web_include_js = "/assets/frappe_pilot/js/frappe_pilot.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "frappe_pilot/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {"Pilot Settings": "public/js/pilot_settings.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "frappe_pilot/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "frappe_pilot.utils.jinja_methods",
# 	"filters": "frappe_pilot.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "frappe_pilot.install.before_install"
after_install = "frappe_pilot.install.after_install"
after_migrate = [
	"frappe_pilot.install.after_migrate",
	"frappe_pilot.setup.desk.after_migrate",
]

# Uninstallation
# ------------

before_uninstall = "frappe_pilot.uninstall.before_uninstall"
after_uninstall = "frappe_pilot.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "frappe_pilot.utils.before_app_install"
# after_app_install = "frappe_pilot.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "frappe_pilot.utils.before_app_uninstall"
# after_app_uninstall = "frappe_pilot.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "frappe_pilot.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"frappe_pilot.tasks.all"
# 	],
# 	"daily": [
# 		"frappe_pilot.tasks.daily"
# 	],
# 	"hourly": [
# 		"frappe_pilot.tasks.hourly"
# 	],
# 	"weekly": [
# 		"frappe_pilot.tasks.weekly"
# 	],
# 	"monthly": [
# 		"frappe_pilot.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "frappe_pilot.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "frappe_pilot.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "frappe_pilot.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["frappe_pilot.utils.before_request"]
# after_request = ["frappe_pilot.utils.after_request"]

# Job Events
# ----------
# before_job = ["frappe_pilot.utils.before_job"]
# after_job = ["frappe_pilot.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"frappe_pilot.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

add_to_apps_screen = [
	{
		"name": "frappe_pilot",
		"logo": "/assets/frappe_pilot/images/frappe-pilot-logo.svg",
		"title": "Frappe Pilot",
		"route": "/desk/pilot",
		"has_permission": "frappe_pilot.api.config.has_app_permission",
	}
]

website_route_rules = [
	{"from_route": "/pilot/stream/ping", "to_route": "pilot_stream/ping"},
	{"from_route": "/pilot/stream/<path:agent_name>", "to_route": "pilot_stream"},
	{"from_route": "/pilot/stream", "to_route": "pilot_stream"},
	{"from_route": "/pilot/trigger/webhook/<slug>", "to_route": "pilot_trigger_webhook"},
	{"from_route": "/pilot/<path:app_path>", "to_route": "pilot"},
]

page_renderer = [
	"frappe_pilot.ai.agent_stream_renderer.AgentStreamRenderer",
]

doc_events = {
	"*": {
		"after_insert": "frappe_pilot.ai.agent_hooks.run_hooked_agents",
		"on_update": "frappe_pilot.ai.agent_hooks.run_hooked_agents",
		"on_submit": "frappe_pilot.ai.agent_hooks.run_hooked_agents",
		"on_cancel": "frappe_pilot.ai.agent_hooks.run_hooked_agents",
		"on_trash": "frappe_pilot.ai.agent_hooks.run_hooked_agents",
	},
	"Pilot Agent Trigger": {
		"after_insert": "frappe_pilot.ai.agent_hooks.clear_doc_event_agents_cache",
		"on_update": "frappe_pilot.ai.agent_hooks.clear_doc_event_agents_cache",
		"on_trash": "frappe_pilot.ai.agent_hooks.clear_doc_event_agents_cache",
	},
	"Pilot Knowledge Source": {
		"after_insert": "frappe_pilot.ai.knowledge.hooks.on_knowledge_source_created",
		"on_update": "frappe_pilot.ai.knowledge.hooks.on_knowledge_source_updated",
		"on_trash": "frappe_pilot.ai.knowledge.hooks.on_knowledge_source_deleted",
	},
	"Pilot Knowledge Input": {
		"after_insert": "frappe_pilot.ai.knowledge.hooks.on_knowledge_input_saved",
		"on_update": "frappe_pilot.ai.knowledge.hooks.on_knowledge_input_saved",
		"on_trash": "frappe_pilot.ai.knowledge.hooks.on_knowledge_input_deleted",
	},
}

scheduler_events = {
	"all": [
		"frappe_pilot.ai.agent_scheduler.run_scheduled_agents",
	],
	"daily": [
		"frappe_pilot.ai.knowledge.maintenance.cleanup_orphaned_files",
		"frappe_pilot.ai.knowledge.maintenance.optimize_indexes",
		"frappe_pilot.tasks.insight_digest.run_daily_insight_digest",
	],
	"hourly": [
		"frappe_pilot.ai.mcp_client.auto_sync_mcp_server_tools",
	],
}

after_app_install = [
	"frappe_pilot.ai.app_seeding.seeder.on_app_installed",
]

pilot_tools = []
pilot_insight_modules = []
pilot_insight_tools = []

