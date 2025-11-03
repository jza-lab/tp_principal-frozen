from .base_model import BaseModel
import logging

class RegistroParoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de registros de paro en la base de datos.
    """
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
    def get_table_name(self) -> str:
        return "registros_paro"

    def get_schema_name(self) -> str:
        return "mes_kanban"

    def _get_query_builder(self):
        """
        Sobrescribe el método base para especificar el esquema 'mes_kanban'.
        """
        return self.db.schema(self.get_schema_name()).table(self.get_table_name())
