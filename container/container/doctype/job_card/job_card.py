import frappe

# Populate Jobcard Tables with Filtered Work Order Data Based on Operations
def after_insert(self, method):
    wo = frappe.get_doc("Work Order", self.work_order)

    self.custom_items_required = []
    self.container_information = []

    operation_items = set()
    for item in wo.required_items:
        if item.operation == self.operation:
            operation_items.add(item.item_code)
            self.append("custom_items_required", {
                "operation": self.operation,
                "item_code": item.item_code,
                "source_warehouse": item.source_warehouse,
                "allow_alternative_item":item.allow_alternative_item,
                "include_item_in_manufacturing":item.include_item_in_manufacturing,
                "required_qty": item.required_qty,
                "transferred_qty": item.transferred_qty,
                "rate":item.rate,
                "consumed_qty":item.consumed_qty,
                "returned_qty":item.returned_qty,
                "amount":item.amount,
                "available_qty_at_source_warehouse":item.available_qty_at_source_warehouse,
                "available_qty_at_wip_warehouse":item.available_qty_at_wip_warehouse,
                "stock_uom": item.stock_uom
            })

    for container in wo.custom_work_order_containers_reserved:
        if container.item_code in operation_items:
            self.append("custom_container_information", {
                "item_code": container.item_code,
                "container": container.container,
                "warehouse": container.warehouse,
                "qty_as_per_work_order": container.qty_as_per_work_order,
                "transfered_qty": container.transfered_qty,
                "transfered_qty_in_secondary_uom": container.transfered_qty_in_secondary_uom
            })

    self.save(ignore_permissions=True)