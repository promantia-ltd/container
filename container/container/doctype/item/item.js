frappe.ui.form.on('Item', {
    before_save:function(frm){
        let primaryCount = 0;
        let secondaryCount = 0;

        $.each(frm.doc.uoms || [], function(i, row) {
            if (row.uom_type === 'Primary UOM') {
                primaryCount++;
            } else if (row.uom_type === 'Secondary UOM') {
                secondaryCount++;
            }
        });

        if (frm.doc.is_containerized && primaryCount !== 1 || secondaryCount !== 1) {
            frappe.msgprint(__("There should be exactly one Primary and one Secondary UOM Type."));
            frappe.validated = false;
        }
    }

})
