import frappe,json

@frappe.whitelist()
def get_containers(selected_containers,item):
	selected_containers=json.loads(selected_containers)
	item=json.loads(item)
	total_qty=0
	containers=""
	for value in selected_containers:
		container_doc=frappe.get_doc("Container",value)
		total_qty+=container_doc.primary_available_qty
		containers+=container_doc.name+","
	if containers[-1] ==",":
		containers=containers[0:-1]
	return containers,total_qty
