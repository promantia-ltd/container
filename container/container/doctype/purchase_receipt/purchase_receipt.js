frappe.provide("container.container");

frappe.ui.form.on('Purchase Receipt', {
    refresh: function(frm) {
        if (frm.is_new()){
            frm.set_value("custom_container_set_qty", 0)
            frm.clear_table('custom_container_qty_details');
        }
        if (!frm.is_new() && !frm.doc.is_return) {
            if (frm.doc.docstatus == 0) {
                frm.add_custom_button('Set Containers Qty', () => {
                    frm.__container_dialog_shown = true;
                    show_container_dialog(frm);
                });
            } else {
                frm.remove_custom_button('Set Containers Qty');
            }
        }
    },
    before_submit: function(frm) {
        const has_containerized_items = frm.doc.items.some(item => item.is_containerized);

        if (has_containerized_items && !frm.doc.custom_container_set_qty && !frm.doc.is_return) {
            frappe.throw("Cannot Submit until containerized item quantities are Saved and Submitted.");
        }
    },
	after_save:function(frm,cdt,cdn){
        if (frm.is_new() || frm.doc.is_return) return;
        if (!frm.__container_dialog_shown) {
            frm.__container_dialog_shown = true;
            show_container_dialog(frm);
            throw "Opening container dialog...";
        }

		if(frm.doc.docstatus !=1){
		set_bobbin_weight_for_container(frm.doc.items,frm)
		}
	},

    onload: function (frm) {
        // Ensure `is_containerized` is set correctly on page load
        frm.doc.items.forEach(function (item) {
            frappe.db.get_value("Item", { name: item.item_code }, "is_containerized")
                .then(r => {
                    if (r.message) {
                        frappe.model.set_value(item.doctype, item.name, "is_containerized", r.message.is_containerized);
                    }
                });
        });
    },
})
frappe.ui.form.on('Purchase Receipt Item', {
	item_code:function(frm,cdt,cdn){
		let d=locals[cdt][cdn]
		frappe.db.get_value("Item",{"name" :d.item_code},"*",(db)=>{
			frappe.model.set_value(cdt,cdn,"is_containerized",db.is_containerized);
			frappe.model.set_value(cdt,cdn,"has_bobbin",db.has_bobbin);
			frappe.model.set_value(cdt,cdn,"bobbin_type",db.bobbin_type);
			frappe.model.set_value(cdt,cdn,"custom_has_batch",db.custom_has_batch);
		});
		let validate;
		if (!validate){
			validate=1
			// container_and_batch_selector(frm,cdt,cdn)
		}
	},
	quantity:function(frm,cdt,cdn){
		let d=locals[cdt][cdn]
		frappe.model.set_value(cdt,cdn,"qty",d.quantity);
	},
    containers: function(frm, cdt, cdn) {
        if (frm.doc.is_return == 1){
            let row = locals[cdt][cdn];
            if (row.containers) {
                let container_list = row.containers
                    .split('\n')
                    .map(c => c.trim())
                    .filter(Boolean);

                if (container_list.length > 0) {
                    frappe.call({
                        method: "frappe.client.get_list",
                        args: {
                            doctype: "Container",
                            filters: {
                                name: ["in", container_list]
                            },
                            fields: ["name", "primary_available_qty"],
                            limit_page_length: container_list.length
                        },  
                        callback: function(response) {
                            let total_qty = 0;
                            (response.message || []).forEach(container => {
                                total_qty += flt(container.primary_available_qty);
                            });

                            if (total_qty > 0) {
                                frappe.model.set_value(cdt, cdn, "qty", -total_qty);
                            } else {
                                frappe.model.set_value(cdt, cdn, "qty", 0);
                            }
                        }
                    });
                } else {
                    frappe.model.set_value(cdt, cdn, "qty", 0);
                }
            } else {
                frappe.model.set_value(cdt, cdn, "qty", 0);
            }
        }
    },
	custom_add_contaierbatch_no:function(frm,cdt,cdn){
		// container_and_batch_selector(frm,cdt,cdn)
	}
})
function container_and_batch_selector(frm,cdt,cdn){
	// container batch bundle functionality
	let item = locals[cdt][cdn];
		let me = this;
		let path = "assets/container/js/utils/container_batch_selector.js";

		frappe.db.get_value("Item", item.item_code, ["custom_has_batch", "is_containerized"])
			.then((r) => {
				if (r.message && (r.message.custom_has_batch || r.message.is_containerized)) {
					item.is_containerized = r.message.is_containerized;
					item.has_batch_no = r.message.custom_has_batch;
					item.type_of_transaction = "Inward";
					item.is_rejected = true;

					frappe.require(path, function() {
						new container.ContainerBatchPackageSelector(
							frm, item, (r) => {
								if (r) {
									let update_values = {
										"custom_container_and_batch_bundle": r.name,
										"qty": Math.abs(r.total_qty)
									}

									if (r.warehouse) {
										update_values["warehouse"] = r.warehouse;
									}

									frappe.model.set_value(item.doctype, item.name, update_values);
								}
							}
						);
					});
				}
			});
}


