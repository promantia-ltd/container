"""
Batch enablement trial for 60002284BK and 281049 (ERPNext v15).

Steps
  1. Snapshot stock per item/warehouse and every container holding available or reserved qty
  2. Stock Reconciliation #1: every row to qty 0 at its current rate
  3. Switch the items to batch (has_batch_no, create_new_batch, batch_number_series, custom_has_batch)
  4. Create one opening batch per item/warehouse and stamp it on that warehouse's containers
  5. Stock Reconciliation #2: same qty and rate back, with the opening batch on each row
  6. Check stock, value, batch qty and containers against the snapshot

Opening batches keep Moving Average valuation, as the items use today (use_batchwise_valuation = 0).
Stock Reconciliation Item valuation_rate needs precision 9
(Property Setter in this app's fixtures) so the stock value comes back unchanged.

Run (take a backup first and keep the scheduler off):
  bench --site hotset execute container.batch_migration.enable_batch_trial.run --kwargs "{'dry_run': 1}"
  bench --site hotset execute container.batch_migration.enable_batch_trial.run --kwargs "{'dry_run': 0}"
  bench --site hotset execute container.batch_migration.enable_batch_trial.rollback

A dry run does every step and every check, then rolls everything back. A real run commits only if
every check passes. The snapshot and result are saved under sites/<site>/private/batch_trial/.
"""

import json
import os
from contextlib import contextmanager

import frappe
from frappe.utils import add_to_date, cint, flt, get_datetime, now_datetime

ITEMS = ["60002284BK", "281049"]
COMPANY = "HIPL India Pvt Ltd."

WAREHOUSE_CODES = {
	"Finished Goods - HIPL": "FG",
	"Stores - Hotset": "STORES",
	"PlantFoor - HIPL": "PLANTFLOOR",
	"Rejects and Returns - HIPL": "REJECTS",
}

QTY_TOLERANCE = 0.001
VALUE_TOLERANCE = 0.01


def run(dry_run=True):
	dry_run = cint(dry_run)
	snapshot = take_snapshot()
	precheck(snapshot)
	save_json("snapshot.json", snapshot)

	result = {"dry_run": dry_run}
	# Hooks in the container and hotset apps call frappe.db.commit(); hold every commit so the
	# whole run is one transaction that can be rolled back.
	with held_commits():
		try:
			t1 = add_to_date(now_datetime(), minutes=-2)
			t2 = add_to_date(now_datetime(), minutes=-1)

			result["reco_zero"] = make_reconciliation(snapshot["rows"], t1, put_back=False)
			switch_items_to_batch()
			result["batches"] = create_batches_and_link_containers(snapshot)
			result["reco_put_back"] = make_reconciliation(snapshot["rows"], t2, put_back=True)

			result["checks"] = check(snapshot, result)
			ok = all(c["ok"] for c in result["checks"])
		except Exception:
			frappe.db.rollback()
			clear_item_cache()
			print("FAILED, everything rolled back")
			raise

	print_checks(result["checks"])

	if dry_run or not ok:
		frappe.db.rollback()
		clear_item_cache()
		print("\nRolled back:", "dry run" if dry_run else "a check failed")
	else:
		frappe.db.commit()
		save_json("result.json", result)
		print(f"\nCommitted. Reconciliations {result['reco_zero']} and {result['reco_put_back']}.")


# Step 1


def take_snapshot():
	rows = frappe.db.sql(
		"""select item_code, warehouse, actual_qty as qty, stock_value as value, valuation_rate as rate
		from `tabBin` where item_code in %(items)s and actual_qty != 0
		order by item_code, warehouse""",
		{"items": ITEMS},
		as_dict=True,
	)
	for row in rows:
		row.batch_no = opening_batch_name(row.item_code, row.warehouse)

	containers = frappe.db.sql(
		"""select c.name, c.item_code, c.warehouse, c.primary_available_qty, c.secondary_available_qty,
			c.actual_container_qty, c.status, c.batch_no,
			ifnull((select sum(sd.reserved_qty) from `tabStock Details` sd where sd.parent = c.name), 0) as reserved_qty
		from `tabContainer` c where c.item_code in %(items)s""",
		{"items": ITEMS},
		as_dict=True,
	)
	# a container counts toward stock when it holds available qty or a Stock Details reservation
	containers = [c for c in containers if flt(c.primary_available_qty) > 0 or flt(c.reserved_qty) > 0]

	return {"taken_at": str(now_datetime()), "rows": rows, "containers": containers}


