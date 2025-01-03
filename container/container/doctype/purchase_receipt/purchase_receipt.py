import math
import json
import frappe
from datetime import datetime, timedelta
from frappe import _
from frappe.model.naming import make_autoname
from frappe.utils import (
    cint
)
from frappe.utils import flt
container_no_doc="Container"
def on_submit(self,method):
    container_list=[]
    bobbin_weight=[]
    for item in self.get("items"):
        item_doc=frappe.get_doc("Item",item.item_code)
        if item_doc.is_containerized and item_doc.container_number_series:
            secondary_uom=frappe.db.get_value("UOM Conversion Detail",{"parent":item.item_code,"uom_type":"Secondary UOM"},"uom")
            secondary_uom_cf=frappe.db.get_value("UOM Conversion Detail",{"parent":item.item_code,"uom_type":"Secondary UOM"},"conversion_factor")
            if not secondary_uom_cf:
                frappe.throw("Please Mention secondary uom for this item "+item.item_code)
            warehouse_temperature=frappe.db.get_value("Warehouse",item.warehouse,["temperature","name"],as_dict=True)
            if item_doc.dynamic_aging:
                base_expiry_date,expiry_date,aging_rate,creation_date=calculate_base_and_room_erpiry_date(item_doc,warehouse_temperature) #Get the base and room temperature 
            try:
                container_series=frappe.db.get_value("Item",{"name":item.item_code,"is_containerized":1},"container_number_series")
                container_nos = get_auto_container_nos(container_series,item.no_of_containers)
                frappe.db.set_value("Purchase Receipt Item",{"parent":self.name,"name":item.name},"containers",container_nos)
                item.containers=container_nos
                container_list=container_nos.split("\n")
                if item.bobbin_weight:
                    bobbin_weight.extend(item.bobbin_weight.split("\n"))
                else:
                    for val in range(int(item.no_of_containers)):
                        bobbin_weight.append(0)
                sle=frappe.get_doc("Stock Ledger Entry",{"voucher_no":item.parent,"item_code":item.item_code,"voucher_detail_no":item.name})
                sle.db_set("containers",container_nos)
                for container in range(len(container_list)):
                    container_doc =frappe.get_doc(dict(doctype = container_no_doc,
                                container_no=container_list[container],
                                item_code=item.item_code,
                                warehouse=item.warehouse,
                                item_name=item.item_name,
                                item_group=item.item_group,
                                description=item.description,
                                purchase_document_type=self.doctype,
                                purchase_document_no=self.name,
                                supplier=self.supplier,
                                supplier_name=self.supplier_name,
                                primary_uom=item.stock_uom,
                                primary_available_qty=(item.stock_qty/item.no_of_containers),
                                secondary_uom=secondary_uom,
                                secondary_available_qty=((item.stock_qty/item.no_of_containers)/secondary_uom_cf),
                                status="Inactive",
                                uom=item.stock_uom,
                                batch_no=item.batch_no,
                                purchase_rate=item.rate
                                ))
                    if item_doc.dynamic_aging:
                        container_doc.db_set("base_expiry_date",base_expiry_date)
                        container_doc.db_set("expiry_date",expiry_date)
                        container_doc.append("aging_history",{
                            "datetime":creation_date,
                            "warehouse":item.warehouse,
                            "warehouse_temperature":warehouse_temperature.temperature,
                            "aging_rate":aging_rate,
                            "base_expiry_date":base_expiry_date,
                            "rt_expiry_date":expiry_date,
                            "creation_document_type":self.doctype,
                            "stock_txn_reference":self.name,
                            "shelf_life_in_days":item_doc.shelf_life_in_days,
                            "description":"Created from "+self.doctype+" ref No:"+self.name
                        })
                    container_doc.save(ignore_permissions=True)
                    frappe.db.commit()
                bobbin_weight=[]
            except Exception as e:
                frappe.db.rollback()
                frappe.log_error("An error occurred: {}".format(str(e)))
                frappe.throw("An error occurred,please contact the administrator.For more info check the Error Log")
