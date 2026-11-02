__version__ = "2.0.0"

import erpnext.manufacturing.doctype.bom.bom
from container.container.doctype.bom.bom import get_bom_material_detail

# Monkey patching BOM class method get_bom_material_detail
erpnext.manufacturing.doctype.bom.bom.BOM.get_bom_material_detail = get_bom_material_detail