def precheck(snapshot):
	errors = []

	if cint(frappe.get_meta("Stock Reconciliation Item").get_field("valuation_rate").precision) != 9:
		errors.append("Stock Reconciliation Item valuation_rate precision is not 9; sync the container fixtures")

	for item in ITEMS:
		if frappe.db.get_value("Item", item, "has_batch_no"):
			errors.append(f"{item} is already batch-tracked")

	for row in snapshot["rows"]:
		if flt(row.qty) < 0:
			errors.append(f"{row.item_code} / {row.warehouse}: negative stock {row.qty}")
		if frappe.db.exists("Batch", row.batch_no):
			errors.append(f"Batch {row.batch_no} already exists")

		# stock = available on containers + reserved in their Stock Details
		container_qty = sum(
			flt(c.primary_available_qty) + flt(c.reserved_qty)
			for c in snapshot["containers"]
			if c.item_code == row.item_code and c.warehouse == row.warehouse
		)
		if abs(flt(row.qty) - container_qty) > QTY_TOLERANCE:
			errors.append(f"{row.item_code} / {row.warehouse}: stock {row.qty} vs containers {container_qty}")

	stock_keys = {(r.item_code, r.warehouse) for r in snapshot["rows"]}
	for c in snapshot["containers"]:
		if (c.item_code, c.warehouse) not in stock_keys:
			errors.append(f"Container {c.name} holds qty in {c.warehouse} where {c.item_code} has no stock")

	if errors:
		frappe.throw("Precheck failed:<br>" + "<br>".join(errors))
	print(f"Precheck passed: {len(snapshot['rows'])} rows, {len(snapshot['containers'])} containers")


# Steps 2 and 5


def make_reconciliation(rows, posting_datetime, put_back):
	posting_datetime = get_datetime(posting_datetime)
	reco = frappe.new_doc("Stock Reconciliation")
	reco.company = COMPANY
	reco.purpose = "Stock Reconciliation"
	reco.set_posting_time = 1
	reco.posting_date = posting_datetime.date()
	reco.posting_time = posting_datetime.time()

	for row in rows:
		reco.append(
			"items",
			{
				"item_code": row.item_code,
				"warehouse": row.warehouse,
				"qty": row.qty if put_back else 0,
				"valuation_rate": flt(row.value) / flt(row.qty),
				"batch_no": row.batch_no if put_back else None,
				# ERPNext builds the Serial and Batch Bundle from batch_no on submit
				"use_serial_batch_fields": 1 if put_back else 0,
			},
		)

	reco.insert(ignore_permissions=True)
	reco.submit()
	print(f"{'Put back' if put_back else 'Zeroed'} stock: Stock Reconciliation {reco.name}")
	return reco.name


# Step 3


def switch_items_to_batch():
	for item in ITEMS:
		# Item.validate refuses has_batch_no once transactions exist; stock is 0 here, so set it directly
		frappe.db.set_value(
			"Item",
			item,
			{
				"has_batch_no": 1,
				"create_new_batch": 1,
				"batch_number_series": f"{item}-B-.####",
				"custom_has_batch": 1,
			},
		)
		frappe.clear_document_cache("Item", item)
	print("Items switched to batch:", ", ".join(ITEMS))


# Step 4


def opening_batch_name(item_code, warehouse):
	code = WAREHOUSE_CODES.get(warehouse) or warehouse.split(" - ")[0].upper().replace(" ", "")
	return f"OPN-{item_code}-{code}"


def create_batches_and_link_containers(snapshot):
	created = {}
	for row in snapshot["rows"]:
		batch = frappe.get_doc(
			{
				"doctype": "Batch",
				"batch_id": row.batch_no,
				"item": row.item_code,
				"manufacturing_date": frappe.utils.today(),
				"description": f"Opening batch for {row.warehouse} (batch enablement trial)",
			}
		)
		batch.insert(ignore_permissions=True)
		# Batch.insert turns batch-wise valuation on from Stock Settings; keep Moving Average instead
		batch.db_set("use_batchwise_valuation", 0)

		linked = []
		for c in snapshot["containers"]:
			if c.item_code == row.item_code and c.warehouse == row.warehouse:
				frappe.db.set_value("Container", c.name, "batch_no", batch.name, update_modified=False)
				linked.append(c.name)

		created[batch.name] = linked
		print(f"Batch {batch.name}: {len(linked)} containers linked")
	return created


# Step 6