def calculate_base_and_room_erpiry_date(item_doc,w_temperature):
    if item_doc.dynamic_aging:
        creation_date = frappe.utils.now_datetime() or datetime.now()
        base_aging_rate,rt_aging_rate=None,None
        base_expiry_date= creation_date+timedelta(int(item_doc.shelf_life_in_days))
        for base_temperature in item_doc.get("temperature_characteristics"):
            if base_temperature.type=="Base Temperature":
                base_aging_rate=base_temperature.aging_rate
            elif base_temperature.type=="Room Temperature":
                rt_aging_rate=base_temperature.aging_rate
        if base_aging_rate and rt_aging_rate:
            out_life=int(item_doc.shelf_life_in_days) * base_aging_rate / rt_aging_rate
        elif base_aging_rate and not(rt_aging_rate):
            frappe.throw("Please mention the room temperature aging rate in item master")
        elif not(base_aging_rate) and rt_aging_rate:
            get_default_aging_rate=frappe.db.get_value("NTPT Settings","NTPT Settings","default_aging_rate")
            if not get_default_aging_rate:
                frappe.throw("Please mention the base temperature aging rate in item master")
            else:
                out_life=int(item_doc.shelf_life_in_days) * get_default_aging_rate / rt_aging_rate
        else:
            frappe.throw("Please mention the base and room temperature in item aging characteristics section")
        rt_expiry_date=creation_date+timedelta(out_life)
        aging_rate=get_aging_rate(w_temperature,item_doc)
        return base_expiry_date,rt_expiry_date,aging_rate,creation_date
    return None, None, None, None
def get_aging_rate(w_temperature,item_doc):
    aging_rate=None
    for temperature in item_doc.get("temperature_characteristics"):
         if temperature.temperature==w_temperature.temperature:
             aging_rate=temperature.aging_rate
    if not aging_rate:
        frappe.throw(f"The "+str(w_temperature.name)+" warehouse temperature "+str(w_temperature.temperature)+"not specified in the Item Master,Please contact the administrator.")
    return aging_rate
def on_cancel(self,method=None):
     container_no_list=[]
     for item in self.get('items'):
        item_container=item.containers
        if item_container:
            containers=item_container.split("\n")
            for container in containers:
                if frappe.db.get_value("Container", {'name':container}, "warehouse")!=item.warehouse:
                    frappe.throw('Document cannot be cancelled as the Container '+container+' has been transfered to another warehouse')
                elif len(frappe.db.get_all("Stock Details",filters={'parent': container,'reserved_qty':['>',0]},fields={'name'}))>0:
                    frappe.throw('Document cannot be cancelled as the Container has some qty reserved')
                container_no_list.extend(item_container.split("\n"))
     for container in container_no_list:
        sp_doc=frappe.get_doc(container_no_doc,container)
        sp_doc.db_set("status","Inactive")
        frappe.db.commit()
        
def get_auto_container_nos(container_no_series, qty):
    container_nos = []
    for i in range(cint(qty)):
        container_nos.append(get_new_container_number(container_no_series))

    return "\n".join(container_nos)


def get_new_container_number(series):
    sr_no = make_autoname(series, "Container")
    if frappe.db.exists("Container", sr_no):
        sr_no = get_new_container_number(series)
    return sr_no

@frappe.whitelist()
def get_uom_qty_and_expiry_date(container_no_list):
    uom=[]
    qty=[]
    expiry_date=[]
    updated=[]
    warehouse=[]
    container_no_list=json.loads(container_no_list)
    for container in container_no_list:
        get_qty=frappe.db.get_value(container_no_doc,container,["primary_uom","primary_available_qty","updated","warehouse"],as_dict=True)
        get_expiry_date=frappe.db.get_value(container_no_doc,container,"expiry_date")
        item_code=frappe.db.get_value(container_no_doc,container,"item_code")
        purchase_uom=frappe.db.get_value("Item",{"name":item_code},"purchase_uom")
        if purchase_uom:
            purchase_uom_conversion = frappe.db.get_value(
                        "UOM Conversion Detail",
                        {"parent": item_code, "uom": purchase_uom},
                        "conversion_factor",
                    )
            if purchase_uom_conversion:
                if get_qty:
                    uom.append(purchase_uom)
                    qty.append(get_qty.primary_available_qty/purchase_uom_conversion)
                    updated.append(get_qty.updated)
                    warehouse.append(get_qty.warehouse)
                if get_expiry_date:
                    expiry_date.append(get_expiry_date)
            else:
                frappe.throw('Please mention the UOM conversion for '+purchase_uom+' at the Item '+item_code)
        else:
            frappe.throw("Please mention the Purchase UOM for the Item "+item_code)
            
    return uom,qty,expiry_date,updated,warehouse
    

