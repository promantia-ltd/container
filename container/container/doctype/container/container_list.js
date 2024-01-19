frappe.listview_settings['Container'] = {
	add_fields: ["item_code", "warehouse", "expiry_date", "delivery_document_type","status"],
	get_indicator: (doc) => {
		if (doc.delivery_document_type) {
			return [__("Delivered"), "green", "delivery_document_type,is,set"];
		} else if (doc.expiry_date && frappe.datetime.get_diff(doc.expiry_date, frappe.datetime.nowdate()) <= 0) {
			return [__("Expired"), "red", "expiry_date,not in,|expiry_date,<=,Today|delivery_document_type,is,not set"];
		} else if (!doc.warehouse) {
			return [__("Inactive"), "grey", "warehouse,is,not set"];
		}else if (doc.status=="Inactive") {
			return [__("Inactive"), "grey", "status,=,Inactive"];
		}else if (doc.status=="Slitted") {
			return [__("Slitted"), "orange", "status,=,Slitted"];
		}else if (doc.status=="Used") {
			return [__("Used"), "blue", "status,=,Used"];
		}
		else {
			return [__("Active"), "green", "delivery_document_type,is,not set"];
		}
	}
};