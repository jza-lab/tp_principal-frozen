from .base_model import BaseModel

class RegistroDesperdicioModel(BaseModel):
    """
    Modelo para interactuar con la tabla de registros de desperdicio en la base de datos.
    """
    def get_table_name(self):
        return "mes_kanban.registros_desperdicio"

    def get_schema_name(self):
        return "mes_kanban"
