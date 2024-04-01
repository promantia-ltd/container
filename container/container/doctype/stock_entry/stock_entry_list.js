
frappe.listview_settings['Stock Entry'].onload = function(listview) {
	listview.page.actions.find('[data-label="Cancel"],[data-label="Submit"]').parent().parent().remove()
};