def check(snapshot, result):
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	checks = []

	def add(name, ok, detail):
		checks.append({"check": name, "ok": bool(ok), "detail": detail})

	for row in snapshot["rows"]:
		label = f"{row.item_code} / {row.warehouse}"
		now = frappe.db.get_value(
			"Bin", {"item_code": row.item_code, "warehouse": row.warehouse}, ["actual_qty", "stock_value"], as_dict=True
		)
		add(f"Stock qty {label}", abs(flt(now.actual_qty) - flt(row.qty)) <= QTY_TOLERANCE,
			f"{row.qty} -> {now.actual_qty}")
		add(f"Stock value {label}", abs(flt(now.stock_value) - flt(row.value)) <= VALUE_TOLERANCE,
			f"{flt(row.value, 3)} -> {flt(now.stock_value, 3)}")

		batch_qty = get_batch_qty(batch_no=row.batch_no, warehouse=row.warehouse)
		add(f"Batch qty {row.batch_no}", abs(flt(batch_qty) - flt(row.qty)) <= QTY_TOLERANCE,
			f"batch {batch_qty} vs stock {row.qty}")
		add(f"Moving Average valuation {row.batch_no}",
			not frappe.db.get_value("Batch", row.batch_no, "use_batchwise_valuation"), "")

	for c in snapshot["containers"]:
		now = frappe.db.get_value(
			"Container", c.name, ["batch_no", "primary_available_qty", "status"], as_dict=True
		)
		reserved = frappe.db.sql(
			"select ifnull(sum(reserved_qty), 0) from `tabStock Details` where parent = %s", c.name
		)[0][0]
		unchanged = (
			abs(flt(now.primary_available_qty) - flt(c.primary_available_qty)) <= QTY_TOLERANCE
			and abs(flt(reserved) - flt(c.reserved_qty)) <= QTY_TOLERANCE
			and now.status == c.status
		)
		add(f"Container {c.name}", now.batch_no == opening_batch_name(c.item_code, c.warehouse) and unchanged,
			f"batch {now.batch_no}, available {now.primary_available_qty}, reserved {reserved}, {now.status}")

	for item in ITEMS:
		flags = frappe.db.get_value("Item", item, ["has_batch_no", "create_new_batch", "custom_has_batch"], as_dict=True)
		add(f"Item flags {item}", flags.has_batch_no and flags.create_new_batch and flags.custom_has_batch, str(flags))

	gl_net = frappe.db.sql(
		"""select ifnull(sum(debit - credit), 0) from `tabGL Entry`
		where voucher_type = 'Stock Reconciliation' and voucher_no in %(v)s and is_cancelled = 0
			and account = %(account)s""",
		{
			"v": [result["reco_zero"], result["reco_put_back"]],
			"account": frappe.get_cached_value("Company", COMPANY, "stock_adjustment_account"),
		},
	)[0][0]
	add("Stock Adjustment net of both reconciliations", abs(flt(gl_net)) <= VALUE_TOLERANCE, flt(gl_net, 3))

	return checks


def print_checks(checks):
	print()
	for c in checks:
		print(f"{'OK  ' if c['ok'] else 'FAIL'}  {c['check']}: {c['detail']}")
	failed = [c for c in checks if not c["ok"]]
	print(f"\n{len(checks) - len(failed)} passed, {len(failed)} failed")


# Rollback of a committed run


def rollback():
	result = load_json("result.json")
	snapshot = load_json("snapshot.json")

	for name in (result["reco_put_back"], result["reco_zero"]):
		reco = frappe.get_doc("Stock Reconciliation", name)
		if reco.docstatus == 1:
			reco.cancel()
		print(f"Cancelled {name}")

	for c in snapshot["containers"]:
		frappe.db.set_value("Container", c["name"], "batch_no", c["batch_no"], update_modified=False)

	for item in ITEMS:
		frappe.db.set_value(
			"Item", item,
			{"has_batch_no": 0, "create_new_batch": 0, "batch_number_series": None, "custom_has_batch": 0},
		)
	clear_item_cache()

	for batch in result["batches"]:
		frappe.delete_doc("Batch", batch, force=True, ignore_permissions=True)

	frappe.db.commit()
	print("Rolled back. Recheck the stock balance before using these items.")


# Helpers


@contextmanager
def held_commits():
	original = frappe.db.commit
	frappe.db.commit = lambda *args, **kwargs: None
	try:
		yield
	finally:
		frappe.db.commit = original


def clear_item_cache():
	# a rollback restores the Item rows in the database but not their cached documents
	for item in ITEMS:
		frappe.clear_document_cache("Item", item)


def output_path(filename):
	folder = frappe.get_site_path("private", "batch_trial")
	os.makedirs(folder, exist_ok=True)
	return os.path.join(folder, filename)


def save_json(filename, data):
	with open(output_path(filename), "w") as f:
		json.dump(data, f, indent=1, default=str)


def load_json(filename):
	with open(output_path(filename)) as f:
		return json.load(f)
