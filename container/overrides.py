import frappe
from erpnext.stock.serial_batch_bundle import get_serial_nos_batch
from erpnext.stock.doctype.serial_no.serial_no import (
	get_serial_nos
)
from frappe.utils import cint

# hooks.py imports this module and patches SerialBatchCreation.set_serial_batch_entries with the
# function below; the remaining functions are doc_events / before_migrate hooks.

CONFIGURABLE_DECIMAL_TYPES = ("Currency", "Float", "Percent")
DEFAULT_DECIMAL_LENGTH = 21
DEFAULT_DECIMAL_PRECISION = 9

# Configuration: Fields that should use custom precision instead of system precision
# NOTE: currently not consulted; only CUSTOM_PRECISION_PATTERNS below is used.
CUSTOM_PRECISION_FIELDS = {
	# fieldname: precision
	"conversion_factor": 6,  # UOM conversion factors need high precision
	"uom_conversion_factor": 6,
	# Add more fields here as needed:
	# "exchange_rate": 6,
	# "per_unit_price": 4,
}

# Configuration: Field patterns that should use custom precision
# These use pattern matching for fieldnames
CUSTOM_PRECISION_PATTERNS = {
	# pattern: precision
	"conversion_factor": 6,  # Any field ending with conversion_factor (only the key is used, not the value)
	# "_rate": 4,  # Example: Any field ending with _rate
}

# FIXME: frappe.get_single runs at import time, so precision changes need a restart and import needs a DB connection
sys_settings = frappe.get_single("System Settings")
conversion_field_precision = cint(sys_settings.get("conversion_factor_precision", DEFAULT_DECIMAL_PRECISION))
float_field_precision = cint(sys_settings.get("float_precision", DEFAULT_DECIMAL_PRECISION))

def set_serial_batch_entries(self, doc):
	"""Patched SerialBatchCreation.set_serial_batch_entries: build bundle entries per Container when any match."""
	# If containers are found for the voucher, existing entries are replaced by one entry per container;
	# otherwise falls back to the standard serial_nos / batches behaviour.
	# FIXME: reads fields that do not exist (doc.custom_has_container, entries.custom_container,
	# Stock Entry.custom_required_item); `in ("Manufacture")` is a substring test, not tuple membership;
	# `entities` is unbound when self has no batch_no.
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
							entities = frappe.get_all('Container', filters={'name': ['in',entity_names]}, pluck='name')
					elif transaction_type in ("Manufacture") and self.type_of_transaction == 'Inward':
						entities = frappe.get_all('Container', filters={'item_code': self.item_code, 'purchase_document_no': self.voucher_no}, pluck='name')
			# Manufacture consumption: one entry per container listed against the item
			if self.voucher_type=="Stock Entry" and frappe.db.get_value('Stock Entry',self.voucher_no,"stock_entry_type") in ("Manufacture") and self.type_of_transaction == 'Outward':
				stock_entry_doc=frappe.get_doc("Stock Entry",self.voucher_no)
				manufacture_entity_list=[]
				for item in stock_entry_doc.custom_required_item:
					if self.item_code==item.item_code and item.entity_no:
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



def auto_round_floats_globally(doc, method):
	"""
	Automatically round all Float/Currency/Percent fields to appropriate precision.
	
	This is called via doc_events hook on validate for ALL doctypes.
	Ensures all numeric values are rounded before save, with special handling
	for conversion_factor and other custom precision fields.
	
	:param doc: Document being validated
	:param method: Method name (from hook, not used)
	"""
	# Skip certain doctypes that should not be auto-rounded
	skip_doctypes = [
		"System Settings",  # Avoid circular dependency
		"DefaultValue",
		"Singles",
		"Version",
	]
	
	if doc.doctype in skip_doctypes:
		return
	
	# Skip if document doesn't have round_floats_in method
	if not hasattr(doc, 'round_floats_in'):
		return
	
	try:
		# Round numeric fields in parent document
		_round_fields_with_custom_precision(doc)
		
		# Round numeric fields in child tables
		for df in doc.meta.get_table_fields():
			for child in doc.get(df.fieldname) or []:
				_round_fields_with_custom_precision(child)
				
	except Exception as e:
		# Log error but don't break document save
		frappe.logger().error(f"Error auto-rounding floats in {doc.doctype}: {str(e)}")


