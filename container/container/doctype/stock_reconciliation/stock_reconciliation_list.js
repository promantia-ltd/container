frappe.listview_settings['Stock Reconciliation'] = {
    onload: function(listview) {
        setTimeout(() => {
            listview.page.actions.find('[data-label="Cancel"]').closest('li').remove();
            listview.page.actions.find('[data-label="Delete"]').closest('li').remove();
        }, 500);
    }
};      