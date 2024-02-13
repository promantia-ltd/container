frappe.ui.form.on('Stock Entry', {
    onload:function(frm){
        let finished_item=""
		if(frm.doc.__islocal==1){
		frappe.db.get_value("Work Order",frm.doc.work_order,["source_warehouse","wip_warehouse"],(w)=>{
			if(frm.doc.docstatus==0){
				frm.set_value("from_warehouse",w.source_warehouse)
			}
		if(frm.doc.stock_entry_type=="Material Transfer for Manufacture"){
		const container_used=[];
			if(frm.doc.bom_no){
				frappe.db.get_value("BOM",frm.doc.bom_no,"quantity",(c)=>{
					frappe.model.with_doc("BOM", frm.doc.bom_no, function() {
					cur_frm.clear_table("items");
					let warehouse_list=[]
					let target_warehouse=""
					let tabletransfer= frappe.model.get_doc("BOM", frm.doc.bom_no)
						$.each(tabletransfer.items, function(index, detail){	
							for (let i=0;i<detail.no_of_inputs;i++){
							target_warehouse=""
							frappe.call({
								method:"container.container.doctype.stock_entry.stock_entry.get_target_warehouses",
								args:{
									operation:detail.operation,
									work_order:frm.doc.work_order,
									warehouse_list:warehouse_list,
									wip_warehouse:w.wip_warehouse,
									item:detail.item_code
								},
								async:false,
								callback: function(r){
									target_warehouse=r.message
									warehouse_list.push(target_warehouse)
								}
							})

						frappe.call({
								method:"container.container.doctype.stock_entry.stock_entry.get_container_no",
								args:{
									item:detail.item_code,
									warehouse:w.source_warehouse,
									t_warehouse:target_warehouse,
									qty:((detail.stock_qty/c.quantity)*frm.doc.fg_completed_qty)/detail.no_of_inputs,	
									container_used:container_used,
									uom:detail.uom,
									work_order:frm.doc.work_order
								},
								async:false,
								callback: function(r){
									if(r.message.target || r.message.source){
										if (r.message.target && r.message.source && r.message.partially_reserved){
											// this partially reserved target
											if (r.message.target.container_no){
												container_used.push(r.message.target.container_no)
												let child=frm.add_child("reserved_items");
												child.s_warehouse=r.message.target.s_warehouse;
												child.t_warehouse=r.message.target.t_warehouse;
												child.item_code=detail.item_code;
												child.item_name=detail.item_name;
												child.required_qty=(detail.stock_qty/c.quantity)*frm.doc.fg_completed_qty/detail.no_of_inputs;
												child.basic_rate=detail.rate;
												child.uom=detail.uom;
												child.stock_uom=detail.stock_uom;
												child.conversion_factor=detail.conversion_factor;
												child.transfer_qty=detail.stock_qty;
												let container_no="";
												let qty=0;
												let available_qty_use="";
												let available_qty="";
												for (let i = 0; i < r.message.target.container_no.length; i++) {
													container_no=container_no+String(r.message.target.container_no[i])+","
													available_qty=available_qty+String(r.message.target.primary_available_qty[i])+","
													available_qty_use=available_qty_use+String(r.message.target.primary_available_qty_used[i])+","
													qty=qty + r.message.target.qty_in_bom_uom[i]
												}
												child.containers=container_no
												child.qty=qty
												child.available_qty=available_qty
												child.remaining_qty=r.message.target.remaining_qty
												child.available_qty_use=available_qty_use
											}

											// this partially reserved source
											if (r.message.source.container_no){
												container_used.push(r.message.source.container_no)
												let child=frm.add_child("items");
												child.s_warehouse=r.message.source.s_warehouse;
												child.t_warehouse=r.message.source.t_warehouse;
												child.item_code=detail.item_code;
												child.item_name=detail.item_name;
												child.basic_rate=detail.rate;
												child.uom=detail.uom;
												child.stock_uom=detail.stock_uom;
												child.conversion_factor=detail.conversion_factor;
												child.transfer_qty=detail.stock_qty;
												let container_no="";
												let qty=0;
												let available_qty_use="";
												let available_qty="";
												let required_qty = 0;
												for (let i = 0; i < r.message.source.container_no.length; i++) {
													container_no=container_no+String(r.message.source.container_no[i])+",";
													available_qty=available_qty+String(r.message.source.primary_available_qty[i])+",";
													available_qty_use=available_qty_use+String(r.message.source.primary_available_qty_used[i])+",";
													qty=qty + r.message.source.qty_in_bom_uom[i];
													required_qty = required_qty + r.message.source.primary_available_qty_used[i]
												}
												child.containers=container_no;
												child.qty=qty;
												child.available_qty=available_qty;
												child.remaining_qty=r.message.source.remaining_qty;
												child.available_qty_use=available_qty_use;
												child.required_qty = required_qty;

												}
										}
									// this is completely reserved at target
									if(r.message.target && r.message.complete_reserved_at_target == 1){
										container_used.push(r.message.target.container_no)
										let child=frm.add_child("items");
										child.s_warehouse=r.message.target.s_warehouse;
										child.t_warehouse=r.message.target.t_warehouse;
										child.item_code=detail.item_code;
										child.item_name=detail.item_name;
										child.required_qty=(detail.stock_qty/c.quantity)*frm.doc.fg_completed_qty/detail.no_of_inputs;
										child.basic_rate=detail.rate;
										child.uom=detail.uom;
										child.stock_uom=detail.stock_uom;
										child.conversion_factor=detail.conversion_factor;
										child.transfer_qty=detail.stock_qty;
										let container_no="";
										let qty=0;
										let available_qty_use="";
										let available_qty="";
										for (let i = 0; i < r.message.target.container_no.length; i++) {
											container_no=container_no+String(r.message.target.container_no[i])+","
											available_qty=available_qty+String(r.message.target.primary_available_qty[i])+","
											available_qty_use=available_qty_use+String(r.message.target.primary_available_qty_used[i])+","
											qty=qty + r.message.target.qty_in_bom_uom[i]
										}
										child.containers=container_no
										child.qty=qty
										child.available_qty=available_qty
										child.remaining_qty=r.message.target.remaining_qty
										child.available_qty_use=available_qty_use
									}
									// this completly reserved at source
									else if(r.message.source && r.message.complete_reserved_at_target == 0 && !(r.message.target)) {
										container_used.push(r.message.source.container_no)
										let child=frm.add_child("items");
										child.s_warehouse=r.message.source.s_warehouse;
										child.t_warehouse=r.message.source.t_warehouse;
										child.item_code=detail.item_code;
										child.item_name=detail.item_name;
										child.required_qty=(detail.stock_qty/c.quantity)*frm.doc.fg_completed_qty/detail.no_of_inputs;
										child.basic_rate=detail.rate;
										child.uom=detail.uom;
										child.stock_uom=detail.stock_uom;
										child.conversion_factor=detail.conversion_factor;
										child.transfer_qty=detail.stock_qty;
										let container_no="";
										let qty=0;
										let available_qty_use="";
										let available_qty="";
										for (let i = 0; i < r.message.source.container_no.length; i++) {
											container_no=container_no+String(r.message.source.container_no[i])+","
											available_qty=available_qty+String(r.message.source.primary_available_qty[i])+","
											available_qty_use=available_qty_use+String(r.message.source.primary_available_qty_used[i])+","
											qty=qty + r.message.source.qty_in_bom_uom[i]
										}
										child.containers=container_no
										child.qty=qty
										child.available_qty=available_qty
										child.remaining_qty=r.message.source.remaining_qty
										child.available_qty_use=available_qty_use
									}
									
									frm.refresh_field("reserved_items")
									}
									else{
										var child=frm.add_child("items");
										child.s_warehouse=frm.doc.from_warehouse;
										child.t_warehouse=target_warehouse;
										child.item_code=detail.item_code;
										child.item_name=detail.item_name;
										child.required_qty=((detail.stock_qty/c.quantity)*frm.doc.fg_completed_qty)/detail.no_of_inputs;
										child.qty=((detail.stock_qty/c.quantity)*frm.doc.fg_completed_qty)/detail.no_of_inputs;
										child.basic_rate=detail.rate;
										child.uom=detail.stock_uom;
										child.conversion_factor=detail.conversion_factor;
										child.transfer_qty=detail.stock_qty;
									}
							}
							});
						}
						})
					})
				})
			}
		}
		})
		}
		frappe.db.get_value("Work Order",frm.doc.work_order,["source_warehouse","wip_warehouse"],(w)=>{
		if(frm.doc.stock_entry_type=="Manufacture"){
			var container_used=[];
			if(frm.doc.__islocal==1){
				if(frm.doc.bom_no){
					frappe.db.get_value("BOM",frm.doc.bom_no,"quantity",(c)=>{
						frappe.model.with_doc("BOM", frm.doc.bom_no, function() {
							$.each(frm.doc.items, function(idx, item){
								if(item.is_finished_item==1){
									finished_item=item
								}
							})

						cur_frm.clear_table("items");
						let warehouse_list=[]
						let target_warehouse=""
						var tabletransfer= frappe.model.get_doc("BOM", frm.doc.bom_no)
							$.each(tabletransfer.items, function(index, detail){	
							for(let i=0;i<detail.no_of_inputs;i++){
								target_warehouse=""
								frappe.call({
									method:"container.container.doctype.stock_entry.stock_entry.get_target_warehouses",
									args:{
										operation:detail.operation,
										work_order:frm.doc.work_order,
										warehouse_list:warehouse_list,
										wip_warehouse:w.wip_warehouse,
										item:detail.item_code
									},
									async:false,
									callback: function(r){
										target_warehouse=r.message
										warehouse_list.push(target_warehouse)
									}
								})

							frappe.call({
									method:"container.container.doctype.stock_entry.stock_entry.get_item_container_no",
									args:{
										item:detail.item_code,
										warehouse:target_warehouse,
										qty:((detail.stock_qty/c.quantity)*frm.doc.fg_completed_qty)/detail.no_of_inputs,
										work_order:frm.doc.work_order,
										container_used:container_used,
										uom:detail.uom
									},
									async:false,
									callback: function(r){
										if(r.message!=false){
										container_used.push(r.message[0])
										var child=frm.add_child("items");
										child.s_warehouse=target_warehouse;
										child.item_code=detail.item_code;
										child.item_name=detail.item_name;
										child.required_qty=((detail.stock_qty/c.quantity)*frm.doc.fg_completed_qty)/detail.no_of_inputs;
										child.qty=((detail.stock_qty/c.quantity)*frm.doc.fg_completed_qty)/detail.no_of_inputs;
										child.basic_rate=detail.rate;
										child.uom=detail.stock_uom;
										child.stock_uom=detail.stock_uom;
										child.conversion_factor=1;
										child.transfer_qty=detail.stock_qty;
										var uom_conversion_factor=1
										frappe.model.with_doc("Item", child.item_code, function() {
											var tabletransfer= frappe.model.get_doc("Item", child.item_code)
												$.each(tabletransfer.uoms, function(index, uom_detail){
													if(uom_detail.uom!=child.uom){
														uom_conversion_factor=uom_detail.conversion_factor
										var item_qty=child.qty/uom_conversion_factor;
										
									let container_no=""
									let available_qty_use=""
									let available_qty=""
									for (let i = 0; i < r.message[0].length; i++) {
										container_no=container_no+String(r.message[0][i])+","
										available_qty=available_qty+String(r.message[1][i])+","
										available_qty_use=available_qty_use+String(r.message[3][i])+","
									}
									child.containers=container_no
									child.available_qty=available_qty
									child.remaining_qty=r.message[2]
									child.available_qty_use=available_qty_use
									
													}
	
												})
										})	
									}
									else{
									
										var child=frm.add_child("items");
										child.s_warehouse=target_warehouse;
										child.item_code=detail.item_code;
										child.item_name=detail.item_name;
										child.qty=((detail.stock_qty/c.quantity)*frm.doc.fg_completed_qty)/detail.no_of_inputs;
										child.basic_rate=detail.rate;
										child.uom=detail.stock_uom;
										child.conversion_factor=detail.conversion_factor;
										child.transfer_qty=detail.stock_qty;
									}
								}
								});
							}
							})
							var fin_child=frm.add_child("items");
							fin_child.t_warehouse=finished_item.t_warehouse;
							fin_child.is_finished_item=finished_item.is_finished_item;
							fin_child.item_code=finished_item.item_code;
							fin_child.item_name=finished_item.item_name;
							fin_child.qty=finished_item.qty;
							fin_child.basic_rate=finished_item.basic_rate;
							fin_child.uom=finished_item.uom;
							fin_child.stock_uom=finished_item.uom;
							fin_child.conversion_factor=finished_item.conversion_factor;
							fin_child.transfer_qty=finished_item.transfer_qty;
						})
						// frm.refresh_field("information_of_containers_assigned")

					})
				}
			}
			}
		});
    },
	assign_containers:function(frm){
		let used=[];
		if(frm.doc.items && frm.doc.docstatus==0 && frm.doc.stock_entry_type!="Manufacture"){
		$.each(frm.doc.items,function(idx, row){
		frappe.call({
			method:"container.container.doctype.stock_entry.stock_entry.assign_containers",
			args:{
				item:row,
				used:used,
				work_order:frm.doc.work_order
			},
			async:false,
			callback: function(r){
				if(r.message){
					let container_no="";	
					let available_qty_use="";
					let available_qty="";
					for (let i = 0; i < r.message[0].length; i++) {
						container_no=container_no+String(r.message[0][i])+","
						available_qty=available_qty+String(r.message[1][i])+","
						available_qty_use=available_qty_use+String(r.message[3][i])+","
					}
					used.push(container_no);
					row["containers"]=container_no;
					row["available_qty"]=available_qty;
					row["remaining_qty"]=r.message[2];
					row["available_qty_use"]=available_qty_use;
					row["required_qty"]=row["qty"];
					row["qty"]=r.message[4];
					// $.each(frm.doc.information_of_containers_assigned,function(id,detail){
					// 	if (detail["idx"]==row["idx"] && detail["item_code"]==row["item_code"]){
					// 		detail["containers"]=container_no
					// 	}
					// })
				}
				frm.refresh_field("items")
				// frm.refresh_field("information_of_containers_assigned")
				
			}
		});
	})
	}
	else if(frm.doc.docstatus==1){
		frappe.msgprint("Sorry,you can not assign containers for submited document.")
	}else if(frm.doc.stock_entry_type=="Manufacture"){
		frappe.msgprint("Assign containers disabled for manufacture entry.")
	}

	},
	on_submit:function(frm){
		// slit raw material containers
		if (frm.doc.stock_entry_type=="Manufacture"){
		frappe.call({
			method:"container.container.doctype.stock_entry.stock_entry.slit_container_and_unreserve_container",
			args:{
				self:frm.doc
			},
			async:false,
			callback: function(r){
				
			}
		})
		}
	},
	custom_material_return:function(frm,cdt,cdn){
		if(frm.doc.custom_material_return==1){
			frm.set_value('stock_entry_type','Material Transfer')
			frm.set_value('custom_transfer_type','Material Return')
		}
		else{
			frm.set_value('stock_entry_type','')
			frm.set_value('custom_transfer_type','')
		}
	},
	custom_scrap_entry:function(frm,cdt,cdn){
		if(frm.doc.custom_scrap_entry==1){
			frm.set_value('stock_entry_type','Material Transfer')
			frm.set_value('custom_transfer_type','Scrap Entry')
			frappe.db.get_value("Warehouse",{"custom_rejected_warehouse":1},["name"],(w)=>{
				if(w.name){
					frm.set_value('to_warehouse',w.name)
				}
			})
		}
		else{
			frm.set_value('stock_entry_type','')
			frm.set_value('custom_transfer_type','')
		}
	},
	custom_workstation:function(frm,cdt,cdn){
		frm.set_query("custom_return_source_warehouse", function() {
			return {
					query: "container.container.doctype.stock_entry.stock_entry.fetch_return_source_warehouse",
					filters:{
						"workstation":frm.doc.custom_workstation
					}
			};
		});
		frm.set_query("custom_return_item_code", function() {
			return {
					query: "container.container.doctype.stock_entry.stock_entry.fetch_item_code",
					filters:{
						"workstation":frm.doc.custom_workstation
					}
			};
		});
		frm.set_query("custom_return_container", function() {
			return {
					query: "container.container.doctype.stock_entry.stock_entry.fetch_container",
					filters:{
						"workstation":frm.doc.custom_workstation
					}
			};
		});
	},
	custom_get_items_for_material_return:function(frm,cdt,cdn){
		get_transfer_records(frm,cdt,cdn)
	},
	custom_get_items_for_scrap_transfer:function(frm,cdt,cdn){
		get_transfer_records(frm,cdt,cdn)
	}
});

