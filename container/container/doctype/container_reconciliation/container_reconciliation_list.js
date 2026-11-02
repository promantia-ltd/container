frappe.listview_settings['Container Reconciliation'] = {
    // Remove bulk Cancel/Delete from the list view actions (after the menu has rendered)
    onload: function(listview) {
        setTimeout(() => {
            listview.page.actions.find('[data-label="Cancel"]').closest('li').remove();
            listview.page.actions.find('[data-label="Delete"]').closest('li').remove();
        }, 500);
    }
};      