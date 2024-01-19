// Copyright (c) 2023, Mohan and contributors
// For license information, please see license.txt

frappe.ui.form.on('Slit Containers', {
	refresh:function(frm,cdt,cdn){
		frm.set_query("container", "slitted_containers_details", function(frm, cdt, cdn) {
			let d=locals[cdt][cdn]
			return {
					query: "container.container.doctype.slit_containers.slit_containers.get_container_filter",
					filters:{
						"item_code":d.item_code
					},
				};
		});
	},
	item_code:function(frm){
		frm.clear_table("slitted_containers_details");
		let child=frm.add_child("slitted_containers_details");
		child.item_code=frm.doc.item_code
		frm.refresh_field("slitted_containers_details")
	}

})
frappe.ui.form.on('Slitted Containers Details', {
	slit_container:function(frm,cdt,cdn){
		set_slit_container_qty(frm,cdt,cdn)
	}
});
function set_slit_container_qty(frm,cdt,cdn){
	if (frm.doc.docstatus==0){
	let data=locals[cdt][cdn]
	let item_list=[];
	let container_no_dict_total=[]
	let containers=undefined
	frappe.call({
		method:"container.container.doctype.slit_containers.slit_containers.get_virtual_naming_series",
			args:{
				container:data.container,
				no_of_containers:data.no_of_slitted_containers
			},
			async:false,
			callback: function(r){
				containers=r.message
			}
	});
	for (let i = 0; i <data.no_of_slitted_containers ; i++) {
		item_list.push(data.item_code)
		let qty=data.qty_in_the_container/data.no_of_slitted_containers
		let container_no_dict=[{'item_code':item_list[i],'container':containers[i],'qty':qty}]
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
				label: "Virtual Container",
				fieldname: 'container',
				fieldtype: 'Data',
				in_list_view: 1,
				columns:3,
				read_only: 1,
			},
			{
				label: 'Qty',
				fieldname: 'qty',
				fieldtype: 'Float',
				in_list_view: 1,
				columns:2,
			},

		]
		let fields = [{
			label: 'Set The Qty For Each Container',
			fieldtype: 'Table',
			fieldname: 'slit_container',
			fields: fields1,
			cannot_add_rows: true,
			cannot_delete_rows: 1,
			in_place_edit: true,
			read_only: 1,
			data:container_no_dict_total
		}]
		let d = new frappe.ui.Dialog({
			size:"large",
			title: 'Change Qty',
			fields: fields,
			primary_action_label: 'Save',
			primary_action() {
				let dialog_info = d.get_values();
				frappe.call({
					method:"container.container.doctype.slit_containers.slit_containers.validate_container_qty",
						args:{
							sub_containers:dialog_info,
							qty:data.qty_in_the_container
						},
						async:false,
						callback: function(r){
								frappe.call({
								method:"container.container.doctype.slit_containers.slit_containers.set_container_qty",
									args:{
										sub_containers:dialog_info,
									},
									async:false,
									callback: function(r){
										frappe.model.set_value(cdt,cdn,"qty_for_each_container",r.message)
										msgprint("Saved Successfully")
									}
								});
						}
					})
				d.hide();
			}
		});
		d.show();
	}
}

