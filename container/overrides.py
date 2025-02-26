import frappe
from erpnext.stock.serial_batch_bundle import get_serial_nos_batch
from erpnext.stock.doctype.serial_no.serial_no import (
	get_serial_nos
)

def set_serial_batch_entries(self, doc):
	# Overridden to update batch bundle with multiple entities based on voucher number.
	# If entities are found for the given voucher_no, clear existing entries and set custom_has_entity flag.
	# For each entity, append relevant details like qty, warehouse, and batch_no to entries.
	# If no entities match, proceed with the default behavior of setting entries based on serial_nos or batches.
	try:
		voucher_no = getattr(self, 'voucher_no', None)
		if voucher_no:
			if hasattr(self, "batch_no"):
				if self.type_of_transaction == 'Outward':
					entities = frappe.get_all('Container', filters={'item_code': self.item_code, 'delivery_document_no': self.voucher_no,'batch_no': self.batch_no}, pluck='name')
				else:
					entities = frappe.get_all('Container', filters={'item_code': self.item_code, 'purchase_document_no': self.voucher_no,'batch_no': self.batch_no}, pluck='name')
				if self.voucher_type=="Stock Entry":
					transaction_type=frappe.db.get_value('Stock Entry',self.voucher_no,"stock_entry_type")
					if transaction_type in ("Material Transfer","Material Transfer for Manufacture"):
						entity_se= frappe.get_all('Stock Entry Detail', filters={'name':self.voucher_detail_no }, pluck='containers')
						entity_names=get_serial_nos(entity_se)
						st_details = frappe.get_all('Stock Details', filters={'stock_entry': self.voucher_no},group_by="parent", pluck='parent')
						if len(st_details)>0:
							entity_list = [b for b in st_details if b]
							entities = frappe.get_all('Container', filters={'name': ['in',entity_names]}, pluck='name')
					elif transaction_type in ("Manufacture") and self.type_of_transaction == 'Inward':
						entities = frappe.get_all('Container', filters={'item_code': self.item_code, 'purchase_document_no': self.voucher_no}, pluck='name')
			# if Manufacture entry
			if self.voucher_type=="Stock Entry" and frappe.db.get_value('Stock Entry',self.voucher_no,"stock_entry_type") in ("Manufacture") and self.type_of_transaction == 'Outward':
						stock_entry_doc=frappe.get_doc("Stock Entry",self.voucher_no)
						manufacture_entity_list=[]
						for item in stock_entry_doc.custom_required_item:
							if self.item_code==item.item_code and item.entity_no:
								# item_required_qty=item.consumed_qty
								manufacture_entity_list.append({"entity":item.entity_no,"qty":item.consumed_qty,"batch_no":item.batch_no})
						if len(manufacture_entity_list)>0:
							doc.custom_has_container = 1
							doc.entries.clear()
							for entity_name in manufacture_entity_list:
								container_doc = frappe.get_doc("Container", entity_name['entity'])
								doc.append("entries", {
									"custom_container": entity_name['entity'],
									"qty": entity_name['qty'] * (-1 if self.type_of_transaction == "Outward" else 1),
									"warehouse": container_doc.warehouse,
									"batch_no": container_doc.batch_no
								})
			else:
				if entities:
					doc.custom_has_container = 1
					doc.entries.clear()
					for entity_name in entities:
						container_doc = frappe.get_doc("Container", entity_name)
						doc.append("entries", {
							"custom_container": container_doc.name,
							"qty": container_doc.primary_available_qty * (-1 if self.type_of_transaction == "Outward" else 1),
							"warehouse": container_doc.warehouse,
							"batch_no": self.batch_no
						})
						# if self.type_of_transaction == "Outward" and transaction_type not in ("Material Transfer","Material Transfer for Manufacture"):
						# 	container_doc.db_set('primary_available_qty', 0)
				else:
					if self.get("serial_nos"):
						serial_no_wise_batch = frappe._dict({})
						if self.has_batch_no:
							serial_no_wise_batch = get_serial_nos_batch(self.serial_nos)

						qty = -1 if self.type_of_transaction == "Outward" else 1
						for serial_no in self.serial_nos:
							doc.append(
								"entries",
								{
									"serial_no": serial_no,
									"qty": qty,
									"batch_no": serial_no_wise_batch.get(serial_no) or self.get("batch_no"),
									"incoming_rate": self.get("incoming_rate"),
								},
							)

					elif self.get("batches"):
						for batch_no, batch_qty in self.batches.items():
							doc.append(
								"entries",
								{
									"batch_no": batch_no,
									"qty": batch_qty * (-1 if self.type_of_transaction == "Outward" else 1),
									"incoming_rate": self.get("incoming_rate"),
								},
							)

	except Exception as e:
		frappe.db.rollback()
		frappe.log_error("An error occurred: {}".format(str(e)))
		frappe.throw("An error occurred while creation of Serial and Batch Bundle,please contact the administrator.For more info check the Error Log")