function set_quantity_for_container_nos(items, frm) {
    let container_no_list = [];
    let qty = [];
    let uom = [];
    let expiry_date = [];
    let updated = [];
    let item_list = [];
    let is_container_no = false;
    let dummy_containers = [];
    let warehouse = [];
    let container_ref_list = []; // To hold Container Reference Numbers
    let container_no_dict_total = [];

    // Loop through the items to prepare container data
    $.each(items, function (idx, item) {
        if (item.containers) {
            is_container_no = true;
            let container_nos = item.containers;
            const individual_container_no_list = container_nos.split("\n");
            container_no_list = container_no_list.concat(individual_container_no_list);

            if (item.dummy_containers) {
                const d_containers = item.dummy_containers.split("\n");
                dummy_containers = dummy_containers.concat(d_containers);
            }

            for (let i = 0; i < individual_container_no_list.length; i++) {
                item_list = item_list.concat(item.item_code);
            }
        }
    });

    frappe.call({
        method: "container.container.doctype.purchase_receipt.purchase_receipt.get_uom_qty_and_expiry_date",
        args: {
            container_no_list: container_no_list,
        },
        async: false,
        callback: function (r) {
            uom.push(r.message[0]);
            qty.push(r.message[1]);
            expiry_date.push(r.message[2]);
            updated.push(r.message[3]);
            warehouse.push(r.message[4]);
        },
    });

    
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Container",
            filters: {
                name: ["in", container_no_list],
            },
            fields: ["name", "custom_container_reference"],
            limit_page_length: 1000,  // Fetch up to 1000 records
        },
        async: false,
        callback: function (r) {
    
            const container_refs = {};
            r.message.forEach((container) => {
                container_refs[container.name] = container.custom_container_reference || "";
            });
    
            // Build container data including Container Reference Number
            for (let i = 0; i < container_no_list.length; i++) {
                container_no_dict_total.push({
                    container_no: container_no_list[i],
                    warehouse: warehouse[0][i],
                    container: dummy_containers[i],
                    item_code: item_list[i],
                    quantity: qty[0][i],
                    uom: uom[0][i],
                    expiry_date: expiry_date[0][i],
                    updated: updated[0][i],
                    custom_container_reference: container_refs[container_no_list[i]] || "", // Populate reference number
                });
            }
        },
    });
    

    // Create the dialog
    let fields1 = [
        {
            label: "Container",
            fieldname: "container_no",
            fieldtype: "Link",
            options: "Container",
            in_list_view: 1,
            columns: 2,
        },
        {
            label: "Accepted Warehouse",
            fieldname: "warehouse",
            fieldtype: "Link",
            options: "Warehouse",
            in_list_view: 1,
            columns: 2,
        },
        {
            label: "Container Ref",
            fieldname: "custom_container_reference",
            fieldtype: "Data",
            in_list_view: 1,
            columns: 1,
        },
        {
            label: "Item",
            fieldname: "item_code",
            fieldtype: "Link",
            options: "Item",
            in_list_view: 1,
            columns: 2,
            read_only: 1,
        },
        {
            label: "Qty",
            fieldname: "quantity",
            fieldtype: "Float",
            in_list_view: 1,
            reqd: 1,
            default: 0,
            columns: 1,
        },
        {
            label: "UOM",
            fieldname: "uom",
            fieldtype: "Link",
            options: "UOM",
            in_list_view: 1,
            reqd: 1,
            columns: 1,
        },
        {
            label: "Updated",
            fieldname: "updated",
            fieldtype: "Check",
            default: 0,
            in_list_view: 1,
            columns: 1,
        },
    ];

    fields1 = fields1.concat({
        label: "Expiry Date",
        fieldname: "expiry_date",
        fieldtype: "Date",
        in_list_view: 1,
        columns: 2,
        default: "",
    });

    let fields = [
        {
            label: "Container Nos and Quantities",
            fieldtype: "Table",
            fieldname: "container_no_qty",
            fields: fields1,
            cannot_add_rows: true,
            cannot_delete_rows: 1,
            in_place_edit: true,
            data: container_no_dict_total,
        },
    ];

    let d = new frappe.ui.Dialog({
        size: "large",
        title: "Input the quantity for each container number",
        fields: fields,
        primary_action_label: "Save", // Primary button: Save
        primary_action() {
            let data = d.get_values();

            frappe.call({
                method: "container.container.doctype.purchase_receipt.purchase_receipt.save_container_reference_number",
                args: {
                    quantity: JSON.stringify(data),
                    docstatus: 0, // Save only, do not change container status
                },
            });

            d.hide();
        },
    });

    // Add the secondary action button
    d.set_secondary_action(() => {
        let data = d.get_values();

        frappe.call({
            method: "container.container.doctype.purchase_receipt.purchase_receipt.set_quantity_container_no",
            args: {
                quantity: JSON.stringify(data),
                items: JSON.stringify(frm.doc.items),
                docstatus: 1, // Save and submit
                docname: frm.doc.name,
                is_return: frm.doc.is_return
            },
            async: false,
            callback: function (r) {
                if (r.message === "1") {
                    frappe.msgprint("Containers updated and activated successfully!");
                    $(frm.page.inner_toolbar).find('button:contains("Set Container Qty")').hide();
                }
            },
        });

        d.hide();
    });
    d.set_secondary_action_label("Save and Submit"); // Secondary button: Save and Submit

    d.show();
}


