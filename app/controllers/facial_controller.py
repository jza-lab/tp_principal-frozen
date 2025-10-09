import os
import cv2
import numpy as np
import base64
import re
from datetime import datetime
import json
import logging
from typing import Dict
from app.database import Database
from app.models.totem_sesion import TotemSesionModel
from app.models.usuario_turno import UsuarioTurnoModel
from app.models.autorizacion_ingreso import AutorizacionIngresoModel
from app.models.notificacion import NotificacionModel
from datetime import datetime, timedelta, time

logger = logging.getLogger(__name__)

class FacialController:
    """
    Controlador actualizado para operaciones faciales usando la nueva estructura de sesiones.
    """
    
    def __init__(self):
        self.db = Database().client
        self.totem_sesion_model = TotemSesionModel()
        self.turno_model = UsuarioTurnoModel()
        self.autorizacion_model = AutorizacionIngresoModel()
        self.notificacion_model = NotificacionModel()
        self.save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Data")
        os.makedirs(self.save_dir, exist_ok=True)

    def _get_image_from_data_url(self, image_data_url):
        """Convierte data URL a imagen OpenCV"""
        try:
            image_data = re.sub('^data:image/.+;base64,', '', image_data_url)
            image_bytes = base64.b64decode(image_data)
            np_arr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            return frame
        except Exception as e:
            logger.error(f"Error decodificando imagen: {e}")
            return None

    def identificar_rostro(self, image_data_url):
        """
        Intenta identificar un usuario a partir de una imagen facial.
        Ahora solo busca usuarios activos sin depender de flags obsoletos.
        """
        import face_recognition
        frame = self._get_image_from_data_url(image_data_url)
        if frame is None:
            return {'success': False, 'message': 'Error al procesar la imagen.'}

        # Asegurarse de que el frame es RGB para face_recognition
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_encodings = face_recognition.face_encodings(rgb_frame)

        if not face_encodings:
            return {'success': False, 'message': 'No se detectó rostro en la imagen'}

        input_encoding = face_encodings[0]

        try:
            # Solo buscar usuarios activos con encoding facial
            response = self.db.table("usuarios").select(
                "id, email, nombre, apellido, facial_encoding, role_id, roles(codigo, nombre), activo, turno_id"
            ).not_.is_("facial_encoding", "null").eq("activo", True).execute()
            
            usuarios = response.data
            if not usuarios:
                return {'success': False, 'message': 'No hay usuarios con rostros registrados.'}

            known_encodings = []
            usuarios_con_encoding = []

            # Decodificar y recopilar los encodings válidos
            for usuario in usuarios:
                if usuario.get('facial_encoding'):
                    try:
                        encoding = np.array(json.loads(usuario['facial_encoding']))
                        known_encodings.append(encoding)
                        usuarios_con_encoding.append(usuario)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(f"No se pudo decodificar el encoding para el usuario ID: {usuario.get('id')}")
                        continue
            
            if not known_encodings:
                return {'success': False, 'message': 'No se encontraron codificaciones faciales válidas.'}

            face_distances = face_recognition.face_distance(known_encodings, input_encoding)

            best_match_index = np.argmin(face_distances)
            min_distance = face_distances[best_match_index]

            logger.info(f"Distancia mínima encontrada: {min_distance} para el usuario: {usuarios_con_encoding[best_match_index].get('email')}")

            TOLERANCE = 0.5
            if min_distance <= TOLERANCE:
                best_match_user = usuarios_con_encoding[best_match_index]
                # Aplanar la estructura del rol para mantener compatibilidad
                if 'roles' in best_match_user and best_match_user['roles']:
                    best_match_user['rol'] = best_match_user['roles']['codigo']
                return {'success': True, 'usuario': best_match_user}
            else:
                return {'success': False, 'message': 'Rostro no reconocido.'}

        except Exception as e:
            logger.error(f"Error en la base de datos durante la identificación facial: {e}")
            return {'success': False, 'message': 'Error del servidor.'}

    def registrar_rostro(self, user_id, image_data_url):
        """
        Registra un rostro para un usuario específico, previniendo duplicados y fotos sin rostro.
        """
        # Primero, validar que la imagen contiene un rostro y que es único.
        validacion_rostro = self.validar_y_codificar_rostro(image_data_url)
        if not validacion_rostro.get('success'):
            return validacion_rostro

        new_encoding_json = validacion_rostro.get('encoding')

        try:
            # Si la validación es exitosa, actualizar el usuario con el nuevo encoding.
            response = self.db.table("usuarios").update({
                "facial_encoding": new_encoding_json,
                "updated_at": datetime.now().isoformat()
            }).eq("id", user_id).execute()
            
            if response.data:
                return {'success': True, 'message': 'Rostro registrado correctamente.'}
            else:
                return {'success': False, 'message': 'Usuario no encontrado al intentar guardar el rostro.'}
                
        except Exception as e:
            logger.error(f"Error en la base de datos durante el registro facial: {e}")
            return {'success': False, 'message': 'Error del servidor al guardar el rostro.'}

    def validar_y_codificar_rostro(self, image_data_url):
        """
        Valida que una imagen contenga un único rostro y que no esté ya registrado.
        Devuelve el encoding si la validación es exitosa.
        """
        import face_recognition
        frame = self._get_image_from_data_url(image_data_url)
        if frame is None:
            return {'success': False, 'message': 'Error al procesar la imagen.'}

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_encodings = face_recognition.face_encodings(rgb_frame)

        if not face_encodings:
            return {'success': False, 'message': 'No se pudo detectar un rostro en la imagen. Asegúrese de que la cara esté bien iluminada y centrada.'}
        
        if len(face_encodings) > 1:
            return {'success': False, 'message': 'Se detectaron múltiples rostros en la imagen. Por favor, tome una foto solo con su cara.'}

        identificacion_previa = self.identificar_rostro(image_data_url)
        if identificacion_previa.get('success'):
            return {'success': False, 'message': 'Este rostro ya ha sido registrado por otro usuario.'}
            
        new_encoding_json = json.dumps(face_encodings[0].tolist())
        return {'success': True, 'encoding': new_encoding_json}

    def registrar_acceso(self, usuario_id, tipo, metodo, dispositivo, sesion_totem_id=None, ubicacion_totem=None, observaciones=None):
        """Registra entrada/salida en la base de datos con la nueva estructura"""
        try:
            registro_data = {
                "usuario_id": usuario_id,
                "fecha_hora": datetime.now().isoformat(),
                "tipo": tipo,
                "metodo": metodo,
                "dispositivo": dispositivo,
                "sesion_totem_id": sesion_totem_id,
                "ubicacion_totem": ubicacion_totem,
                "observaciones": observaciones
            }

            logger.info(f"📝 Registrando acceso: usuario={usuario_id}, tipo={tipo}, metodo={metodo}")

            response = self.db.table("registros_acceso").insert(registro_data).execute()

            if response.data:
                logger.info(f"✅ Registro de {tipo} para usuario {usuario_id}")
                return {'success': True, 'data': response.data[0]}
            else:
                logger.error("❌ No se pudo insertar el registro")
                return {'success': False, 'error': 'Error registrando acceso'}
                
        except Exception as e:
            logger.error(f"❌ Error registrando acceso: {e}")
            return {'success': False, 'error': str(e)}

    def _validar_acceso_por_turno(self, usuario: dict):
        """
        Valida el acceso de un usuario según su turno, la hora actual y las autorizaciones.
        La lógica es más estricta: la tardanza sin autorización deniega el acceso.
        """
        usuario_id = usuario['id']
        turno_id = usuario.get('turno_id')

        if not turno_id:
            logger.info(f"Usuario {usuario_id} no tiene turno asignado. Acceso permitido por defecto.")
            return {'success': True}

        turnos_result = self.turno_model.find_all()
        if not turnos_result.get('success'):
            return {'success': False, 'message': 'Error del sistema: No se pudo verificar el turno.'}
        
        turnos_data = turnos_result['data']
        turno_asignado = next((t for t in turnos_data if t['id'] == turno_id), None)
        
        if not turno_asignado:
            return {'success': False, 'message': 'Error: Su turno configurado no es válido.'}

        # Excepción para el turno rotativo
        if turno_asignado.get('nombre').upper() == 'ROTATIVO':
            logger.info(f"Usuario {usuario_id} tiene turno rotativo. Acceso permitido a cualquier hora.")
            return {'success': True}

        ahora = datetime.now()
        hora_actual = ahora.time()
        fecha_actual = ahora.date()
        margen_tolerancia = timedelta(minutes=15)

        hora_inicio_turno = datetime.strptime(turno_asignado['hora_inicio'], '%H:%M:%S').time()
        hora_fin_turno = datetime.strptime(turno_asignado['hora_fin'], '%H:%M:%S').time()
        
        inicio_permitido = (datetime.combine(fecha_actual, hora_inicio_turno) - margen_tolerancia).time()
        limite_tardanza = (datetime.combine(fecha_actual, hora_inicio_turno) + margen_tolerancia).time()

        # 1. Chequeo de acceso dentro del turno normal (con tolerancia de ingreso)
        if inicio_permitido <= hora_actual <= hora_fin_turno:
            # Si está después del límite de tardanza, igual se registra. La penalización es lógica.
            if hora_actual > limite_tardanza:
                mensaje = f"El empleado {usuario.get('nombre')} {usuario.get('apellido')} (Legajo: {usuario.get('legajo')}) ha llegado tarde a las {hora_actual.strftime('%H:%M:%S')}."
                self.notificacion_model.create({'usuario_id': usuario_id, 'tipo': 'TARDANZA', 'mensaje': mensaje})
                logger.info(f"NOTIFICACION CREADA: Usuario {usuario_id} llegó tarde.")
            
            logger.info(f"Acceso en turno para usuario {usuario_id}.")
            return {'success': True}

        # 2. Si está fuera de su turno, buscar autorización para TARDANZA o TURNO_ESPECIAL
        logger.info(f"Usuario {usuario_id} intenta acceder fuera de su turno. Buscando autorización...")

        # Intenta buscar autorización para tardanza primero
        auth_tardanza = self.autorizacion_model.find_by_usuario_and_fecha(usuario_id, fecha_actual, tipo='TARDANZA')
        if auth_tardanza.get('success'):
            logger.info(f"Acceso permitido para usuario {usuario_id} con autorización de TARDANZA.")
            return {'success': True}

        # Si no hay de tardanza, busca para turno especial
        auth_especial = self.autorizacion_model.find_by_usuario_and_fecha(usuario_id, fecha_actual, tipo='TURNO_ESPECIAL')
        if auth_especial.get('success'):
            autorizacion = auth_especial['data']
            turno_autorizado_id = autorizacion.get('turno_autorizado_id')
            
            if not turno_autorizado_id:
                logger.error(f"Autorización ID {autorizacion['id']} no tiene un turno_autorizado_id.")
                return {'success': False, 'message': 'Error en la configuración de la autorización.'}

            turno_autorizado = next((t for t in turnos_data if t['id'] == turno_autorizado_id), None)
            if not turno_autorizado:
                return {'success': False, 'message': 'Error: Turno autorizado inválido.'}

            hora_inicio_auth = datetime.strptime(turno_autorizado['hora_inicio'], '%H:%M:%S').time()
            hora_fin_auth = datetime.strptime(turno_autorizado['hora_fin'], '%H:%M:%S').time()
            inicio_permitido_auth = (datetime.combine(fecha_actual, hora_inicio_auth) - margen_tolerancia).time()

            if inicio_permitido_auth <= hora_actual <= hora_fin_auth:
                logger.info(f"Acceso permitido para usuario {usuario_id} con autorización para el turno '{turno_autorizado['nombre']}'.")
                return {'success': True}
            else:
                logger.warning(f"Acceso denegado. Usuario {usuario_id} con autorización pero fuera de horario del turno autorizado.")
                return {'success': False, 'message': 'Autorización encontrada, pero intenta acceder fuera del horario permitido.'}

        # 3. Si no hay ninguna autorización válida, denegar acceso.
        logger.warning(f"Acceso denegado. Usuario {usuario_id} sin autorización válida para hoy.")
        return {'success': False, 'message': 'Acceso fuera de horario. Requiere autorización de supervisor.'}

    def _manejar_logica_acceso(self, usuario: dict, metodo: str):
        """
        Lógica actualizada para registrar entrada/salida usando sesiones de tótem.
        """
        usuario_id = usuario['id']
        usuario_nombre = usuario.get('nombre', 'Usuario')

        # Verificar si ya tiene sesión activa hoy
        tiene_sesion_activa = self.totem_sesion_model.verificar_sesion_activa_hoy(usuario_id)

        if not tiene_sesion_activa:
            # Lógica de ENTRADA
            logger.info(f"Procesando ENTRADA para {usuario_nombre} a través de {metodo}")
            
            # Validar acceso por turno
            validacion_turno = self._validar_acceso_por_turno(usuario)
            if not validacion_turno.get('success'):
                return validacion_turno

            # Crear sesión de tótem
            resultado_sesion = self.totem_sesion_model.crear_sesion(usuario_id, metodo)
            if not resultado_sesion.get('success'):
                return {
                    'success': False,
                    'message': 'Error al registrar la sesión de entrada'
                }

            # Registrar acceso de entrada
            self.registrar_acceso(
                usuario_id, 
                "ingreso", 
                metodo, 
                "TOTEM",
                sesion_totem_id=resultado_sesion['data']['id'],
                ubicacion_totem='TOTEM_PRINCIPAL'
            )
            
            return {
                'success': True,
                'tipo_acceso': 'ENTRADA',
                'message': f"¡Bienvenido, {usuario_nombre}!",
                'usuario': usuario
            }
        else:
            # Lógica de SALIDA
            logger.info(f"Procesando SALIDA para {usuario_nombre} a través de {metodo}")
            
            # Cerrar sesión de tótem
            resultado_cierre = self.totem_sesion_model.cerrar_sesion(usuario_id)
            if not resultado_cierre.get('success'):
                logger.warning(f"No se pudo cerrar sesión para usuario {usuario_id}")

            # Registrar acceso de salida
            self.registrar_acceso(
                usuario_id, 
                "egreso", 
                metodo, 
                "TOTEM",
                ubicacion_totem='TOTEM_PRINCIPAL'
            )

            return {
                'success': True,
                'tipo_acceso': 'SALIDA',
                'message': f"👋 ¡Hasta luego, {usuario_nombre}!",
                'usuario': usuario
            }

    def procesar_acceso_unificado_totem(self, image_data_url):
        """
        Procesa un acceso facial desde el tótem, identificando al usuario y registrando la entrada/salida.
        """
        try:
            resultado_identificacion = self.identificar_rostro(image_data_url)
            if not resultado_identificacion.get('success'):
                return resultado_identificacion

            usuario = resultado_identificacion['usuario']
            return self._manejar_logica_acceso(usuario, "FACIAL")

        except Exception as e:
            logger.error(f"Error en procesar_acceso_unificado_totem: {str(e)}")
            return {'success': False, 'message': f'Error en el servidor: {str(e)}'}

    def procesar_acceso_manual_totem(self, legajo, password):
        """
        Procesa un acceso manual desde el tótem, autenticando y registrando la entrada/salida.
        """
        try:
            from app.controllers.usuario_controller import UsuarioController
            usuario_controller = UsuarioController()
            
            resultado_autenticacion = usuario_controller.autenticar_usuario_para_totem(legajo, password)
            if not resultado_autenticacion.get('success'):
                return {'success': False, 'message': resultado_autenticacion.get('error', 'Credenciales inválidas.')}
            
            usuario = resultado_autenticacion.get('data')
            if not usuario:
                return {'success': False, 'message': 'No se pudo obtener datos del usuario.'}

            return self._manejar_logica_acceso(usuario, "CREDENCIAL")

        except Exception as e:
            logger.error(f"Error en procesar_acceso_manual_totem: {str(e)}")
            return {'success': False, 'message': f'Error en el servidor: {str(e)}'}