frappe.provide("container.container");

frappe.ui.form.on('Purchase Receipt', {
    // Reset container data on new (e.g. duplicated) PRs; show "Set Containers Qty" on saved drafts
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
    // Block submit until container quantities were saved via "Save and Submit" in the dialog
    before_submit: function(frm) {
        const has_containerized_items = frm.doc.items.some(item => item.is_containerized);

        if (has_containerized_items && !frm.doc.custom_container_set_qty && !frm.doc.is_return) {
            frappe.throw("Cannot Submit until containerized item quantities are Saved and Submitted.");
        }
    },
	// Open the container dialog after the first save of this form session
	after_save:function(frm,cdt,cdn){
        if (frm.is_new() || frm.doc.is_return) return;
        if (!frm.__container_dialog_shown) {
            frm.__container_dialog_shown = true;
            show_container_dialog(frm);
            // Deliberate: throwing stops the rest of after_save (bobbin dialog) once the container dialog is open
            throw "Opening container dialog...";
        }

		if(frm.doc.docstatus !=1){
		set_bobbin_weight_for_container(frm.doc.items,frm)
		}
	},

    // Refresh `is_containerized` on each item from the Item master
    onload: function (frm) {
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
	// Copy container/bobbin/batch flags from the Item master
	item_code:function(frm,cdt,cdn){
		let d=locals[cdt][cdn]
		frappe.db.get_value("Item",{"name" :d.item_code},"*",(db)=>{
			frappe.model.set_value(cdt,cdn,"is_containerized",db.is_containerized);
			frappe.model.set_value(cdt,cdn,"has_bobbin",db.has_bobbin);
			frappe.model.set_value(cdt,cdn,"bobbin_type",db.bobbin_type);
			frappe.model.set_value(cdt,cdn,"custom_has_batch",db.custom_has_batch);
		});
	},
	// `quantity` is the gross qty entered by the user; mirror it into qty
	quantity:function(frm,cdt,cdn){
		let d=locals[cdt][cdn]
		frappe.model.set_value(cdt,cdn,"qty",d.quantity);
	},
	// Keep this line's saved container rows in sync with the line warehouse
	warehouse: function(frm, cdt, cdn) {
		let item = locals[cdt][cdn];
		let new_warehouse = item.warehouse;
		if (!new_warehouse) return;

		// Update warehouse on all custom_container_qty_details rows
		// that belong to this PR item line
		(frm.doc.custom_container_qty_details || []).forEach(row => {
			if (row.pr_item_name === item.name) {
				frappe.model.set_value(
					row.doctype, row.name, 'warehouse', new_warehouse
				);
			}
		});
		frm.refresh_field('custom_container_qty_details');
	},
    // On returns, set qty to minus the available qty of the selected containers
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
	// Container/batch selector is disabled; handler intentionally left empty
	custom_add_contaierbatch_no:function(frm,cdt,cdn){
	}
})

// Bobbin-type dialog: deducts selected bobbin weights from each line's qty (only when an item has_bobbin)
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

// Dialog to enter qty/warehouse/reference per container; rows are stored in custom_container_qty_details
function show_container_dialog(frm) {
    let container_data = [];
    let sl_no = 1;

    // Map accepted qty per PR item row (keyed by item.name, not item_code)
    // This correctly handles the same item appearing on multiple PR lines
    let item_qty_map = {};
    frm.doc.items.forEach(item => {
        if (item.is_containerized) {
            item_qty_map[item.name] = flt(item.qty);
        }
    });

    // Build data rows — one set per PR item line, keyed by item.name
    frm.doc.items.forEach(item => {
        if (!item.is_containerized) return;
        let no_of_containers = item.no_of_containers || 0;
        if (no_of_containers <= 0) return;

        let qty_per_container = flt(item.qty) / no_of_containers;
        let uom = item.uom || item.stock_uom || 'Unit';

        // Reuse saved rows of this PR line (matched by pr_item_name) only if their count still matches
        let existing = (frm.doc.custom_container_qty_details || []).filter(
            cd => cd.pr_item_name === item.name
        );

        if (existing.length === no_of_containers) {
            existing.forEach(row => {
                container_data.push({
                    sl_no: sl_no++,
                    pr_item_line: item.idx,
                    pr_item_name: item.name,
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
                    pr_item_line: item.idx,
                    pr_item_name: item.name,
                    item_code: item.item_code,
                    // FIXME: warehouse is editable per row, so it may differ from the line warehouse
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

    // Grid columns (in_list_view: 1) — kept minimal so Qty is always visible.
    // Sl.No, Warehouse, Updated, Expiry Date are accessible by expanding a row.
    const fields = [
        { label: "Sl.No",          fieldname: "sl_no",          fieldtype: "Int",   read_only: 1, in_list_view: 1 },
        { label: "Item",           fieldname: "item_code",      fieldtype: "Link",  options: "Item",      read_only: 1, in_list_view: 1 },
        { label: "Warehouse",      fieldname: "warehouse",      fieldtype: "Link",  options: "Warehouse", in_list_view: 1 },
        { label: "Container Ref",  fieldname: "container_ref",  fieldtype: "Data",                        in_list_view: 1 },
        { label: "Qty",            fieldname: "qty",            fieldtype: "Float",                       in_list_view: 1, reqd: 1 },
        { label: "UOM",            fieldname: "uom",            fieldtype: "Link",  options: "UOM",       in_list_view: 1, reqd: 1 },
        { label: "Line #",         fieldname: "pr_item_line",   fieldtype: "Int",   read_only: 1, in_list_view: 0 },
        { label: "Expiry Date",    fieldname: "expiry_date",    fieldtype: "Date",                        in_list_view: 0 },
        { label: "Updated",        fieldname: "updated",        fieldtype: "Check",                       in_list_view: 0 },
        { label: "PR Item Name",   fieldname: "pr_item_name",   fieldtype: "Data",  read_only: 1, in_list_view: 0 }
    ];

    // Validate per PR item line (pr_item_name), not per item_code
    // This correctly handles the same item on multiple lines
    function validate(data) {
        let line_total_qty = {};
        data.container_details.forEach(row => {
            let key = row.pr_item_name;
            line_total_qty[key] = (line_total_qty[key] || 0) + flt(row.qty);
        });
        for (let pr_item_name in line_total_qty) {
            let total = Math.round(flt(line_total_qty[pr_item_name]) * 1e3) / 1e3;
            let accepted = Math.round(flt(item_qty_map[pr_item_name]) * 1e3) / 1e3;
            // Find item_code and line # for the error message
            let ref_row = data.container_details.find(r => r.pr_item_name === pr_item_name);
            let item_code = ref_row ? ref_row.item_code : pr_item_name;
            let line_no = ref_row ? ref_row.pr_item_line : '';

            if (total > accepted) {
                frappe.throw(`Qty exceeded for ${item_code} (Line ${line_no}): Containers=${total}, Accepted=${accepted}`);
                return false;
            }
            if (total < accepted) {
                frappe.throw(`Qty insufficient for ${item_code} (Line ${line_no}): Containers=${total}, Accepted=${accepted}`);
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
            // FIXME: Save skips the per-line qty validation (only "Save and Submit" runs validate())
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
