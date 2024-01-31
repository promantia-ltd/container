import frappe
from frappe import _
from frappe.utils import (
	flt,cstr
)
import json

class OverProductionError(frappe.ValidationError):
	pass


class CapacityError(frappe.ValidationError):
	pass


class StockOverProductionError(frappe.ValidationError):
	pass


class OperationTooLongError(frappe.ValidationError):
	pass


class ItemHasVariantError(frappe.ValidationError):
	pass


class SerialNoQtyError(frappe.ValidationError):
	pass

from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder
from container.container.doctype.stock_entry.stock_entry import reserve_once

precision = frappe.get_cached_value('Container Settings', None, 'container_precision')
if not precision:
    precision = 4
else:
     precision = int(precision)   

@frappe.whitelist()
def reserve_qty(item, warehouse, item_qty, work_order, container_reserved_used):
    container_no_set = []
    comment = ""
    reserve_qty_str=""
    qty = float(item_qty)
    container_reserved_used = json.loads(container_reserved_used)
    used_s = [] 
    has_partially_reserved = frappe.get_cached_value('Container Settings', None, 'has_partially_reserved')


    if container_reserved_used:
        used_s = used_containers(container_reserved_used)

    item_doc = frappe.get_doc("Item", item)

    if item_doc.is_containerized == 1:
        query = frappe.db.sql("""
            SELECT name, primary_available_qty
            FROM `tabContainer`
            WHERE item_code = %s AND warehouse = %s AND status = "Active" 
            AND primary_available_qty > 0 ORDER BY creation
        """, (item, warehouse), as_dict=True)

        reserved = False
        reserved_containers = reserve_once(item_doc, work_order)

        if query:
            required_qty = flt(qty, precision)

            for data in query:
                if data.name not in used_s and data.name not in reserved_containers:
                    if data.primary_available_qty < required_qty:
                        container_no_set.append(data.name)
                        required_qty = required_qty - flt(data.primary_available_qty, precision)
                    elif data.primary_available_qty >= required_qty:
                        container_no_set.append(data.name)
                        break

            required_qty = flt(qty, precision)

            for container in container_no_set:
                sp_doc = frappe.get_doc("Container", container)
                stock_detail_doc_name = frappe.db.get_value('Stock Details', {'parent': sp_doc.name, 'work_order': work_order}, 'name')

                if sp_doc.primary_available_qty < required_qty:
                    #if less qty there in container that required it will reserve other wise it will move to else
                    required_qty = required_qty - flt(sp_doc.primary_available_qty, precision)

                    if has_partially_reserved:
                        #partially reserve the qty that will update in reserved_qty field
                        if stock_detail_doc_name:
                            stock_detail_doc = frappe.get_doc("Stock Details", stock_detail_doc_name)
                            reserved_qty = stock_detail_doc.reserved_qty + flt(sp_doc.primary_available_qty,precision)
                            stock_detail_doc.db_set('reserved_qty',reserved_qty)
                        else:
                            sp_doc.append('stock_details', {
                                'work_order': work_order,
                                'warehouse': warehouse,
                                'reserved_qty':sp_doc.primary_available_qty,
                                'consumed_qty': 0
                            })
                            
                        #available_qty fully reserved so remaining_qty is set to 0
                        remaining_qty = 0
                        if remaining_qty < 0:
                            remaining_qty = 0

                        reserve_qty_str = "  Reserved Qty : " + cstr(flt(sp_doc.primary_available_qty, precision))
                        sp_doc.db_set('primary_available_qty', remaining_qty)
                        sp_doc.save(ignore_permissions=True)

                    else:
                        if stock_detail_doc_name:
                            stock_detail_doc = frappe.get_doc("Stock Details", stock_detail_doc_name)
                            stock_detail_doc.db_set("is_reserved", 1)
                        else:
                            sp_doc.append('stock_details', {
                                'work_order': work_order,
                                'warehouse': warehouse,
                                'is_reserved': 1,
                                'consumed_qty': 0
                            })
                            
                            sp_doc.save(ignore_permissions=True)

                    comment = comment + warehouse + " : <a href='/app/container/" + container + "'>" + container + "</a>" + cstr(reserve_qty_str) + "<br>" 
                    frappe.db.commit()

                elif sp_doc.primary_available_qty >= required_qty:
                    if has_partially_reserved:
                        if stock_detail_doc_name:
                            stock_detail_doc = frappe.get_doc("Stock Details", stock_detail_doc_name)
                            reserved_qty = flt(stock_detail_doc.reserved_qty + required_qty, precision)
                            stock_detail_doc.db_set('reserved_qty',reserved_qty)
                        else:
                            sp_doc.append('stock_details', {
                                'work_order': work_order,
                                'warehouse': warehouse,
                                'reserved_qty':required_qty,
                                'consumed_qty': 0
                            })

                        reserve_qty_str = "  Reserved Qty : " + cstr(flt(required_qty, precision))
                        remaining_qty = flt(flt(sp_doc.primary_available_qty, precision) - required_qty, precision)
                        if remaining_qty < 0:
                            remaining_qty = 0
                        sp_doc.db_set('primary_available_qty', remaining_qty)
                        sp_doc.save(ignore_permissions=True)

                    else:
                        if stock_detail_doc_name:
                            stock_detail_doc = frappe.get_doc("Stock Details", stock_detail_doc_name)
                            stock_detail_doc.db_set("is_reserved", 1)
                        else:
                            sp_doc.append('stock_details', {
                                'work_order': work_order,
                                'warehouse': warehouse,
                                'reserved_qty': 1,
                                'consumed_qty': 0
                            })
                            sp_doc.save(ignore_permissions=True)

                    comment = comment + warehouse + " : <a href='/app/container/" + container + "'>" + container + "</a>" + cstr(reserve_qty_str) + "<br>" 
                    frappe.db.commit()
                    reserved = True
                    return comment, reserved, container_no_set

        else:
            return reserved

    else:
        # Handle the case where the item is not containerized
        return None

		
@frappe.whitelist()
def add_comment(doctype,docname,comment):
	wo_doc = frappe.get_doc(doctype,docname)
	wo_doc.add_comment('Comment',comment)

@frappe.whitelist()
def check_stock(item, warehouse, item_qty, container_used, work_order):
	qty = float(item_qty)
	container_used = json.loads(container_used)
	used = []

	if container_used:
		used = used_containers(container_used)

	item_doc = frappe.get_doc("Item", item)

	if item_doc.is_containerized == 1:
		query = frappe.db.sql("""
			SELECT name, primary_available_qty
			FROM `tabContainer`
			WHERE item_code = %s AND warehouse = %s AND status NOT IN ("Inactive", "Expired")
			AND primary_available_qty > 0 ORDER BY primary_available_qty ASC, creation
		""", (item, warehouse), as_dict=True)

		reserved_containers = reserve_once(item_doc, work_order)
		container_no = []
		if query:
			check_qty = 0

			for value in query:
				if value.name not in used and value.name:
					if value.primary_available_qty <= qty:
						check_qty += value.primary_available_qty
						if check_qty < qty:
							container_no.append(value.name)
						else:
							return True, container_no
					else:
						container_no.append(value.name)
						return True, container_no

			if check_qty >= qty:
				return True, container_no
			else:
				return False, container_no
		else:
			return False, container_no
	else:
		# Handle the case where the item is not containerized
		return False, []

		
def used_containers(container_used):
	used = []
	for val in container_used:
		for each in val:
			used.append(each)
	return used
	

