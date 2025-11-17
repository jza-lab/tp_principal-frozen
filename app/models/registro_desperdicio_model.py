from .base_model import BaseModel
import logging

class RegistroDesperdicioModel(BaseModel):
    """
    Modelo para interactuar con la tabla de registros de desperdicio en la base de datos.
    """
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
    def get_table_name(self) -> str:
        return "registros_desperdicio"

    def get_schema_name(self) -> str:
        return "mes_kanban"

    def _get_query_builder(self):
        """
        Sobrescribe el método base para especificar el esquema 'mes_kanban'.
        """
        return self.db.schema(self.get_schema_name()).table(self.get_table_name())

    def find_all_enriched(self, filters: dict = None, order_by: str = None) -> dict:
        """
        Obtiene todos los registros de desperdicio, enriqueciendo los datos con
        información del usuario y el motivo del desperdicio.
        """
        try:
            query = self._get_query_builder().select(
                '*, motivo_desperdicio:motivo_desperdicio_id(descripcion), usuario:usuario_id(nombre, apellido)'
            )
            
            if filters:
                for key, value in filters.items():
                    if isinstance(value, tuple):
                        operator, val = value
                        query = query.filter(key, operator, val)
                    else:
                        query = query.eq(key, value)
            
            if order_by:
                column, order = order_by.split('.')
                query = query.order(column, desc=order.lower() == 'desc')
            
            result = query.execute()
            
            return self.handle_postgrest_response(result)

        except Exception as e:
            self.logger.error(f"Error al obtener registros enriquecidos de {self.get_table_name()}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
