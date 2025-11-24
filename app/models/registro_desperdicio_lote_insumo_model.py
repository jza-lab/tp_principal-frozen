# app/models/registro_desperdicio_lote_insumo_model.py
from app.models.base_model import BaseModel
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class RegistroDesperdicioLoteInsumoModel(BaseModel):
    def get_table_name(self) -> str:
        return 'registros_desperdicio_lote_insumo'

    def get_schema_name(self) -> str:
        return "mes_kanban"

    def _get_query_builder(self):
        """Sobrescribe el método base para especificar el esquema."""
        return self.db.schema(self.get_schema_name()).table(self.get_table_name())

    def get_by_lote_id(self, lote_insumo_id: int):
        """Obtiene todos los registros de desperdicio para un lote específico."""
        try:
            # Se elimina el join a 'usuarios' que causa el error de cross-schema.
            # El join a 'motivos' funciona porque está en el mismo schema 'mes_kanban'.
            # Nota: Para insumos, la tabla de motivos suele ser 'motivos_desperdicio'
            result = self._get_query_builder().select(
                '*, motivo:motivos_desperdicio(descripcion)'
            ).eq('lote_insumo_id', lote_insumo_id).order('created_at', desc=True).execute()

            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error buscando registros de desperdicio por lote de insumo: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_all_in_date_range(self, fecha_inicio: datetime, fecha_fin: datetime):
        """Obtiene todos los registros de desperdicio dentro de un rango de fechas."""
        try:
            query = self._get_query_builder().select(
                '*, motivo:motivos_desperdicio(descripcion)'
            )
            query = query.gte('created_at', fecha_inicio.isoformat())
            query = query.lte('created_at', fecha_fin.isoformat())
            result = query.execute()
            
            if result.data:
                return {'success': True, 'data': result.data}
            else:
                return {'success': True, 'data': []}

        except Exception as e:
            logger.error(f"Error buscando registros de desperdicio de insumo por rango de fecha: {str(e)}")
            return {'success': False, 'error': str(e)}
