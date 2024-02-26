frappe.ui.form.on('Item', {
    before_save:function(frm){
        let primaryCount = 0;
        let secondaryCount = 0;
        let default_uom_in_bom = 0;

        $.each(frm.doc.uoms || [], function(i, row) {
            if (row.uom_type === 'Primary UOM') {
                primaryCount++;
            } else if (row.uom_type === 'Secondary UOM') {
                secondaryCount++;
            }
            if (row.default_uom_in_bom == 1){
                default_uom_in_bom += 1
            }
        });

        if (frm.doc.is_containerized == 1 && (primaryCount !== 1 || secondaryCount !== 1)) {
            frappe.msgprint(__("There should be exactly one Primary and one Secondary UOM Type in UOMs Table."));
            frappe.validated = false;
        }
        if (frm.doc.is_containerized == 1 && default_uom_in_bom > 1){
            frappe.msgprint(__("There should be exactly one Default Uom In BOM enabled in UOMs Table."));
            frappe.validated = false;
        }
    }

})
