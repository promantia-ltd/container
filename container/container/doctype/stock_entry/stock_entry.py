import json
from collections import defaultdict
import datetime
import frappe
from frappe import _
from frappe.utils import cint, comma_or, cstr, flt
from erpnext.stock.doctype.serial_no.serial_no import (
	get_serial_nos
)
from container.container.doctype.purchase_receipt.purchase_receipt import get_auto_container_nos

class FinishedGoodError(frappe.ValidationError):
	pass
class ContainersNotAssigned(Exception):
	pass
class LessQtyInContainers(Exception):
	pass

import datetime

work_order_doctype = "Work Order"
material_request_doctype = "Material Request"
container_doctype = "Container"
has_partially_reserved = frappe.get_cached_value('Container Settings', None, 'has_partially_reserved')

precision = frappe.get_cached_value('Container Settings', None, 'container_precision')
if not precision:
    precision = 4
else:
     precision = int(precision)


@frappe.whitelist()
def get_container_no(item, warehouse, t_warehouse, qty, container_used, uom, work_order):
	container_used = json.loads(container_used)
	used = [each for val in container_used for each in val] if container_used else []

	container_no, primary_available_qty, primary_available_qty_used = [], [], []
	qty_check = 0
	remaining_qty = ""
	item_doc = frappe.get_doc("Item", item)

	if item_doc.is_containerized == 1:
		uom_list = frappe.db.get_all("UOM Conversion Detail", filters={'parenttype': 'Item', 'parent': item, 'uom': uom}, fields={'*'})
		stock_qty = flt(qty) / flt(uom_list[0].conversion_factor)
		required_qty = stock_qty
		query = get_containers(item, warehouse)
		
		#check qty with the container primary qty
		get_uom_c_factor = get_conversion_factor(item, uom)

		if not get_uom_c_factor:
			frappe.throw("Conversion factor did not find for the uom " + uom)

		primary_uom_converted_qty = stock_qty * get_uom_c_factor

		qty_check = sum(value.primary_available_qty for value in query)

		if primary_uom_converted_qty > qty_check:
			frappe.throw(f"Stock qty is exceeded for Item {item} in warehouse {warehouse}. Expected: {stock_qty}, available is less than that")

		minimal_expiry_containers = get_minimal_expiry_containers(item, query)
		container_no, primary_available_qty, primary_available_qty_used, remaining_qty = container_pick(query,primary_uom_converted_qty, used,minimal_expiry_containers)

		avilable_qty_in_bom_uom = []

		#conver the available qty to the required uom qty based on bom
		if required_qty != primary_uom_converted_qty:
			for q in primary_available_qty:
				avilable_qty_in_bom_uom.append(q/get_uom_c_factor)
		else:
			avilable_qty_in_bom_uom = primary_available_qty
		
	return container_no, primary_available_qty, remaining_qty, primary_available_qty_used, avilable_qty_in_bom_uom

def get_conversion_factor(item, uom):
	return frappe.db.get_value("UOM Conversion Detail", {'parenttype':'Item','parent':item,'uom':uom}, "conversion_factor")


def get_containers(item, warehouse):
    query = frappe.db.sql("""
        SELECT name, primary_available_qty, expiry_date
        FROM `tabContainer`
        WHERE item_code = %s AND warehouse = %s AND status = "Active" AND primary_available_qty > 0
        ORDER BY creation
    """, (item, warehouse), as_dict=True)
    return query


def get_minimal_expiry_containers(item, query):
    containers_with_minimal_expiry = []
    item_doc = frappe.get_doc("Item", item)
    minimal_days = frappe.db.get_value("Item Group", item_doc.item_group, "min_days")

    for date in query:
        if date.expiry_date:
            days = get_days_diff(date.expiry_date)
            if days < minimal_days:
                containers_with_minimal_expiry.append(date.name)

    return containers_with_minimal_expiry


def get_days_diff(date):
    today = datetime.datetime.today()
    diff = date - today
    return diff.days


def reserve_once(item_doc, work_order):
    reserved_containers = []
    
    if item_doc:
        reserved_containers = frappe.db.sql("""
            SELECT sd.parent
            FROM `tabContainer` c, `tabStock Details` sd
            WHERE c.name = sd.parent AND c.item_code = %s AND c.status NOT IN ("Inactive", "Expired" ,"Used") 
            AND sd.is_reserved = 1 AND sd.work_order NOT IN (%s)
            ORDER BY c.creation
        """, (item_doc.name, work_order), as_list=True)

        if reserved_containers:
            containers = used_containers(reserved_containers)
            return containers

    return reserved_containers

def used_containers(container_used):
    return [each for val in container_used for each in val]