def _round_fields_with_custom_precision(doc):
	"""
	Round float fields in a document, handling custom precision fields separately.
	
	:param doc: Document or child table row to round
	"""
	from frappe.utils import flt
	
	# Get all numeric fields
	numeric_fields = doc.meta.get("fields", {
		"fieldtype": ["in", ["Currency", "Float", "Percent"]]
	})
	
	if not numeric_fields:
		return
	
	# Get system rounding method for performance
	rounding_method = frappe.get_system_settings("rounding_method")
	
	# Separate fields into custom precision and regular precision
	precision_fieldnames = []
	
	for df in numeric_fields:
		fieldname = df.fieldname
		field_precision=df.precision
		
		# Check if this field is a conversion factor field
		is_custom = False
		
		# Suffix match against CUSTOM_PRECISION_PATTERNS
		for pattern in CUSTOM_PRECISION_PATTERNS:
			if fieldname.endswith(pattern):
				is_custom = True
				break
		
		if is_custom:
			precision_fieldnames.append({"name":fieldname,"precision":field_precision,"conversion_factor":1})
		else:
			precision_fieldnames.append({"name":fieldname,"precision":field_precision,"conversion_factor":0})
	
	# Round precision fields individually with their specific precision
	for field in precision_fieldnames:
		current_value = doc.get(field['name'])
		if current_value is not None:
			fieldname=field['name']
			# Get precision for this specific field
			precision = get_field_precision_for_fieldname(field['precision'],field['conversion_factor'])
			rounded_value = flt(current_value, precision, rounding_method=rounding_method)
			doc.set(fieldname, rounded_value)


def get_field_precision_for_fieldname(precision,conversion_factor):
	"""
	Return the precision to round a field to.

	:param precision: The field's own precision (DocField/Property Setter); wins when set
	:param conversion_factor: 1 for conversion-factor-like fields, else 0
	:return: Precision value
	"""
	if precision and precision!='':
		float_precision=precision
	else:
	
		if conversion_factor==1:
			float_precision = conversion_field_precision
		else:
			float_precision = float_field_precision
	

	return float_precision or cint(frappe.db.get_default("float_precision")) or 3


def add_conversion_factor_precision_field():
    """before_migrate hook: create the System Settings.conversion_factor_precision custom field if missing."""
    if not frappe.db.exists("Custom Field", "System Settings-conversion_factor_precision"):
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "System Settings",
            "fieldname": "conversion_factor_precision",
            "label": "Conversion Factor Precision",
            "fieldtype": "Int",
            "insert_after": "float_precision",
            "default": 3
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        print("Custom Field added successfully.")
    else:
        print("Custom Field already exists.")


def set_conversion_factor_precision():
	"""before_migrate hook: apply conversion_factor_precision to every *conversion_factor* Float DocField."""
	# Step 1: Get precision from System Settings
	precision = frappe.db.get_single_value("System Settings", "conversion_factor_precision")
	if not precision:
		precision=9

	# Step 2: Fetch all float fields with fieldname like 'conversion_factor'
	fields = frappe.db.get_all(
		"DocField",
		filters={
			"fieldtype": "Float",
			"fieldname": ["like", "%conversion_factor%"]
		},
		fields=["name", "fieldname", "parent", "label"]
	)

	if not fields:
		frappe.msgprint("No Float fields found with name like 'conversion_factor'.")
	else:
		frappe.logger().info(f"Found {len(fields)} fields to update.")

		for f in fields:
			# Create or update property setter
			frappe.logger().info(f"Setting precision={precision} for {f.parent}.{f.fieldname}")
			frappe.make_property_setter({
				"doctype": f.parent,
				"fieldname": f.fieldname,
				"property": "precision",
				"value": precision,
				"property_type": "Int",
				"doctype_or_field": "DocField",
			}, validate_fields_for_doctype=False)

		frappe.db.commit()
		frappe.msgprint(f"Property Setters created for {len(fields)} fields with precision = {precision}.")
