import frappe
from datetime import datetime, timedelta
from container.container.doctype.purchase_receipt.purchase_receipt import get_auto_container_nos,calculate_base_and_room_erpiry_date,get_aging_rate
from container.container.doctype.stock_entry.stock_entry import partially_reserved
from frappe import _
from frappe.exceptions import ValidationError


container_doctype="Container"

def on_submit(self,method=None):
    if not self.system_generated and self.stock_entry_type=="Manufacture":
        no_of_containers=0
        qty=0
        if self.work_order:
            wo_doc=frappe.get_doc("Work Order",self.work_order)
            item_doc=frappe.get_doc("Item",wo_doc.production_item)
        else:
            row_fg_item=self.get_finished_item_row()
            item_doc=frappe.get_doc("Item",row_fg_item)
        try:
            if item_doc.is_containerized:
                for item in self.get("items"):
                    if item.is_finished_item:
                        #getting number of containers for fg_item
                        no_of_containers=item.no_of_containers
                        qty=item.qty
                if not no_of_containers and not qty:
                    finished_item=frappe.db.get_list("Stock Entry Details",filters={"is_finished_item":1},fields=["qty","no_of_containers"],as_dict=True)
                    no_of_containers=finished_item.no_of_containers
                    qty=finished_item.qty
                fg_item=1
                # get the least expiry date from among the raw items
                get_min_expiry_date=least_expiry_date(self)
                comment,containers=create_containers(self,item_doc,qty,get_min_expiry_date,fg_item,no_of_containers)
                frappe.db.sql("""update `tabStock Entry Detail` set containers=%s where parent=%s and is_finished_item=1""",(containers,self.name))
                frappe.msgprint("Created Containers are ("+str(no_of_containers)+"): "+comment)
        except Exception as e:
            frappe.log_error("An error occurred: {}".format(str(e)))
            frappe.throw("An error occurred. Please contact the administrator.For more info check the Error Log")
        else:
            #it will execute after successful run of try block
            update_expiry_date(self)
    elif self.stock_entry_type=="Material Transfer" or self.stock_entry_type=="Material Transfer for Manufacture":
        #update the aging history when the container transfer from one warehouse to another
        update_expiry_date(self)

def get_finished_item_row(self):
		finished_item_row = None
		if self.purpose in ("Manufacture", "Repack"):
			for d in self.get("items"):
				if d.is_finished_item:
					finished_item_row = d

		return finished_item_row

def create_containers(self,item_doc,qty,get_min_expiry_date,fg_item=0,no_of_containers=1):
    comment=""
    containers=""
    shelf_life=item_doc.shelf_life_in_days
    secondary_uom=frappe.db.get_value("UOM Conversion Detail",{"parent":item_doc.item_code,"uom_type":"Secondary UOM"},"uom")
    secondary_uom_cf=frappe.db.get_value("UOM Conversion Detail",{"parent":item_doc.item_code,"uom_type":"Secondary UOM"},"conversion_factor")
    if not secondary_uom_cf:
        frappe.throw("Please mention secondary uom for this item "+item_doc.item_code)
    if not self.to_warehouse:
        frappe.throw("Please mention the target warehouse")
    warehouse_temperature=frappe.db.get_value("Warehouse",self.to_warehouse,"temperature")
    if not warehouse_temperature:
        has_partially_reserved = partially_reserved()
        if not has_partially_reserved:
            frappe.throw("Please mention the Temperature in Warehouse "+self.to_warehouse)
        else:
            warehouse_temperature = None
    base_expiry_date,expiry_date,aging_rate,creation_date=calculate_base_and_room_erpiry_date(item_doc,warehouse_temperature) #Get the base and room temperature 
    container_series=frappe.db.get_value("Item",{"name":item_doc.item_code,"is_containerized":1},"container_number_series")
    container_nos = get_auto_container_nos(container_series,no_of_containers)
    container_list=container_nos.split("\n")
    if get_min_expiry_date["status"]=="SUCCESS" and get_min_expiry_date["min_base_expiry_date"] and get_min_expiry_date["min_room_expiry_date"]:  #used to set the min expiry date(If it contains semi fg items)
        base_expiry_date=get_min_expiry_date["min_base_expiry_date"]
        expiry_date=get_min_expiry_date["min_room_expiry_date"]
        shelf_life=get_min_expiry_date["shelf_life"]
    try:
        for container in range(len(container_list)):
            container_doc =frappe.get_doc(dict(doctype = container_doctype,
                        container_no=container_list[container],
                        item_code=item_doc.item_code,
                        warehouse=self.to_warehouse,
                        temperature=warehouse_temperature,
                        item_name=item_doc.item_name,
                        item_group=item_doc.item_group,
                        description=item_doc.description,
                        purchase_document_type=self.doctype,
                        purchase_document_no=self.name,
                        primary_uom=item_doc.stock_uom,
                        primary_available_qty=(qty/len(container_list)),
                        secondary_uom=secondary_uom,
                        secondary_available_qty=(qty/len(container_list))/secondary_uom_cf,
                        status="Active",
                        base_expiry_date=base_expiry_date,
                        expiry_date=expiry_date,
                        uom=item_doc.stock_uom,
                        fg_item=fg_item,
                        ))
            if item_doc.dynamic_aging:
                container_doc.append("aging_history",{
                            "datetime":creation_date,
                            "warehouse":self.to_warehouse,
                            "warehouse_temperature":warehouse_temperature,
                            "aging_rate":aging_rate,
                            "base_expiry_date":base_expiry_date,
                            "rt_expiry_date":expiry_date,
                            "creation_document_type":self.doctype,
                            "stock_txn_reference":self.name,
                            "shelf_life_in_days":shelf_life,
                            "description":"Created from "+self.doctype+" ref No:"+self.name
                            })
            containers+=container_list[container]+","
            comment=comment+"<a href='/app/container/"+container_list[container]+"'>"+container_list[container]+"</a><br>"
            container_doc.save(ignore_permissions=True)
            frappe.db.commit()
        return comment,containers
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error("An error occurred: {}".format(str(e)))
        frappe.throw("An error occurred while Creating Container . Please contact the administrator.For more info check the Error Log")
