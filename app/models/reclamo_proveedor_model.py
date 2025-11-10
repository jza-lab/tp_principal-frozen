from app.models.base_model import BaseModel

class ReclamoProveedorModel(BaseModel):
    def get_table_name(self):
        return 'reclamos_proveedores'
