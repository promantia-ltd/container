frappe.ui.form.on('Pick List', {
	refresh: function(frm){
		cur_frm.set_query("uom", "locations", function(doc,cdt,cdn) {
            let child = locals[cdt][cdn];
            return{
                query: "container.container.doctype.purchase_receipt.purchase_receipt.get_item_uom_list",
                filters: {'item': child.item_code}
            }
        });
        if (frm.doc.custom_containers_information_text)
        var wrapper = frm.get_field("custom_containers_information").$wrapper.html(
            `			<table class="table table-bordered table-hover">
            <tr class="text-muted">
                <th style="background-color: var(--scrollbar-track-color);  cursor:pointer; width="0.1%">No.</th>
                <th style="background-color: var(--scrollbar-track-color);  cursor:pointer; width="1%">Item Code</th>
                <th style="background-color: var(--scrollbar-track-color);  cursor:pointer; width="1%">Container</th>
                <th style="background-color: var(--scrollbar-track-color);  cursor:pointer; width="3%">Warehouse</th>
                <th style="background-color: var(--scrollbar-track-color);  cursor:pointer; width="1%">Expire date</th>
                <th style="background-color: var(--scrollbar-track-color);  cursor:pointer; width="1%">RT-Expire date</th>
                <th style="background-color: var(--scrollbar-track-color);  cursor:pointer; width="1%">Primary Available qty</th>
                <th style="background-color: var(--scrollbar-track-color); cursor:pointer; width="1%">Primary UOM</th>
            </tr>
            ${frm.doc.custom_containers_information_text}
        </table>`
        )
	},
})