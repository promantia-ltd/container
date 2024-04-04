
 frappe.ui.form.on('Work Order', {
	refresh:function(frm){
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
	
// 		frappe.db.get_value('Stock Settings', {name: 'Stock Settings'}, 'default_warehouse', (r) => {
// 			frm.set_value("source_warehouse",r.default_warehouse)
// 		})
// 		if(frm.doc.docstatus==1){
// 			let stock_avail_qty=0;
// 			let item_count=0;
// 			let check_stock=0;
// 			const container_used=[];
// 			const container_reserved_used=[]
// 			frm.remove_custom_button('Start');
// 			const show_start_btn = (frm.doc.skip_transfer
// 							|| frm.doc.transfer_material_against == 'Job Card') ? 0 : 1;
// 			if (show_start_btn) {
// 				if ((flt(frm.doc.material_transferred_for_manufacturing) < flt(frm.doc.qty))
// 						&& frm.doc.status != 'Stopped') {
// 							frm.has_start_btn = true;
// 							frm.add_custom_button('Start', function(){
// 				if(frm.doc.bom_no){
// 						let comment="Reserved Qty<br>"
// 						frappe.db.get_value("BOM",frm.doc.bom_no,"quantity",(c)=>{
// 								let warehouse_list=[]
// 								let target_warehouse=""
// 						frappe.model.with_doc("BOM", frm.doc.bom_no, function() {
// 				           			let tabletransfer= frappe.model.get_doc("BOM", frm.doc.bom_no)
// 						$.each(tabletransfer.items, function(index, row){
// 							for (var i=0;i<row.no_of_inputs;i++){
// 							target_warehouse=""
// 							if(row.operation==undefined){
// 								frappe.throw("Please Mention Operation in Bom Item")
// 							}
// 							frappe.call({
// 								method:"container.container.doctype.stock_entry.stock_entry.get_target_warehouses",
// 									args:{
// 										work_order:frm.doc.name,
// 										warehouse_list:warehouse_list,
// 										operation:row.operation,
// 										wip_warehouse:frm.doc.wip_warehouse,
// 										item:row.item_code
// 									},
// 									async:false,
// 									callback: function(r){
// 										target_warehouse=r.message
// 										warehouse_list.push(target_warehouse)
// 									}
// 								})
// 							item_count+=1;
// 							frappe.call({
// 							method:"container.container.doctype.work_order.work_order.check_stock",
// 							args:{
// 								item:row.item_code,				
// 								warehouse:target_warehouse,
// 								item_qty:((row.stock_qty/c.quantity)*(frm.doc.qty-frm.doc.material_transferred_for_manufacturing))/row.no_of_inputs,
// 								container_used:container_used,
// 								work_order:frm.doc.name								
// 								},
// 								async:false,
// 								callback: function(r){
// 								if (r.message != undefined && r.message[1].length > 0){
// 									container_used.push(r.message[1])
// 								}
// 								if(r.message != undefined && r.message[0]==true){
// 									check_stock+=1;
// 								}
												
// 								}
// 							});
// 						}
// 						})
// 						if(check_stock==item_count){
// 							let warehouse_list_stock=[]
// 							let target_warehouse_stock=""
// 				           	$.each(tabletransfer.items, function(index, row){
// 							for (var i=0;i<row.no_of_inputs;i++){
// 							target_warehouse_stock=""
// 							frappe.call({
// 								method:"container.container.doctype.stock_entry.stock_entry.get_target_warehouses",
// 								args:{
// 									operation:row.operation,
// 									work_order:frm.doc.name,
// 									warehouse_list:warehouse_list_stock,
// 									wip_warehouse:frm.doc.wip_warehouse,
// 									item:row.item_code
// 									},
// 									async:false,
// 									callback: function(r){
// 										target_warehouse_stock=r.message
// 										warehouse_list_stock.push(target_warehouse_stock)
// 									}
// 								})
// 							frappe.call({
// 								method:"container.container.doctype.work_order.work_order.reserve_qty",
// 								args:{
// 									item:row.item_code,				
// 									warehouse:target_warehouse_stock,
// 									item_qty:((row.qty/c.quantity)*(frm.doc.qty-frm.doc.material_transferred_for_manufacturing))/row.no_of_inputs,
// 									work_order:frm.doc.name,
// 									container_reserved_used:container_reserved_used
// 								},
// 								async:false,
// 								callback: function(r){
// 									if (r.message[2].length !=0){
// 										container_reserved_used.push(r.message[2])
// 									}
// 									if(r.message.length==3){
// 										comment=comment.concat(r.message[0])
// 										stock_avail_qty+=1;	
// 									}			
// 									}
// 								});
// 							}
// 							})
// 							frm.remove_custom_button('Start');
// 								}
// 								else{
// 									erpnext.work_order.make_se(frm, 'Material Transfer for Manufacture');
// 								}
// 						if(item_count==stock_avail_qty){
// 							frappe.call({
// 								method:"container.container.doctype.work_order.work_order.add_comment",
// 								args:{
// 									doctype:"Work Order",
// 									docname:frm.doc.name,
// 									comment:comment	
// 								},
// 								async:false,
// 								callback: function(r){
// 								}
// 							});
// 							msgprint('<b>Stock Reserved Successfully</b><br>'+comment,'Alert')
// 							frappe.call({
// 		                                async: false,
// 		                                "method": "frappe.client.set_value",
// 		                                "args": {
// 		                                        "doctype": "Work Order",
// 		                                        "name": frm.doc.name,
// 		                                        "fieldname": "skip_material_transfer",
// 		                                        "value":1
// 		                                    }
// 		                                });
// 									}
// 								})
								
// 							})
							
// 						}
						
						
// 					}).addClass('btn-primary');
					 
// 				}
// 				}
// 				}
		    }
 })
