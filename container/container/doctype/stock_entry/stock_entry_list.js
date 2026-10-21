// Hide the bulk Cancel/Submit list actions so Stock Entries can only be submitted/cancelled from the form.

frappe.listview_settings['Stock Entry'].onload = function(listview) {
	listview.page.actions.find('[data-label="Cancel"],[data-label="Submit"]').parent().parent().remove()
};