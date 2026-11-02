"""Runtime replacements of ERPNext functions used by the container app.

These used to run only when hooks.py was imported. Frappe serves hooks from the Redis cache when
developer mode is off, so a background job (for example Repost Item Valuation) could run without
them. apply() is called from hooks.py and registered on before_request and before_job, so every
web request and every job has them.
"""


def apply():
	import erpnext.controllers.status_updater as standard_updater
	import erpnext.stock.doctype.purchase_receipt.purchase_receipt as pr_module
	from erpnext.stock.serial_batch_bundle import SerialBatchCreation

	from container import overrides
	from container.api import StatusUpdaterCustom
	from container.container.doctype.purchase_receipt.purchase_receipt import (
		get_item_account_wise_additional_cost,
	)

	# For updating entities to the Serial and Batch Bundle entries.
	# overrides reads System Settings at import, which can load hooks.py and reach here before overrides
	# has finished importing; the before_request / before_job call sets it once the import completes.
	if hasattr(overrides, "set_serial_batch_entries"):
		SerialBatchCreation.set_serial_batch_entries = overrides.set_serial_batch_entries

	# Splits manually distributed LCV charges across tax accounts instead of crediting each in full
	pr_module.get_item_account_wise_additional_cost = get_item_account_wise_additional_cost

	standard_updater.StatusUpdater.limits_crossed_error = StatusUpdaterCustom.limits_crossed_error
