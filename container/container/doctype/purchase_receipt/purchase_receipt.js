frappe.provide("container.container");

frappe.ui.form.on('Purchase Receipt', {
	on_submit: function(frm,cdt,cdn){
		set_quantity_for_container_nos(frm.doc.items,frm);
	},
	refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            // Reset button_hide to 0 for amended documents
            frm.set_value('button_hide', 0);
        }

        if (frm.doc.button_hide != "1" && frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Set Container Qty'), function() {
                set_quantity_for_container_nos(frm.doc.items, frm);
            });
        }
    },
	after_save:function(frm,cdt,cdn){
		if(frm.doc.docstatus !=1){
		set_bobbin_weight_for_container(frm.doc.items,frm)
		}
	}
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

    // Fetch Container Reference Numbers
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Container",
            filters: {
                name: ["in", container_no_list],
            },
            fields: ["name", "custom_container_reference"],
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
                async: false,
                callback: function (r) {
                    if (r.message === 1) {
                        frappe.msgprint("Containers saved successfully!");
                    }
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
            },
            async: false,
            callback: function (r) {
                if (r.message === 1) {
                    frappe.msgprint("Containers updated and activated successfully!");
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