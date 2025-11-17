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
            # Usamos RPC para ejecutar una función SQL personalizada que maneja el join cross-schema.
            # Esto nos da control total sobre la consulta.
            rpc_params = {
                'p_orden_produccion_id': filters.get('orden_produccion_id') if filters else None
            }

            # Llamamos a la función 'get_registros_desperdicio_enriquecidos' que debemos crear en la BD.
            query = self.db.rpc('get_registros_desperdicio_enriquecidos', rpc_params)
            
            # El ordenamiento se aplica al resultado del RPC.
            if order_by:
                column, order = order_by.split('.')
                query = query.order(column, desc=order.lower() == 'desc')
            
            result = query.execute()

            return self.handle_postgrest_response(result)

        except Exception as e:
            self.logger.error(f"Error al obtener registros enriquecidos de {self.get_table_name()}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def handle_postgrest_response(self, response):
        """
        Helper para manejar la respuesta de PostgREST de forma consistente.
        """
        if hasattr(response, 'data'):
            return {'success': True, 'data': response.data}
        else:
            # Manejar posibles errores o respuestas inesperadas
            return {'success': False, 'error': 'Respuesta inesperada de la base deatos.'}
