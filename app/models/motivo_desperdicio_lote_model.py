# app/models/motivo_desperdicio_lote_model.py
from app.models.base_model import BaseModel

class MotivoDesperdicioLoteModel(BaseModel):
    def get_table_name(self) -> str:
        return 'motivos_desperdicio_lote'

    def get_schema_name(self) -> str:
        return "mes_kanban"

    def _get_query_builder(self):
        """Sobrescribe el método base para especificar el esquema."""
        return self.db.schema(self.get_schema_name()).table(self.get_table_name())

    def get_all(self):
        """Obtiene todos los motivos de desperdicio."""
        try:
            result = self._get_query_builder().select('*').execute()
            return {'success': True, 'data': result.data}
        except Exception as e:
            return {'success': False, 'error': str(e)}
