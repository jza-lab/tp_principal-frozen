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

    def obtener_actividad_filtrada(self, filtros: dict) -> Dict:
        """
        Obtiene la actividad del tótem (ingresos y egresos) según los filtros proporcionados.
        Filtros: 'fecha_desde', 'fecha_hasta', 'sector_id'.
        """
        try:
            query = self.db.table(self.get_table_name())\
                .select('*, usuario:usuarios(id, nombre, apellido, legajo, roles(nombre), sectores:usuario_sectores(sectores(nombre)))')

            if filtros:
                if filtros.get('fecha_desde'):
                    query = query.gte('fecha_inicio', f"{filtros['fecha_desde']}T00:00:00")
                if filtros.get('fecha_hasta'):
                    query = query.lte('fecha_inicio', f"{filtros['fecha_hasta']}T23:59:59")
                
                # Filtrado por sector requiere un join
                if filtros.get('sector_id'):
                    # Subconsulta para obtener los user_id del sector especificado
                    user_ids_in_sector = self.db.table('usuario_sectores')\
                        .select('usuario_id')\
                        .eq('sector_id', filtros['sector_id'])\
                        .execute()
                    
                    if user_ids_in_sector.data:
                        user_ids = [item['usuario_id'] for item in user_ids_in_sector.data]
                        query = query.in_('usuario_id', user_ids)
                    else:
                        # Si no hay usuarios en ese sector, no habrá resultados
                        return {'success': True, 'data': []}

            # Si no se proporcionan fechas, por defecto muestra la actividad de hoy
            if not filtros or (not filtros.get('fecha_desde') and not filtros.get('fecha_hasta')):
                from datetime import date
                hoy = date.today().isoformat()
                query = query.gte('fecha_inicio', f'{hoy}T00:00:00')
                query = query.lte('fecha_inicio', f'{hoy}T23:59:59')

            response = query.order('fecha_inicio', desc=True).execute()

            if response.data:
                return {'success': True, 'data': response.data}
            return {'success': True, 'data': []}
        except Exception as e:
            logger.error(f"Error obteniendo la actividad del tótem filtrada: {str(e)}")
            return {'success': False, 'error': str(e)}