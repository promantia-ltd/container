import frappe
import json


@frappe.whitelist()
def get_containers(selected_containers, item):
    selected_containers = json.loads(selected_containers)
    item = json.loads(item)
    total_qty = 0
    containers = ""
    for value in selected_containers:
        container_doc = frappe.get_doc("Container", value)
        total_qty += container_doc.primary_available_qty
        containers += container_doc.name + ","
    if containers[-1] == ",":
        containers = containers[0:-1]
    return containers, total_qty


def container_processing(doc, method):
    for item in doc.items:
        if item.is_containerized:
            container_list = item.container_list
            container_no_list = container_list.split(",")
            # chek containers are valid and qty is available at the containers
            validate_container_qty(container_no_list=container_no_list,
                                   item_code=item.item_code,
                                   required_qty=item.stock_qty,
                                   warehouse=item.warehouse)
            update_containers(container_no_list=container_no_list,
                              required_qty=item.stock_qty,
                              delivery_note_docname=doc.name)


def validate_container_qty(container_no_list, item_code, required_qty, warehouse):
    total_qty = 0
    for container in container_no_list:
        if container:
            # if extra containers are mentioned that are not required ask the user to remove them
            if total_qty >= required_qty:
                frappe.throw('The container ' + container + ' is not required as qty \
                             required is already considered using the other containers mentioned')
            # get the total quantity available in the containers
            total_qty = total_qty + validate_container(container, item_code, warehouse)
    # if total qty in the mentioned containers does not dsatisfy the required qty
    if total_qty < required_qty:
        frappe.throw('The containers mentioned do not have the total quantity required for the item ' + item_code +
                     '. Add some more containers with the availale quantity')


def validate_container(container, item_code, warehouse):
    if frappe.db.get_value("Item",
                           {"name": item_code}, "ignore_scrap_qty") == 1:
        scrap_qty = 0.1
    else:
        scrap_qty = 0
    if frappe.db.exists(
        "Container",
        {
            "name": container,
            "item_code": item_code,
            "warehouse": warehouse
        },
    ):
        available_qty = frappe.db.get_value(
            "Container",
            {"name": container, "item_code": item_code},
            "primary_available_qty",
        )
        if available_qty > scrap_qty:
            return available_qty
        else:
            frappe.throw('The mentioned Container does \
                         not have available qty to be used')
    else:
        frappe.throw(
            "The mentioned container " + container
            + " does not exist in the system \
            or does not belong to the Item mentioned"
        )


def update_containers(container_no_list, required_qty, delivery_note_docname):
    qty_to_be_assigned = required_qty
    for container in container_no_list:
        if container:
            available_qty = frappe.db.get_value(
                "Container",
                {"name": container},
                "primary_available_qty"
            )
            if available_qty <= qty_to_be_assigned:
                container_consumed_qty = available_qty
            else:
                container_consumed_qty = qty_to_be_assigned
            
            # Update container primary and secondary qty after consumption
            container_doc = frappe.get_doc("Container", container)
            container_pending_qty = container_doc.primary_available_qty - qty_to_be_assigned
            container_doc.db_set('primary_available_qty', container_pending_qty)
            secondary_uom_conversion_value = frappe.db.get_value("UOM Conversion Detail", {
                'parenttype': 'Item',
                'parent': container_doc.item_code,
                'uom_type': 'Secondary UOM'},
                'conversion_factor')
            secondary_available_qty = container_pending_qty/secondary_uom_conversion_value
            container_doc.db_set('secondary_available_qty', secondary_available_qty)
            # add consumption details in stock details of Container
            update_stock_detail_table(container=container, consumed_qty=container_consumed_qty, delivery_note_docname=delivery_note_docname)
            # add a comment in container doc to show how much is consumed
            comment = f"{container_doc.warehouse} : <a href='/app/delivery-note/{delivery_note_docname}'>{delivery_note_docname}</a> " + str(container_consumed_qty) + "<br>"
            container_doc.add_comment('Comment', comment)

            # add a comment in Delivery Note doc to show how much is consumed
            delivery_note_doc = frappe.get_doc("Delivery Note", delivery_note_docname)
            comment = f"{container_doc.warehouse} : <a href='/app/container/{container_doc.name}'>{container_doc.name}</a> " + str(container_consumed_qty) + "<br>"
            delivery_note_doc.add_comment('Comment', comment)
    frappe.db.commit()


def update_stock_detail_table(container, consumed_qty, delivery_note_docname):
    container_doc = frappe.get_doc("Container", container)
    container_doc.append('stock_details', {
        'delivery_note': delivery_note_docname,
        'warehouse': container_doc.warehouse,
        'consumed_qty': consumed_qty
        })
    container_doc.save(ignore_permissions=True)


def update_containers_on_cancel(doc, method):
    for item in doc.items:
        if item.is_containerized:
            container_list = item.container_list
            container_no_list = container_list.split(",")
            for container in container_no_list:
                update_containers_after_cancel_dn(container, doc.name)
            frappe.db.commit()


def update_containers_after_cancel_dn(container, delivery_note):
    stock_detail_docname = frappe.db.get_value(
            "Stock Details",
            {"parent": container, "delivery_note": delivery_note},
            "name"
        )
    stock_detail_doc = frappe.get_doc("Stock Details", stock_detail_docname)
    consumed_qty = stock_detail_doc.consumed_qty
    container_doc = frappe.get_doc("Container", container)
    stock_detail_doc.db_set('consumed_qty', 0)
    container_doc.db_set('primary_available_qty', container_doc.primary_available_qty + consumed_qty)
    secondary_uom_conversion_value = frappe.db.get_value("UOM Conversion Detail", {
                'parenttype': 'Item',
                'parent': container_doc.item_code,
                'uom_type': 'Secondary UOM'},
                'conversion_factor')
    secondary_consumed_qty = consumed_qty/secondary_uom_conversion_value
    container_doc.db_set('secondary_available_qty', container_doc.secondary_available_qty + secondary_consumed_qty)
