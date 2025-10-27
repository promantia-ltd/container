frappe.ui.form.on("Shipment", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Fetch Items'), () => {
                fetch_and_add_items(frm);
            });
        }
    }
});

function fetch_and_add_items(frm) {
    if (!frm.doc.custom_sales_invoice_list || frm.doc.custom_sales_invoice_list.length === 0) {
        frappe.msgprint(__('Please add at least one Sales Invoice before fetching items.'));
        return;
    }

    const invoice_list = frm.doc.custom_sales_invoice_list
        .map(row => row.sales_invoice)
        .filter(Boolean);

    frappe.dom.freeze(__('Fetching items from Sales Invoices...'));

    frappe.call({
        method: "container.container.doctype.shipment.shipment.fetch_and_add_items_to_shipment",
        args: {
            shipment_name: frm.doc.name,
            sales_invoices: invoice_list
        },
        callback: function (r) {
            frappe.dom.unfreeze();
            if (r.message) {
                frappe.show_alert({ message: r.message, indicator: "green" });
                frm.reload_doc();
            }
        },
        error: function(err) {
            frappe.dom.unfreeze();
            console.error(err);
            frappe.msgprint(__('Error fetching items.'));
        }
    });
}
