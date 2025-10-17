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
        La consulta se hace utilizando UTC para evitar problemas de zona horaria.
        """
        try:
            from datetime import time, timezone, datetime
            
            # Definir el inicio y el fin del día de hoy en UTC
            today_utc = datetime.now(timezone.utc).date()
            start_of_day_utc = datetime.combine(today_utc, time.min, tzinfo=timezone.utc)
            end_of_day_utc = datetime.combine(today_utc, time.max, tzinfo=timezone.utc)

            response = self.db.table(self.get_table_name())\
                .select('id', count='exact')\
                .eq('usuario_id', usuario_id)\
                .eq('activa', True)\
                .gte('fecha_inicio', start_of_day_utc.isoformat())\
                .lte('fecha_inicio', end_of_day_utc.isoformat())\
                .execute()

            # Si el conteo es mayor a 0, significa que ya hay una sesión activa hoy.
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