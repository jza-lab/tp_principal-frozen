from app.controllers.base_controller import BaseController
from app.models.autorizacion_ingreso import AutorizacionIngresoModel
from app.models.totem_sesion import TotemSesionModel
from app.models.usuario_turno import UsuarioTurnoModel
from app.models.usuario import UsuarioModel
from datetime import date, time
import logging

logger = logging.getLogger(__name__)

class AutorizacionController(BaseController):
    """
    Controlador para la lógica de negocio relacionada con las autorizaciones de ingreso.
    """
    def __init__(self):
        super().__init__()
        self.model = AutorizacionIngresoModel()
        self.totem_sesion = TotemSesionModel()
        self.turno_model = UsuarioTurnoModel()
        self.usuario_model = UsuarioModel()

    # region Operaciones CRUD
    def crear_autorizacion(self, data: dict) -> dict:
        """
        Valida los datos y las reglas de negocio antes de crear una nueva autorización.
        """
        # 1. Limpieza y conversión de datos de entrada
        try:
            data['usuario_id'] = int(data['usuario_id'])
            data['turno_autorizado_id'] = int(data['turno_autorizado_id']) if data.get('turno_autorizado_id') else None
            fecha_autorizada = date.fromisoformat(data.get('fecha_autorizada'))
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Error en la conversión de datos para crear autorización: {e}")
            return {'success': False, 'error': 'Los datos proporcionados son inválidos (ID de usuario, turno o fecha).'}

        # 2. Validación de datos base
        if fecha_autorizada < date.today():
            return {'success': False, 'error': 'No se pueden crear autorizaciones para fechas pasadas.'}
        if not data.get('turno_autorizado_id'): 
            return {'success': False, 'error': 'Debe seleccionar un turno.'}
        
        turno_auth_result = self.turno_model.find_by_id(data['turno_autorizado_id'])
        if not turno_auth_result.get('success'): 
            return {'success': False, 'error': 'El turno seleccionado no es válido.'}
        
        # 3. Validaciones de lógica de negocio específicas por tipo
        tipo_autorizacion = data.get('tipo')
        usuario_id = data.get('usuario_id')
        
        validation_result = None
        if tipo_autorizacion == 'TARDANZA':
            validation_result = self._validar_llegada_tardia(usuario_id)
        elif tipo_autorizacion == 'HORAS_EXTRAS':
            turno_autorizado_details = turno_auth_result['data']
            validation_result = self._validar_horas_extras(usuario_id, turno_autorizado_details)

        if validation_result and not validation_result.get('success'):
            return validation_result

        # 4. Creación del registro si todas las validaciones pasan
        return self.model.create(data)

    def obtener_autorizaciones_pendientes(self) -> dict:
        """Obtiene todas las autorizaciones con estado 'PENDIENTE'."""
        return self.model.find_all_pending()

    def obtener_todas_las_autorizaciones(self) -> dict:
        """Obtiene un historial de todas las autorizaciones agrupadas por estado."""
        return self.model.find_all_grouped_by_status()

    def actualizar_estado_autorizacion(self, autorizacion_id: int, estado: str, comentario: str) -> dict:
        """
        Actualiza el estado y el comentario de una autorización específica.
        """
        return self.model.update_estado(autorizacion_id, estado, comentario)

    # endregion

    # region Métodos de Validación (Helpers)
    def _validar_llegada_tardia(self, usuario_id: int) -> dict:
        """
        Valida la regla de negocio para autorizaciones de llegada tardía.
        Regla: No se puede crear si el empleado ya ha fichado su ingreso.
        """
        if self.totem_sesion.verificar_sesion_activa_hoy(usuario_id):
            return {'success': False, 'error': 'El empleado ya ingresó. No se puede crear una autorización de llegada tardía.'}
        return {'success': True}

    def _validar_horas_extras(self, usuario_id: int, turno_autorizado_details: dict) -> dict:
        """
        Valida las reglas de negocio para autorizaciones de horas extras.
        Reglas:
        - Turno Mañana: Las horas extras deben ser posteriores al turno habitual.
        - Turno Tarde: Las horas extras deben finalizar antes del turno habitual.
        """
        user_result = self.usuario_model.find_by_id(usuario_id)
        if not user_result.get('success'): 
            return {'success': False, 'error': 'Usuario no encontrado.'}
        
        usuario = user_result['data']
        turno_habitual = usuario.get('turno')
        if not turno_habitual: 
            return {'success': False, 'error': 'El empleado no tiene un turno habitual asignado.'}

        try:
            nombre_turno_habitual = turno_habitual['nombre'].lower()
            hora_inicio_autorizada = time.fromisoformat(turno_autorizado_details['hora_inicio'])
            hora_fin_autorizada = time.fromisoformat(turno_autorizado_details['hora_fin'])

            if 'mañana' in nombre_turno_habitual:
                hora_fin_habitual = time.fromisoformat(turno_habitual['hora_fin'])
                if hora_inicio_autorizada < hora_fin_habitual:
                    return {'success': False, 'error': 'Las horas extras para el turno mañana deben ser posteriores a su turno habitual.'}
            
            if 'tarde' in nombre_turno_habitual:
                hora_inicio_habitual = time.fromisoformat(turno_habitual['hora_inicio'])
                if hora_fin_autorizada > hora_inicio_habitual:
                    return {'success': False, 'error': 'Las horas extras para el turno tarde deben finalizar antes del inicio de su turno habitual.'}

        except (ValueError, TypeError) as e:
            logger.warning(f"Error al parsear horas en validación de horas extras para usuario {usuario_id}: {e}")
            return {'success': False, 'error': 'Error en los datos de turno para la validación de horas extras.'}

        return {'success': True}
    # endregion
