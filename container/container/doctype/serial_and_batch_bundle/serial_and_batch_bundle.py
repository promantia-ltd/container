import frappe
from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import SerialandBatchBundle
from frappe import _, bold


class CustomSerialandBatchBundle(SerialandBatchBundle):
	# TO make sure duplicate batch valiadtion will not happen as we will have
	# the batch updated with each line along with container
	def validate_duplicate_serial_and_batch_no(self):
		# Skip validation if custom_has_container is True
		if self.custom_has_container:
			return

		# Call the parent class's method for validation
		super().validate_duplicate_serial_and_batch_no()

	def validate_serial_and_batch_no(self):

		if self.item_code and not self.has_serial_no and not self.has_batch_no and not self.custom_has_container:
			msg = f"The Item {self.item_code} does not have Serial No or Batch No or Container No"
			frappe.throw(_(msg))

		serial_nos = []
		batch_nos = []

		serial_batches = {}
		for row in self.entries:
			if not row.qty and row.batch_no and not row.serial_no:
				frappe.throw(
					_("At row {0}: Qty is mandatory for the batch {1}").format(
						bold(row.idx), bold(row.batch_no)
					)
				)

			if self.has_serial_no and not row.serial_no:
				frappe.throw(
					_("At row {0}: Serial No is mandatory for Item {1}").format(
						bold(row.idx), bold(self.item_code)
					),
					title=_("Serial No is mandatory"),
				)

			if self.has_batch_no and not row.batch_no:
				frappe.throw(
					_("At row {0}: Batch No is mandatory for Item {1}").format(
						bold(row.idx), bold(self.item_code)
					),
					title=_("Batch No is mandatory"),
				)

			if row.serial_no:
				serial_nos.append(row.serial_no)

			if row.batch_no and not row.serial_no:
				batch_nos.append(row.batch_no)

			if row.serial_no and row.batch_no and self.type_of_transaction == "Outward":
				serial_batches.setdefault(row.serial_no, row.batch_no)

		if serial_nos:
			self.validate_incorrect_serial_nos(serial_nos)

		elif batch_nos:
			self.validate_incorrect_batch_nos(batch_nos)

		if serial_batches:
			self.validate_serial_batch_no(serial_batches)


	def before_insert(self):
		if self.has_batch_no:
			for entry in self.entries:
				if entry.custom_container:
					frappe.db.set_value("Container", entry.custom_container, "batch_no", entry.batch_no)
			frappe.db.commit()