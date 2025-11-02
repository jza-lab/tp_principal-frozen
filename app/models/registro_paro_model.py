from .base_model import BaseModel

class RegistroParoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de registros de paro en la base de datos.
    """
    def get_table_name(self):
        return "mes_kanban.registros_paro"

    def get_schema_name(self):
        return "mes_kanban"