@frappe.whitelist()
def get_item_container_no(item, warehouse, qty, work_order, container_used, uom):
	if isinstance(container_used, str):
		container_used = json.loads(container_used)
		
	used = [each for val in container_used for each in val] if container_used else []

	remaining_qty = ""
	item_doc = frappe.get_doc("Item", item)

	if item_doc.is_containerized == 1:
		uom_list = frappe.db.get_all("UOM Conversion Detail", filters={'parenttype': 'Item', 'parent': item, 'uom': uom}, fields={'*'})
		stock_qty = flt((flt(qty,precision) / flt(uom_list[0].conversion_factor)), precision)

		if stock_qty:
			if has_partially_reserved:
				query = frappe.db.sql("""
					SELECT sd.parent, c.primary_available_qty, sd.reserved_qty
					FROM `tabContainer` c, `tabStock Details` sd
					WHERE c.name = sd.parent AND c.item_code = %s AND sd.warehouse = %s 
					AND c.status NOT IN ("Inactive", "Expired") AND sd.reserved_qty > 0 AND sd.work_order = %s
					ORDER BY c.creation
				""", (item, warehouse, work_order), as_dict=True
				)

			else:
				query = frappe.db.sql("""
					SELECT sd.parent, c.primary_available_qty, sd.is_reserved
					FROM `tabContainer` c, `tabStock Details` sd
					WHERE c.name = sd.parent AND c.item_code = %s AND c.primary_available_qty > 0 AND sd.warehouse = %s 
					AND c.status NOT IN ("Inactive", "Expired") AND sd.is_reserved = 1 AND sd.work_order = %s
					ORDER BY c.creation
				""", (item, warehouse, work_order), as_dict=True
				)
				
			if query:
				container_no, reserved_qty, reserved_qty_used = [], [], []
				required_qty = flt(stock_qty, precision)

				for data in query:
					if data.parent not in used:
						if flt(data.primary_available_qty, precision) < required_qty:
							#here full container qty is used
							container_no.append(data.parent)
							
							if has_partially_reserved:
								#this based on partial qty
								required_qty = required_qty - flt(data.reserved_qty, precision)
								reserved_qty.append(data.reserved_qty)
								reserved_qty_used.append(flt(data.reserved_qty, precision))

							else:
								#here full container is reserved
								required_qty = required_qty - flt(data.primary_available_qty, precision)
								reserved_qty.append(data.primary_available_qty)
								reserved_qty_used.append(flt(data.primary_available_qty, precision))

						elif flt(data.primary_available_qty, precision) >= required_qty:
							container_no.append(data.parent)
							if has_partially_reserved:
								reserved_qty.append(data.reserved_qty)
								reserved_qty_used.append(flt(required_qty, precision))
								remaining_qty = f"{data.parent}:{flt(flt(data.reserved_qty, precision) - required_qty, precision)}"

							else:
								reserved_qty.append(data.primary_available_qty)
								reserved_qty_used.append(flt(required_qty, precision))
								remaining_qty = f"{data.parent}:{flt(data.primary_available_qty - required_qty, precision)}"
					
							break

				return container_no, reserved_qty, remaining_qty, reserved_qty_used

	else:
		return False


def before_submit(doc, method):
    try:
        if doc.stock_entry_type == "Manufacture":
            for item in doc.items:
                item_doc = frappe.get_doc("Item", item.item_code)
                
                if item.is_finished_item != 1:
                    container_no = item.containers

                    if not container_no and item_doc.is_containerized:
                        raise ContainersNotAssigned(f'Please set appropriate containers for item at row {item.idx}')
                    elif item_doc.is_containerized:
                        available_qty = [flt(value, precision) for value in str(item.available_qty).split(',') if value]
                        total_available_qty = sum(available_qty)

                        if flt(item.required_qty, 4) > flt(total_available_qty, 4):
                            raise LessQtyInContainers(f'Assigned containers have less quantity than required quantity at row {item.idx}')

    except (ContainersNotAssigned, LessQtyInContainers) as e:
        frappe.throw(str(e))


from frappe import throw