function set_bobbin_weight_for_container(items,frm){
	let count=0;
	let item_list=[];
	let bobbin_type=[];
	let has_bobbin=0;
	let container_no_dict_total=[]
	let container_no=[]
	$.each(items, function (idx,item) {
			for (let i = 0; i <items[idx].no_of_containers; i++) {
				item_list=item_list.concat(item.item_code)
				if(item.bobbin_type){
				bobbin_type=bobbin_type.concat(item.bobbin_type)
				}
				else{
					bobbin_type=bobbin_type.concat("")	
				}
				count+=1
			}
			if (item.has_bobbin){
				has_bobbin=item.has_bobbin
			}
			frappe.call({
				method:"container.container.doctype.purchase_receipt.purchase_receipt.get_containers",
				args:{
					no_of_containers:item.no_of_containers,
					name:item.name
				},
				async:false,
				callback: function(r){
					for (let j = 0; j < r.message.length; j++) {
					container_no.push(r.message[j])
					}
				}
			});
	})


	if(has_bobbin==1){
	for (let i = 0; i < count; i++) {
		let container_no_dict=[{'item_code':item_list[i],'container_no':container_no[i],'bobbin_type':bobbin_type[i]}]
		container_no_dict_total=container_no_dict_total.concat(container_no_dict)
	}
	let fields1 = [];
	fields1 = [
            {
				label: 'Item',
				fieldname: 'item_code',
				fieldtype: 'Link',
				options: 'Item',
				in_list_view: 1,
				columns:2,
				read_only: 1,
			},
			{
				label: "Container",
				fieldname: 'container_no',
				fieldtype: 'Link',
				options: "Container",
				in_list_view: 1,
				columns:2,
				read_only: 1,
			},
			{
				label: 'Bobbin Type',
				fieldname: 'bobbin_type',
				fieldtype: 'Link',
				options: 'Bobbin Type',
				in_list_view: 1,
				columns:2,
			},

		]
		let fields = [{
			label: 'Container Nos and Quantities',
			fieldtype: 'Table',
			fieldname: 'bobbin_type',
			fields: fields1,
			cannot_add_rows: true,
			cannot_delete_rows: 1,
			in_place_edit: true,
			read_only: 1,
			data:container_no_dict_total
		}]
		let d = new frappe.ui.Dialog({
			size:"large",
			title: 'Input the bobbin type for each container No',
			fields: fields,
			primary_action_label: 'Save',
			primary_action() {
				var data = d.get_values();
				frappe.call({
				method:"container.container.doctype.purchase_receipt.purchase_receipt.set_total_qty",
					args:{
						bobbin_type:data,
						items:frm.doc.items	
					},
					async:false,
					callback: function(r){
						msgprint("Saved Successfully")
						frm.reload_doc()
					}
				});
				d.hide();
				
			}
		});
		d.show();
	}
}

