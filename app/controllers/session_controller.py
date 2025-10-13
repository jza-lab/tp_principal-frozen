from app.controllers.base_controller import BaseController
from app.models.totem_sesion import TotemSesionModel
from app.models.usuario import UsuarioModel
from app.models.autorizacion_ingreso import AutorizacionIngresoModel
from app.models.usuario_turno import UsuarioTurnoModel
from datetime import datetime, timedelta, time
import logging

logger = logging.getLogger(__name__)

class SessionController(BaseController):
    def __init__(self):
        super().__init__()
        self.totem_sesion_model = TotemSesionModel()
        self.usuario_model = UsuarioModel()
        self.autorizacion_model = AutorizacionIngresoModel()
        self.turno_model = UsuarioTurnoModel()

    def close_expired_sessions(self):
        """
        Busca todas las sesiones de tótem activas y las cierra si el turno del usuario ha
        finalizado y no hay una autorización de horas extras aprobada.
        """
        logger.info("Iniciando la tarea de cierre de sesiones expiradas...")
        active_sessions_result = self.totem_sesion_model.find_all_active()

        if not active_sessions_result.get('success') or not active_sessions_result.get('data'):
            logger.info("No se encontraron sesiones de tótem activas.")
            return {'success': True, 'message': 'No hay sesiones activas para verificar.'}

        sessions_closed = 0
        for session in active_sessions_result['data']:
            usuario_id = session['usuario_id']
            user_result = self.usuario_model.find_by_id(usuario_id, include_sectores=False, include_direccion=False)

            if not user_result.get('success'):
                logger.warning(f"No se pudo encontrar el usuario con ID {usuario_id} para la sesión {session['id']}.")
                continue

            usuario = user_result['data']
            turno_id = usuario.get('turno_id')

            if not turno_id:
                logger.info(f"El usuario {usuario_id} no tiene un turno asignado. Se omite la sesión.")
                continue

            turno_result = self.turno_model.find_by_id(turno_id)
            if not turno_result.get('success'):
                logger.warning(f"No se pudo encontrar el turno con ID {turno_id} para el usuario {usuario_id}.")
                continue

            turno = turno_result['data']
            try:
                hora_fin_turno = datetime.strptime(turno['hora_fin'], '%H:%M:%S').time()
            except (ValueError, TypeError):
                logger.error(f"Formato de hora_fin ('{turno['hora_fin']}') inválido para el turno {turno_id}.")
                continue

            # Combinar la fecha de inicio de la sesión con la hora de fin del turno
            session_start_date = datetime.fromisoformat(session['fecha_inicio']).date()
            shift_end_datetime = datetime.combine(session_start_date, hora_fin_turno)
            
            # Sumar el período de gracia de 15 minutos
            grace_period_end = shift_end_datetime + timedelta(minutes=15)
            
            # Si el tiempo actual es posterior al final del turno más el período de gracia
            if datetime.now() > grace_period_end:
                logger.info(f"La sesión {session['id']} del usuario {usuario_id} ha expirado. Verificando horas extras...")
                
                # Verificar si existe una autorización de horas extras aprobada para hoy
                today = datetime.now().date()
                overtime_auth_result = self.autorizacion_model.find_by_usuario_and_fecha(usuario_id, today, tipo='HORAS_EXTRAS')
                
                has_approved_overtime = False
                if overtime_auth_result.get('success'):
                    auth_data = overtime_auth_result['data']
                    if auth_data.get('estado') == 'APROBADO':
                        has_approved_overtime = True

                if not has_approved_overtime:
                    logger.info(f"Cerrando sesión para el usuario {usuario_id} por falta de autorización de horas extras.")
                    self.totem_sesion_model.cerrar_sesion(usuario_id)
                    # Aquí también se invalidaría la sesión web. Por ahora, solo cerramos la del tótem.
                    sessions_closed += 1
                else:
                    logger.info(f"El usuario {usuario_id} tiene horas extras aprobadas. La sesión permanecerá abierta.")

        logger.info(f"Tarea finalizada. Se cerraron {sessions_closed} sesiones.")
        return {'success': True, 'message': f'Se cerraron {sessions_closed} sesiones expiradas.'}

    def find_all_active_sessions(self):
        """
        Obtiene todas las sesiones de tótem que están actualmente activas.
        """
        return self.totem_sesion_model.find_all_active()
