# Copyright (c) 2023, hotset_customizations and contributors
# For license information, please see license.txt

import frappe

container_reconciliation_doc = "Container Reconciliation"


@frappe.whitelist()
def get_container_data(docname):
    container_reco_doc = frappe.get_doc(container_reconciliation_doc, docname)
    item_code = container_reco_doc.item_code
    warehouse = container_reco_doc.warehouse
    new_containers = frappe.db.get_all(
        "Container Reconciliation Items Add",
        filters={"parenttype": container_reconciliation_doc, "parent": docname},
        fields={"*"},
    )
    old_containers = frappe.db.get_all(
        "Container Reconciliation Items",
        filters={"parenttype": container_reconciliation_doc, "parent": docname},
        fields={"*"},
    )
    old_container_list = ""
    for sn in old_containers:
        old_container_list = old_container_list + sn.container + "\n"
    new_container_list = ""
    for sn in new_containers:
        new_container_list = new_container_list + sn.container + "\n"
    return (
        item_code,
        warehouse,
        old_container_list + new_container_list,
        container_reco_doc.qty_after_reconciliation,
    )


@frappe.whitelist()
def on_submit(doc, method):
    try:
        if doc.custom_container_reconciliation:
            container_reco_doc = frappe.get_doc(
                container_reconciliation_doc, doc.custom_container_reconciliation
            )

            item_doc = frappe.get_doc("Item", container_reco_doc.item_code)
            sr_item_doc_name = ""
            container_nos = ""
            container_reco_doc = frappe.get_doc(
                container_reconciliation_doc, doc.custom_container_reconciliation
            )
            new_containers = frappe.db.get_all(
                "Container Reconciliation Items Add",
                filters={
                    "parenttype": container_reconciliation_doc,
                    "parent": doc.custom_container_reconciliation,
                },
                fields={"*"},
            )
            old_containers = frappe.db.get_all(
                "Container Reconciliation Items",
                filters={
                    "parenttype": container_reconciliation_doc,
                    "parent": doc.custom_container_reconciliation,
                },
                fields={"*"},
            )

            for sr_item in doc.items:
                if sr_item.item_code == item_doc.item_code:
                    sr_item_doc_name = sr_item.name
                    container_nos = sr_item.custom_containers
            if sr_item_doc_name != "" and container_nos != "":
                sle = frappe.get_doc(
                    "Stock Ledger Entry",
                    {
                        "voucher_no": doc.name,
                        "item_code": item_doc.item_code,
                        "voucher_detail_no": sr_item_doc_name,
                    },
                )
                sle.db_set("containers", container_nos)

            for sn in old_containers:
                serial_no = frappe.get_doc("Container", sn.container)
                serial_no.db_set("primary_available_qty", sn.stock_qty)
                serial_no.db_set("secondary_available_qty", sn.secondary_qty)
            add_new_sl_count = 0
            for sn in new_containers:
                container_doc = frappe.get_doc(
                    dict(
                        doctype="Container",
                        container_no=sn.container,
                        item_code=container_reco_doc.item_code,
                        warehouse=container_reco_doc.warehouse,
                        item_name=item_doc.item_name,
                        item_group=item_doc.item_group,
                        description=item_doc.description,
                        purchase_document_type=doc.doctype,
                        purchase_document_no=doc.name,
                        primary_uom=sn.stock_uom,
                        primary_available_qty=sn.stock_qty,
                        secondary_uom=sn.secondary_uom,
                        secondary_available_qty=sn.secondary_qty,
                        status="Active",
                        uom=sn.stock_uom,
                    )
                )
                container_doc.save(ignore_permissions=True)
                frappe.db.commit()
                add_new_sl_count = add_new_sl_count + 1
            series = frappe.db.get_value(
                "Item", container_reco_doc.item_code, "container_number_series"
            )
            container_reco_doc.db_set("reconciliation_completed", 1)
            frappe.db.sql(
                "UPDATE `tabSeries` SET `current` = `current` + %s WHERE `name`=%s",
                (
                    add_new_sl_count,
                    series.split(".#")[0],
                ),
            )
            frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error("An error occurred: {}".format(str(e)))
        frappe.throw(
            "An error occurred,please contact the administrator.For more info check the Error Log"
        )
