from .base_model import BaseModel
from datetime import date
import logging

logger = logging.getLogger(__name__)

class AutorizacionIngresoModel(BaseModel):
    def __init__(self):
        super().__init__()

    def get_table_name(self) -> str:
        return 'u_autorizaciones_ingreso'

    def find_by_usuario_and_fecha(self, usuario_id: int, fecha: date, tipo: str = None, estado: str = None):
        """
        Busca una autorización para un usuario y fecha, con filtros opcionales de tipo y estado.
        """
        try:
            query = self.db.table(self.table_name)\
                .select("*, turno:turno_autorizado_id(nombre, hora_inicio, hora_fin)")\
                .eq("usuario_id", usuario_id)\
                .eq("fecha_autorizada", fecha.isoformat())

            if tipo:
                query = query.eq('tipo', tipo)
            
            if estado:
                query = query.eq('estado', estado)

            response = query.execute()
            
            if response.data:
                return {'success': True, 'data': response.data} # Devolver siempre una lista
            
            error_message = 'No se encontraron autorizaciones para los criterios especificados.'
            return {'success': False, 'error': error_message}
            
        except Exception as e:
            logger.error(f"Error al buscar autorización para usuario {usuario_id} en fecha {fecha}: {e}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}

    def create(self, data: dict):
        """
        Crea un nuevo registro de autorización de ingreso.
        """
        try:
            data['estado'] = 'PENDIENTE'
            # Asegurarse de que no exista una autorización para el mismo usuario y fecha
            existing = self.find_by_usuario_and_fecha(data['usuario_id'], data['fecha_autorizada'])
            if existing.get('success'):
                # Si ya existe, la actualizamos (update or insert)
                response = self.db.table(self.table_name)\
                    .update(data)\
                    .eq("id", existing['data']['id'])\
                    .execute()
            else:
                # Si no existe, la creamos
                response = self.db.table(self.table_name).insert(data).execute()

            if response.data:
                return {'success': True, 'data': response.data[0]}
            return {'success': False, 'error': 'No se pudo crear o actualizar la autorización.'}
        except Exception as e:
            logger.error(f"Error al crear autorización: {e}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}

    def find_all_by_status(self, status: str = None):
        """
        Busca todas las autorizaciones de ingreso, opcionalmente filtradas por estado.
        """
        try:
            query = self.db.table(self.table_name).select(
                "*, usuario:usuario_id(nombre, apellido, legajo), turno:turno_autorizado_id(nombre, hora_inicio, hora_fin)"
            )

            if status:
                query = query.eq("estado", status)

            response = query.order('fecha_autorizada', desc=True).execute()

            if response.data:
                return {'success': True, 'data': response.data}
            
            error_msg = f'No se encontraron autorizaciones con estado "{status}".' if status else 'No se encontraron autorizaciones.'
            return {'success': False, 'error': error_msg}
        except Exception as e:
            logger.error(f"Error al buscar autorizaciones: {e}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}

    def find_all_pending(self):
        """
        Busca todas las autorizaciones de ingreso pendientes.
        """
        return self.find_all_by_status("PENDIENTE")

    def update_estado(self, autorizacion_id: int, estado: str, comentario: str = None):
        """
        Actualiza el estado de una autorización de ingreso.
        """
        try:
            response = self.db.table(self.table_name)\
                .update({"estado": estado, "comentario_supervisor": comentario})\
                .eq("id", autorizacion_id)\
                .execute()
            
            if response.data:
                return {'success': True, 'data': response.data[0]}
            return {'success': False, 'error': 'No se pudo actualizar la autorización.'}
        except Exception as e:
            logger.error(f"Error al actualizar autorización: {e}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}