def update_expiry_date(self):
    submited_trans_date=frappe.utils.now_datetime() or datetime.now()
    for item in self.get("items"):
        item_doc=frappe.get_doc("Item",item.item_code)
        if item_doc.is_containerized and item_doc.container_number_series and item_doc.dynamic_aging:
            if item.containers and not item.is_finished_item:
                container_list=item.containers.split(",")
                for con in range(len(container_list)):
                    if container_list[con]:
                        container_doc=frappe.get_doc(container_doctype,container_list[con])
                        last_trans_name=frappe.get_all('Aging History', filters={'parent': container_list[con]}, order_by='idx DESC', limit=1)
                        latest_aging_details=frappe.get_doc("Aging History",last_trans_name)
                        shelf_life_in_days,base_expiry_date,expiry_date=get_base_room_temp_expiry_date_and_shelf_life(latest_aging_details,item_doc,submited_trans_date)
                        target_warehouse=get_target_warehouse(self,item.item_code)
                        target_warehouse_temperature=frappe.db.get_value("Warehouse",target_warehouse,["temperature","name"],as_dict=True)
                        if not target_warehouse_temperature.temperature:
                            frappe.throw("Please mention the temperature in warehouse "+item.t_warehouse)
                        target_aging_rate=get_aging_rate(target_warehouse_temperature,item_doc)
                        try:
                            container_doc.db_set("temperature",target_warehouse_temperature.temperature)
                            container_doc.db_set("base_expiry_date",base_expiry_date)
                            container_doc.db_set("expiry_date",expiry_date)
                            container_doc.append("aging_history",{
                                "datetime":submited_trans_date,
                                "warehouse":target_warehouse,
                                "warehouse_temperature":target_warehouse_temperature.temperature,
                                "aging_rate":target_aging_rate,
                                "base_expiry_date":base_expiry_date,
                                "rt_expiry_date":expiry_date,
                                "creation_document_type":self.doctype,
                                "stock_txn_reference":self.name,
                                "shelf_life_in_days":shelf_life_in_days,
                                "description":"Created from "+self.doctype+" ref No:"+self.name+".Transfered from "+item.s_warehouse+" to "+target_warehouse
                            })
                            # container_doc.save(ignore_permissions=True)
                            frappe.db.commit()
                        except Exception as e:
                            frappe.db.rollback()
                            frappe.log_error("An error occurred: {}".format(str(e)))
                            frappe.throw("An error occurred While Updating the expiry date. Please contact the administrator.For more info check the Error Log")
            elif not item.containers and not item.is_finished_item:
                frappe.throw("Containers Not assigned for the item "+item.item_code+" at row "+str(item.idx))

            
