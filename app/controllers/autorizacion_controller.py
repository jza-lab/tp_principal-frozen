from app.controllers.base_controller import BaseController
from app.models.autorizacion_ingreso import AutorizacionIngresoModel
from app.models.totem_sesion import TotemSesionModel
from app.models.usuario_turno import UsuarioTurnoModel
from app.models.usuario import UsuarioModel
from datetime import date, datetime, time
import logging

logger = logging.getLogger(__name__)

class AutorizacionController(BaseController):
    def __init__(self):
        super().__init__()
        self.model = AutorizacionIngresoModel()
        self.totem_sesion = TotemSesionModel()
        self.turno_model = UsuarioTurnoModel()
        self.usuario_model = UsuarioModel()

    def crear_autorizacion(self, data: dict):
        # 1. Validaciones básicas de datos
        try:
            fecha_autorizada = date.fromisoformat(data.get('fecha_autorizada'))
            if fecha_autorizada < date.today():
                return {'success': False, 'error': 'No se pueden crear autorizaciones para fechas pasadas.'}
        except (ValueError, TypeError):
            return {'success': False, 'error': 'Formato de fecha inválido.'}

        turno_id = data.get('turno_autorizado_id')
        if not turno_id:
            return {'success': False, 'error': 'Debe seleccionar un turno.'}
        
        turno_auth_result = self.turno_model.find_by_id(int(turno_id))
        if not turno_auth_result.get('success'): 
            return {'success': False, 'error': 'El turno seleccionado no es válido.'}
        
        turno_autorizado_details = turno_auth_result['data']
        nombre_turno_autorizado = turno_autorizado_details['nombre'].lower()
        if 'mañana' not in nombre_turno_autorizado and 'tarde' not in nombre_turno_autorizado:
            return {'success': False, 'error': 'Solo se pueden autorizar turnos de Mañana o Tarde.'}

        # 2. Validaciones de lógica de negocio
        usuario_id = data.get('usuario_id')
        tipo_autorizacion = data.get('tipo')

        # Regla para 'LLEGADA_TARDIA'
        if tipo_autorizacion == 'LLEGADA_TARDIA':
            if self.totem_sesion.verificar_sesion_activa_hoy(usuario_id):
                return {'success': False, 'error': 'El empleado ya ingresó. No se puede crear una autorización de llegada tardía.'}

        # Reglas para 'HORAS_EXTRAS'
        if tipo_autorizacion == 'HORAS_EXTRAS':
            user_result = self.usuario_model.find_by_id(usuario_id)
            if not user_result.get('success'): 
                return {'success': False, 'error': 'Usuario no encontrado.'}
            
            usuario = user_result['data']
            turno_habitual = usuario.get('turno')
            if not turno_habitual:
                return {'success': False, 'error': 'El empleado no tiene un turno habitual asignado.'}

            nombre_turno_habitual = turno_habitual['nombre'].lower()

            # Regla para Turno Mañana
            if 'mañana' in nombre_turno_habitual:
                hora_fin_habitual = datetime.strptime(turno_habitual['hora_fin'], '%H:%M:%S').time()
                hora_inicio_autorizada = datetime.strptime(turno_autorizado_details['hora_inicio'], '%H:%M:%S').time()
                if hora_inicio_autorizada < hora_fin_habitual:
                    return {'success': False, 'error': 'Las horas extras para el turno mañana deben ser posteriores a su turno habitual.'}
            
            # Regla para Turno Tarde
            if 'tarde' in nombre_turno_habitual:
                hora_inicio_habitual = datetime.strptime(turno_habitual['hora_inicio'], '%H:%M:%S').time()
                hora_inicio_autorizada = datetime.strptime(turno_autorizado_details['hora_inicio'], '%H:%M:%S').time()
                hora_fin_autorizada = datetime.strptime(turno_autorizado_details['hora_fin'], '%H:%M:%S').time()

                if hora_inicio_autorizada > hora_inicio_habitual:
                    return {'success': False, 'error': 'Las horas extras para el turno tarde deben ser anteriores a su turno habitual.'}

                if hora_fin_autorizada > time(23, 0, 0):
                    return {'success': False, 'error': 'Las horas extras para el turno tarde no pueden extenderse más allá de las 23:00 hs.'}

        # 3. Si todas las validaciones pasan, crear la autorización
        return self.model.create(data)

    def obtener_autorizaciones_pendientes(self):
        return self.model.find_all_pending()

    def actualizar_estado_autorizacion(self, autorizacion_id: int, estado: str, comentario: str):
        return self.model.update_estado(autorizacion_id, estado, comentario)
