import frappe
from container.container.doctype.stock_entry.stock_entry import reserve_once


def calculate_the_total_standard_rate(doc, method):
    try:
        used = []
        count = 1
        td_data = ""
        for each in doc.locations:
            item_doc = frappe.get_doc("Item", each.item_code)
            if item_doc.is_containerized:
                (
                    container_no,
                    primary_available_qty,
                    remaining_qty,
                    primary_available_qty_used,
                    transferred_qty,
                ) = assign_containers(each, used, doc.work_order)
                result_dict = {}
                for i, container in enumerate(container_no):
                    container_data = frappe.db.sql(
                        f"""
                        select
                        item_code,
                        name,
                        ifnull(warehouse,"") as warehouse,
                        ifnull(base_expiry_date,"") as base_expiry_date,
                        ifnull(expiry_date,"")as expiry_date ,
                        ifnull(primary_available_qty,0) as primary_available_qty ,
                        ifnull(primary_uom,"") as primary_uom
                        from `tabContainer`
                        where
                        name ='{container}' """,
                        as_dict=1,
                    )[0]
                    td_data = (
                        td_data
                        + f"""<tr>
                        <td class="text-center text-muted">{count}</td>
                        <td class="text-center text-muted"><a href="/app/item/{container_data["item_code"]}">{container_data["item_code"]}</a</td>
                        <td class="text-center text-muted"><a href="/app/container/{container_data["name"]}">{container_data["name"]}</a{container_data["name"]}</td>
                        <td class="text-center text-muted"><a href="/app/warehouse/{container_data["warehouse"]}">{container_data["warehouse"]}</a</td>
                        <td class="text-center text-muted">{container_data["base_expiry_date"]}</td>
                        <td class="text-center text-muted">{container_data["expiry_date"]}</td>
                        <td class="text-center text-muted">{container_data["primary_available_qty"]}</td>
                        <td class="text-center text-muted">{container_data["primary_uom"]}</td>
                        </tr>"""
                    )
                    result_dict[container] = (
                        primary_available_qty[i] if i < len(primary_available_qty) else ""
                    )
                    count += 1
                if result_dict:
                    each.custom_containers = frappe.json.dumps(result_dict)
                if primary_available_qty:
                    each.custom_container_qty = sum(primary_available_qty)
        doc.custom_containers_information_text = td_data
    except Exception as e:
        doc.log_error(f"{doc.name}", e)
        raise e


def assign_containers(item, used, work_order=None):
    container_no, primary_available_qty, primary_available_qty_used = [], [], []
    remaining_qty = ""
    query = None
    item_doc = frappe.get_doc("Item", item.item_code)
    if item_doc.is_containerized and item_doc.container_number_series:
        reserved_containers = reserve_once(item_doc, work_order)
        if item.warehouse:
            query = get_containers(item.item_code, item.warehouse)

        required_qty = item.qty
        if query:
            (
                container_no,
                primary_available_qty,
                primary_available_qty_used,
                remaining_qty,
            ) = container_pick(query, required_qty, used, reserved_containers)
            transferred_qty = sum([i for i in primary_available_qty])
            return (
                container_no,
                primary_available_qty,
                remaining_qty,
                primary_available_qty_used,
                transferred_qty,
            )
        else:
            frappe.msgprint(
                "Not enough containers to assign,Please make sure containers are available for all the items"
            )


def get_containers(item, warehouse):
    query = frappe.db.sql(
        """
        select name,primary_available_qty,expiry_date
        from `tabContainer`
        where item_code = %s and warehouse=%s and status in ("Active")
        and primary_available_qty>0 order by creation
        """,
        (item, warehouse),
        as_dict=True,
    )
    return query


def container_pick(query, required_qty, used, reserved_containers):
    container_no, primary_available_qty, primary_available_qty_used = [], [], []
    remaining_qty = ""
    for data in query:
        if data.name not in used and data.name not in reserved_containers and data.name:
            available_qty = round(data.primary_available_qty, 4)
            if available_qty < required_qty:
                container_no.append(data.name)
                primary_available_qty.append(available_qty)
                required_qty = round(required_qty - available_qty, 4)
                primary_available_qty_used.append(round(available_qty, 4))
            elif available_qty >= required_qty:
                container_no.append(data.name)
                remaining_qty = (
                    str(data.name) + ":" + str(round(available_qty - required_qty, 4))
                )
                primary_available_qty.append(available_qty)
                primary_available_qty_used.append(round(required_qty, 4))
                required_qty = 0
                break
    return (
        container_no,
        primary_available_qty,
        primary_available_qty_used,
        remaining_qty,
    )
