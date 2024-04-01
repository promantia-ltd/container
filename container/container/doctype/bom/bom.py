
import frappe
from frappe import _ 
from frappe.utils import cint, cstr, flt, today

#This custom method monkey patching the standard BOM class method
#To set the default uom in BOM Item
@frappe.whitelist()
def get_bom_material_detail(self, args=None):
    """Get raw material details like uom, desc and rate."""
    if not args:
        args = frappe.form_dict.get("args")

    if isinstance(args, str):
        import json
        args = json.loads(args)

    item = self.get_item_det(args["item_code"])

    args["bom_no"] = args["bom_no"] or item and cstr(item["default_bom"]) or ""
    args["transfer_for_manufacture"] = (
        cstr(args.get("include_item_in_manufacturing", ""))
        or item
        and item.include_item_in_manufacturing
        or 0
    )
    args.update(item)

    uom = ""
    conversion_factor = 1

    try:
        uom_details = frappe.db.get_all(
            "UOM Conversion Detail",
            filters={'parenttype': 'Item', 'parent': args["item_code"], 'default_uom_in_bom': 1},
            fields=['uom', 'conversion_factor']
        )
    except Exception as e:
        frappe.log_error(f"Error fetching UOM details: {e}")
        uom_details = []

    if uom_details:
        uom = uom_details[0]['uom']
        conversion_factor = uom_details[0]['conversion_factor']

    rate = self.get_rm_rate(args)

    ret_item = {
        "item_name": item and args["item_name"] or "",
        "description": item and args["description"] or "",
        "image": item and args["image"] or "",
        "stock_uom": item and args["stock_uom"] or "",
        "uom": uom or args["stock_uom"],
        "conversion_factor": conversion_factor or args["conversion_factor"],
        "bom_no": args["bom_no"],
        "rate": rate,
        "qty": args.get("qty") or args.get("stock_qty") or 1,
        "stock_qty": args.get("qty") or args.get("stock_qty") or 1,
        "base_rate": flt(rate) * (flt(self.conversion_rate) or 1),
        "include_item_in_manufacturing": cint(args.get("transfer_for_manufacture")),
        "sourced_by_supplier": args.get("sourced_by_supplier", 0),
    }

    if args.get("do_not_explode"):
        ret_item["bom_no"] = ""

    return ret_item
    

def validate(doc,method):
    sequence_order=1
    for item in doc.items:
        if item.custom_sequence_order==0:
            item.custom_sequence_order=sequence_order
        sequence_order=sequence_order+1

    