@frappe.whitelist()
def set_quantity_container_no(quantity, items, docstatus, docname):
    try:
        sp_quantity = json.loads(quantity)
        items = json.loads(items)

        # Dictionary to sum up stock_qty for each item_code
        item_total_stock_qty = {}
        # Dictionary to track total quantity per warehouse for each item
        warehouse_total_qty = {}

        # Loop through the items and accumulate stock quantity for each warehouse
        for item in items:
            item_code = item["item_code"]
            warehouse = item["warehouse"]

            # Accumulate total stock quantity per item
            if item_code not in item_total_stock_qty:
                item_total_stock_qty[item_code] = 0
            item_total_stock_qty[item_code] += flt(item['stock_qty'])

            # Initialize warehouse-wise quantity tracking for each item
            if item_code not in warehouse_total_qty:
                warehouse_total_qty[item_code] = {}

            if warehouse not in warehouse_total_qty[item_code]:
                warehouse_total_qty[item_code][warehouse] = 0
            warehouse_total_qty[item_code][warehouse] += flt(item['stock_qty'])

        # Loop to validate quantities for each item and warehouse
        for item in items:
            item_doc = frappe.get_doc("Item", item["item_code"])
            item_code = item["item_code"]
            original_warehouse = item["warehouse"]
            total_qty = 0
            uom = set()

            # Sum up the total quantity and UOM from the container quantities
            for sp in sp_quantity['container_no_qty']:
                if item_code == sp["item_code"]:
                    total_qty += flt(sp["quantity"])
                    uom.add(sp["uom"])

            # Validate UOM consistency
            if len(uom) > 1:
                frappe.throw(_("All UOMs must be the same for item {0}. Found multiple UOMs: {1}")
                             .format(item_code, ', '.join(uom)))

            # Ensure total quantity for each warehouse matches expected
            for sp in sp_quantity['container_no_qty']:
                if sp['item_code'] == item_code:
                    container_warehouse = sp["warehouse"]
                    container_qty = flt(sp["quantity"])

                    # Check if the warehouse matches the original warehouse for the item
                    if container_warehouse not in warehouse_total_qty[item_code]:
                        frappe.throw(_("Item {0} cannot be moved from {1} to {2}.")
                                     .format(item_code, original_warehouse, container_warehouse))

                    # Check if the total quantity for this warehouse matches the original expected quantity
                    expected_qty_in_warehouse = warehouse_total_qty[item_code][container_warehouse]
                    current_qty_in_warehouse = sum(
                        sp_["quantity"] for sp_ in sp_quantity['container_no_qty'] 
                        if sp_['item_code'] == item_code and sp_["warehouse"] == container_warehouse
                    )

                    # Validation: total quantity in the same warehouse must match
                    if current_qty_in_warehouse != expected_qty_in_warehouse and docstatus == 1:
                        frappe.throw(_("The total quantity for item {0} in warehouse {1} should match the expected quantity {2}. Currently entered: {3}")
                                     .format(item_code, container_warehouse, expected_qty_in_warehouse, current_qty_in_warehouse))

            # Conversion and rounding for total quantities
            purchase_uom_conversion = frappe.db.get_value(
                "UOM Conversion Detail",
                {"parent": item_doc.item_code, "uom": item_doc.purchase_uom},
                "conversion_factor"
            )
            total_qty = round(total_qty * purchase_uom_conversion, 3)

            # Final check based on total stock_qty and document status
            total_stock_qty = item_total_stock_qty[item_code]
            if docstatus == '1':
                if flt(total_qty) > flt(total_stock_qty):
                    frappe.throw(_("Quantity exceeded. Expected Total Qty of the item {0} in warehouse {1} should not be more than {2}")
                                 .format(item_code, original_warehouse, total_stock_qty))
                if flt(total_qty) < flt(total_stock_qty):
                    frappe.throw(_("Quantity of {0} in warehouse {1} should be equal to the accepted qty {2}")
                                 .format(item_code, original_warehouse, total_stock_qty))

        # Update containers if quantities are valid
        if docstatus == '1' or any(sp["updated"] == 1 for sp in sp_quantity['container_no_qty']):
            for sp in sp_quantity['container_no_qty']:
                if docstatus == '1' or sp["updated"] == 1:
                    purchase_uom_conversion = frappe.db.get_value(
                        "UOM Conversion Detail",
                        {"parent": sp['item_code'], "uom": sp["uom"]},
                        "conversion_factor"
                    )
                    secondary_uom_cf = frappe.db.get_value(
                        "UOM Conversion Detail",
                        {"parent": sp['item_code'], "uom_type": "Secondary UOM"},
                        "conversion_factor"
                    )

                    sp_doc = frappe.get_doc("Container", sp['container_no'])
                    sp_doc.db_set('primary_available_qty', flt(sp['quantity']) * purchase_uom_conversion)
                    sp_doc.db_set("secondary_available_qty", flt(sp['quantity']) * purchase_uom_conversion / secondary_uom_cf)
                    sp_doc.db_set('updated', sp['updated'])

                    # Update custom_container_reference and status
                    if docstatus == '1':
                        sp_doc.db_set('status', 'Active')
                        sp_doc.db_set('custom_container_reference', sp['custom_container_reference'])

                    if 'expiry_date' in sp:
                        sp_doc.db_set('expiry_date', sp['expiry_date'])

                    frappe.db.commit()

        if docstatus == '1':
            frappe.db.set_value('Purchase Receipt', {'name': docname}, "button_hide", 1)
        return docstatus
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"An error occurred: {str(e)}")
        frappe.throw(f"An error occurred: {str(e)}")