function get_transfer_records(frm,cdt,cdn){
	if(!frm.doc.custom_workstation){
		frappe.throw('Please select a Worksttaion')
	}
	else{
		frappe.call({
			method:"container.container.doctype.stock_entry.stock_entry.fetch_stock_transfer_records",
					args:{
						workstation:frm.doc.custom_workstation,
						return_warehouse:frm.doc.custom_return_source_warehouse,
						item_code:frm.doc.custom_return_item_code,
						return_container:frm.doc.custom_return_container,
						transfer_type: frm.doc.custom_transfer_type
					},
					async:false,
					callback: function(r){
						cur_frm.clear_table("items");
						for (let i=0;i<r.message.length;i++)
						{
							var child = cur_frm.add_child("items");
							child.s_warehouse=r.message[i]['source_warehouse']
							child.t_warehouse=frm.doc.to_warehouse
							child.item_code=r.message[i]['item_code']
							child.qty=r.message[i]['qty']
							frappe.model.set_value('Stock Entry Detail', child.name, "uom", r.message[i]['uom']);
							frappe.model.set_value('Stock Entry Detail', child.name, "stock_uom", r.message[i]['uom']);

							//child.uom=r.message[i]['uom']
							child.containers=r.message[i]['container']
						}
						cur_frm.refresh_field("items")
					}
			});
	}
}