def get_base_room_temp_expiry_date_and_shelf_life(latest_aging_details,item_doc,submited_trans_date):
    try:
        #here datetime is the field name in aging history
        prev_trans_date=latest_aging_details.datetime
        #calculate the duriation in hours
        trans_duriation_in_hours=(submited_trans_date - prev_trans_date).total_seconds() / 3600
        #get the room temperature from item master
        rt_aging_rate=get_rt_temperature(item_doc)
        prev_shelf_life_in_hour=(latest_aging_details.shelf_life_in_days)*24
        shelf_life,base_expiry_date,rt_expity_date=get_shelf_life_base_rt_expiry_date(prev_shelf_life_in_hour,rt_aging_rate,trans_duriation_in_hours,submited_trans_date,latest_aging_details)
    except Exception as e:
        frappe.log_error("An error occurred: {}".format(str(e)))
    return shelf_life,base_expiry_date,rt_expity_date
    
def get_shelf_life_base_rt_expiry_date(prev_shelf_life_in_hour,rt_aging_rate,duriation_in_hours,trans_date,latest_aging_details):
    #for new shelf life consider the latest aging history aging rate (Base)
    new_shelf_life_hours=prev_shelf_life_in_hour-(float(latest_aging_details.aging_rate)*duriation_in_hours)
    new_shelf_life_in_days=new_shelf_life_hours/24
    new_base_expiry_date=trans_date+timedelta(new_shelf_life_in_days)
    #consider the room temperatrure aging rate (Room)
    new_rt_temperature_in_days=(new_shelf_life_hours/rt_aging_rate)/24
    new_rt_expity_date=trans_date+timedelta(new_rt_temperature_in_days)
    return new_shelf_life_in_days,new_base_expiry_date,new_rt_expity_date

def get_rt_temperature(item_doc):
    rt_aging_rate=None
    for temperature in item_doc.get("temperature_characteristics"):
         if temperature.type=="Room Temperature":
             rt_aging_rate=temperature.aging_rate
    if not rt_aging_rate:
        frappe.throw(f"Please mention the room temperature at the item master")
    return rt_aging_rate

def get_target_warehouse(self,item_code):
    target_warehouse=self.to_warehouse
    for item in self.get("items"):
        if self.stock_entry_type in ["Manufacture"] and item.is_finished_item:      #for Manufacture entry the raw material targer warehouse was empty
            target_warehouse=item.t_warehouse                                       #Consider the Fg_item Warehouse
        elif self.stock_entry_type in ["Material Transfer for Manufacture","Material Transfer"] and item.item_code==item_code:
            target_warehouse=item.t_warehouse
    return target_warehouse

#Api for Calculate least expiry date
def least_expiry_date(self):
    try:
        api_responce={}
        all_container_list=get_expiry_date_containers(self) #get raw meterials with expirt_date
        if all_container_list:
            status,message,min_base_expiry_date,min_room_expiry_date,shelf_life=get_base_room_least_expiry_date(all_container_list)
            api_responce={
            "status":status,
            "message":message,
            "shelf_life":shelf_life,
            "min_base_expiry_date":min_base_expiry_date,
            "min_room_expiry_date":min_room_expiry_date,
            }
        else:
            api_responce={
            "status":"FAILED",
            "message":"No Containers"
            }
    except Exception as e:
        frappe.log_error("An error occurred: {}".format(str(e)))
    return api_responce
def get_expiry_date_containers(self):
    all_container_list=[]
    for item in self.get("items"):
        if not item.is_finished_item and item.containers:
            containers=item.containers.split(",")
            for container in containers:
                if container:
                    conatiner_doc=frappe.get_doc(container_doctype,container)
                    if conatiner_doc.aging_history and conatiner_doc.expiry_date:
                        all_container_list.append(container)
    return all_container_list
