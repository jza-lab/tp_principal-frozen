from .base_model import BaseModel

class MotivoDesperdicioModel(BaseModel):
    """
    Modelo para interactuar con la tabla de motivos de desperdicio en la base de datos.
    """
    def get_table_name(self):
        return "motivos_desperdicio"

    def get_schema_name(self):
        return "mes_kanban"

    def _get_query_builder(self):
        """
        Sobrescribe el método base para especificar el esquema 'mes_kanban'.
        """
        return self.db.schema(self.get_schema_name()).table(self.get_table_name())
