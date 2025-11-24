from app.models.base_model import BaseModel

class HistorialCostosProductoModel(BaseModel):
    def __init__(self):
        self.table_name = 'historial_costos_productos'
        super().__init__()

    def get_table_name(self):
        return self.table_name
