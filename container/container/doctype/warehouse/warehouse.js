frappe.ui.form.on('Warehouse', {
    onload:function(frm){
        frappe.db.get_value("Container Settings","Container Settings",["has_partially_reserved"],(p)=>{
           if(p.has_partially_reserved == "1"){
            frm.set_df_property('temperature', 'reqd', 0);
            frm.set_df_property('temperature', 'hidden', 1);
           }
           else{
            frm.set_df_property('temperature', 'reqd', 1);
            frm.set_df_property('temperature', 'hidden', 0);
           }
        })
    }
})