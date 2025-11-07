import os
import cv2
import numpy as np
import base64
import re
import json
import logging
import time  # Importar el módulo time
from typing import Dict, Optional
from datetime import datetime, timedelta
from flask import render_template
from app.database import Database
from app.models.totem_sesion import TotemSesionModel
from app.controllers.usuario_controller import UsuarioController
from app.utils.date_utils import get_now_in_argentina
from app.models.totem_2fa_token import Totem2FATokenModel
from app.services.email_service import send_email
from app.controllers.registro_controller import RegistroController

try:
    import face_recognition
except ImportError:
    face_recognition = None

logger = logging.getLogger(__name__)

class FacialController:
    """
    Controlador para gestionar todas las operaciones de reconocimiento facial,
    incluyendo el registro, la identificación y el procesamiento de acceso.
    """
    
    def __init__(self):
        """
        Inicializa el controlador, estableciendo la conexión a la base de datos
        y preparando las dependencias de otros modelos y controladores.
        """
        self.db = Database().client
        self.totem_sesion_model = TotemSesionModel()
        self.usuario_controller = UsuarioController()
        self.token_2fa_model = Totem2FATokenModel()
        self.registro_controller = RegistroController()
        
        # Inicialización del caché para perfiles faciales
        self._cached_encodings = []
        self._cached_users = []
        self._cache_is_dirty = True  # Flag para forzar la recarga inicial

        # El directorio para guardar datos faciales no se usa activamente,
        self.save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Data")
        os.makedirs(self.save_dir, exist_ok=True)

    # region Métodos Públicos (Puntos de Entrada)
    def procesar_acceso_unificado_totem(self, image_data_url: str) -> Dict:
        """
        Punto de entrada para el acceso facial desde el tótem.
        Identifica al usuario y registra la entrada o salida correspondiente.
        """
        try:
            resultado_identificacion = self.identificar_rostro(image_data_url)
            if not resultado_identificacion.get('success'):
                return resultado_identificacion

            usuario = resultado_identificacion['usuario']
            return self._manejar_logica_acceso(usuario, "FACIAL")

        except Exception as e:
            logger.error(f"Error en procesar_acceso_unificado_totem: {str(e)}", exc_info=True)
            return {'success': False, 'message': f'Error interno del servidor: {str(e)}'}

    def procesar_acceso_manual_totem(self, legajo: str, password: str) -> Dict:
        """
        Punto de entrada para el acceso manual desde el tótem.
        Autentica al usuario y registra la entrada o salida.
        """
        try:
            resultado_autenticacion = self.usuario_controller.autenticar_usuario_para_totem(legajo, password)
            if not resultado_autenticacion.get('success'):
                return {'success': False, 'message': resultado_autenticacion.get('error', 'Credenciales inválidas.')}
            
            usuario = resultado_autenticacion.get('data')
            if not usuario:
                return {'success': False, 'message': 'No se pudieron obtener los datos del usuario.'}

            # 1. Verificar horario ANTES de enviar el correo
            validacion_turno = self.usuario_controller.verificar_acceso_por_horario(usuario)
            if not validacion_turno.get('success'):
                return {'success': False, 'message': validacion_turno.get('error')}

            # 2. Verificar que el usuario tenga un email
            if not usuario.get('email'):
                logger.error(f"Usuario {legajo} no tiene un email registrado para 2FA.")
                return {'success': False, 'message': 'No tienes un correo electrónico registrado. Contacta a un administrador.'}

            # 3. Si todo es correcto, generar y enviar token 2FA
            resultado_token = self.token_2fa_model.create_token(usuario['id'])
            if not resultado_token.get('success'):
                return {'success': False, 'message': resultado_token.get('error', 'No se pudo generar el código de verificación.')}
            
            token = resultado_token.get('token')
            subject = "Tu Código de Verificación para Fichar"
            body = render_template('totem/token_2fa.html', nombre_usuario=usuario.get('nombre', ''), token=token)
            
            sent, message = send_email(usuario['email'], subject, body, config_prefix='TOKEN_MAIL')
            if not sent:
                logger.error(f"Fallo al enviar el email 2FA a {usuario['email']}: {message}")
                return {'success': False, 'message': 'No se pudo enviar el correo de verificación. Inténtalo de nuevo más tarde.'}

            return {'success': True, 'requires_2fa': True, 'message': 'Se ha enviado un código a tu correo.'}

        except Exception as e:
            logger.error(f"Error en procesar_acceso_manual_totem: {str(e)}", exc_info=True)
            return {'success': False, 'message': f'Error interno del servidor: {str(e)}'}

    def verificar_token_2fa(self, legajo: str, token: str) -> Dict:
        """Verifica el token 2FA y completa el fichaje si es válido."""
        try:
            user_result = self.usuario_controller.model.find_by_legajo(legajo)
            if not user_result.get('success'):
                return {'success': False, 'message': 'Usuario no encontrado.'}
            
            usuario = user_result['data']
            verification_result = self.token_2fa_model.verify_token(usuario['id'], token)

            if verification_result.get('success'):
                return self._manejar_logica_acceso(usuario, "CREDENCIAL")
            
            return verification_result

        except Exception as e:
            logger.error(f"Error en verificar_token_2fa: {e}", exc_info=True)
            return {'success': False, 'message': f'Error interno: {str(e)}'}

    def reenviar_token_2fa(self, legajo: str) -> Dict:
        """Reenvía un nuevo token 2FA al correo del usuario."""
        try:
            user_result = self.usuario_controller.model.find_by_legajo(legajo)
            if not user_result.get('success'):
                return {'success': False, 'message': 'Usuario no encontrado.'}
            
            usuario = user_result['data']

            # Límite de reenvíos
            recent_tokens_count = self.token_2fa_model.count_recent_tokens(usuario['id'])
            if recent_tokens_count >= 3:
                return {'success': False, 'message': 'Has alcanzado el límite de reenvíos. Por favor, intenta de nuevo más tarde.'}

            # Cooldown para reenviar token (mantenido por si acaso)
            active_token = self.token_2fa_model.find_active_token(usuario['id'])
            if active_token:
                created_at = datetime.fromisoformat(active_token['created_at'])
                now = get_now_in_argentina()
                if now - created_at < timedelta(seconds=30):
                    return {'success': False, 'message': 'Debes esperar 30 segundos para reenviar el código.'}

            # Reutilizar la misma lógica de creación y envío
            resultado_token = self.token_2fa_model.create_token(usuario['id'])
            if not resultado_token.get('success'):
                return {'success': False, 'message': resultado_token.get('error')}
            
            token = resultado_token.get('token')
            subject = "Tu Nuevo Código de Verificación para Fichar"
            body = render_template('totem/token_2fa.html', nombre_usuario=usuario.get('nombre', ''), token=token)
            
            sent, message = send_email(usuario['email'], subject, body, config_prefix='TOKEN_MAIL')
            if not sent:
                return {'success': False, 'message': 'No se pudo enviar el correo. Intenta de nuevo.'}

            return {'success': True, 'message': 'Se ha enviado un nuevo código a tu correo.'}

        except Exception as e:
            logger.error(f"Error en reenviar_token_2fa: {e}", exc_info=True)
            return {'success': False, 'message': f'Error interno: {str(e)}'}

    def registrar_rostro(self, user_id: int, image_data_url: str) -> Dict:
        """
        Registra un nuevo rostro para un usuario específico.
        """
        validacion_rostro = self.validar_y_codificar_rostro(image_data_url)
        if not validacion_rostro.get('success'):
            return validacion_rostro

        new_encoding_json = validacion_rostro.get('encoding')
        try:
            response = self.db.table("usuarios").update({
                "facial_encoding": new_encoding_json,
                "updated_at": get_now_in_argentina().isoformat()
            }).eq("id", user_id).execute()
            
            if response.data:
                # Invalidar el caché para forzar la recarga en la próxima identificación
                self._invalidar_cache()
                return {'success': True, 'message': 'Rostro registrado correctamente.'}
            
            return {'success': False, 'message': 'Usuario no encontrado al intentar guardar el rostro.'}
                
        except Exception as e:
            logger.error(f"Error de base de datos durante el registro facial: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'Error del servidor al guardar el rostro.'}

    # endregion

    # region Lógica de Reconocimiento Facial
    def identificar_rostro(self, image_data_url: str) -> Dict:
        """
        Identifica un usuario comparando una imagen facial con los perfiles
        registrados en la base de datos.
        """
        if face_recognition is None:
            return {'success': False, 'message': 'Librería de reconocimiento facial no disponible.'}

        t0 = time.time()
        frame = self._get_image_from_data_url(image_data_url)
        if frame is None:
            return {'success': False, 'message': 'Error al procesar la imagen.'}
        t1 = time.time()
        logger.info(f"[PERF] Decodificación de imagen: {t1 - t0:.2f} segundos.")

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_encodings = face_recognition.face_encodings(rgb_frame)
        t2 = time.time()
        logger.info(f"[PERF] Detección y codificación de rostros: {t2 - t1:.2f} segundos.")

        if not face_encodings:
            return {'success': False, 'message': 'No se detectó un rostro en la imagen.'}

        input_encoding = face_encodings[0]

        if self._cache_is_dirty:
            self._cargar_y_cachear_perfiles()

        if not self._cached_encodings:
            return {'success': False, 'message': 'No hay perfiles faciales cargados o disponibles.'}

        face_distances = face_recognition.face_distance(self._cached_encodings, input_encoding)
        best_match_index = np.argmin(face_distances)
        min_distance = face_distances[best_match_index]

        TOLERANCE = 0.5  # Umbral de similitud
        if min_distance <= TOLERANCE:
            best_match_user = self._cached_users[best_match_index]
            logger.info(f"Rostro identificado con distancia {min_distance}: {best_match_user.get('email')}")
            return {'success': True, 'usuario': best_match_user}
        
        return {'success': False, 'message': 'Rostro no reconocido.'}

    def validar_y_codificar_rostro(self, image_data_url: str) -> Dict:
        """
        Valida que una imagen contenga un único rostro, que no esté ya registrado, y devuelve su codificación.
        """
        if face_recognition is None:
            return {'success': False, 'message': 'Librería de reconocimiento facial no disponible.'}
            
        frame = self._get_image_from_data_url(image_data_url)
        if frame is None:
            return {'success': False, 'message': 'Error al procesar la imagen.'}

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_encodings = face_recognition.face_encodings(rgb_frame)

        if not face_encodings:
            return {'success': False, 'message': 'No se pudo detectar un rostro. Asegúrese de que la cara esté bien iluminada y centrada.'}
        
        if len(face_encodings) > 1:
            return {'success': False, 'message': 'Se detectaron múltiples rostros en la imagen.'}

        identificacion_previa = self.identificar_rostro(image_data_url)
        if identificacion_previa.get('success'):
            return {'success': False, 'message': 'Este rostro ya pertenece a otro usuario registrado.'}
            
        new_encoding_json = json.dumps(face_encodings[0].tolist())
        return {'success': True, 'encoding': new_encoding_json}

    # endregion

    # region Métodos de Soporte (Helpers)
    def _get_image_from_data_url(self, image_data_url: str) -> Optional[np.ndarray]:
        """
        Decodifica y redimensiona una imagen en formato Data URL.
        """
        try:
            image_data = re.sub('^data:image/.+;base64,', '', image_data_url)
            image_bytes = base64.b64decode(image_data)
            np_arr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is None:
                logger.error("No se pudo decodificar la imagen.")
                return None

            # --- Optimización: Redimensionar la imagen ---
            max_width = 640
            h, w, _ = frame.shape
            if w > max_width:
                ratio = max_width / w
                new_h = int(h * ratio)
                frame = cv2.resize(frame, (max_width, new_h), interpolation=cv2.INTER_AREA)
                logger.info(f"Imagen redimensionada de {w}x{h} a {max_width}x{new_h}.")
            
            return frame

        except Exception as e:
            logger.error(f"Error procesando imagen desde Data URL: {e}", exc_info=True)
            return None

    def _preparar_perfiles(self, usuarios: list) -> tuple:
        """
        Procesa una lista de usuarios de la BD, extrayendo y decodificando
        sus perfiles faciales.
        """
        known_encodings = []
        usuarios_con_encoding = []
        for usuario in usuarios:
            if usuario.get('facial_encoding'):
                try:
                    encoding = np.array(json.loads(usuario['facial_encoding']))
                    known_encodings.append(encoding)
                    usuarios_con_encoding.append(usuario)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Perfil facial corrupto o inválido para usuario ID: {usuario.get('id')}")
                    continue
        return known_encodings, usuarios_con_encoding

    def _manejar_logica_acceso(self, usuario: Dict, metodo: str) -> Dict:
        """
        Lógica centralizada para gestionar una entrada o salida en el tótem.
        """
        usuario_id = usuario['id']
        usuario_nombre = usuario.get('nombre', 'Usuario')

        tiene_sesion_activa = self.totem_sesion_model.verificar_sesion_activa_hoy(usuario_id)

        if not tiene_sesion_activa:
            # Lógica de ENTRADA
            validacion_turno = self.usuario_controller.verificar_acceso_por_horario(usuario)
            if not validacion_turno.get('success'):
                return {'success': False, 'message': validacion_turno.get('error')}

            resultado_sesion = self.totem_sesion_model.crear_sesion(usuario_id, metodo)
            if not resultado_sesion.get('success'):
                return {'success': False, 'message': 'Error al registrar la sesión de entrada.'}

            self._registrar_evento_acceso("ingreso", usuario_id, metodo, resultado_sesion['data']['id'])
            
            from types import SimpleNamespace
            usuario_log = SimpleNamespace(nombre=usuario.get('nombre'), apellido=usuario.get('apellido'), roles=[usuario.get('roles', {}).get('codigo')])
            detalle = "Acceso al Tótem."
            self.registro_controller.crear_registro(usuario_log, 'Accesos Totem', f"Ingreso por {metodo}", detalle)

            return {'success': True, 'tipo_acceso': 'ENTRADA', 'message': f"¡Bienvenido, {usuario_nombre}!"}
        else:
            # Lógica de SALIDA
            self.totem_sesion_model.cerrar_sesion(usuario_id)
            self._registrar_evento_acceso("egreso", usuario_id, metodo)
            
            from types import SimpleNamespace
            usuario_log = SimpleNamespace(nombre=usuario.get('nombre'), apellido=usuario.get('apellido'), roles=[usuario.get('roles', {}).get('codigo')])
            detalle = "Cierre de sesión en el Tótem."
            self.registro_controller.crear_registro(usuario_log, 'Accesos Totem', 'Egreso', detalle)

            return {'success': True, 'tipo_acceso': 'SALIDA', 'message': f"¡Hasta luego, {usuario_nombre}!"}

    def _registrar_evento_acceso(self, tipo: str, usuario_id: int, metodo: str, sesion_id: Optional[int] = None):
        """
        Registra un evento de acceso (ingreso/egreso) en la tabla 'registros_acceso'.
        """
        try:
            self.db.table("registros_acceso").insert({
                "usuario_id": usuario_id,
                "fecha_hora": get_now_in_argentina().isoformat(),
                "tipo": tipo,
                "metodo": metodo,
                "dispositivo": "TOTEM",
                "sesion_totem_id": sesion_id,
                "ubicacion_totem": 'TOTEM_PRINCIPAL'
            }).execute()
        except Exception as e:
            logger.error(f"Fallo al registrar evento de acceso ({tipo}) para usuario {usuario_id}: {e}", exc_info=True)

    def _cargar_y_cachear_perfiles(self):
        """
        Carga los perfiles faciales de todos los usuarios activos desde la base de datos
        y los almacena en el caché de la clase para un acceso rápido.
        """
        try:
            logger.info("Recargando perfiles faciales desde la base de datos...")
            response = self.db.table("usuarios").select(
                "id, email, nombre, apellido, facial_encoding, role_id, turno_id, roles(*), turno:turno_id(*)"
            ).not_.is_("facial_encoding", "null").eq("activo", True).execute()
            
            if response.data:
                self._cached_encodings, self._cached_users = self._preparar_perfiles(response.data)
                self._cache_is_dirty = False
                logger.info(f"Caché actualizado con {len(self._cached_encodings)} perfiles faciales.")
            else:
                self._cached_encodings, self._cached_users = [], []
                self._cache_is_dirty = False
                logger.info("No se encontraron perfiles faciales para cachear.")
        except Exception as e:
            logger.error(f"Error al cargar y cachear perfiles faciales: {e}", exc_info=True)
            # En caso de error, vaciamos el caché para evitar usar datos obsoletos.
            self._cached_encodings, self._cached_users = [], []
            self._cache_is_dirty = True

    def _invalidar_cache(self):
        """
        Marca el caché de perfiles faciales como 'sucio', forzando una recarga
        en la próxima operación de identificación.
        """
        self._cache_is_dirty = True
        logger.info("Caché de perfiles faciales invalidado.")

    # endregion
