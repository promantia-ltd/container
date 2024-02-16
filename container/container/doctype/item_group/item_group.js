frappe.ui.form.on('Item Group', {
    onload:function(frm){
        frappe.db.get_value("Container Settings","Container Settings",["has_partially_reserved"],(p)=>{
           if(p.has_partially_reserved == "1"){
            frm.set_df_property('min_days', 'hidden', 1);
           }
           else{
            frm.set_df_property('min_days', 'hidden', 0);
           }
        })
    }
})