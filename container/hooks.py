from . import __version__ as app_version
import erpnext.controllers.status_updater as _standard_updator
from container.api import StatusUpdaterCustom as _custom_updator

app_name = "container"
app_title = "Container"
app_publisher = "Mohan"
app_description = "Container For Procurement"
app_email = "mohan.k@promantia.com"
app_license = "mit"


_standard_updator.StatusUpdater.limits_crossed_error = _custom_updator.limits_crossed_error


# required_apps = []

# Includes in <head>
# ------------------

fixtures=[
{
    "dt": "Custom Field",
	"filters":[
        ["module","=", "Container"]
    ]
},
{
    "dt": 'Property Setter',
	"filters": [
        ["module","=", "Container"]
    ]
},
]

# include js, css files in header of desk.html
# app_include_css = "/assets/container/css/container.css"
app_include_js = "/assets/container/js/multi_select_dialog.js"

# include js, css files in header of web template
# web_include_css = "/assets/container/css/container.css"
# web_include_js = "/assets/container/js/container.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "container/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Work Order" : "container/doctype/work_order/work_order.js",
    "Stock Entry":"container/doctype/stock_entry/stock_entry.js",
    "Purchase Receipt":"container/doctype/purchase_receipt/purchase_receipt.js",
    }
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "container/public/icons.svg"

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
# 	"methods": "container.utils.jinja_methods",
# 	"filters": "container.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "container.install.before_install"
# after_install = "container.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "container.uninstall.before_uninstall"
# after_uninstall = "container.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "container.utils.before_app_install"
# after_app_install = "container.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "container.utils.before_app_uninstall"
# after_app_uninstall = "container.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "container.notifications.get_notification_config"

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

doc_events = {
"Stock Entry":{
    "on_submit":[
				"container.api.on_submit",
                "container.container.doctype.stock_entry.stock_entry.set_containers_status",
                "container.container.doctype.stock_entry.stock_entry.after_submit",
                ],
		"validate": ["container.container.doctype.stock_entry.stock_entry.validate"],
		"on_cancel": ["container.container.doctype.stock_entry.stock_entry.on_cancel"],
		"before_submit": [
            "container.container.doctype.stock_entry.stock_entry.before_submit"
            ]
    },
"Purchase Receipt":{
    "on_submit":"container.container.doctype.purchase_receipt.purchase_receipt.on_submit",
    "on_cancel":"container.container.doctype.purchase_receipt.purchase_receipt.on_cancel",
    # "validate": "container.container.doctype.purchase_order.purchase_order.calculate_the_total_standard_rate",
    },
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	# "all": [
	# 	"container.tasks.all"
	# ],
	"daily": [
		"container.api.daily_update_expiry_date"
	],
	# "hourly": [
	# 	"container.tasks.hourly"
	# ],
	# "weekly": [
	# 	"container.tasks.weekly"
	# ],
	# "monthly": [
	# 	"container.tasks.monthly"
	# ],
}

# Testing
# -------

# before_tests = "container.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "container.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "container.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["container.utils.before_request"]
# after_request = ["container.utils.after_request"]

# Job Events
# ----------
# before_job = ["container.utils.before_job"]
# after_job = ["container.utils.after_job"]

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
# 	"container.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

