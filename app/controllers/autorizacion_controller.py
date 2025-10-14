from app.controllers.base_controller import BaseController
from app.models.autorizacion_ingreso import AutorizacionIngresoModel
from app.models.totem_sesion import TotemSesionModel
from app.models.usuario_turno import UsuarioTurnoModel
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)

class AutorizacionController(BaseController):
    def __init__(self):
        super().__init__()
        self.model = AutorizacionIngresoModel()
        self.totem_sesion = TotemSesionModel()
        self.turno_model = UsuarioTurnoModel()

    def crear_autorizacion(self, data: dict):
        # 1. Validar fecha
        fecha_autorizada_str = data.get('fecha_autorizada')
        try:
            fecha_autorizada = date.fromisoformat(fecha_autorizada_str)
            if fecha_autorizada < date.today():
                return {'success': False, 'error': 'No se pueden crear autorizaciones para fechas pasadas.'}
        except (ValueError, TypeError):
            return {'success': False, 'error': 'Formato de fecha inválido.'}

        # 2. Validar turno (mañana o tarde)
        turno_id = data.get('turno_autorizado_id')
        if not turno_id:
            return {'success': False, 'error': 'Debe seleccionar un turno.'}
        
        turno_details_result = self.turno_model.find_by_id(int(turno_id))
        if not turno_details_result.get('success'):
            return {'success': False, 'error': 'El turno seleccionado no es válido.'}
        
        turno_details = turno_details_result['data']
        nombre_turno = turno_details['nombre'].lower()
        if 'mañana' not in nombre_turno and 'tarde' not in nombre_turno:
            return {'success': False, 'error': 'Solo se pueden autorizar turnos de Mañana o Tarde.'}

        # 3. Validar tipo de autorización vs. ingreso previo
        usuario_id = data.get('usuario_id')
        tipo_autorizacion = data.get('tipo')

        if tipo_autorizacion == 'HORAS_EXTRAS' and 'tarde' in nombre_turno:
            return {'success': False, 'error': 'No se pueden crear autorizaciones de horas extras para el turno tarde.'}

        if tipo_autorizacion == 'LLEGADA_TARDIA':
            sesion_activa = self.totem_sesion.verificar_sesion_activa_hoy(usuario_id)
            if sesion_activa:
                return {'success': False, 'error': 'El empleado ya ingresó. No se puede crear una autorización de llegada tardía.'}
        
        return self.model.create(data)

    def obtener_autorizaciones_pendientes(self):
        return self.model.find_all_pending()

    def actualizar_estado_autorizacion(self, autorizacion_id: int, estado: str, comentario: str):
        return self.model.update_estado(autorizacion_id, estado, comentario)
