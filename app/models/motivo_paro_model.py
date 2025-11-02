from .base_model import BaseModel

class MotivoParoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de motivos de paro en la base de datos.
    """
    def get_table_name(self):
        return "mes_kanban.motivos_paro"

    def get_schema_name(self):
        return "mes_kanban"
