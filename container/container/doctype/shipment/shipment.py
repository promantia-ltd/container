import frappe
import json

@frappe.whitelist()
def fetch_and_add_items_to_shipment(shipment_name, sales_invoices):

    if isinstance(sales_invoices, str):
        sales_invoices = json.loads(sales_invoices)

    if not sales_invoices:
        frappe.throw("No Sales Invoices provided.")

    # Get the Shipment document
    shipment = frappe.get_doc("Shipment", shipment_name)

    shipment.set("shipment_goods_details", [])

    # Fetch all items in a single query
    invoice_items = frappe.db.get_all(
        "Sales Invoice Item",
        fields=["parent as sales_invoice", "item_code", "item_name", "qty", "description", "delivery_note"],
        filters={"parent": ["in", sales_invoices]},
        order_by="idx asc"
    )

    # Append items to the Shipment child table
    for item in invoice_items:
        shipment.append("shipment_goods_details", {
            "item": item.item_code,
            "item_name": item.item_name,
            "qty": item.qty,
            "description": item.description,
            "delivery_note": item.delivery_note or ''
        })

    shipment.save(ignore_permissions=True)

    return f"{len(invoice_items)} items added successfully from Sales Invoices."
