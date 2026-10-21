# Copyright (c) 2023, Mohan and contributors
# For license information, please see license.tx
import frappe
from frappe import ValidationError, _
from frappe.utils import (
	getdate,
	nowdate,
)
from frappe.utils import flt

from frappe.model.document import Document

class SerialNoCannotCreateDirectError(ValidationError):
	pass

class SerialNoCannotCannotChangeError(ValidationError):
	pass

class Container(Document):
	def validate(self):
		self.set_maintenance_status()
		self.set_qty()
		self.validate_item()
		self.set_status()
		self.calculate_base_and_room_tempt_in_days()
	def before_save(self):
		self.set_raw_containers_for_fg()

	def before_insert(self):
		self.initial_qty=self.primary_available_qty

	# FIXME: never sets "Delivered"; the list view derives Delivered / Partially Delivered itself
	def set_status(self):
		if not self.warehouse or self.status == "Inactive" :
			self.status = "Inactive"
		if self.expiry_date and getdate(self.expiry_date) <= getdate(nowdate()):
			self.status = "Expired"
		elif self.slitted_container:
			self.status = "Slitted"
		elif self.updated:
			self.status = "Active"

	def set_maintenance_status(self):
		if not self.warranty_expiry_date and not self.amc_expiry_date:
			self.maintenance_status = None

		if self.warranty_expiry_date and getdate(self.warranty_expiry_date) < getdate(nowdate()):
			self.maintenance_status = "Out of Warranty"

		if self.amc_expiry_date and getdate(self.amc_expiry_date) < getdate(nowdate()):
			self.maintenance_status = "Out of AMC"

		if self.amc_expiry_date and getdate(self.amc_expiry_date) >= getdate(nowdate()):
			self.maintenance_status = "Under AMC"

		if self.warranty_expiry_date and getdate(self.warranty_expiry_date) >= getdate(nowdate()):
			self.maintenance_status = "Under Warranty"

	def validate_item(self):
		"""
		Validate whether serial no is required for this item
		"""
		item = frappe.get_cached_doc("Item", self.item_code)
		if item.is_containerized != 1:
			frappe.throw(
				_("Item {0} is not setup for Container. Check Item master").format(self.item_code)
			)

		self.item_group = item.item_group
		self.description = item.description
		self.item_name = item.item_name
		self.brand = item.brand
		self.warranty_period = item.warranty_period
		# FIXME: elif means secondary qty is not clamped when primary qty was also negative
		if self.primary_available_qty<0:
			self.primary_available_qty = 0
		elif self.secondary_available_qty<0:
			self.secondary_available_qty = 0

	def set_qty(self):
		secondary_uom_list=frappe.db.get_all("UOM Conversion Detail",filters={'parenttype':'Item','parent':self.item_code,'uom_type':'Secondary UOM'},fields={'*'})
		if secondary_uom_list:
			secondary_uom_conversion=secondary_uom_list[0]['conversion_factor']
			# Secondary qty is always derived from primary qty; it is never edited independently
			self.secondary_available_qty=self.primary_available_qty/secondary_uom_conversion
			if secondary_uom_list[0]['uom']:
				self.secondary_uom=secondary_uom_list[0]['uom']
			else:
				frappe.throw("Please mention the secondary uom in item master")
		
	def calculate_base_and_room_tempt_in_days(self):
		today=frappe.utils.now() or nowdate()
		if self.base_expiry_date:
			base_expiry_date_in_days = frappe.utils.data.date_diff(self.base_expiry_date, today)
			self.base_expiry_date_in_days=base_expiry_date_in_days
		if self.expiry_date:
			rt_expiry_date_in_days=frappe.utils.data.date_diff(self.expiry_date, today)
			self.rt_expiry_date_in_days=rt_expiry_date_in_days
	
	# NOTE: identical to module-level prevent_delete_if_linked (also wired via doc_events); both run.
	def on_trash(self):
		if self.purchase_document_no and self.purchase_document_type:
			docstatus = frappe.db.get_value(
				self.purchase_document_type, self.purchase_document_no, "docstatus"
			)
			if docstatus == 1:
				frappe.throw(
					_("Container {0} cannot be deleted because it is linked to submitted {1} {2}. "
					  "Cancel the linked document first.").format(
						frappe.bold(self.name),
						self.purchase_document_type,
						frappe.utils.get_link_to_form(
							self.purchase_document_type,
							self.purchase_document_no
						)
					),
					title=_("Deletion Not Allowed")
				)

	def set_raw_containers_for_fg(self):
		"""For containers created by a Stock Entry, record the source containers per item in used_containers."""
		if self.purchase_document_type == "Stock Entry" and not self.used_containers:
			containers = []

			get_containers = get_stock_entry_containers(self)

			# Stock Entry Detail.containers is a comma-separated list, often with a trailing comma
			for container in get_containers:
				if container.get("containers") and container["containers"].endswith(","):
					container["containers"] = container["containers"][:-1]

				if container.get("containers"):
					containers.append({
						container["item_code"]: container["containers"].split(",")
					})

			for cont in containers:
				for key, value in cont.items():
					all_containers=",".join(value)
					self.append("used_containers", {
						'item_code': key,
						'containers': all_containers
					})

def prevent_delete_if_linked(doc, method=None):
	"""Block deletion of any Container linked to a submitted stock transaction."""
	if doc.purchase_document_no and doc.purchase_document_type:
		docstatus = frappe.db.get_value(
			doc.purchase_document_type, doc.purchase_document_no, "docstatus"
		)
		if docstatus == 1:
			frappe.throw(
				_("Container {0} cannot be deleted because it is linked to submitted {1} {2}. "
				  "Cancel the linked document first.").format(
					frappe.bold(doc.name),
					doc.purchase_document_type,
					frappe.utils.get_link_to_form(
						doc.purchase_document_type,
						doc.purchase_document_no
					)
				),
				title=_("Deletion Not Allowed")
			)


def get_stock_entry_containers(self):
	return frappe.db.get_all("Stock Entry Detail",{'parent':self.purchase_document_no},['item_code','t_warehouse','containers'])

def update_all_containers():
    """Background job: recompute actual_container_qty and consumption_status for every Container."""
    frappe.flags.in_test = True  # optional safety bypass

    containers = frappe.get_all("Container", fields=["name", "primary_available_qty", "initial_qty"])
    batch_size = 50

    for i in range(0, len(containers), batch_size):
        batch = containers[i:i+batch_size]
        for container in batch:
            doc = frappe.get_doc("Container", container.name)

            total_reserved_qty = 0.0
            total_consumed_qty = 0.0

            for row in doc.get("stock_details") or []:
                total_reserved_qty += flt(row.reserved_qty)
                total_consumed_qty += flt(row.consumed_qty)

            new_actual_qty = flt(doc.primary_available_qty) + total_reserved_qty

            new_consumption_status = ""
            if total_consumed_qty >= flt(doc.initial_qty):
                new_consumption_status = "Consumed"
            elif total_consumed_qty > 0:
                new_consumption_status = "Partially Consumed"

            updated = False
            if flt(doc.actual_container_qty) != new_actual_qty:
                doc.actual_container_qty = new_actual_qty
                updated = True

            if doc.consumption_status != new_consumption_status:
                doc.consumption_status = new_consumption_status
                updated = True

            if updated:
                doc.save()

        frappe.db.commit()


@frappe.whitelist()
def update_actual_container_qty():
    """Enqueue update_all_containers on the long queue."""
    frappe.enqueue(
        "container.container.doctype.container.container.update_all_containers",
        queue="long",
    	timeout=5000,
    )
