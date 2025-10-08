from .base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

class NotificacionModel(BaseModel):
    def __init__(self):
        super().__init__('notificaciones')

    def create(self, data: dict):
        """
        Crea una nueva notificación.
        """
        try:
            response = self.db.table(self.table_name).insert(data).execute()
            if response.data:
                return {'success': True, 'data': response.data[0]}
            return {'success': False, 'error': 'No se pudo crear la notificación.'}
        except Exception as e:
            logger.error(f"Error al crear notificación: {e}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}

    def find_unread(self):
        """
        Busca todas las notificaciones no leídas.
        """
        try:
            response = self.db.table(self.table_name)\
                .select("*, usuario:usuarios(nombre, apellido)")\
                .eq("leida", False)\
                .order("created_at", desc=True)\
                .execute()
            
            if response.data:
                return {'success': True, 'data': response.data}
            return {'success': True, 'data': []}
        except Exception as e:
            logger.error(f"Error al buscar notificaciones no leídas: {e}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}

    def mark_as_read(self, notificacion_id: int):
        """
        Marca una notificación como leída.
        """
        try:
            response = self.db.table(self.table_name)\
                .update({'leida': True})\
                .eq('id', notificacion_id)\
                .execute()
            
            if response.data:
                return {'success': True, 'data': response.data[0]}
            return {'success': False, 'error': 'No se pudo marcar la notificación como leída.'}
        except Exception as e:
            logger.error(f"Error al marcar notificación como leída: {e}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}