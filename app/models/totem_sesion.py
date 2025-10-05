from app.models.base_model import BaseModel
import logging
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)

class TotemSesionModel(BaseModel):
    def get_table_name(self):
        return 'totem_sesiones'

    def crear_sesion(self, usuario_id: int, metodo_acceso: str, dispositivo_totem: str = 'TOTEM_PRINCIPAL') -> Dict:
        """
        Crea una nueva sesión de totem para el usuario.
        """
        try:
            import secrets
            session_id = secrets.token_urlsafe(32)

            data = {
                'usuario_id': usuario_id,
                'session_id': session_id,
                'metodo_acceso': metodo_acceso,
                'dispositivo_totem': dispositivo_totem,
                'activa': True
            }

            response = self.db.table(self.get_table_name()).insert(data).execute()
            if response.data:
                return {'success': True, 'data': response.data[0]}
            else:
                return {'success': False, 'error': 'No se pudo crear la sesión'}
        except Exception as e:
            logger.error(f"Error creando sesión de totem: {str(e)}")
            return {'success': False, 'error': str(e)}

    def cerrar_sesion(self, usuario_id: int) -> Dict:
        """
        Cierra la sesión activa de un usuario en el totem.
        """
        try:
            response = self.db.table(self.get_table_name())\
                .update({'activa': False, 'fecha_fin': datetime.utcnow().isoformat()})\
                .eq('usuario_id', usuario_id)\
                .eq('activa', True)\
                .execute()

            if response.data:
                return {'success': True, 'data': response.data[0]}
            else:
                return {'success': False, 'error': 'No se encontró sesión activa'}
        except Exception as e:
            logger.error(f"Error cerrando sesión de totem: {str(e)}")
            return {'success': False, 'error': str(e)}

    def obtener_sesion_activa(self, usuario_id: int) -> Dict:
        """
        Obtiene la sesión activa de un usuario, si existe.
        """
        try:
            response = self.db.table(self.get_table_name())\
                .select('*')\
                .eq('usuario_id', usuario_id)\
                .eq('activa', True)\
                .execute()

            if response.data:
                return {'success': True, 'data': response.data[0]}
            else:
                return {'success': False, 'error': 'No hay sesión activa'}
        except Exception as e:
            logger.error(f"Error obteniendo sesión activa: {str(e)}")
            return {'success': False, 'error': str(e)}

    def verificar_sesion_activa_hoy(self, usuario_id: int) -> bool:
        """
        Verifica si el usuario tiene una sesión activa hoy.
        """
        try:
            from datetime import date
            hoy = date.today().isoformat()
            
            response = self.db.table(self.get_table_name())\
                .select('*')\
                .eq('usuario_id', usuario_id)\
                .eq('activa', True)\
                .gte('fecha_inicio', f'{hoy}T00:00:00')\
                .lte('fecha_inicio', f'{hoy}T23:59:59')\
                .execute()

            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error verificando sesión activa hoy: {str(e)}")
            return False