def get_base_room_least_expiry_date(all_container_list):
    base_expiry_date=[]
    rt_expiry_date=[]
    min_base_expiry_date,min_rt_expiry_date=None,None
    status,message="",""
    for container in all_container_list:
        get_present_expiry_date=get_container_life(container)   #call api to get now expiry date
        if get_present_expiry_date["base_expiry_date"] and get_present_expiry_date["rt_expiry_date"]:
            base_expiry_date.append( get_present_expiry_date["base_expiry_date"])
            rt_expiry_date.append(get_present_expiry_date["rt_expiry_date"])
        elif not get_present_expiry_date["base_expiry_date"]:
            status="FAILED"
            message="Mandatory field Base expiry date not provided"
        elif not get_present_expiry_date["rt_expiry_date"]:
            status="FAILED"
            message="Mandatory field Room expiry date not provided"
    if base_expiry_date and rt_expiry_date:
        status="SUCCESS"
        message="Successfully fetched Expiry Date"
        min_rt_expiry_date=min(rt_expiry_date)
        #min base temperature consider the rt_expiry_date index to match base 
        min_base_expiry_date=base_expiry_date[rt_expiry_date.index(min_rt_expiry_date)]
        shelf_life=get_present_expiry_date["shelf_life"]
    return status,message,min_base_expiry_date,min_rt_expiry_date,shelf_life

@frappe.whitelist()
def get_container_life(container,aging_rate=None,trans_date=frappe.utils.now_datetime() or datetime.now()):
    try:
        shelf_life,base_expiry_date,rt_expity_date=None,None,None
        container_doc=frappe.get_doc(container_doctype,container)
        item_doc=frappe.get_doc("Item",container_doc.item_code)
        prev_trans_name=frappe.get_all('Aging History', filters={'parent': container}, order_by='idx DESC', limit=1)
        prev_trans_details=frappe.get_doc("Aging History",prev_trans_name[0]["name"])
        if prev_trans_details and trans_date:
            if aging_rate:
                prev_trans_details.aging_rate=aging_rate
            shelf_life,base_expiry_date,rt_expity_date=get_base_room_temp_expiry_date_and_shelf_life(prev_trans_details,item_doc,trans_date)
        if shelf_life and base_expiry_date and rt_expity_date:
            responce={
                "status":"SUCCESS",
                "message":"Successfully Fetched Expiry Date",
                "shelf_life":shelf_life,
                "base_expiry_date":base_expiry_date,
                "rt_expiry_date":rt_expity_date
            }
        elif not prev_trans_details:
            responce={
                "status":"FAILED",
                "message":"Not Found The Previous Transaction Details",
            }
        else:
            responce={
                "status":"FAILED",
                "message":"Failed To Fetched Expiry Date"
            }
    except Exception as e:
        frappe.log_error("An error occurred: {}".format(str(e)))
        frappe.throw("No responce,An error occurred: {}".format(str(e)))

    return responce

# Cron job to update Daily Expiry Date
@frappe.whitelist()
def daily_update_expiry_date():
    has_partially_reserved = frappe.db.get_single_value('Container Settings', 'has_partially_reserved')
    if not has_partially_reserved:
        containers=frappe.db.sql("""select tsn.name from `tabContainer` tsn ,`tabItem` ti where tsn.item_code=ti.name and ti.dynamic_aging=1""",as_dict=True)
        for container in containers:
            container_doc,prev_trans_name,prev_trans_details,existing_text=None,None,None,None
            container_doc=frappe.get_doc(container_doctype,container.name)
            prev_trans_name=frappe.get_all("Aging History", filters={'parent': container.name}, order_by='idx DESC', limit=1)
            prev_trans_details=frappe.get_doc("Aging History",prev_trans_name[0]["name"])
            existing_text=prev_trans_details.description
            get_data=get_container_life(container.name)
            if get_data["status"]=="SUCCESS" and get_data["shelf_life"]>0:
                container_doc.db_set("base_expiry_date",get_data["base_expiry_date"])
                container_doc.db_set("expiry_date",get_data["rt_expiry_date"])
                container_doc.save(ignore_permissions=True)
                try:
                    frappe.db.set_value("Aging History",prev_trans_name[0]["name"],"datetime",frappe.utils.now_datetime() or datetime.now())
                    frappe.db.set_value("Aging History",prev_trans_name[0]["name"],"shelf_life_in_days",get_data["shelf_life"])
                    frappe.db.set_value("Aging History",prev_trans_name[0]["name"],"base_expiry_date",get_data["base_expiry_date"])
                    frappe.db.set_value("Aging History",prev_trans_name[0]["name"],"rt_expiry_date",get_data["rt_expiry_date"])
                    frappe.db.set_value("Aging History",prev_trans_name[0]["name"],"description",str(existing_text)+"\n"+"Updated Time:"+str(frappe.utils.now_datetime() or datetime.now()))
                    frappe.db.commit()
                except Exception as e:
                    frappe.db.rollback()
                    frappe.log_error("An error occurred"+str(container)+": {}".format(str(e)))
                    continue
            elif get_data["status"]=="FAILED":
                try:
                    frappe.log_error(title="Return Failed"+str(container),message=" Status: {}".format(str(get_data)))
                except Exception as e:
                    continue
            elif get_data["shelf_life"]<0:
                try:
                    frappe.log_error(title="This Container Expired"+str(container),message=" Status: {}".format(str(get_data)))
                except Exception as e:
                    continue