def set_containers_status(doc, method):
	item_with_stock = []
	comment = "<b>Stock Reserved Successfully</b><br>Assigned Containers:<br>"
	reserve_qty_str = ""


	if doc.stock_entry_type == "Material Transfer for Manufacture" and doc.once_reserved != 1:
		for item in doc.items:
			item_data = [item.item_code, item.t_warehouse]
			item_doc = frappe.get_doc("Item", item.item_code)
			qty_assigned = item.available_qty_use.split(",")

			if item_doc.is_containerized == 1:
				container_nos = get_serial_nos(item.containers)

				for index, sno in enumerate(container_nos):
					container_doc = frappe.get_doc(container_doctype, sno)
					stock_detail_doc = frappe.db.get_value('Stock Details', {'parent': container_doc.name, 'work_order': doc.work_order}, 'name')

					container_doc.db_set('warehouse', item.t_warehouse)
					# container_doc.save(ignore_permissions=True)

					try:
						if stock_detail_doc:
							stock_detail_doc = frappe.get_doc("Stock Details", stock_detail_doc)
							if has_partially_reserved:
								reserved_qty = stock_detail_doc.reserved_qty or 0 + flt(qty_assigned[index], precision)
								stock_detail_doc.db_set('reserved_qty', reserved_qty)
								container_doc.db_set("primary_available_qty", container_doc.primary_available_qty - reserved_qty)
								reserve_qty_str = "  Reserved Qty : " + str(flt(qty_assigned[index], precision))

							else:
								stock_detail_doc.db_set('is_reserved', 1)
						else:
							container_doc.append('stock_details', {
								'work_order': doc.work_order,
								'stock_entry': doc.name,
								'warehouse': item.t_warehouse,
								'consumed_qty': 0
							})

							if has_partially_reserved:
								reserved_qty = flt(qty_assigned[index], precision)
								container_doc.stock_details[-1].reserved_qty = reserved_qty
								container_doc.db_set("primary_available_qty", container_doc.primary_available_qty - reserved_qty)
								reserve_qty_str = "  Reserved Qty : " + str(reserved_qty)

							else:
								container_doc.stock_details[-1].is_reserved = 1

						container_doc.save(ignore_permissions=True)

					except Exception as e:
						frappe.db.rollback()
						frappe.log_error("An error occurred: {}".format(str(e)))
						frappe.throw("An error occurred, While updating containers.For more info check the Error Log")

					comment += f"{item.t_warehouse} : <a href='/app/container/{container_doc.name}'>{container_doc.name}</a>" + str(reserve_qty_str) + "<br>"
					frappe.db.commit()
					item_with_stock.append(item_data)

				doc.once_reserved = 1

		doc.add_comment('Comment', comment)


	if doc.stock_entry_type=="Manufacture" and not doc.system_generated:
		if doc.work_order:
			for item in doc.items:
				try:
					if item.is_finished_item!=1:
						item_doc=frappe.get_doc("Item",item.item_code)
						if item_doc.is_containerized==1:
							secondary_uom_list=frappe.db.get_all("UOM Conversion Detail",filters={'parenttype':'Item','parent':item.item_code,'uom_type':'Secondary UOM'},fields={'*'})
							if secondary_uom_list:
								secondary_uom_conversion=secondary_uom_list[0]['conversion_factor']
							else:
								frappe.throw("Secondary UOM not found,Please specify secondary uom in item master")

							primary_uom_list=frappe.db.get_all("UOM Conversion Detail",filters={'parenttype':'Item','parent':item.item_code,'uom_type':'Primary UOM'},fields={'*'})
							if primary_uom_list:
								primary_uom_conversion=primary_uom_list[0]['conversion_factor']
							else:
								frappe.throw("Primary UOM not found,Please specify primary uom in item master")

							container_no_list=[]
							container_no=item.containers
							if container_no:
								reserved_qty=str(item.available_qty_use).split(",")
								container_no_list=container_no.split(",")
								list_length = len(container_no_list)
								for i in range(list_length):
									if container_no_list[i]!="" and reserved_qty[i]!="":
										stock_qty=flt(reserved_qty[i], precision)*primary_uom_conversion
										secondary_uom_qty=stock_qty*secondary_uom_conversion
										container_doc=frappe.get_doc(container_doctype,container_no_list[i])
										stock_detail_doc=frappe.db.get_value('Stock Details',{'parent':container_doc.name,'work_order': doc.work_order},'name')

										try:
											if stock_detail_doc:
												stock_detail_doc=frappe.get_doc("Stock Details",stock_detail_doc)
												if has_partially_reserved:
													reserved_total = flt(stock_detail_doc.reserved_qty, precision) - flt(reserved_qty[i], precision)
													if reserved_total < 0:
														reserved_total = 0
													consumed_qty = stock_detail_doc.consumed_qty or 0 + flt(stock_detail_doc.reserved_qty, precision)
													stock_detail_doc.db_set('consumed_qty', consumed_qty)
													stock_detail_doc.db_set('reserved_qty',reserved_total)
													container_doc.add_comment('Comment','Used qty: '+str(flt(flt(reserved_qty[i]), precision))+' for transaction with Stock Entry: '+doc.name)
					
												else:
													stock_detail_doc=frappe.get_doc("Stock Details",stock_detail_doc)
													stock_detail_doc.db_set('consumed_qty',stock_detail_doc.consumed_qty  or 0 + flt(reserved_qty[i], precision))
													container_doc.db_set("primary_available_qty",container_doc.primary_available_qty - flt(reserved_qty[i], precision))
													container_doc.db_set('secondary_available_qty',container_doc.secondary_available_qty - secondary_uom_qty)
													container_doc.add_comment('Comment','Used qty: '+str(flt(flt(reserved_qty[i]), precision))+' for transaction with Stock Entry: '+doc.name)

												# stock_detail_doc.save(ignore_permissions=True)
												# container_doc.save(ignore_permissions=True)
												frappe.db.commit()
												a=10
										
										except Exception as e:
											frappe.db.rollback()
											frappe.log_error("An error occurred: {}".format(str(e)))
											frappe.throw("An error occurred, While updating containers.For more info check the Error Log")
							else:
								frappe.throw('Please set appropriate container for item at row '+str(item.idx))

				except Exception as e:
					frappe.db.rollback()
					frappe.log_error("An error occurred: {}".format(str(e)))
					frappe.throw("An error occurred, While updating containers.For more info check the Error Log")


	if doc.stock_entry_type == "Manufacture" and not doc.system_generated and not doc.work_order:
		for item in doc.items:
			if item.is_finished_item != 1:
				container_no_list = item.containers.split("\n") if item.containers else []

				for container_no in container_no_list:
					if container_no:
						container_doc = frappe.get_doc(container_doctype, container_no)
						container_doc.db_set('primary_available_qty', container_doc.primary_available_qty - item.qty)
						container_doc.add_comment('Comment', f"Used qty: {flt(item.qty, 4)} for transaction with Stock Entry: {doc.name}")
						frappe.db.commit()

				if not container_no_list:
					throw('Please set appropriate container for item at row ' + str(item.idx))


def validate(doc,method):
	try:
	#This code is forstanderd rate fetching
	# 	for each in doc.items:
	# 		each.custom_total_standard_rate = each.custom_standard_rate * each.qty
	# 		if each.custom_total_standard_rate:
	# 			each.custom_percentage_difference_to_actual_amount = ((each.basic_rate - each.custom_total_standard_rate)/each.custom_total_standard_rate)*100
		if doc.stock_entry_type=="Material Transfer for Manufacture" or doc.stock_entry_type=="Material Transfer":
			for item in doc.items:
				item_doc=frappe.get_doc("Item",item.item_code)
				if item.is_finished_item!=1 and item_doc.is_containerized==1:
					containers=item.containers
					if not containers:
						raise ContainersNotAssigned('Please set appropriate container for item at row '+str(item.idx))
					elif containers[-1] in [","]:
						#last comma should not consider
						containers=containers[:-1]
					containers=containers.split(",")
					for cont in containers:
						container_doc=frappe.get_doc("Container",cont)
						if container_doc.warehouse !=item.s_warehouse:
							frappe.throw('Source warehouse not matching with selected container warehouse at row '+str(item.idx)+',please check in container :'+"<a href='/app/container/"+cont+"'>"+cont+"</a><br>")

	except ContainersNotAssigned as e:
		frappe.throw(str(e))