@frappe.whitelist()
def button_hide(quantity, name):
    sp_quantity = json.loads(quantity)
    check = any(sp['updated'] == 0 for sp in sp_quantity['container_no_qty'])
    button_hide_value = 0 if check else 1
    frappe.db.set_value('Purchase Receipt', {'name': name}, "button_hide", button_hide_value)


@frappe.whitelist()
def set_total_qty(bobbin_type,items):
    uom_list=[]
    total_weight=0
    bobbin_wt=""
    bt=""
    bobbin_type=json.loads(bobbin_type)
    items=json.loads(items)
    for item in items:
        for type in bobbin_type['bobbin_type']:
            if item['item_code']==type['item_code']:
                bobbin_weight=frappe.db.get_value("Bobbin Type",type['bobbin_type'],['weight','uom'],as_dict=True)
                bt+=str(type['bobbin_type'])+"\n"
                if bobbin_weight:
                    if item['uom']==bobbin_weight.uom:
                        total_weight+=bobbin_weight.weight
                        bobbin_wt+=str(bobbin_weight.weight)+"\n"
                    else:
                        uom_details=frappe.db.get_all("UOM Conversion Detail",filters={'parent':item['item_code']},fields=["*"])
                        for uom_check in uom_details:
                            uom_list.append(uom_check['uom'])
                        if bobbin_weight.uom not in uom_list:
                            frappe.throw("Uom Not Matching with the item and the bobbin type")
                        for uom in uom_details:
                            if uom['uom']==bobbin_weight.uom:
                                total_weight+=bobbin_weight.weight/uom['conversion_factor']
                                bobbin_wt+=str(bobbin_weight.weight/uom['conversion_factor'])+"\n"
                else:
                    bobbin_wt+="0"+"\n"
        frappe.db.set_value("Purchase Receipt Item",item['name'],"total_qty",item['quantity']-total_weight)
        frappe.db.set_value("Purchase Receipt Item",item['name'],"bobbin_weight",bobbin_wt)
        frappe.db.set_value("Purchase Receipt Item",item['name'],"bobbin_type_for_each_container",bt)
        frappe.db.set_value("Purchase Receipt Item",item['name'],"qty",item['quantity']-total_weight)
        frappe.db.set_value("Purchase Receipt Item",item['name'],"received_qty",item['quantity']-total_weight)
        total_weight=0
        bobbin_wt=""
        bt=""

@frappe.whitelist()
def get_containers(no_of_containers,name):
    container_nos=[]
    containers=""
    no_of_containers=int(no_of_containers)
    for value in range(no_of_containers):
        container_nos.append("Container "+str(value+1))
    last_container=len(container_nos)-1
    for container in range(len(container_nos)):
        if last_container !=container:
            containers+=container_nos[container]+"\n"
        else:
            containers+=container_nos[container]
    # frappe.db.set_value("Purchase Receipt Item",name,"dummy_containers",containers)
    return container_nos