from erpnext.controllers.status_updater import StatusUpdater

class StatusUpdaterCustom(StatusUpdater):
    def limits_crossed_error(self, args, item, qty_or_amount):
        """Raise exception for limits crossed"""
        if (
            self.doctype in ["Sales Invoice", "Delivery Note"]
            and qty_or_amount == "amount"
            and self.is_internal_customer
        ):
            return

        elif (
            self.doctype in ["Purchase Invoice", "Purchase Receipt"]
            and qty_or_amount == "amount"
            and self.is_internal_supplier
        ):
            return

        elif self.doctype in ["Purchase Invoice", "Purchase Receipt"]:
            return

        if qty_or_amount == "qty":
            action_msg = _(
                'To allow over receipt / delivery, update "Over Receipt/Delivery Allowance" in Stock Settings or the Item.'
            )
        else:
            action_msg = _(
                'To allow over billing, update "Over Billing Allowance" in Accounts Settings or the Item.'
            )

        frappe.throw(
            _(
                "This document is over limit by {0} {1} for item {4}. Are you making another {3} against the same {2}?"
            ).format(
                frappe.bold(_(item["target_ref_field"].title())),
                frappe.bold(item["reduce_by"]),
                frappe.bold(_(args.get("target_dt"))),
                frappe.bold(_(self.doctype)),
                frappe.bold(item.get("item_code")),
            )
            + "<br><br>"
            + action_msg,
            ValidationError,
            title=_("Limit Crossed"),
        )


@frappe.whitelist(allow_guest=True)
def reset_multiple_items_quantity(item_codes=None):
    """
    Reset actual_qty and projected_qty to 0 for multiple items
    Args:
        item_codes: List of item codes or comma-separated string of item codes
    """
    # Convert string input to list if needed
    if isinstance(item_codes, str):
        item_codes = [code.strip() for code in item_codes.split(",")]
    
    # If no items provided, use default list (without duplicates)
    if not item_codes:
        item_codes = [
    "398300-old", "351820-old", "351818-old", "351038-old", "398107-old",
    "351830-test-old", "398108-old", "398300-Tt-old", "351850-old",
    "351843-old", "351842-old", "356000-old", "355006-old", "355001-old",
    "353007-old", "353006-old", "351841-old", "351836-old", "351835-old",
    "351834-old", "351833-old", "351832-old", "398200-old", "398105-old",
    "398104-old", "398103-old", "398101-old", "491805-old", "491806-old",
    "398000-old", "351826-old", "398102-old", "398201-old", "398106-old",
]
    if not item_codes:
        return {"message": "No items provided to reset quantities."}

    # Get all bins for these items with positive quantities
    bins = frappe.get_all(
        "Bin",
        filters=[
            ["item_code", "in", item_codes],
            ["actual_qty", ">", 0],
            ["projected_qty", ">", 0]
        ],
        fields=["name", "item_code", "actual_qty", "projected_qty", "warehouse"],
        or_filters=[
            ["actual_qty", ">", 0],
            ["projected_qty", ">", 0]
        ]
    )

    if not bins:
        return {"message": f"No stock found for any of the {len(item_codes)} items."}

    updated_bins = 0
    for bin in bins:
        frappe.db.set_value("Bin", bin["name"], {
            "actual_qty": 0,
            "projected_qty": 0
        })
        updated_bins += 1

    frappe.db.commit()

    # Get unique affected items
    affected_items = list({bin["item_code"] for bin in bins})

    return {
        "message": f"Successfully reset quantities for {updated_bins} bins",
        "total_items": len(item_codes),
        "updated_bins": updated_bins,
        "affected_items": affected_items
    }