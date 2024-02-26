// Copyright (c) 2024, Mohan and contributors
// For license information, please see license.txt



// Copyright (c) 2023, hotset_customizations and contributors
// For license information, please see license.txt

frappe.ui.form.on('Container Reconciliation', {
    refresh: function(frm) {
		frm.page.menu.find('[data-label="Duplicate"]').parent().parent().remove();
		$('*[data-fieldname="items"]').find('.grid-remove-rows').hide();
		$('*[data-fieldname="new_container_nos"]').find('.grid-remove-rows').hide();
		cur_frm.fields_dict["items"].grid.wrapper.find('.grid-add-row').hide();
		cur_frm.fields_dict["new_container_nos"].grid.wrapper.find('.grid-add-row').hide();



		frm.set_query("item_code",function(){
			return{
				filters: {
					"is_containerized":1
				}
			};
		 });
		add_serial_nos(frm.doc.item_code,frm)
		if(frm.doc.docstatus==1 && !frm.doc.reconciliation_completed){
			frm.add_custom_button(__('Create Stock Reconciliation'), function () {
				frappe.call({
					method: "container.container.doctype.container_reconciliation.container_reconciliation.create_stock_reconciliation",
					args:{
						docname:frm.doc.name
					},
					callback:function(r){
						frappe.new_doc('Stock Reconciliation', {company: frm.doc.company,custom_container_reconciliation:frm.doc.name,purpose:"Stock Reconciliation"});
					}
				})
			})
		}
	},
	before_save: function(frm) {
		$.each(frm.doc.items, function (idx,item) {
			frappe.call({
				method: "container.container.doctype.container_reconciliation.container_reconciliation.check_reservations",
				args:{
					container:item.container,
					warehouse: frm.doc.warehouse
				},
				callback:function(r){
					if(r.message==false){
						frappe.validated = false;
						frappe.throw('Item cannot be Reconciled if the Serial Nos are reserved for In Progress Work Orders. Finish the Work Order or Unreserve the Stock')
				
					}
				}
			})
		})
	},
	warehouse: function(frm) {
		add_serial_nos(frm.doc.item_code,frm)
		if(frm.doc.item_code){
			add_current_serial_nos(frm)
		}
	},
    item_code: function(frm) {
		frm.clear_table("items");
		frm.clear_table("new_container_nos");
        add_serial_nos(frm.doc.item_code,frm)
		if(frm.doc.warehouse){
			add_current_serial_nos(frm)
		}
		
	}
});

function add_current_serial_nos(frm){
	frm.clear_table("items");
	frappe.call({
		method: "container.container.doctype.container_reconciliation.container_reconciliation.get_containers",
		args:{
			item:frm.doc.item_code,
			warehouse:frm.doc.warehouse
		},
		callback:function(r){
			
			for (let i = 0; i < r.message[0].length; i++) {
				var child=frm.add_child("items");
				child.container=r.message[0][i]['name']
				child.current_qty=r.message[0][i]['primary_available_qty']
				child.uom=r.message[1]['stock_uom']
				//stock UOM
				child.stock_uom=r.message[1]['stock_uom']
				child.stock_qty=r.message[0][i]['primary_available_qty']
				//Secondary UOM
				child.secondary_uom=r.message[1]['secondary_uom']
				child.secondary_qty=r.message[0][i]['secondary_available_qty']
				
			}
			cur_frm.refresh_field("items")
			frm.set_value('secondary_conversion_factor',r.message[1]['secondary_conversion_factor'])
			frm.set_value('current_qty',r.message[2])
			frm.set_value('qty_after_reconciliation',r.message[2])
			
			cur_frm.refresh_field("secondary_conversion_factor")
			cur_frm.refresh_field("tertiary_conversion_factor")
		}
	})
}

function add_serial_nos(item,frm){
	if(frm.doc.item_code && frm.doc.warehouse && frm.doc.docstatus==0){
		frm.add_custom_button(__('Add Containers'), function () {
			var d = new frappe.ui.Dialog({
			title: __('Add new Containers'),
			fields: [
				{
					"label" : "No of New Containers to be created",
					"fieldname": "serial_no_count",
					"fieldtype": "Int",
					"reqd": 1
				}
			],
			primary_action: function() {
				var data = d.get_values();
				frappe.call({
			method: "container.container.doctype.container_reconciliation.container_reconciliation.get_new_containers",
			args:{
				item:frm.doc.item_code,
				count:data.serial_no_count

			},
			callback:function(r){
				frm.clear_table("new_container_nos");
				for (let i = 0; i < r.message[0].length; i++) {
					var child=frm.add_child("new_container_nos");
					child.container=r.message[0][i]
					//stock UOM
					child.stock_uom=r.message[1]['stock_uom']
					child.stock_qty=1
					//Secondary UOM
					child.secondary_uom=r.message[1]['secondary_uom']
					child.secondary_qty=1/frm.doc.secondary_conversion_factor
					
				}
				cur_frm.refresh_field("new_container_nos")
				var total_qty=0
				$.each(frm.doc.items, function (idx,item) {
					total_qty=total_qty+item.stock_qty
				})
				$.each(frm.doc.new_container_nos, function (idx,item) {
					total_qty=total_qty+item.stock_qty
				})
			frm.set_value('qty_after_reconciliation',total_qty)
			cur_frm.refresh_field("qty_after_reconciliation")
			d.hide();
			}
		})
			},
			primary_action_label: __('Add')
		});
		d.show();
				});
	 }
	

}

frappe.ui.form.on('Container Reconciliation Items', {
	stock_qty(frm,cdt,cdn) {
		var item=locals[cdt][cdn];
		// your code here
		if(item.stock_qty<0){
			item.stock_qty=0
			cur_frm.refresh_field("items")
			frappe.throw('Qty cannot be less than Zero ')
		}
		else{
			item.secondary_qty=item.stock_qty/frm.doc.secondary_conversion_factor
			cur_frm.refresh_field("items")
			var total_qty=0
				$.each(frm.doc.items, function (idx,item) {
					total_qty=total_qty+item.stock_qty
				})
				$.each(frm.doc.new_container_nos, function (idx,item) {
					total_qty=total_qty+item.stock_qty
				})
			frm.set_value('qty_after_reconciliation',total_qty)
			cur_frm.refresh_field("qty_after_reconciliation")
		}
	}
})


frappe.ui.form.on('Container Reconciliation Items Add', {
	stock_qty(frm,cdt,cdn) {
		var item=locals[cdt][cdn];
		// Add new Conatiners with for additional stock
		if(item.stock_qty<0){
			item.stock_qty=0
			cur_frm.refresh_field("items")
			frappe.throw('Qty cannot be less than Zero ')
		}
		else{
			item.secondary_qty=item.stock_qty/frm.doc.secondary_conversion_factor
			cur_frm.refresh_field("items")
			var total_qty=0
				$.each(frm.doc.items, function (idx,item) {
					total_qty=total_qty+item.stock_qty
				})
				$.each(frm.doc.new_container_nos, function (idx,item) {
					total_qty=total_qty+item.stock_qty
				})
			frm.set_value('qty_after_reconciliation',total_qty)
			cur_frm.refresh_field("qty_after_reconciliation")
		}
	}
})