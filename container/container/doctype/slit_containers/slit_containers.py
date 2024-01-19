# Copyright (c) 2023, Mohan and contributors
# For license information, please see license.txt

import frappe
import json
import ast
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
	cint
)
from container.container.doctype.purchase_receipt.purchase_receipt import get_auto_container_nos

class SlitContainers(Document):
	def on_submit(self):
		all_comment=""
		for item in self.get("slitted_containers_details"):
			#Create manufacture stock entry
			self.create_manufature_entry(item)
			#Create sub containers
			comment,containers=create_sub_containers(self,item)
			if comment and containers :
				all_comment+=comment
				#yes,update parent container 
				try:
					container_doc=frappe.get_doc("Container",item.container)
					container_doc.db_set("slitted_container",1)
					container_doc.db_set("slitted_doc_ref",self.name)
					container_doc.db_set("primary_available_qty",0)
					container_doc.db_set("secondary_available_qty",0)
					container_doc.add_comment('Comment',"This Container Slitted In To :"+comment)
					for container in containers :
						qty_each=ast.literal_eval(item.qty_for_each_container) or "{}"
						if container in qty_each.keys():
							container_doc.append("slitted_details",{
								'item_code':item.item_code,
								'container':container,
								'qty_each':qty_each[container],
							})
						container_doc.save(ignore_permissions=True)
					frappe.db.commit()
				except frappe.exceptions.MandatoryError as e:
					#sub containers are created commit the parent container
					frappe.db.commit()
					frappe.log_error("An error occurred: {}".format(str(e)))
					frappe.msgprint("An error occurred while updating parent container.Please contact the administrator,For more info check the Error Log")
			else:
				frappe.db.rollback()
		frappe.msgprint("Slitted Containers : "+all_comment)
	def create_manufature_entry(self,item):
		try:
			container_doc=frappe.get_doc("Container",item.container)
			stock_entry_doc=frappe.get_doc(dict(doctype = 'Stock Entry',
					purpose="Manufacture",
					stock_entry_type="Manufacture",
					docstatus=1,
					system_generated=1,
					comment="Created from Slit Containers doctype(System Generated) Ref : "+self.name
					))
			for item in self.get("slitted_containers_details"):
				qty_each=ast.literal_eval(item.qty_for_each_container) or "{}"
				qty_each=list(qty_each.keys())
				str_container=",".join(qty_each)
				stock_entry_doc.append('items', {
							"item_code":item.item_code,
							"s_warehouse":item.warehouse,
							"qty":item.qty_in_the_container,
							"required_qty":item.qty_in_the_container,
							"containers":item.container,
							"available_qty_use":item.qty_in_the_container,
							"available_qty":item.qty_in_the_container,
							"remaining_qty":item.container+":"+str(0),
							"uom":container_doc.primary_uom,
							})
				stock_entry_doc.append('items', {     
							"is_finished_item":1,
							"item_code":item.item_code,
							"t_warehouse":item.warehouse,
							"qty":item.qty_in_the_container,
							"required_qty":0,
							"containers":str_container,
							"uom":container_doc.primary_uom,
							})
			stock_entry_doc.save(ignore_permissions=True)
			frappe.db.commit()
		except Exception as e:
			frappe.log_error("An error occurred: {}".format(str(e)))
			frappe.throw("Error while creating stock entry,Please contact administrator")


@frappe.whitelist()
def get_virtuval_naming_series(container,no_of_containers):
	renamed_container = []
	#mandatory to pass .# here 
	container+="-.#"
	container_nos = get_auto_virtual_container_nos(container,no_of_containers)
	container_list=container_nos.split("\n")
	for each in container_list:
		renamed_container.append(each.replace("-", ""))
	return renamed_container

@frappe.whitelist()
def set_container_qty(sub_containers):
	sub_container_and_qty_each={}
	sub_containers=json.loads(sub_containers)
	for sub in sub_containers['slit_container']:
		#append the value in to dict
		sub_container_and_qty_each[sub['container']]=sub['qty']
	#pass the value as str
	return str(sub_container_and_qty_each)

@frappe.whitelist()
def validate_container_qty(sub_containers,qty):
	total_sub_qty=0
	sub_containers=json.loads(sub_containers)
	for sub in sub_containers['slit_container']:
		total_sub_qty+=sub['qty']
	total_sub_qty=int(total_sub_qty)
	qty=int(float(qty))
	if total_sub_qty > qty:
		frappe.throw(_("Quantity exceeded available qty is this "+str(qty)+" ,but the total of sub container qty is more than the available qty ("+str(total_sub_qty)+")"))
	elif total_sub_qty < qty:
		frappe.throw(_("Available qty is this "+str(qty)+" ,but the total of sub container qty is less than the available qty ("+str(total_sub_qty)+")"))