function show_container_dialog(frm) {
    let container_data = [];
    let sl_no = 1;

    // Map accepted qty
    let item_qty_map = {};
    frm.doc.items.forEach(item => {
        if (item.is_containerized) {
            item_qty_map[item.item_code] = flt(item.qty);
        }
    });

    // Build data rows
    frm.doc.items.forEach(item => {
        if (!item.is_containerized) return;
        let no_of_containers = item.no_of_containers || 0;
        if (no_of_containers <= 0) return;

        let qty_per_container = flt(item.qty) / no_of_containers;
        let uom = item.purchase_uom || item.stock_uom || 'Unit';

        let existing = (frm.doc.custom_container_qty_details || []).filter(cd => cd.item_code === item.item_code);

        if (existing.length === no_of_containers) {
            existing.forEach(row => {
                container_data.push({
                    sl_no: sl_no++,
                    item_code: row.item_code,
                    warehouse: row.warehouse,
                    container_ref: row.container_ref,
                    qty: row.qty,
                    uom: row.uom || uom,
                    expiry_date: row.expiry_date,
                    updated: row.updated || 0
                });
            });
        } else {
            for (let i = 0; i < no_of_containers; i++) {
                container_data.push({
                    sl_no: sl_no++,
                    item_code: item.item_code,
                    warehouse: item.warehouse,
                    container_ref: '',
                    qty: qty_per_container,
                    uom: uom,
                    expiry_date: null,
                    updated: 0
                });
            }
        }
    });

    // Columns
    const fields = [
        { label: "Sl.No", fieldname: "sl_no", fieldtype: "Int", read_only: 1, in_list_view: 1 },
        { label: "Warehouse", fieldname: "warehouse", fieldtype: "Link", options: "Warehouse", read_only: 1, in_list_view: 1 },
        { label: "Container Ref", fieldname: "container_ref", fieldtype: "Data", in_list_view: 1 },
        { label: "Item", fieldname: "item_code", fieldtype: "Link", options: "Item", read_only: 1, in_list_view: 1 },
        { label: "Qty", fieldname: "qty", fieldtype: "Float", in_list_view: 1, reqd: 1 },
        { label: "UOM", fieldname: "uom", fieldtype: "Link", options: "UOM", in_list_view: 1, reqd: 1 },
        { label: "Updated", fieldname: "updated", fieldtype: "Check", in_list_view: 1 },
        { label: "Expiry Date", fieldname: "expiry_date", fieldtype: "Date", in_list_view: 1 }
    ];

    // Validation (we'll call it only in secondary_action)
    function validate(data) {
        let item_total_qty = {};
        data.container_details.forEach(row => {
            item_total_qty[row.item_code] = (item_total_qty[row.item_code] || 0) + flt(row.qty);
        });
        for (let item_code in item_total_qty) {
            let total = Math.round(flt(item_total_qty[item_code]) * 1e3) / 1e3;
            let accepted = Math.round(flt(item_qty_map[item_code]) * 1e3) / 1e3;

            // Round both to 3 decimal places for safe comparison
            total = Math.round(total * 1e3) / 1e3;
            accepted = Math.round(accepted * 1e3) / 1e3;

            if (total > accepted) {
                frappe.throw(`Qty exceeded for ${item_code}: Containers=${total}, Accepted=${accepted}`);
                return false;
            }
            if (total < accepted) {
                frappe.throw(`Qty insufficient for ${item_code}: Containers=${total}, Accepted=${accepted}`);
                return false;
            }
        }
        return true;
    }

    let dialog = new frappe.ui.Dialog({
        size: "large",
        title: "Set Container Quantities",
        fields: [
            {
                label: "Container Details",
                fieldtype: "Table",
                fieldname: "container_details",
                fields: fields,
                in_place_edit: true,
                cannot_add_rows: true,
                cannot_delete_rows: true,
                data: container_data
            },
            {
                fieldtype: "HTML",
                fieldname: "total_qty_html",
                options: "<b>Total Qty: 0</b>"
            }
        ],
        primary_action_label: "Save",
        primary_action() {
            let data = dialog.get_values();
            if (!data) return;

            frm.clear_table('custom_container_qty_details');
            data.container_details.forEach((row, idx) => {
                let child = frm.add_child('custom_container_qty_details');
                Object.assign(child, row);
                child.slno = idx + 1;
            });
            frm.refresh_field('custom_container_qty_details');
            frm.save().then(() => {
                frappe.msgprint("Saved successfully");
                dialog.hide();
            });
        },
        secondary_action_label: "Save and Submit",
        secondary_action() {
            // Validation only for submit
            let data = dialog.get_values();
            if (!data) return;
            if (!validate(data)) return;

            frm.clear_table('custom_container_qty_details');
            data.container_details.forEach((row, idx) => {
                let child = frm.add_child('custom_container_qty_details');
                Object.assign(child, row);
                child.slno = idx + 1;
            });

            frm.set_value("custom_container_set_qty", 1);

            frm.refresh_field('custom_container_qty_details');
            frm.save().then(() => {
                frappe.msgprint("Saved successfully");
                dialog.hide();

                // Auto-submit
                setTimeout(() => {
                    frm.remove_custom_button('Set Containers Qty');
                    frm.submit();
                }, 500);
            });
        }
    });

    function update_total() {
        let rows = dialog.fields_dict.container_details.grid.get_data();
        let total = 0;
        rows.forEach(row => {
            total += flt(row.qty);
        });
        dialog.fields_dict.total_qty_html.$wrapper.html(`<b>Total Qty: ${total}</b>`);
    }

    dialog.fields_dict.container_details.grid.wrapper.on('input change', 'input[data-fieldname="qty"]', update_total);
    update_total();

    dialog.show();
}



