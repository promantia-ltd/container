// Copyright (c) 2024, Mohan and contributors
// For license information, please see license.txt

// Copyright (c) 2023, Mohan and contributors
// For license information, please see license.txt

frappe.ui.form.on('Container', {
	onload: function(frm) {
		var today = frappe.datetime.get_today();
		if (frm.doc.base_expiry_date && frm.doc.expiry_date){
			let base_expiry_date_in_days = frappe.datetime.get_diff(frm.doc.base_expiry_date, today);
			let rt_expiry_date_in_days=frappe.datetime.get_diff(frm.doc.expiry_date, today);
			if (frm.doc.base_expiry_date_in_days !=base_expiry_date_in_days && frm.doc.rt_expiry_date_in_days !=rt_expiry_date_in_days){
				frm.set_value("base_expiry_date_in_days",base_expiry_date_in_days);
				frm.set_value("rt_expiry_date_in_days",rt_expiry_date_in_days);
				frm.save()
			}
		}
		else if (frm.doc.expiry_date){
			let rt_expiry_date_in_days=frappe.datetime.get_diff(frm.doc.expiry_date, today);
			if (frm.doc.rt_expiry_date_in_days !=rt_expiry_date_in_days){
				frm.set_value("rt_expiry_date_in_days",rt_expiry_date_in_days);
				frm.save()
			}
		}
	},
	base_expiry_date:function(frm){
		calculate_base_and_room_temp_in_days(frm)
	},
	expiry_date:function(frm){
		calculate_base_and_room_temp_in_days(frm)
	}
});

function calculate_base_and_room_temp_in_days(frm){
	var today = frappe.datetime.get_today();
		if (frm.doc.base_expiry_date && frm.doc.expiry_date){
			let base_expiry_date_in_days = frappe.datetime.get_diff(frm.doc.base_expiry_date, today);
			let rt_expiry_date_in_days=frappe.datetime.get_diff(frm.doc.expiry_date, today);
			frm.set_value("base_expiry_date_in_days",base_expiry_date_in_days);
			frm.set_value("rt_expiry_date_in_days",rt_expiry_date_in_days);
		}
		else if(frm.doc.base_expiry_date){
			let base_expiry_date_in_days = frappe.datetime.get_diff(frm.doc.base_expiry_date, today);
			frm.set_value("base_expiry_date_in_days", base_expiry_date_in_days);
		}
		else if(frm.doc.expiry_date){
			let rt_expiry_date_in_days=frappe.datetime.get_diff(frm.doc.expiry_date, today);
			frm.set_value("rt_expiry_date_in_days", rt_expiry_date_in_days);
		}
	}