from frappe import get_doc, get_list, delete_doc, throw, msgprint

def on_cancel(doc, method):
	comment = ""

	if doc.stock_entry_type == "Material Transfer for Manufacture":
		comment = "Released Containers:<br>"
		for item in doc.items:
			if item.containers:
				item_doc = get_doc("Item", item.item_code)
				qty_assigned = item.available_qty_use.split(",")

				if item_doc.is_containerized == 1:
					container_nos = get_serial_nos(item.containers)

					for index,sno in enumerate(container_nos):
						container_doc = get_doc(container_doctype, sno)
						stock_detail_doc=frappe.db.get_value('Stock Details',{'parent':container_doc.name,'work_order': doc.work_order},'name')
						
						try:
							if stock_detail_doc:
								stock_detail_doc=frappe.get_doc("Stock Details",stock_detail_doc)

								if has_partially_reserved:
									#check if any other workorder is received in this serial no
									other_reserved_stock_details=frappe.db.get_all("Stock Details",filters={'parent':container_doc.name,'reserved_qty':['>',1]},fields={'*'})

									reserved_qty = flt(stock_detail_doc.reserved_qty, precision) - flt(qty_assigned[index], precision)

									if reserved_qty < 0:
										reserved_qty = 0

									 #if still some partial qty is reserved or some workorder is reserved do not allow cancellation as caused stock issue
									if reserved_qty > 1 or len(other_reserved_stock_details) > 1:
										frappe.throw('This container is reserved for some other Work Order. Either unreserve or cancel the other Work Order')
										frappe.db.rollback()

									primary_available_qty = container_doc.primary_available_qty + flt(stock_detail_doc.reserved_qty, precision)
									container_doc.db_set('primary_available_qty', primary_available_qty)
									stock_detail_doc.db_set('reserved_qty',reserved_qty)
									
								else:     
									stock_detail_doc.db_set('is_reserved', 0)

							if not stock_detail_doc.is_reserved  and stock_detail_doc.reserved_qty == 0 and stock_detail_doc.consumed_qty == 0:
								delete_doc("Stock Details", stock_detail_doc.name)
								frappe.db.commit()

							container_doc.db_set('warehouse', item.s_warehouse)
							container_doc.save(ignore_permissions=True)
							frappe.db.commit()
							comment += f"{item.t_warehouse} : {sno}<br>"

						except Exception as e:
							frappe.db.rollback()
							frappe.log_error("An error occurred: {}".format(str(e)))
							frappe.throw("An error occurred, while canceling stock entry .For more info check the Error Log")

		doc.add_comment('Comment', comment)

	if doc.stock_entry_type == "Manufacture":
		for item in doc.items:
			if item.is_finished_item != 1:
				container_no_list = get_serial_nos(item.containers)
				secondary_uom_conversion, primary_uom_conversion = get_uom_conversion(item)

				reserved_qty=item.available_qty_use.split(",")

				for i, container_no in enumerate(container_no_list):
					if container_no and item.available_qty_use[i]:
						stock_qty = flt(item.available_qty_use[i], precision) * primary_uom_conversion
						secondary_uom_qty = stock_qty * secondary_uom_conversion

						container_doc = get_doc(container_doctype, container_no)
						stock_detail_doc=frappe.db.get_value('Stock Details',{'parent':container_doc.name,'work_order': doc.work_order},'name')

						if stock_detail_doc:
							stock_detail_doc = get_doc("Stock Details", stock_detail_doc)
							
							#it will back to reserved state
							if has_partially_reserved:
								stock_detail_doc.db_set('reserved_qty',flt(stock_detail_doc.reserved_qty, precision) + flt(reserved_qty[i], precision))
								consumed_qty = stock_detail_doc.consumed_qty - flt(reserved_qty[i], precision)
								if consumed_qty < 0:
									consumed_qty = 0
								stock_detail_doc.db_set('consumed_qty', consumed_qty)
								container_doc.add_comment('Comment', f"Released qty: {flt(flt(reserved_qty[i]), precision)} for transaction with Stock Entry: {doc.name}")
								frappe.db.commit()
							else:
								#for ntpt manufacturing cancle entry is on hold
								pass

			else:
				fg_containers = get_list("Container",filters={"purchase_document_no": item.parent, "fg_item": 1},fields=['name'])

				if fg_containers:
					cont = ""

					for fg_cont in fg_containers:
						created_container_doc = get_doc(container_doctype, fg_cont.name)
						created_container_doc.db_set("status", "Inactive")
						cont += fg_cont.name + "\n"
						frappe.db.commit()

					comment = f"Set the inactive status for these containers: {cont}"
					msgprint(comment)

		doc.add_comment('Comment', comment)

	if doc.stock_entry_type == "Material Transfer":
		container_nos = []

		for item in doc.items:
			if item.containers:
				container_nos.extend(get_serial_nos(item.containers))

		for container_no in container_nos:
			container_no_doc = get_doc(container_doctype, container_no)
			container_no_doc.db_set('warehouse', item.s_warehouse)
			frappe.db.commit()