def get_auto_virtual_container_nos(container_no_series, qty):
	container_nos = []
	count=0
	for i in range(cint(qty)):
		series=container_no_series.split(".")
		#to match the serial no saved in series table
		current=frappe.db.sql("""select current from `tabSeries` where name=%s""",(series[0]),as_dict=True)
		if i==0 and current and current[0]["current"] is not None:
			count=current[0]["current"]
		elif container_nos:
			#increment for next series
			count+=1
		container_nos.append(get_new_container_number(container_no_series,count))

	return "\n".join(container_nos)

def get_new_container_number(series,current):
	sr_no = make_virtual_autoname(current,series)
	if frappe.db.exists("Container", sr_no):
		current+=1
		sr_no = get_new_container_number(series,current)
	return sr_no

def make_virtual_autoname(current,series):
	parts = series.split(".")
	return parse_naming_series(current,parts)

def parse_naming_series(current,parts: list[str] | str):
	name = ""
	if isinstance(parts, str):
		parts = parts.split(".")
	series_set = False
	for e in parts:
		if not e:
			continue
		part = ""
		if e.startswith("#"):
			if not series_set:
				digits = len(e)
				part = getseries(current,digits)
				series_set = True
		else:
			part = e
		if isinstance(part, str):
			name += part + '.'
	return name[:-1]

def getseries(current,digits):
	current = cint(current) + 1
	return ("%0" + str(digits) + "d") % current

def create_sub_containers(self,item):
    comment=""
    containers=[]
    qty_for_each_container=item.qty_for_each_container or "{}"
    #convert str to dict
    qty_for_each_container=ast.literal_eval(qty_for_each_container)
    item_doc=frappe.get_doc("Item",item.item_code)
    secondary_uom_cf=frappe.db.get_value("UOM Conversion Detail",{"parent":item_doc.item_code,"uom_type":"Secondary UOM"},"conversion_factor")
    parent_container_doc=frappe.get_doc("Container",item.container)
    #we should concat the same sting here as well 
	#for sync of virtual and created conatiners
    container_series=item.container+"-.#"
    container_nos = get_auto_container_nos(container_series,item.no_of_slitted_containers)
    container_list=container_nos.split("\n")
    #validate the virual and created containers
    validate_virtual_and_created_containers(qty_for_each_container,container_list)
    try:
        for container in range(item.no_of_slitted_containers):
            container_doc =frappe.get_doc(dict(doctype = "Container",
				container_no=container_list[container],
				item_code=item_doc.item_code,
				warehouse=parent_container_doc.warehouse,
				temperature=parent_container_doc.temperature,
				item_name=item_doc.item_name,
				item_group=item_doc.item_group,
				description=item_doc.description,
				purchase_document_type=self.doctype,
				purchase_document_no=item.parent,
				primary_uom=parent_container_doc.primary_uom,
				secondary_uom=parent_container_doc.secondary_uom,
				status="Active",
				container_details=parent_container_doc.container_details,
				base_expiry_date=parent_container_doc.base_expiry_date,
				expiry_date=parent_container_doc.expiry_date,
				uom=item_doc.stock_uom,
				fg_item=parent_container_doc.fg_item,
				primary_available_qty=float(qty_for_each_container[container_list[container]]),
				secondary_available_qty=float(qty_for_each_container[container_list[container]])/secondary_uom_cf,
				sub_container=1,
				parent_ref=item.container
				))
	    	#copy the parent aging history of latest record
            container_doc=copy_aging_history(self,item,container_doc)
            containers.append(container_list[container])
            comment=comment+"<a href='/app/container/"+container_list[container]+"'>"+container_list[container]+"</a><br>"
            container_doc.save(ignore_permissions=True)
            frappe.db.commit()
        return comment,containers
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error("An error occurred: {}".format(str(e)))
        frappe.throw("An error occurred while creating container,please contact the administrator.For more info check the Error Log")
def validate_virtual_and_created_containers(qty_for_each_container,container_list):
	for container in container_list:
		if container in qty_for_each_container.keys():
			continue
		else:
		    frappe.throw("Virtual containers do not match the created containers. Please reset the containers by clicking the 'Split Container' button.")

def copy_aging_history(self,item,container_doc):
	prev_trans_details=None
	prev_trans_name=frappe.get_all('Aging History', filters={'parent': item.container}, order_by='idx DESC', limit=1)
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
			"creation_document_type":self.doctype,
			"stock_txn_reference":self.name,
			"shelf_life_in_days":prev_trans_details.shelf_life_in_days,
			"description":"Slitted from "+self.doctype+" ref No:"+self.name
			})
	else:
		return container_doc
	return container_doc

@frappe.whitelist()
def get_container_filter(doctype, txt, searchfield, start, page_len, filters):
	item_code = str(filters['item_code'])
	return frappe.db.sql("""select distinct not_reserved_container.container from (select tc.name as container,(select count(`tabStock Details`.is_reserved) from `tabStock Details` 
		where `tabStock Details`.parent=container and `tabStock Details`.is_reserved=1) as cnt
		from `tabContainer` tc left join `tabStock Details` tsd on tc.name=tsd.parent
		where tc.primary_available_qty>0 and tc.status in ("Active") and tc.item_code=%s) as not_reserved_container where not_reserved_container.cnt<1
		""",(item_code))