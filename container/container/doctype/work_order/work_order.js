frappe.ui.form.on('Work Order', {
	refresh:function(frm){
		// Release all container reservations held by this submitted Work Order
		if(frm.doc.docstatus==1){
			frm.add_custom_button('Unreserve Stock', function(){
				frappe.call({
					method:"container.container.doctype.work_order.work_order.unreserve_stock",
					args:{
						work_order:frm.doc.name
					},
					async:false,
					callback: function(r){

					}
				})
			})
		}
		// Rebuild the reserved-containers table: delete existing rows, then regenerate from Stock Details
		frm.add_custom_button(__('Update Reserved Containers Data'), function() {
			if(frm.doc.docstatus==1){
				frappe.call({
					method:"container.container.doctype.work_order.work_order.delete_reserved_containers",
					args:{
						work_order:frm.doc.name
					},
					async:false,
					callback: function(r){

					}
				})
				frappe.call({
					method:"container.container.doctype.work_order.work_order.update_reserved_containers",
					args:{
						work_order:frm.doc.name
					},
					async:false,
					callback: function(r){
						frappe.msgprint('Updated')
					}
				})
			}
		})
	}
})
