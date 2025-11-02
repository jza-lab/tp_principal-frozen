from .base_model import BaseModel

class MotivoDesperdicioModel(BaseModel):
    """
    Modelo para interactuar con la tabla de motivos de desperdicio en la base de datos.
    """
    def get_table_name(self):
        return "mes_kanban.motivos_desperdicio"

    def get_schema_name(self):
        return "mes_kanban"
