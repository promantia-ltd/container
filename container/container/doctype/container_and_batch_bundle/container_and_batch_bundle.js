// // Copyright (c) 2023, Mohan and contributors
// // For license information, please see license.txt
frappe.ui.form.on("Container and Batch Bundle", {
    
})


// frappe.ui.form.on("Container and Batch Bundle", {
// 	onload(frm) {
//         if (!(frm.doc.voucher_no)){
//             frappe.call({
//                 args:{
//                     name:frm.doc.name
//                 },
//                 method:"container.container.doctype.container_and_batch_bundle.container_and_batch_bundle.update_voucher_no",
//                 async:false,
//                 callback: function(r){
//                     frm.refresh_field("voucher_detail_no")
//                     frm.refresh_field("voucher_no")
//                 }
//             });
//         }
// 	},
// });