def get_uom_conversion(item):
	secondary_uom_list=frappe.db.get_all("UOM Conversion Detail",filters={'parenttype':'Item','parent':item.item_code,'uom_type':'Secondary UOM'},fields={'*'})
	if secondary_uom_list:
		secondary_uom_conversion=secondary_uom_list[0]['conversion_factor']
	else:
		frappe.throw("Secondary UOM not found,Please specify secondary uom in item master")

	primary_uom_list=frappe.db.get_all("UOM Conversion Detail",filters={'parenttype':'Item','parent':item.item_code,'uom_type':'Primary UOM'},fields={'*'})
	if primary_uom_list:
		primary_uom_conversion=primary_uom_list[0]['conversion_factor']
	else:
		frappe.throw("Primary UOM not found,Please specify primary uom in item master")
		
	return secondary_uom_conversion, primary_uom_conversion


@frappe.whitelist()
def get_target_warehouses(operation,work_order,warehouse_list,wip_warehouse,item=None):
	operation_list=frappe.db.get_all("Work Order Operation",filters={'parenttype':'Work Order','parent':work_order,'operation':operation},fields={'workstation'})
	converted=json.loads(warehouse_list)
	input_sources=frappe.db.get_all("Input Sources",filters={'parenttype':'Workstation','parent':operation_list[0]['workstation'],'w_name':['not in',converted]},fields={'w_name'},order_by="idx")
	workstation=frappe.db.get_value("Workstation",operation_list[0]['workstation'],"input_source_enabled")
	item_doc=frappe.get_doc("Item",item)
	if workstation and item_doc.machine_loaded=="Machine Loaded Container":
		if input_sources!=[]:
			individual_warehouse=input_sources[0].w_name
			return individual_warehouse
		else:
			frappe.throw('Unable to assign the Input sources as no sources mentioned at the workstation selected in the Work Order')
			return False
	return wip_warehouse

def after_submit(doc,method):
	if doc.stock_entry_type=="Material Receipt":
		container_no_list=frappe.db.get_list(container_doctype,filters={'purchase_document_type':doc.doctype,'purchase_document_no': doc.name},fields={'*'})
		for no in container_no_list:
			container_no_doc=frappe.get_doc(container_doctype,no.name)
			item_doc=frappe.get_doc("Item",no.item_code)
			uom_list=frappe.db.get_list("UOM Conversion Detail",filters={'uom': ['!=',item_doc.stock_uom],'parent': item_doc.item_code},fields={'*'})
			if uom_list!=[]:
				container_no_doc.db_set('primary_available_qty', 1/uom_list[0].conversion_factor)
				container_no_doc.db_set('secondary_uom', uom_list[0].uom)
			container_no_doc.db_set('warehouse',container_no_doc.warehouse)
			frappe.db.commit()
	elif doc.stock_entry_type=="Material Transfer":
		for item in doc.items:
			container_nos = get_serial_nos(item.containers)
			for container_no in container_nos:
				container_no_doc=frappe.get_doc(container_doctype,container_no)
				container_no_doc.db_set('warehouse',item.t_warehouse)
			frappe.db.commit()
	#update the sle for all the stock entrys
	update_sle(doc)

@frappe.whitelist()
def change_containers(selected_containers,item):
	selected_containers=json.loads(selected_containers)
	item=json.loads(item)
	qty_check=0
	for value in selected_containers:
		container_no_doc=frappe.get_doc(container_doctype,value)
		if qty_check<flt(item['required_qty'], precision):
			qty_check+=container_no_doc.primary_available_qty
		else:
			if flt(item['required_qty'], precision)==0:
				frappe.throw("Please mention the required qty.")
			else:
				frappe.throw("Selected containers qty excceding the required qty.")
	if qty_check<item['required_qty']:
		frappe.throw("Selected containers available qty less than required qty.")
	get_data=get_container_data(selected_containers,item['required_qty'])
	transferred_qty=sum([i for i in get_data[2]])
	if get_data:
		stock_entry_detail=frappe.db.get_list("Stock Entry Detail",parent_doctype="Stock Entry")
		if item['name'] in [stock_entry_detail[i]['name'] for i in range(len(stock_entry_detail))]:   #Draft and Notsaved doc also we can change the Containers
			frappe.db.set_value("Stock Entry Detail",item['name'],"containers",get_data[0][0])
			frappe.db.set_value("Stock Entry Detail",item['name'],"available_qty",get_data[0][1])
			frappe.db.set_value("Stock Entry Detail",item['name'],"available_qty_use",get_data[0][2])
			frappe.db.set_value("Stock Entry Detail",item['name'],"remaining_qty",get_data[1])
			frappe.db.set_value("Stock Entry Detail",item['name'],"qty",transferred_qty)
			#currently this is not needed my be in future it is usefull
			# update_container_table(get_data,item)
		else:
			get_data=list(get_data)
			get_data.append(transferred_qty)
			return get_data
@frappe.whitelist()        
def get_container_data(selected_containers,qty):
	primary_available_qty=[]
	primary_available_qty_used=[]
	containers=[]
	required_qty=qty
	for container in selected_containers:
		container_doc=frappe.get_doc(container_doctype,container)
		if container_doc.primary_available_qty < required_qty:
			primary_available_qty.append(container_doc.primary_available_qty)
			primary_available_qty_used.append(container_doc.primary_available_qty)
			required_qty-=container_doc.primary_available_qty
			containers.append(container)
		else:
			primary_available_qty.append(container_doc.primary_available_qty)
			primary_available_qty_used.append(flt(required_qty,2))
			remaining_qty=str(container)+":"+str(flt(container_doc.primary_available_qty-required_qty,2))
			containers.append(container)
			break
	convert_data=convert_container_data_to_str(primary_available_qty,primary_available_qty_used,containers)
	return convert_data,remaining_qty,primary_available_qty

