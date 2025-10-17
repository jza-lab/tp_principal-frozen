from app.controllers.base_controller import BaseController
from app.models.usuario import UsuarioModel
from app.models.totem_sesion import TotemSesionModel
from app.models.sector import SectorModel
from app.models.usuario_sector import UsuarioSectorModel
from app.models.rol import RoleModel
from app.models.usuario_turno import UsuarioTurnoModel
from app.schemas.usuario_schema import UsuarioSchema
from typing import Dict, Optional, List
from marshmallow import ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta, time
import logging
import json
import pytz
from app.utils.date_utils import get_now_in_argentina
from app.controllers.direccion_controller import GeorefController
from app.models.autorizacion_ingreso import AutorizacionIngresoModel
from app.models.direccion import DireccionModel
from flask import session
from app.models.permisos import PermisosModel

logger = logging.getLogger(__name__)

class UsuarioController(BaseController):
    """
    Controlador para toda la lógica de negocio relacionada con los usuarios.
    """

    def __init__(self):
        super().__init__()
        self.model = UsuarioModel()
        self.totem_sesion = TotemSesionModel()
        self.sector_model = SectorModel()
        self.usuario_sector_model = UsuarioSectorModel()
        self.role_model = RoleModel()
        self.turno_model = UsuarioTurnoModel()
        self.schema = UsuarioSchema()
        self.usuario_direccion_controller = GeorefController()
        self.direccion_model = DireccionModel()

    # region Gestión de Usuarios (CRUD)

    def crear_usuario(self, data: Dict) -> Dict:
        """Valida y crea un nuevo usuario, incluyendo su dirección y sectores."""
        try:
            address_fields = ['calle', 'altura', 'piso', 'depto', 'localidad', 'provincia', 'codigo_postal']
            direccion_data = {field: data.get(field) for field in address_fields if data.get(field) is not None}
            user_data = {k: v for k, v in data.items() if k not in address_fields}
            
            sectores_ids = user_data.pop('sectores', [])
            validated_data = self.schema.load(user_data)

            if self.model.find_by_email(validated_data['email']).get('data'):
                return {'success': False, 'error': 'El correo electrónico ya está en uso.'}

            password = validated_data.pop('password')
            validated_data['password_hash'] = generate_password_hash(password)
            
            if any(direccion_data.values()):
                direccion_normalizada = self._normalizar_y_preparar_direccion(direccion_data)
                if direccion_normalizada:
                    # Asumo que _get_or_create_direccion existe en BaseController o similar
                    direccion_id = self._get_or_create_direccion(direccion_normalizada)
                    if direccion_id:
                        validated_data['direccion_id'] = direccion_id

            resultado_creacion = self.model.create(validated_data)
            if not resultado_creacion.get('success'):
                return resultado_creacion

            usuario_creado = resultado_creacion['data']
            usuario_id = usuario_creado['id']

            if sectores_ids:
                resultado_sectores = self._asignar_sectores_usuario(usuario_id, sectores_ids)
                if not resultado_sectores.get('success'):
                    self.model.db.table("usuarios").delete().eq("id", usuario_id).execute()
                    return resultado_sectores

            return self.model.find_by_id(usuario_id, include_direccion=True)

        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            logger.error(f"Error al crear usuario: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def actualizar_usuario(self, usuario_id: int, data: Dict) -> Dict:
        """Orquesta la actualización completa de un usuario."""
        try:
            required_fields = {
                'nombre': 'El nombre no puede estar vacío.',
                'apellido': 'El apellido no puede estar vacío.',
                'email': 'El email no puede estar vacío.',
                'telefono': 'El teléfono no puede estar vacío.',
                'legajo': 'El legajo no puede estar vacío.',
                'cuil_cuit': 'El CUIL/CUIT no puede estar vacío.'
            }
            for field, message in required_fields.items():
                if not data.get(field) or not str(data[field]).strip():
                    return {'success': False, 'error': message}

            fields_to_sanitize = ['telefono', 'cuil_cuit', 'fecha_nacimiento', 'fecha_ingreso', 'turno_id', 'piso', 'depto', 'codigo_postal']
            for field in fields_to_sanitize:
                if field in data and (data[field] == '' or data[field] == 'None'):
                    data[field] = None

            existing_result = self.model.find_by_id(usuario_id, include_direccion=True)
            if not existing_result.get('success'):
                return existing_result
            existing_user = existing_result['data']

            sectores_ids = data.pop('sectores', None)
            if isinstance(sectores_ids, str):
                try:
                    sectores_ids = json.loads(sectores_ids)
                except json.JSONDecodeError:
                    return {'success': False, 'error': 'El formato de sectores es inválido.'}

            address_fields = ['calle', 'altura', 'piso', 'depto', 'localidad', 'provincia', 'codigo_postal']
            direccion_data = {field: data.get(field) for field in address_fields}
            user_data = {k: v for k, v in data.items() if k not in address_fields}

            sectores_result = self._actualizar_sectores_usuario(usuario_id, sectores_ids, existing_user)
            if not sectores_result.get('success'):
                return sectores_result

            direccion_result = self._actualizar_direccion_usuario(usuario_id, direccion_data, existing_user)
            if not direccion_result.get('success'):
                return direccion_result
            new_direccion_id = direccion_result.get('direccion_id')

            user_result = self._actualizar_datos_principales(usuario_id, user_data, existing_user, new_direccion_id)
            if not user_result.get('success'):
                return user_result

            return self.model.find_by_id(usuario_id, include_direccion=True)

        except Exception as e:
            logger.error(f"Error en orquestación de actualizar_usuario: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def obtener_usuario_por_id(self, usuario_id: int, include_direccion: bool = False) -> Optional[Dict]:
        """Obtiene un único usuario por su ID."""
        result = self.model.find_by_id(usuario_id, include_direccion=include_direccion)
        return result.get('data')

    def obtener_todos_los_usuarios(self, filtros: Optional[Dict] = None, include_direccion: bool = False) -> List[Dict]:
        """Obtiene una lista de todos los usuarios, con filtros opcionales."""
        result = self.model.find_all(filtros, include_direccion=include_direccion)
        return result.get('data', [])

    def buscar_por_legajo_para_api(self, legajo: str) -> Dict:
        """
        Busca un usuario por legajo y devuelve solo los datos necesarios para la API.
        """
        resultado = self.model.find_by_legajo(legajo)
        if not resultado.get('success'):
            return resultado
        
        usuario = resultado.get('data')
        return {
            'success': True,
            'data': {
                'id': usuario.get('id'),
                'nombre': usuario.get('nombre'),
                'apellido': usuario.get('apellido')
            }
        }

    def eliminar_usuario(self, usuario_id: int) -> Dict:
        """Realiza una eliminación lógica de un usuario (lo desactiva)."""
        return self.model.update(usuario_id, {'activo': False})

    def habilitar_usuario(self, usuario_id: int) -> Dict:
        """Reactiva un usuario que fue desactivado lógicamente."""
        return self.model.update(usuario_id, {'activo': True})

    def obtener_datos_para_vista_perfil(self, usuario_id: int) -> dict:
        """
        Obtiene y prepara todos los datos necesarios para renderizar la vista de perfil de usuario.
        """
        usuario = self.obtener_usuario_por_id(usuario_id, include_direccion=True)
        if not usuario:
            return {'success': False, 'error': 'Usuario no encontrado.'}

        # Parsear fechas de string a objetos datetime para la vista
        for key in ['ultimo_login_web', 'fecha_ingreso']:
            if usuario.get(key) and isinstance(usuario[key], str):
                try:
                    usuario[key] = datetime.fromisoformat(usuario[key].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    usuario[key] = None
        
        # Formatear dirección para visualización
        if usuario.get('direccion'):
            dir_data = usuario['direccion']
            usuario['direccion_formateada'] = f"{dir_data.get('calle', '')} {dir_data.get('altura', '')}, {dir_data.get('localidad', '')}"
        else:
            usuario['direccion_formateada'] = 'No especificada'

        # Obtener datos para los dropdowns
        roles = self.obtener_todos_los_roles()
        sectores = self.obtener_todos_los_sectores()
        turnos = self.obtener_todos_los_turnos()

        return {
            'success': True,
            'data': {
                'usuario': usuario,
                'roles_disponibles': roles,
                'sectores_disponibles': sectores,
                'turnos_disponibles': turnos
            }
        }

    def obtener_datos_para_formulario_usuario(self) -> dict:
        """
        Obtiene los datos maestros necesarios para los formularios de creación/edición de usuarios.
        """
        return {
            'roles': self.obtener_todos_los_roles(),
            'sectores': self.obtener_todos_los_sectores(),
            'turnos': self.obtener_todos_los_turnos()
        }

    # endregion

    # region Autenticación y Sesiones

    def autenticar_usuario_web(self, legajo: str, password: str) -> Dict:
        """Autentica un usuario para el acceso web por legajo y contraseña."""
        logger.info(f"Attempting web authentication for legajo: {legajo}")
        auth_result = self._autenticar_credenciales_base(legajo, password)
        if not auth_result.get('success'):
            logger.warning(f"Web auth failed for legajo {legajo} at credential check: {auth_result.get('error')}")
            return auth_result

        user_data = auth_result['data']
        user_id = user_data['id']
        logger.info(f"Credentials OK for user_id: {user_id}")
        
        totem_check = self.totem_sesion.verificar_sesion_activa_hoy(user_id)
        if not totem_check:
            logger.warning(f"Web auth failed for user_id {user_id}: No active totem session found for today.")
            return {'success': False, 'error': 'Debe registrar su entrada en el tótem primero para acceder por web'}
        
        logger.info(f"Active totem session found for user_id: {user_id}. Proceeding to start session.")
        self.model.update(user_id, {'ultimo_login_web': get_now_in_argentina().isoformat()})
        return self._iniciar_sesion_usuario(user_data)

    def autenticar_usuario_facial_web(self, image_data_url: str) -> Dict:
        """Autentica un usuario para el acceso web por reconocimiento facial."""
        from app.controllers.facial_controller import FacialController
        facial_controller = FacialController()
        
        resultado_identificacion = facial_controller.identificar_rostro(image_data_url)
        if not resultado_identificacion.get('success'):
            return resultado_identificacion
        
        user_data = resultado_identificacion['usuario']
        if not user_data.get('activo', True):
            return {'success': False, 'error': 'Este usuario se encuentra desactivado.'}
        
        if not self.totem_sesion.verificar_sesion_activa_hoy(user_data['id']):
            return {'success': False, 'error': 'Acceso Web denegado. Por favor, registre su ingreso en el tótem.'}
        
        self.model.update(user_data['id'], {'ultimo_login_web': get_now_in_argentina().isoformat()})
        return self._iniciar_sesion_usuario(user_data)

    def autenticar_usuario_para_totem(self, legajo: str, password: str) -> Dict:
        """Autentica un usuario exclusivamente para el tótem (solo credenciales)."""
        return self._autenticar_credenciales_base(legajo, password)
    
    # endregion

    # region Gestión de Tótem

    def cerrar_sesiones_expiradas_totem(self) -> dict:
        """
        Cierra todas las sesiones de tótem activas cuyo turno ha finalizado,
        considerando las autorizaciones de horas extras.
        """
        logger.info("Iniciando tarea de cierre de sesiones de tótem expiradas...")
        active_sessions_result = self.totem_sesion.find_all_active()

        if not active_sessions_result.get('success') or not active_sessions_result.get('data'):
            logger.info("No se encontraron sesiones de tótem activas.")
            return {'success': True, 'message': 'No hay sesiones activas para verificar.'}

        sessions_closed = 0
        for user_session in active_sessions_result['data']:
            user_result = self.model.find_by_id(user_session['usuario_id'])
            if not user_result.get('success'):
                continue

            usuario = user_result['data']
            if self._sesion_debe_cerrarse(usuario, user_session):
                self.totem_sesion.cerrar_sesion(usuario['id'])
                sessions_closed += 1
        
        logger.info(f"Tarea finalizada. Se cerraron {sessions_closed} sesiones de tótem.")
        return {'success': True, 'message': f'Se cerraron {sessions_closed} sesiones expiradas.'}

    # endregion

    # region Verificación de Acceso y Horarios

    def verificar_acceso_web(self, usuario_id: int) -> Dict:
        """Verifica si un usuario tiene permitido el acceso a la plataforma web."""
        user_result = self.model.find_by_id(usuario_id)
        if not user_result.get('success'):
            return {'success': False, 'error': 'Usuario no encontrado'}

        if not self.totem_sesion.verificar_sesion_activa_hoy(usuario_id):
            return {'success': False, 'error': 'Acceso web no permitido. Registre entrada en tótem.'}

        return {'success': True, 'data': user_result.get('data')}

    def verificar_acceso_por_horario(self, usuario: dict) -> dict:
        """
        Verifica si un fichaje es válido, consolidando la lógica de turno habitual,
        períodos de gracia y autorizaciones de llegada tardía.
        """
        # Constante para el período de gracia en minutos
        MINUTOS_DE_GRACIA = 15

        # El rol GERENTE siempre tiene acceso
        if not usuario or usuario.get('roles', {}).get('codigo') == 'GERENTE':
            return {'success': True}

        turno_info = usuario.get('turno')
        if not turno_info or 'hora_inicio' not in turno_info or 'hora_fin' not in turno_info:
            logger.warning(f"Usuario {usuario.get('legajo')} no tiene un turno completo asignado.")
            return {'success': False, 'error': 'Acceso denegado. No tiene un turno asignado.'}

        try:
            now_art = get_now_in_argentina()
            fecha_actual = now_art.date()
            hora_actual = now_art.time()

            hora_inicio_turno = time.fromisoformat(turno_info['hora_inicio'])
            hora_fin_turno = time.fromisoformat(turno_info['hora_fin'])
            
            # --- 1. Verificación del Período de Gracia del Turno Habitual ---
            dt_inicio_turno = datetime.combine(fecha_actual, hora_inicio_turno)
            inicio_ventana_gracia = (dt_inicio_turno - timedelta(minutes=MINUTOS_DE_GRACIA)).time()
            fin_ventana_gracia = (dt_inicio_turno + timedelta(minutes=MINUTOS_DE_GRACIA)).time()

            if fin_ventana_gracia < inicio_ventana_gracia:  # Caso de turno nocturno que cruza medianoche
                if hora_actual >= inicio_ventana_gracia or hora_actual <= fin_ventana_gracia:
                    logger.info(f"Acceso para {usuario.get('legajo')} permitido dentro del período de gracia.")
                    return {'success': True}
            else:  # Caso de turno diurno
                if inicio_ventana_gracia <= hora_actual <= fin_ventana_gracia:
                    logger.info(f"Acceso para {usuario.get('legajo')} permitido dentro del período de gracia.")
                    return {'success': True}

            # --- 2. Si no está en período de gracia, buscar autorización de LLEGADA_TARDIA ---
            # --- 2. Si no está en período de gracia, buscar autorizaciones válidas para hoy ---
            logger.info(f"Usuario {usuario.get('legajo')} fuera del período de gracia. Buscando autorizaciones.")
            autorizacion_model = AutorizacionIngresoModel()
            auth_result = autorizacion_model.find_by_usuario_and_fecha(
                usuario_id=usuario.get('id'),
                fecha=fecha_actual,
                estado='APROBADO'
            )

            if auth_result.get('success') and auth_result.get('data'):
                logger.info(f"DEBUG: Autorizaciones encontradas: {auth_result['data']}")
                for autorizacion in auth_result['data']:
                    tipo_auth = autorizacion.get('tipo')
                    
                    # --- Lógica para LLEGADA_TARDIA ---
                    if tipo_auth == 'LLEGADA_TARDIA':
                        logger.info(f"Evaluando autorización de LLEGADA_TARDIA para {usuario.get('legajo')}.")
                        en_horario_turno = False
                        if hora_fin_turno < hora_inicio_turno: # Turno nocturno
                            if hora_actual >= hora_inicio_turno or hora_actual <= hora_fin_turno:
                                en_horario_turno = True
                        else: # Turno diurno
                            if hora_inicio_turno <= hora_actual <= hora_fin_turno:
                                en_horario_turno = True

                        if en_horario_turno:
                            logger.info(f"Acceso concedido por LLEGADA_TARDIA para {usuario.get('legajo')}.")
                            return {
                                'success': True,
                                'message': 'Acceso permitido.\nIngreso autorizado por excepción registrada.\nRecuerde que este ingreso fue aprobado previamente por su responsable.'
                            }
                        continue # Si está fuera de horario, podría tener otra autorización (ej. horas extras)

                    # --- Lógica para HORAS_EXTRAS ---
                    elif tipo_auth == 'HORAS_EXTRAS':
                        logger.info(f"Evaluando autorización de HORAS_EXTRAS para {usuario.get('legajo')}.")
                        auth_turno = autorizacion.get('turno')
                        if not auth_turno or 'hora_inicio' not in auth_turno or 'hora_fin' not in auth_turno:
                            continue

                        auth_inicio = time.fromisoformat(auth_turno['hora_inicio'])
                        auth_fin = time.fromisoformat(auth_turno['hora_fin'])
                        
                        # Para HORAS_EXTRAS, no hay período de gracia antes del inicio.
                        inicio_ventana_extra = auth_inicio
                        fin_ventana_extra = auth_fin

                        en_horario_extra = False
                        if fin_ventana_extra < inicio_ventana_extra:  # Turno extra cruza medianoche
                            if hora_actual >= inicio_ventana_extra or hora_actual <= fin_ventana_extra:
                                en_horario_extra = True
                        else:  # Turno extra diurno
                            if inicio_ventana_extra <= hora_actual <= fin_ventana_extra:
                                en_horario_extra = True
                        
                        if en_horario_extra:
                            logger.info(f"Acceso concedido por HORAS_EXTRAS para {usuario.get('legajo')}.")
                            return {'success': True, 'message': f"Acceso concedido por autorización de {tipo_auth}."}

            # --- 4. Si no hay período de gracia ni autorización válida, denegar acceso ---
            logger.warning(f"Acceso denegado para {usuario.get('legajo')}. Fuera de horario y sin autorización válida.")
            return {
                'success': False,
                'error': 'Acceso denegado.\nLlegada fuera del horario permitido.\nNo se encontró una autorización para el ingreso.\nPor favor, comuníquese con su supervisor o RRHH.'
            }

        except (ValueError, TypeError) as e:
            logger.error(f"Error procesando acceso para {usuario.get('legajo')}: {e}", exc_info=True)
            return {'success': False, 'error': f'Error interno al verificar horario: {e}'}

    def obtener_estado_acceso(self, usuario_id: int) -> Dict:
        """Obtiene el estado completo de acceso de un usuario (web y tótem)."""
        user_result = self.model.find_by_id(usuario_id)
        if not user_result.get('success'):
            return {'success': False, 'error': 'Usuario no encontrado'}
        user_data = user_result['data']
        
        tiene_sesion_activa = self.totem_sesion.verificar_sesion_activa_hoy(usuario_id)
        sesion_activa = self.totem_sesion.obtener_sesion_activa(usuario_id)

        return {'success': True, 'data': {
            'usuario_id': usuario_id,
            'nombre': user_data.get('nombre'),
            'email': user_data.get('email'),
            'sesion_totem_activa': tiene_sesion_activa,
            'detalle_sesion': sesion_activa.get('data'),
            'ultimo_login_web': user_data.get('ultimo_login_web'),
            'puede_acceder_web': tiene_sesion_activa
        }}

    # endregion

    # region Obtención de Datos Relacionados (Sectores, Roles, Turnos)

    def obtener_todos_los_sectores(self) -> List[Dict]:
        """Obtiene todos los sectores disponibles."""
        return self.sector_model.find_all().get('data', [])

    def obtener_sectores_usuario(self, usuario_id: int) -> List[Dict]:
        """Obtiene los sectores de un usuario específico."""
        resultado = self.usuario_sector_model.find_by_usuario(usuario_id)
        if resultado.get('success'):
            return [item['sectores'] for item in resultado['data'] if item.get('sectores')]
        return []

    def obtener_todos_los_roles(self) -> List[Dict]:
        """Obtiene una lista de todos los roles disponibles."""
        return self.role_model.find_all().get('data', [])

    def obtener_todos_los_turnos(self, usuario_id: Optional[int] = None) -> List[Dict]:
        """Obtiene turnos de trabajo, aplicando lógica de negocio si se especifica un usuario."""
        if usuario_id:
            return self.model.get_turnos_para_usuario(usuario_id).get('data', [])
        
        return self.turno_model.find_all().get('data', [])

    def obtener_turnos_para_autorizacion(self, tipo_autorizacion: str) -> dict:
        """
        Obtiene una lista de turnos filtrada según el tipo de autorización,
        implementando las mejores prácticas de UX para el formulario.
        """
        turnos_result = self.turno_model.find_all()
        if not turnos_result.get('success'):
            return turnos_result

        all_turnos = turnos_result.get('data', [])
        filtered_turnos = []

        if tipo_autorizacion == 'HORAS_EXTRAS':
            # Para horas extras, mostrar solo turnos que parezcan ser para ese fin.
            filtered_turnos = [
                t for t in all_turnos if 'extra' in t.get('nombre', '').lower()
            ]
        elif tipo_autorizacion in ['LLEGADA_TARDIA']:
            # Para llegadas tardías, mostrar solo los turnos principales.
            filtered_turnos = [
                t for t in all_turnos if 'mañana' in t.get('nombre', '').lower() or 'tarde' in t.get('nombre', '').lower()
            ]
        else:
            # Por defecto, o para otros tipos, devolver todos los turnos.
            filtered_turnos = all_turnos
        
        return {'success': True, 'data': filtered_turnos}

    def obtener_sectores_ids_usuario(self, usuario_id: int) -> List[int]:
        """Obtiene una lista solo con los IDs de los sectores de un usuario."""
        sectores = self.obtener_sectores_usuario(usuario_id)
        return [s['id'] for s in sectores if s]

    def gestionar_creacion_usuario_form(self, form_data: dict, facial_controller) -> dict:
        """
        Orquesta la creación de un usuario a partir de datos de formulario,
        incluyendo la validación y registro facial.
        """
        datos_usuario = dict(form_data)
        sectores_str = datos_usuario.get('sectores', '[]')
        try:
            sectores_ids = json.loads(sectores_str)
            datos_usuario['sectores'] = [int(s) for s in sectores_ids if isinstance(sectores_ids, list) and str(s).isdigit()]
        except (json.JSONDecodeError, TypeError):
             datos_usuario['sectores'] = [int(s) for s in datos_usuario.getlist('sectores') if s.isdigit()]

        face_data = datos_usuario.pop('face_data', None)
        if 'role_id' in datos_usuario:
            datos_usuario['role_id'] = int(datos_usuario['role_id'])

        if face_data:
            validacion_facial = facial_controller.validar_y_codificar_rostro(face_data)
            if not validacion_facial.get('success'):
                return validacion_facial

        resultado_creacion = self.crear_usuario(datos_usuario)
        
        if resultado_creacion.get('success') and face_data:
            usuario_creado = resultado_creacion.get('data')
            resultado_facial = facial_controller.registrar_rostro(usuario_creado.get('id'), face_data)
            if not resultado_facial.get('success'):
                # Adjuntar una advertencia en lugar de un error completo
                resultado_creacion['warning'] = f"Usuario creado, pero falló el registro facial: {resultado_facial.get('message')}"
        
        return resultado_creacion

    def gestionar_actualizacion_usuario_form(self, usuario_id: int, form_data: dict) -> dict:
        """
        Orquesta la actualización de un usuario a partir de datos de formulario,
        manejando la normalización de datos.
        """
        datos_actualizados = dict(form_data)
        
        # Procesamiento de Sectores
        sectores_str = datos_actualizados.get('sectores', '[]')
        try:
            sectores_ids = json.loads(sectores_str)
            if isinstance(sectores_ids, list):
                datos_actualizados['sectores'] = [int(s) for s in sectores_ids if str(s).isdigit()]
        except (json.JSONDecodeError, TypeError):
            # Fallback para Formulario normal
            datos_actualizados['sectores'] = [int(s) for s in form_data.getlist('sectores') if s.isdigit()]

        # Role ID y Turno ID
        for key in ['role_id', 'turno_id']:
            if key in datos_actualizados and str(datos_actualizados[key]).isdigit():
                datos_actualizados[key] = int(datos_actualizados[key])
            else:
                datos_actualizados.pop(key, None)
        
        return self.actualizar_usuario(usuario_id, datos_actualizados)

    # endregion

    # region Reportería y Actividad

    def obtener_actividad_totem(self, filtros: Optional[Dict] = None) -> Dict:
        """Obtiene la lista de actividad del tótem, con filtros opcionales."""
        return self.totem_sesion.obtener_actividad_filtrada(filtros)

    def obtener_actividad_web(self, filtros: Optional[Dict] = None) -> Dict:
        """Obtiene la lista de logins en la web, con filtros opcionales."""
        return self.model.find_by_web_login_filtrado(filtros)

    def obtener_porcentaje_asistencia(self) -> float:
        """Calcula el porcentaje de asistencia actual basado en sesiones de tótem activas."""
        todos_activos = self.model.find_all({'activo': True})
        if not todos_activos.get('success') or not todos_activos.get('data'):
            return 0.0
        
        usuarios_activos = todos_activos['data']
        total_usuarios_activos = len(usuarios_activos)
        if total_usuarios_activos == 0:
            return 0.0
        
        cant_en_empresa = sum(1 for usuario in usuarios_activos if self.totem_sesion.verificar_sesion_activa_hoy(usuario['id']))
        return round((cant_en_empresa / total_usuarios_activos) * 100, 0)

    # endregion

    # region Validación y Helpers

    def validar_campo_unico(self, field: str, value: str, user_id: Optional[int] = None) -> Dict:
        """Verifica si un valor de campo ya existe en la base de datos."""
        field_map = {'legajo': 'Legajo', 'email': 'Email', 'cuil_cuit': 'CUIL/CUIT', 'telefono': 'Teléfono'}
        find_methods = {
            'legajo': self.model.find_by_legajo, 'email': self.model.find_by_email,
            'cuil_cuit': self.model.find_by_cuil, 'telefono': self.model.find_by_telefono
        }
        find_method = find_methods.get(field)
        if not find_method:
            return {'valid': False, 'error': 'Campo de validación no soportado.'}

        try:
            result = find_method(value)
            if result.get('success'):
                if user_id and str(result['data']['id']) != str(user_id):
                    return {'valid': False, 'message': f'El {field_map.get(field)} ya está en uso por otro usuario.'}
                if not user_id:
                    return {'valid': False, 'message': f'El {field_map.get(field)} ya está en uso.'}
            
            return {'valid': True}
        except Exception as e:
            logger.error(f"Error en validación de campo único: {str(e)}", exc_info=True)
            return {'valid': False, 'error': 'Error interno durante la validación.'}

    def _autenticar_credenciales_base(self, legajo: str, password: str) -> Dict:
        """Método base reutilizable para autenticar por legajo y contraseña."""
        usuario_result = self.model.find_by_legajo(legajo)
        if not usuario_result.get('success'):
            return {'success': False, 'error': 'Legajo o contraseña incorrectos.'}
        
        user_data = usuario_result['data']
        if not user_data.get('activo', True):
            return {'success': False, 'error': 'Usuario inactivo. Contacte al administrador.'}
        if not check_password_hash(user_data['password_hash'], password):
            return {'success': False, 'error': 'Legajo o contraseña incorrectos.'}
        
        return {'success': True, 'data': user_data}

    def _iniciar_sesion_usuario(self, usuario: Dict) -> Dict:
        """Helper centralizado para establecer la sesión de Flask de un usuario."""
        logger.info(f"Initiating session for user_id: {usuario.get('id')}")
        verificacion_turno = self.verificar_acceso_por_horario(usuario)
        if not verificacion_turno.get('success'):
            logger.warning(f"Session initiation failed for user_id {usuario.get('id')}: {verificacion_turno.get('error')}")
            return verificacion_turno

        logger.info(f"Access verified for user_id: {usuario.get('id')}. Loading permissions.")
        permisos = PermisosModel().get_user_permissions(usuario.get('role_id'))
        rol = usuario.get('roles', {})
        
        session.clear()
        session['usuario_id'] = usuario.get('id')
        session['rol_id'] = usuario.get('role_id')
        session['rol'] = rol.get('codigo')
        session['user_level'] = rol.get('nivel', 0)
        session['usuario_nombre'] = usuario.get('nombre', '')
        session['user_data'] = usuario
        session['permisos'] = permisos
        
        logger.info(f"Session successfully created for user_id: {usuario.get('id')}, role: {rol.get('codigo')}")
        return {'success': True, 'rol_codigo': rol.get('codigo')}

    def _asignar_sectores_usuario(self, usuario_id: int, sectores_ids: List[int]) -> Dict:
        """Helper para asignar una lista de sectores a un usuario."""
        for sector_id in sectores_ids:
            resultado = self.usuario_sector_model.asignar_sector(usuario_id, sector_id)
            if not resultado.get('success'):
                self.usuario_sector_model.eliminar_todas_asignaciones(usuario_id)
                return {'success': False, 'error': f'Error asignando sector ID {sector_id}'}
        return {'success': True}

    def _actualizar_datos_principales(self, usuario_id: int, user_data: Dict, existing_user: Dict, new_direccion_id: Optional[int]) -> Dict:
        """Helper para actualizar los campos principales de un usuario."""
        user_data_changed = any(str(user_data.get(k) or '') != str(existing_user.get(k) or '') for k in user_data)
        if not user_data_changed and new_direccion_id == existing_user.get('direccion_id'):
            return {'success': True}

        try:
            loadable_fields = {k for k, v in self.schema.fields.items() if not v.dump_only}
            validated_data = self.schema.load({k: v for k, v in user_data.items() if k in loadable_fields}, partial=True)
        except ValidationError as e:
            return {'success': False, 'error': f"Datos de usuario inválidos: {e.messages}"}

        if 'password' in validated_data and validated_data['password']:
            validated_data['password_hash'] = generate_password_hash(validated_data.pop('password'))
        else:
            validated_data.pop('password', None)
        
        if 'email' in validated_data:
            existing_email = self.model.find_by_email(validated_data['email']).get('data')
            if existing_email and existing_email['id'] != usuario_id:
                return {'success': False, 'error': 'El correo electrónico ya está en uso.'}

        validated_data['direccion_id'] = new_direccion_id
        return self.model.update(usuario_id, validated_data)

    def _actualizar_direccion_usuario(self, usuario_id: int, direccion_data: Dict, existing_user: Dict) -> Dict:
        """Helper para la lógica de actualización de direcciones."""
        if 'altura' in direccion_data and direccion_data['altura'] == '':
            direccion_data['altura'] = None
        
        has_new_address_data = all(direccion_data.get(f) for f in ['calle', 'altura', 'localidad', 'provincia'])
        original_direccion_id = existing_user.get('direccion_id')

        if not has_new_address_data:
            return {'success': True, 'direccion_id': original_direccion_id}

        existing_address = existing_user.get('direccion') or {}
        address_changed = any(str(direccion_data.get(k) or '') != str(existing_address.get(k) or '') for k in direccion_data)

        if not address_changed:
            return {'success': True, 'direccion_id': original_direccion_id}

        direccion_normalizada = self._normalizar_y_preparar_direccion(direccion_data)
        if not direccion_normalizada:
            return {'success': False, 'error': "No se pudo normalizar la dirección."}

        if original_direccion_id and not self.direccion_model.is_address_shared(original_direccion_id, excluding_user_id=usuario_id):
            update_result = self.direccion_model.update(original_direccion_id, direccion_normalizada)
            if update_result.get('success'):
                return {'success': True, 'direccion_id': original_direccion_id}
        
        # Asumo que _get_or_create_direccion existe
        new_direccion_id = self._get_or_create_direccion(direccion_normalizada)
        if new_direccion_id:
            return {'success': True, 'direccion_id': new_direccion_id}

        return {'success': False, 'error': "No se pudo procesar la nueva dirección."}

    def _actualizar_sectores_usuario(self, usuario_id: int, sectores_ids: Optional[List[int]], existing_user: Dict) -> Dict:
        """Helper para la lógica de actualización de sectores."""
        if sectores_ids is None:
            return {'success': True}
        
        existing_sector_ids = {s['id'] for s in existing_user.get('sectores', [])}
        if set(sectores_ids) == existing_sector_ids:
            return {'success': True}

        self.usuario_sector_model.eliminar_todas_asignaciones(usuario_id)
        if sectores_ids:
            return self._asignar_sectores_usuario(usuario_id, sectores_ids)
        return {'success': True}

    def _normalizar_y_preparar_direccion(self, direccion_data: Dict) -> Optional[Dict]:
        """Helper para normalizar una dirección usando un servicio externo."""
        if not all(direccion_data.get(k) for k in ['calle', 'altura', 'localidad', 'provincia']):
            return direccion_data

        full_street = f"{direccion_data['calle']} {direccion_data['altura']}"
        if direccion_data.get('piso'):
            full_street += f", Piso {direccion_data.get('piso')}"
        if direccion_data.get('depto'):
            full_street += f", Depto {direccion_data.get('depto')}"

        norm_result = self.usuario_direccion_controller.normalizar_direccion(
            direccion=full_street,
            localidad=direccion_data['localidad'],
            provincia=direccion_data['provincia']
        )

        if not norm_result.get('success'):
            return direccion_data 
        
        norm_data = norm_result['data']
        return {
            "calle": norm_data['calle']['nombre'],
            "altura": norm_data['altura']['valor'],
            "piso": direccion_data.get('piso'),
            "depto": direccion_data.get('depto'),
            "codigo_postal": norm_data.get('codigo_postal', direccion_data.get('codigo_postal')),
            "localidad": norm_data['localidad_censal']['nombre'],
            "provincia": norm_data['provincia']['nombre'],
            "latitud": norm_data['ubicacion']['lat'],
            "longitud": norm_data['ubicacion']['lon']
        }

    def _sesion_debe_cerrarse(self, usuario: dict, session: dict) -> bool:
        """
        Determina si una sesión de tótem específica debe cerrarse por haber expirado.
        """
        turno = usuario.get('turno')
        if not turno or not turno.get('hora_fin'):
            return False # No se puede determinar, no se cierra

        try:
            hora_fin_turno = datetime.strptime(turno['hora_fin'], '%H:%M:%S').time()
            session_start_date = datetime.fromisoformat(session['fecha_inicio']).date()
            shift_end_datetime = datetime.combine(session_start_date, hora_fin_turno)
            
            # Si el turno termina al día siguiente (turno noche)
            if shift_end_datetime < datetime.fromisoformat(session['fecha_inicio']):
                shift_end_datetime += timedelta(days=1)

            grace_period_end = shift_end_datetime + timedelta(minutes=15)
            
            now_in_argentina = get_now_in_argentina()

            if now_in_argentina > grace_period_end:
                # La sesión ha expirado, a menos que haya horas extras.
                autorizacion_model = AutorizacionIngresoModel()
                auth_result = autorizacion_model.find_by_usuario_and_fecha(
                    usuario['id'], now_in_argentina.date(), tipo='HORAS_EXTRAS', estado='APROBADO'
                )
                if auth_result.get('success') and auth_result.get('data'):
                    # El usuario tiene autorización, no se cierra la sesión.
                    return False 
                return True # La sesión expiró y no hay autorización.
        except (ValueError, TypeError):
            return False # Error en los datos, no se arriesga a cerrar.
            
        return False
    # endregion
