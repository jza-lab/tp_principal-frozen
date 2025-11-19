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
        información del usuario (desde el schema 'public') y el motivo del desperdicio.
        """
        from app.models.usuario import UsuarioModel

        try:
            # Paso 1: Obtener los datos del esquema 'mes_kanban' sin el join a 'usuarios'
            query = self._get_query_builder().select(
                """
                *,
                motivo_desperdicio:motivo_desperdicio_id (
                    descripcion
                )
                """
            )
            
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            
            if order_by:
                parts = order_by.split('.')
                column = parts[0]
                desc = len(parts) > 1 and parts[1].lower() == 'desc'
                
                # El parámetro es 'nulls_first' y es booleano.
                # 'nullslast' -> nulls_first=False
                # 'nullsfirst' -> nulls_first=True
                nulls_first = len(parts) > 2 and parts[2].lower() == 'nullsfirst'
                query = query.order(column, desc=desc, nullsfirst=nulls_first)
            
            result = query.execute()
            
            if not hasattr(result, 'data'):
                return {'success': False, 'error': 'Respuesta inesperada de la base de datos.'}

            desperdicios = result.data
            if not desperdicios:
                return {'success': True, 'data': []}

            # Paso 2: Enriquecer con los datos del usuario desde el esquema 'public'
            user_ids = list(set(d['usuario_id'] for d in desperdicios if d.get('usuario_id')))
            if user_ids:
                usuario_model = UsuarioModel()
                usuarios_res = usuario_model.db.table('usuarios').select('id, nombre, apellido').in_('id', user_ids).execute()
                usuarios_map = {u['id']: u for u in usuarios_res.data} if usuarios_res.data else {}

                for desperdicio in desperdicios:
                    if desperdicio.get('usuario_id') in usuarios_map:
                        desperdicio['usuario'] = usuarios_map[desperdicio['usuario_id']]

            return {'success': True, 'data': desperdicios}


        except Exception as e:
            self.logger.error(f"Error al obtener registros enriquecidos de {self.get_table_name()}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def handle_postgrest_response(self, response):
        """
        Helper para manejar la respuesta de PostgREST de forma consistente.
        """
        if hasattr(response, 'data'):
            return {'success': True, 'data': response.data or []}
        else:
            # Manejar posibles errores o respuestas inesperadas
            return {'success': False, 'error': 'Respuesta inesperada de la base de datos.'}
