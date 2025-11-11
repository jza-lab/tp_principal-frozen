from app.models.base_model import BaseModel

class ReclamoProveedorItemModel(BaseModel):
    def get_table_name(self):
        return 'reclamo_proveedor_items'