def convert_container_data_to_str(primary_available_qty,primary_available_qty_used,containers):
	container_list,available_qty,available_qty_used="","",""
	for container in range(len(containers)):
		if containers[-1]!=containers[container]:
			container_list+=containers[container]+","
			available_qty+=str(primary_available_qty[container])+","
			available_qty_used+=str(primary_available_qty_used[container])+","
		else:
			container_list+=containers[container]
			available_qty+=str(primary_available_qty[container])
			available_qty_used+=str(primary_available_qty_used[container])
	return container_list,available_qty,available_qty_used

# this Code is commented it may be useful in future
# def update_container_table(get_data,item):
#     containers_doc=frappe.get_doc("Container Info",{"parent":item['parent'],"input_sources":item["s_warehouse"],"item_code":item["item_code"]})
#     containers_doc.db_set("containers",get_data[0][0])
#     containers_doc.db_set("input_sources",item['t_warehouse'])
#     frappe.db.commit()

@frappe.whitelist()  
def assign_containers(item,used,work_order=None):
	container_no,primary_available_qty,primary_available_qty_used=[],[],[]
	remaining_qty=""
	query=None
	item=json.loads(item)
	item_doc=frappe.get_doc("Item",item["item_code"])
	if item_doc.is_containerized and item_doc.container_number_series:
		# reserved_containers=reserve_once(item_doc,work_order)
		if "s_warehouse" in item.keys():
			query=get_containers(item["item_code"],item["s_warehouse"])
		required_qty=item['qty']
		minimal_expiry_containers=get_minimal_expiry_containers(item["item_code"],query)
		if query:
			container_no,primary_available_qty,primary_available_qty_used,remaining_qty=container_pick(query,required_qty,used,minimal_expiry_containers)
			transferred_qty=sum([i for i in primary_available_qty]) 
			return container_no,primary_available_qty,remaining_qty,primary_available_qty_used,transferred_qty
		else:
			frappe.msgprint("Not enough containers to assign,Please make sure containers are available for all the items")

@frappe.whitelist()  
def slit_container_and_unreserve_container(self):
	if not has_partially_reserved:
		self=json.loads(self)
		if self["stock_entry_type"]=="Manufacture" and self['system_generated'] !=1:
			wo_doc=frappe.get_doc("Work Order",self["work_order"])
			bom_doc=frappe.get_doc("BOM",self["bom_no"])
			if wo_doc.produced_qty>=wo_doc.qty:
				for item in bom_doc.get("items"):
					query= frappe.db.sql("""
							select sd.parent,sd.name
							from `tabContainer` c,`tabStock Details` sd
							where c.name=sd.parent and c.item_code = %s and c.status not in ("Inactive","Expired") and sd.is_reserved=1 and sd.work_order=%s order by c.creation
						""", (item.item_code,wo_doc.name),as_dict=True)
					if query:
						for container in query:
							#unreserve the containers 
							frappe.db.set_value("Stock Details",container.name,"is_reserved",0)
			# slit the raw material containers
			slit_container(self)
		
@frappe.whitelist()
def change_container_qty(data,item_name):
	data=json.loads(data)
	available_qty_use=""
	changed_qty=0
	remaining_qty=""
	rem_qty=0
	for qty in data['container_qty_change']:
		if flt(qty['available_qty'], precision) < flt(qty['qty'], precision):
			frappe.throw("Entered Qty was exceeding the available qty in container:"+qty['container_no'])
		available_qty_use+=str(flt(qty['qty'], precision))+","
		changed_qty+=(flt(qty['qty'], precision))
		rem_qty=flt(qty['available_qty'], precision)-flt(qty['qty'], precision)
		remaining_qty+=qty["container_no"]+":"+str(rem_qty)+","
	if available_qty_use:
		stock_entry_detail=frappe.db.get_list("Stock Entry Detail",parent_doctype="Stock Entry")
		if item_name in [stock_entry_detail[i]['name'] for i in range(len(stock_entry_detail))]:   #Draft and Notsaved doc also we can change the containers
			frappe.db.set_value("Stock Entry Detail",item_name,"available_qty_use",available_qty_use)
			frappe.db.set_value("Stock Entry Detail",item_name,"qty",changed_qty)
			frappe.db.set_value("Stock Entry Detail",item_name,"remaining_qty",remaining_qty)
		else:
			return available_qty_use,changed_qty,remaining_qty

def container_pick(query,required_qty,used,minimal_expiry_containers):
	container_no,primary_available_qty,primary_available_qty_used = [],[],[]
	remaining_qty =" "
	
	for data in query:
		if data.name not in used and data.name not in minimal_expiry_containers:
			available_qty = flt(data.primary_available_qty,4)
			if  available_qty < required_qty:
				container_no.append(data.name)
				primary_available_qty.append(available_qty)
				required_qty = flt(required_qty - available_qty,4)
				primary_available_qty_used.append(flt(available_qty,4))
			elif available_qty >= required_qty:
				container_no.append(data.name)
				remaining_qty=str(data.name) + ":" + str(flt(available_qty-required_qty,4))
				primary_available_qty.append(available_qty)
				primary_available_qty_used.append(flt(required_qty,4))
				required_qty = 0
				break     
	return container_no,primary_available_qty,primary_available_qty_used,remaining_qty

