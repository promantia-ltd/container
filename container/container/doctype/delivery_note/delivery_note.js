frappe.provide("container.container");

frappe.ui.form.on('Delivery Note Item', {
	// item_code:function(frm,cdt,cdn){
	// 	let d=locals[cdt][cdn]
	// 	frappe.db.get_value("Item",{"name" :d.item_code},"*",(db)=>{
	// 		frappe.model.set_value(cdt,cdn,"is_containerized",db.is_containerized);
	// 		frappe.model.set_value(cdt,cdn,"custom_has_batch",db.custom_has_batch);
	// 	});
    //     // This is currently on hold (May be useful in future)
    //     // container_and_batch_selector(frm,cdt,cdn)
	// },
    add_containers:function(frm,cdt,cdn){
        if (frm.doc.docstatus ==0){
            let data=locals[cdt][cdn];
            let all_containers=[];
            $.each(frm.doc.items,function(idx, row){
                if (row.container_list){
                    let str_containers=row.container_list;
                    if (str_containers.endsWith(",")){        // container_and_batch_selector(frm,cdt,cdn)

                        str_containers=str_containers.slice(0,-1);
                    }
                    all_containers.push(...str_containers.split(","));
                }
            })
            let d=new frappe.ui.form.MultiSelectDialog({
                doctype: "Container",
                target: frm.doc,
                //mandatory to pass the selected_all_containers for container doctype
                //customized the MultiSelectDialog for the container doctype
                selected_all_containers:all_containers,
                size:"large",
                setters: {
                    warehouse:cur_frm.doc.set_warehouse,
                    item_code:data.item_code,
                    status:"Active",
                    primary_available_qty:null,
                    selected:null
                },
                add_filters_group: 1,
                primary_action_label: "Set Containers",
                columns: ["warehouse","item_code","status","primary_available_qty","selected"],
                get_query() {
                        let filters = {
                            docstatus: ['!=', 2],
                            status: ['=', 'Active'],
                            warehouse: ["=", cur_frm.doc.set_warehouse],
                            item_code: ["=", data.item_code],
                        }
                        return {
                            filters :filters
                        };
                },
                action(selections) {
                    if (selections.length === 0) {
                        frappe.throw(__("Please select {0}", ["Containers"]))
                    }
                    frappe.call({
                        method:"container.container.doctype.delivery_note.delivery_note.get_containers",
                        args:{
                            selected_containers:selections,
                            item:data
                        },
                        async:false,
                        callback: function(r){
                            if(r.message){
                                frappe.model.set_value(cdt,cdn,"container_list",r.message[0])
                                frappe.model.set_value(cdt,cdn,"qty",r.message[1])
                            }
                        }
                    });
                    d.dialog.hide();
                }
            });
        }
        else if(frm.doc.docstatus ==1){
            frappe.msgprint("Sorry,you can not add containers for submited document")
        }
        else if(frm.doc.docstatus ==2){
            frappe.msgprint("Sorry,you can not change containers for cancelled document")
        }
    }
})

function container_and_batch_selector(frm,cdt,cdn){
	let item = locals[cdt][cdn];
		let me = this;
		let path = "assets/container/js/utils/container_batch_selector.js";

		frappe.db.get_value("Item", item.item_code, ["custom_has_batch", "is_containerized"])
			.then((r) => {
				if (r.message && (r.message.custom_has_batch || r.message.is_containerized)) {
					item.is_containerized = r.message.is_containerized;
					item.has_batch_no = r.message.custom_has_batch;
					item.type_of_transaction = "Outward";
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