frappe.ui.form.on('Stock Entry Detail', {
	// item_code: function(frm, cdt, cdn){
	// 	var row = locals[cdt][cdn];
    //     frappe.utils.sleep(500).then(() => {
    //         frappe.call({
    //             args:{
    //                 doc:frm.doc,
    //                 item_code: row.item_code,
    //                 uom: row.uom
    //             },
    //             method:"container.container.doctype.purchase_order.purchase_order.update_standard_rates",
    //             async:false,
    //             callback: function(r){
    //                 if(r.message){
    //                     row.custom_standard_rate = r.message['rate']
    //                     cur_frm.refresh_field("rate");
    //                 }
    //                 else {
    //                     row.custom_standard_rate = 0.0
    //                     cur_frm.refresh_field("rate");
    //                 }
    //             }
    //         });
    //     });
    // },
	change_containers:function(frm,cdt,cdn){
		if (frm.doc.docstatus ==0){
		let data=locals[cdt][cdn];
		let all_containers=[];
		$.each(frm.doc.items,function(idx, row){
			if (row.containers){
				let str_containers=row.containers;
				if (str_containers.endsWith(",")){
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
				warehouse:data.s_warehouse,
				item_code:data.item_code,
				status:"Active",
				primary_available_qty:undefined,
				selected:undefined
			},
			add_filters_group: 1,
			primary_action_label: "Set Containers",
			columns: ["warehouse","item_code","status","primary_available_qty","selected"],
			get_query() {
				return {
					filters: {
						docstatus: ['!=', 2],
						status: ['=', 'Active'],
						warehouse: ["=", data.s_warehouse],
						item_code: ["=", data.item_code],
						primary_available_qty: [">", 0]

					}
				};
			},
			action(selections) {
				if (selections.length === 0) {
					frappe.throw(__("Please select {0}", ["Containers"]))
				}
				frappe.call({
					method:"container.container.doctype.stock_entry.stock_entry.change_containers",
					args:{
						selected_containers:selections,
						item:data
					},
					async:false,
					callback: function(r){
						if(r.message){
							frappe.model.set_value(cdt,cdn,"containers",r.message[0][0])
							frappe.model.set_value(cdt,cdn,"available_qty",r.message[0][1])
							frappe.model.set_value(cdt,cdn,"available_qty_use",r.message[0][2])
							frappe.model.set_value(cdt,cdn,"remaining_qty",r.message[1])
							frappe.model.set_value(cdt,cdn,"qty",r.message[2][0])
							// $.each(frm.doc.information_of_containers_assigned,function(idx, row){
							// 	if (row['item_code']==data.item_code && row['input_sources']==data.t_warehouse){
							// 		row['containers']=r.message[0][0]
							// 		row["input_sources"]=data.t_warehouse
							// 	}
							// 	frm.refresh_field("information_of_containers_assigned")
							// })
						}
						else{
							frm.reload_doc()
						}
					}
				});
				d.dialog.hide();
			}
		});
	}
	else if(frm.doc.docstatus ==1){
		frappe.msgprint("Sorry,you can not change containers for submited document")
	}
	else if(frm.doc.docstatus ==2){
		frappe.msgprint("Sorry,you can not change containers for cancelled document")
	}
	},
	change_qty:function(frm,cdt,cdn){
		let data=locals[cdt][cdn];
		let containers=data.containers.split(",")
		let available_qty=data.available_qty.split(",");
		let available_qty_use=data.available_qty_use.split(",");
		let container_no_dict_total=[]

		for (let i = 0; i < containers.length-1; i++) {
			let container_no_dict=[{'container_no':containers[i],'qty':available_qty_use[i],'available_qty':available_qty[i]}]
			container_no_dict_total=container_no_dict_total.concat(container_no_dict)
		}
		let fields1 = [];
		fields1 = [
			{
				label: 'Container',
				fieldname: 'container_no',
				fieldtype: 'Link',
				options: 'Container',
				in_list_view: 1,
			    columns:3,
				reqd:1,
				read_only:1
			},
			{
				label: 'Container Qty',
				fieldname: 'available_qty',
				fieldtype: 'Data',
				in_list_view: 1,
				reqd:1,
				columns:3,
				default:0,
				read_only:1
			},
			{
				label: 'Change Qty',
				fieldname: 'qty',
				fieldtype: 'Float',
				in_list_view: 1,
				reqd:1,
				default:0,
				columns:3
			}
		]
		let fields = [{
			label: 'Containers To Change The Qty',
			fieldtype: 'Table',
			fieldname: 'container_qty_change',
			fields: fields1,
			cannot_add_rows: true,
			cannot_delete_rows: 1,
			in_place_edit: true,
			read_only: 1,
			data:container_no_dict_total
		}]
		let d = new frappe.ui.Dialog({
			size:"small",
			title: 'Change the Qty Of Containers',
			fields: fields,
			primary_action_label: 'Change Qty',
			primary_action() {
				let data1 = d.get_values();
				frappe.call({
				method:"container.container.doctype.stock_entry.stock_entry.change_container_qty",
					args:{
						data:data1,
						item_name:data.name,
					},
					async:false,
					callback: function(r){
						if(r.message){
							frappe.model.set_value(cdt,cdn,"available_qty_use",r.message[0])
							frappe.model.set_value(cdt,cdn,"qty",r.message[1])
							frappe.model.set_value(cdt,cdn,"remaining_qty",r.message[2])
						}
						else{
							frm.reload_doc()
						}
						msgprint("Qty Changed Successfully")
					}
				});
				d.hide();
				
			}
		});
		d.show();

	}
})