@frappe.whitelist()
def slit_container(self):
	try:
		for item in self['items']:
			item_doc=frappe.get_doc("Item",item['item_code'])
			if item_doc.is_containerized  and item['is_finished_item'] !=1 and self['system_generated'] !=1:
				qty_rem_containers=get_remaining_qty_left_in_container(item)
				all_containers=item['containers']
				if all_containers[-1] in [","]:
				#last comma should not consider
					all_containers=all_containers[:-1]
				all_containers=all_containers.split(",")
				for cont in all_containers:
					"""all the containers are completely utilized
					change the status as used """
					if cont in qty_rem_containers and qty_rem_containers[cont]>0:
						container_doc=frappe.get_doc("Container",cont)
						if are_floats_equal(qty_rem_containers[cont], container_doc.primary_available_qty) and container_doc.primary_available_qty>0:
							# create a sub conatiner,copy the data from parent container
							comment,slitted_container=create_sub_containers(self,cont)
							if comment and slitted_container:
								container_doc.append("slitted_details",{
										'item_code':item['item_code'],
										'container':slitted_container,
										'qty_each':container_doc.primary_available_qty,
									})
								container_doc.db_set("slitted_container",1)
								container_doc.db_set("primary_available_qty",0)
								container_doc.db_set("secondary_available_qty",0)
								container_doc.save(ignore_permissions=True)
								frappe.db.commit()
					else:
						used_container_doc=frappe.get_doc("Container",cont)
						if used_container_doc.primary_available_qty==0:
							used_container_doc.db_set("status","Used")
							frappe.db.commit()
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error("An error occurred while slitting of container: {}".format(str(e)))

def get_remaining_qty_left_in_container(item):
	rem_container={}
	containers=item["remaining_qty"]
	if containers:
		if containers[-1] in [","]:
			#last comma should not consider
			containers=containers[:-1]
		if "," in containers: 
			parts=containers.split(",")
		else:
			parts=[containers]
		for pair in parts:
			key, value = pair.split(':')
			rem_container[key]=flt(value, precision)
	return rem_container

def create_sub_containers(self,parent_container):
	comment=""
	slitted_container=''
	parent_container_doc=frappe.get_doc("Container",parent_container)
	item_doc=frappe.get_doc("Item",parent_container_doc.item_code)
	secondary_uom_cf=frappe.db.get_value("UOM Conversion Detail",{"parent":item_doc.item_code,"uom_type":"Secondary UOM"},"conversion_factor")
	#we should concat the same sting here as well mentioned in slit_container doc
	#for sync of conatiners
	container_series=parent_container+"-.###"
	#only create one container 
	#copy from the parent
	container_nos = get_auto_container_nos(container_series,1)
	container_list=container_nos.split("\n")
	try:
		#we are shifting parent container data to sub or slitted container
		#so,will slit in to one sub container 
		for container in range(1):
			container_doc =frappe.get_doc(dict(doctype = "Container",
				container_no=container_list[container],
				item_code=item_doc.item_code,
				warehouse=parent_container_doc.warehouse,
				temperature=parent_container_doc.temperature,
				item_name=item_doc.item_name,
				item_group=item_doc.item_group,
				description=item_doc.description,
				purchase_document_type=self['doctype'],
				purchase_document_no=self['name'],
				primary_uom=parent_container_doc.primary_uom,
				secondary_uom=parent_container_doc.secondary_uom,
				status="Active",
				container_details=parent_container_doc.container_details,
				base_expiry_date=parent_container_doc.base_expiry_date,
				expiry_date=parent_container_doc.expiry_date,
				uom=item_doc.stock_uom,
				fg_item=parent_container_doc.fg_item,
				primary_available_qty=flt(parent_container_doc.primary_available_qty, precision),
				secondary_available_qty=flt(parent_container_doc.primary_available_qty, precision)/secondary_uom_cf,
				sub_container=1,
				parent_ref=parent_container
				))
			#copy the parent aging history of latest record
			container_doc=copy_aging_history(self,parent_container_doc,container_doc)
			slitted_container+=container_list[container]
			comment=comment+"<a href='/app/container/"+container_list[container]+"'>"+container_list[container]+"</a><br>"
			container_doc.save(ignore_permissions=True)
			frappe.db.commit()
		return comment,slitted_container
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error("An error occurred: {}".format(str(e)))
		frappe.throw("An error occurred while slitting the  container,please contact the administrator.For more info check the Error Log")


def copy_aging_history(self,parent_container_doc,container_doc):
	prev_trans_details=None
	prev_trans_name=frappe.get_all('Aging History', filters={'parent': parent_container_doc.name}, order_by='idx DESC', limit=1)
	if prev_trans_name:
		prev_trans_details=frappe.get_doc("Aging History",prev_trans_name)
	if prev_trans_details:
		#copy the latest aging history
		container_doc.append("aging_history",{
			"datetime":prev_trans_details.datetime,
			"warehouse":prev_trans_details.warehouse,
			"warehouse_temperature":prev_trans_details.warehouse_temperature,
			"aging_rate":prev_trans_details.aging_rate,
			"base_expiry_date":prev_trans_details.base_expiry_date,
			"rt_expiry_date":prev_trans_details.rt_expiry_date,
			"creation_document_type":self['doctype'],
			"stock_txn_reference":self['name'],
			"shelf_life_in_days":prev_trans_details.shelf_life_in_days,
			"description":"Slitted from "+self['doctype']+" ref No:"+self['name']
			})
	else:
		return container_doc
	return container_doc

