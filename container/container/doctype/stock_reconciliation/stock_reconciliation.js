// Copyright (c) 2020, seabridge_app and contributors
// For license information, please see license.txt
frappe.ui.form.on('Stock Reconciliation', {
	refresh(frm){
		if(frm.doc.docstatus==1){
		cur_frm.page.btn_secondary.hide()
		}
		//commented some code as need it is a part of hotset, will be used if required
		// frappe.db.get_value("Hotset Settings","Hotset Settings", "allow_reconciliation",(s)=>{
		// 	if(s.allow_reconciliation==1){
		// 	frm.fields_dict['items'].grid.get_field('item_code').get_query = function(frms, cdt, cdn) {
			
		// 		return {
		// 			filters: {
		// 				'has_serial_no': 0
		// 			}	
		// 		};
		// 	}
		// }
		// })
		

	},
	before_save(frm){
		if(!frm.doc.custom_container_reconciliation){
			// frappe.db.get_value("Hotset Settings","Hotset Settings", "allow_reconciliation",(s)=>{
			// 	if(s.allow_reconciliation==1){
					$.each(frm.doc.items, function(idx, item){
						frappe.db.get_value("Item",item.item_code, "is_containerized",(s)=>{
							if(s.is_containerized==1){
								frappe.validated = false;
								frappe.throw('Please create a Container Reconciliation Document to reconcile the Containerized Items')
							}
						})
					})
			// 	}
			// })
		}
	else{
		$.each(frm.doc.items, function(idx, item){
			frappe.db.get_value("Item",item.item_code, "is_containerized",(s)=>{
				if(s.is_containerized==1){
					frappe.db.get_value("Container Reconciliation",frm.doc.custom_container_reconciliation, ["item_code","qty_after_reconciliation"],(r)=>{
						if(r.item_code==item.item_code){
							frappe.call({
								method: "container.container.doctype.stock_reconciliation.stock_reconciliation.get_container_data",
								args:{
									docname:frm.doc.custom_container_reconciliation
								},
								callback:function(r){
										item.qty=r.message[3]
										item.custom_containers=r.message[2]
									frm.refresh_field("items")
								}
							})
						}
					})
					}
			})
		})

	}
	},
	onload(frm){
		if(frm.doc.custom_container_reconciliation && frm.doc.__islocal){
			frm.clear_table("items");
			frappe.call({
				method: "container.container.doctype.stock_reconciliation.stock_reconciliation.get_container_data",
				args:{
					docname:frm.doc.custom_container_reconciliation
				},
				callback:function(r){
						var child=frm.add_child("items");
					child.item_code=r.message[0]
						child.custom_is_containerized=1
						child.warehouse=r.message[1]
						child.qty=r.message[3]
						child.custom_containers=r.message[2]
						
					frm.refresh_field("items")
				}
			})
		}

	}

	
})
frappe.ui.form.on('Stock Reconciliation Item', {
	item_code(frm,doctype,name){
		// frappe.db.get_value("Hotset Settings","Hotset Settings", "allow_reconciliation",(s)=>{
			// if(s.allow_reconciliation==1){
				var row = locals[doctype][name];
				frappe.db.get_value("Item",row.item_code, "is_containerized",(s)=>{
					if(s.is_containerized==1){
						frappe.throw('Please create a Container Reconciliation Document to reconcile the Containerized Items')
					}
				})
			// }
		// })
	}
})
