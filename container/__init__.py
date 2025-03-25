__version__ = "0.0.1"

import erpnext.manufacturing.doctype.bom.bom
from container.container.doctype.bom.bom import get_bom_material_detail
from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import StockReconciliation
from container.container.doctype.stock_reconciliation.stock_reconciliation import CustomStockReconciliation

# Monkey patching BOM class method get_bom_material_detail
erpnext.manufacturing.doctype.bom.bom.BOM.get_bom_material_detail = get_bom_material_detail
StockReconciliation.get_sle_for_serialized_items = CustomStockReconciliation.get_sle_for_serialized_items