def update_sle(self):
	try:
		for item in self.items:
			item_doc=frappe.get_doc("Item",item.item_code)
			if item_doc.is_containerized and item_doc.container_number_series:
				if self.system_generated:
					update_sle_for_raw(item)
				if not self.system_generated and not item.is_finished_item:
					update_sle_for_raw(item)
				elif not self.system_generated:
					#the container created for fg item not updated in row so
					#filter container from container doc update it in sle
					fg_containers=frappe.db.get_list("Container",filters={"purchase_document_no":item.parent,"fg_item":1},fields=['name'])
					all_containers = [str(d['name']) for d in fg_containers]
					str_containers=",".join(all_containers)
					sle=frappe.get_doc("Stock Ledger Entry",{"voucher_no":item.parent,"item_code":item.item_code,"voucher_detail_no":item.name})
					sle.db_set("containers",str_containers)
					frappe.db.commit()
	except KeyError:
		pass

def update_sle_for_raw(item):
	containers=None
	sle=frappe.get_doc("Stock Ledger Entry",{"voucher_no":item.parent,"item_code":item.item_code,"voucher_detail_no":item.name})
	if item.containers and item.containers[-1]==",":
		containers=item.containers[:-1]
	elif item.containers:
		containers=item.containers
	sle.db_set("containers",containers)
	frappe.db.commit()

@frappe.whitelist()
def fetch_stock_transfer_records(workstation,transfer_type,return_warehouse=None,item_code=None,return_container=None):
    warehouse_stock=[]
    warehouse_list=frappe.db.get_all("Input Sources",filters={'parenttype':'Workstation','parent':workstation},fields={'w_name'})
    for warehouse in warehouse_list:
        stock_list=frappe.db.get_all("Bin",filters={'warehouse':warehouse['w_name']},fields={'actual_qty','item_code'})
        for stock in stock_list:
            is_containerized=frappe.db.get_value('Item',{'item_code':stock['item_code']},'is_containerized')
            if stock['actual_qty']>0 and is_containerized==1:
                primary_uom_conversion=frappe.db.get_all("UOM Conversion Detail",filters={'parenttype':'Item','parent':stock['item_code'],'uom_type':"Primary UOM"},fields={'*'})
                primary_qty=stock['actual_qty']/primary_uom_conversion[0].conversion_factor
                detail={"warehouse":warehouse['w_name'],"item_code":stock['item_code'],'actual_qty':stock['actual_qty'],'primary_qty':primary_qty}
                warehouse_stock.append(detail)
    item_records=[]
    for record in warehouse_stock:
        if transfer_type=="Scrap Entry":
            container_list=frappe.db.get_all("Container",filters={'warehouse':record['warehouse'],'item_code':record['item_code'],'primary_available_qty':['>',0]},fields={'name','primary_available_qty','primary_uom'})
        else:
            container_list=frappe.db.get_all("Container",filters={'warehouse':record['warehouse'],'item_code':record['item_code'],'secondary_available_qty':['>',0.1]},fields={'name','primary_available_qty','primary_uom'})

        for container in container_list:
            if not return_container or (return_container and return_container==container['name']):
                if not return_warehouse or (return_warehouse and return_warehouse==record['warehouse']):
                    if not item_code or (item_code and item_code==record['item_code']):
                        stock_reserved_details=frappe.db.get_all("Stock Details",filters={'parent':container['name'],'reserved_qty':['>',1]},fields={'name'})
                        if len(stock_reserved_details)==0:
                            if container['primary_available_qty']>record['primary_qty']:
                                qty=record['primary_qty']
                            else:
                                qty=container['primary_available_qty']
                            item_record={'source_warehouse':record['warehouse'],'item_code':record['item_code'],'qty':qty,'uom':container['primary_uom'],'container':container['name']}
                            item_records.append(item_record)

    return item_records

@frappe.whitelist()
def fetch_return_source_warehouse(doctype, txt, searchfield, start, page_len, filters):
    if 'workstation' in filters:
        parent_warehouse = filters['workstation']
        return frappe.db.sql("""
                        select w_name
                        from `tabInput Sources`
                        where parent = %s and parenttype="Workstation"
                """, (parent_warehouse))

    else:
         frappe.throw('Please select workstation')


@frappe.whitelist()
def fetch_item_code(doctype, txt, searchfield, start, page_len, filters):
	if 'workstation' in filters:
		parent_warehouse = filters['workstation']
		test= frappe.db.sql("""
						select distinct it.item_code
						from `tabInput Sources` i, `tabBin` b ,
						`tabItem` it where b.warehouse=i.w_name
						and i.parent=%s
						and i.parenttype="Workstation"
						and b.actual_qty>0 and it.item_code=b.item_code
						and it.is_containerized=1
				""", (parent_warehouse))
		return test

	else:
		frappe.throw('Please select workstation')


@frappe.whitelist()
def fetch_container(doctype, txt, searchfield, start, page_len, filters):
    if 'workstation' in filters:
        parent_warehouse = filters['workstation']
        return frappe.db.sql("""
                        select distinct
                        c.name from `tabInput Sources` i,
                        `tabBin` b ,`tabItem` it, `tabContainer` c
                        where b.warehouse=i.w_name
                        and i.parent=%s
                        and i.parenttype="Workstation"
                        and b.actual_qty>0 and it.item_code=b.item_code
                        and it.is_containerized=1 and c.item_code=b.item_code
                        and c.warehouse=b.warehouse and c.primary_available_qty>1
                """, (parent_warehouse))

    else:
         frappe.throw('Please select workstation')

#it will check the three float digits are equal or not
def are_floats_equal(value1, value2, tolerance=1e-3):
	return abs(value1 - value2) < tolerance
