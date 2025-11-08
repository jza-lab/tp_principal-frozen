from app.models.base_model import BaseModel
import logging
from datetime import datetime
from typing import Dict
from app.utils.date_utils import get_now_in_argentina, get_today_utc3_range

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
                .update({'activa': False, 'fecha_fin': get_now_in_argentina().isoformat()})\
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
        Verifica si el usuario tiene una sesión activa que haya comenzado en la fecha actual de Argentina.
        Esta función es crucial para decidir si registrar un INGRESO o un EGRESO.
        """
        try:
            today_str = get_now_in_argentina().date().isoformat()
            start_of_day_iso = f"{today_str}T00:00:00-03:00"
            end_of_day_iso = f"{today_str}T23:59:59.999999-03:00"

            response = self.db.table(self.get_table_name()) \
                .select('id', count='exact') \
                .eq('usuario_id', usuario_id) \
                .eq('activa', True) \
                .gte('fecha_inicio', start_of_day_iso) \
                .lte('fecha_inicio', end_of_day_iso) \
                .execute()

            return response.count > 0

        except Exception as e:
            logger.error(f"Error verificando sesión activa hoy para usuario {usuario_id}: {e}", exc_info=True)
            return False

    def obtener_actividad_filtrada(self, filtros: dict) -> Dict:
        """
        Obtiene la actividad del tótem (ingresos y egresos) según los filtros proporcionados.
        Filtros: 'fecha_desde', 'fecha_hasta', 'sector_id'.
        """
        try:
            # Base de la consulta
            query = self.db.table(self.get_table_name())\
                .select('*, usuario:usuarios(id, nombre, apellido, legajo, role_id, roles(id, nombre), sectores:usuario_sectores(sectores(nombre)))')

            # 1. Filtrar por sector primero si está presente
            if filtros and filtros.get('sector_id'):
                user_ids_in_sector_res = self.db.table('usuario_sectores')\
                    .select('usuario_id')\
                    .eq('sector_id', filtros['sector_id'])\
                    .execute()
                
                if not user_ids_in_sector_res.data:
                    return {'success': True, 'data': []} # No hay usuarios, no hay actividad
                
                user_ids = [item['usuario_id'] for item in user_ids_in_sector_res.data]
                query = query.in_('usuario_id', user_ids)

            # 2. Aplicar filtros de fecha
            has_date_filter = False
            if filtros and filtros.get('fecha_desde'):
                query = query.gte('fecha_inicio', f"{filtros['fecha_desde']}T00:00:00")
                has_date_filter = True
            if filtros and filtros.get('fecha_hasta'):
                query = query.lte('fecha_inicio', f"{filtros['fecha_hasta']}T23:59:59")
                has_date_filter = True

            # 3. Ejecutar la consulta final
            response = query.order('fecha_inicio', desc=True).execute()

            return {'success': True, 'data': response.data or []}
        except Exception as e:
            logger.error(f"Error obteniendo la actividad del tótem filtrada: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def find_all_active(self) -> Dict:
        """
        Obtiene todas las sesiones de tótem que están actualmente activas.
        """
        try:
            response = self.db.table(self.get_table_name())\
                .select('*')\
                .eq('activa', True)\
                .execute()

            if response.data:
                return {'success': True, 'data': response.data}
            else:
                return {'success': False, 'error': 'No hay sesiones activas'}
        except Exception as e:
            logger.error(f"Error obteniendo todas las sesiones activas: {str(e)}")
            return {'success': False, 'error': str(e)}

    def obtener_conteo_sesiones_activas_hoy(self) -> int:
        """
        Cuenta de forma optimizada el número de usuarios únicos con una sesión de tótem
        activa para el día de hoy.
        """
        try:
            start_of_day, end_of_day = get_today_utc3_range()
            
            response = self.db.table(self.table_name) \
                .select('usuario_id', count='exact') \
                .eq('activa', True) \
                .gte('fecha_inicio', start_of_day.isoformat()) \
                .lte('fecha_inicio', end_of_day.isoformat()) \
                .execute()

            return response.count if response.count is not None else 0
        except Exception as e:
            logger.error(f"Error al contar sesiones activas de hoy: {e}", exc_info=True)
            return 0

    def cerrar_sesiones_expiradas(self) -> Dict:
        """
        Busca todas las sesiones de tótem activas y cierra aquellas cuyo turno
        ha finalizado hace más de 15 minutos. Maneja turnos nocturnos.
        """
        try:
            from datetime import timedelta

            query = self.db.table(self.get_table_name()).select(
                'id, fecha_inicio, usuario:usuarios(id, roles(codigo), turno:turno_id(hora_inicio, hora_fin))'
            ).eq('activa', True)
            
            response = query.execute()

            if not response.data:
                return {'success': True, 'message': 'No hay sesiones activas para verificar.'}

            sesiones_a_cerrar = []
            now = datetime.now()

            for sesion in response.data:
                usuario = sesion.get('usuario')
                
                if not usuario or usuario.get('roles', {}).get('codigo') == 'GERENTE' or not usuario.get('turno'):
                    continue

                turno_info = usuario.get('turno')
                hora_inicio_str = turno_info.get('hora_inicio')
                hora_fin_str = turno_info.get('hora_fin')

                if not hora_inicio_str or not hora_fin_str:
                    continue
                
                hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M:%S').time()
                hora_fin = datetime.strptime(hora_fin_str, '%H:%M:%S').time()
                # Usamos UTC para la fecha de la sesión si la BBDD guarda en UTC
                fecha_sesion = datetime.fromisoformat(sesion['fecha_inicio'].replace('Z', '+00:00')).date()
                
                limite_dt = datetime.combine(fecha_sesion, hora_fin) + timedelta(minutes=15)

                if hora_fin < hora_inicio:
                    limite_dt += timedelta(days=1)
                
                # Convertir now a la misma zona horaria que limite_dt si es necesario (asumimos local por ahora)
                if now > limite_dt:
                    sesiones_a_cerrar.append(sesion['id'])

            if not sesiones_a_cerrar:
                return {'success': True, 'message': 'No hay sesiones expiradas.'}

            update_response = self.db.table(self.get_table_name()).update({
                'activa': False,
                'fecha_fin': now.isoformat()
            }).in_('id', sesiones_a_cerrar).execute()

            logger.info(f"Cerradas {len(update_response.data)} sesiones de tótem expiradas.")
            return {'success': True, 'data': update_response.data}

        except Exception as e:
            logger.error(f"Error cerrando sesiones de tótem expiradas: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}