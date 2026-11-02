# Copyright (c) 2024, Mohan and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint

class ContainerReconciliation(Document):
	def on_cancel(self):
		"""Restore each existing container's qty to its pre-reconciliation value."""
		# FIXME: containers created from new_container_nos (in Stock Reconciliation on_submit) are not reversed.
		for item in self.items:
			if item.container:
				container = frappe.get_doc("Container", item.container)

				container.primary_available_qty = item.current_qty or 0
				# FIXME: secondary_available_qty is set from the primary-UOM current_qty without conversion.
				container.secondary_available_qty = item.current_qty or 0
				container.save()

@frappe.whitelist()
def get_new_containers(item,count):
	"""Return (next `count` container names from the item's series, {stock_uom, secondary_uom})."""
	doc=frappe.get_doc('Item',item)
	stock_uom = frappe.db.get_value(
			"Item", item, "stock_uom")
	secondary_uom_conversion=frappe.db.get_all("UOM Conversion Detail",filters={'parenttype':'Item','parent':item,'uom_type':"Secondary UOM"},fields={'*'})
	if doc.is_containerized and secondary_uom_conversion!=[]:
		series=doc.container_number_series
		hash_count=series.count('#')
		prefix=series.split(".#")
		serial_no_list=[]
		# Names are only previewed here; tabSeries is advanced in Stock Reconciliation on_submit.
		# FIXME: the series is read without a lock, so concurrent reconciliations can preview the same names.
		Series = frappe.qb.DocType("Series")
		if frappe.db.get_value("Series", str(prefix[0]), "name", order_by="name") is None:
			frappe.qb.into(Series).insert(str(prefix[0]), 0).columns("name", "current").run()
		current=cint(frappe.db.get_value("Series", str(prefix[0]), "current", order_by="name"))+1
		for i in range(0,int(count)):
			number_part=str(i+current).zfill(hash_count)
			next_series=prefix[0]+number_part
			serial_no_list.append(next_series)
		uom_list={'stock_uom':stock_uom,'secondary_uom':secondary_uom_conversion[0]['uom']}
		return serial_no_list,uom_list

@frappe.whitelist()
def get_containers(item,warehouse):
	"""Return (containers with stock in warehouse, UOM conversion info, Bin actual_qty) for the item."""
	stock_uom= frappe.db.get_value(
			"Item", item, "stock_uom")
	secondary_uom_conversion=frappe.db.get_all("UOM Conversion Detail",filters={'parenttype':'Item','parent':item,'uom_type':"Secondary UOM"},fields={'*'})
	bin_qty=frappe.db.get_value(
			"Bin", {'item_code':item,'warehouse':warehouse}, "actual_qty")
	if secondary_uom_conversion!=[]:
		serial_nos = frappe.get_all(
			"Container", fields=["name","primary_available_qty","secondary_available_qty","secondary_uom"], filters={"item_code": item,"primary_available_qty":['>',0],'status':['!=',"Inactive"],'warehouse':warehouse}
		)
		conversions={'stock_uom':stock_uom,'secondary_conversion_factor':secondary_uom_conversion[0]['conversion_factor'],'secondary_uom':secondary_uom_conversion[0]['uom']}
		return serial_nos, conversions,bin_qty
	else:
		frappe.throw('Please mention Secondary UOM at the Item')


@frappe.whitelist()
def create_stock_reconciliation(docname):
	"""Called by the 'Create Stock Reconciliation' button; builds an unsaved doc only, the client opens the new form itself."""
	serialized_reco_doc=frappe.get_doc('Container Reconciliation',docname)
	reco_doc=frappe.get_doc(dict(doctype = 'Stock Reconciliation',
						    company=serialized_reco_doc.company,
						    purpose="Stock Reconciliation"
			))
	
@frappe.whitelist()
def check_reservations(container,warehouse):
	"""Return False if the container has stock reserved (reserved_qty > 0.1) in the warehouse."""
	reserved_stock=frappe.db.get_all("Stock Details",filters={'parenttype':'Container','parent':container,'warehouse':warehouse,'reserved_qty':['>',0.1]},fields={'*'})
	if reserved_stock!=[]:
		return False
	else:
		return True