import os
import cv2
import numpy as np
import base64
import re
from datetime import datetime
import face_recognition
import json
import logging
from app.database import Database

logger = logging.getLogger(__name__)

class FacialController:
    """
    Controlador de lógica de negocio para todas las operaciones faciales y de registro de asistencia.
    """
    
    def __init__(self):
        self.db = Database().client
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
        Devuelve los datos del usuario si se encuentra una coincidencia.
        """
        frame = self._get_image_from_data_url(image_data_url)
        if frame is None:
            return {'success': False, 'message': 'Error al procesar la imagen.'}

        face_encodings = face_recognition.face_encodings(frame)
        if not face_encodings:
            return {'success': False, 'message': 'No se detectó rostro en la imagen'}

        input_encoding = face_encodings[0]

        try:
            response = self.db.table("usuarios").select(
                "id, email, nombre, facial_encoding, rol, activo"
            ).not_.is_("facial_encoding", "null").eq("activo", True).execute()
            
            usuarios = response.data

            for usuario in usuarios:
                if usuario.get('facial_encoding'):
                    try:
                        known_encoding = np.array(json.loads(usuario['facial_encoding']))
                        match = face_recognition.compare_faces([known_encoding], input_encoding, tolerance=0.6)
                        if match[0]:
                            return {'success': True, 'usuario': usuario}
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.error(f"Error decodificando encoding: {e}")
                        continue

            return {'success': False, 'message': 'Rostro no reconocido.'}
        except Exception as e:
            logger.error(f"Error en la base de datos durante la identificación facial: {e}")
            return {'success': False, 'message': 'Error del servidor.'}

    def registrar_rostro(self, user_id, image_data_url):
        """Registra un rostro para un usuario específico."""
        frame = self._get_image_from_data_url(image_data_url)
        if frame is None:
            return {'success': False, 'message': 'Error al procesar la imagen.'}

        new_encodings = face_recognition.face_encodings(frame)
        if not new_encodings:
            return {'success': False, 'message': 'No se detectó rostro en la imagen.'}

        new_encoding_json = json.dumps(new_encodings[0].tolist())

        try:
            response = self.db.table("usuarios").update({
                "facial_encoding": new_encoding_json,
                "updated_at": datetime.now().isoformat()
            }).eq("id", user_id).execute()
            
            if response.data:
                return {'success': True, 'message': 'Rostro registrado correctamente.'}
            else:
                return {'success': False, 'message': 'Usuario no encontrado.'}
                
        except Exception as e:
            logger.error(f"Error en la base de datos durante el registro facial: {e}")
            return {'success': False, 'message': 'Error del servidor al guardar el rostro.'}

    def registrar_acceso(self, usuario_id, tipo, metodo, dispositivo, observaciones=None):
        """Registra entrada/salida en la base de datos"""
        try:
            registro_data = {
                "usuario_id": usuario_id,
                "fecha_hora": datetime.now().isoformat(),
                "tipo": tipo,
                "metodo": metodo,
                "dispositivo": dispositivo,
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

    def procesar_login_facial(self, image_data_url):
        """
        Procesa el login facial completo: identificación + registro de entrada + activación de flags
        """
        try:
            # 1. Identificar rostro
            resultado_identificacion = self.identificar_rostro(image_data_url)
            
            if not resultado_identificacion.get('success'):
                return resultado_identificacion

            usuario = resultado_identificacion['usuario']
            usuario_id = usuario['id']
            usuario_email = usuario['email']
            usuario_nombre = usuario.get('nombre', '')

            # 2. Registrar entrada
            resultado_registro = self.registrar_acceso(usuario_id, "ENTRADA", "FACIAL", "TOTEM")
            if not resultado_registro.get('success'):
                return resultado_registro

            # 3. Activar flags de acceso web (usando UsuarioController)
            from app.controllers.usuario_controller import UsuarioController
            usuario_controller = UsuarioController()
            resultado_activacion = usuario_controller.activar_login_totem(usuario_id)

            if not resultado_activacion.get('success'):
                logger.error(f"Error activando login tótem: {resultado_activacion.get('error')}")

            return {
                'success': True,
                'message': '✅ Entrada registrada - Acceso web habilitado',
                'usuario': {
                    'id': usuario_id,
                    'email': usuario_email,
                    'nombre': usuario_nombre
                }
            }

        except Exception as e:
            logger.error(f"Error en procesar_login_facial: {str(e)}")
            return {'success': False, 'message': f'Error en el servidor: {str(e)}'}

    def procesar_logout_facial(self, usuario_id):
        """
        Procesa el logout facial completo: registro de salida + desactivación de flags
        """
        try:
            logger.info(f"🚪 Procesando logout facial para usuario ID: {usuario_id}")

            # 1. Registrar salida
            resultado_registro = self.registrar_acceso(usuario_id, "SALIDA", "FACIAL", "TOTEM")
            if not resultado_registro.get('success'):
                logger.error(f"Error registrando salida: {resultado_registro.get('error')}")

            # 2. Desactivar flags de acceso web
            from app.controllers.usuario_controller import UsuarioController
            usuario_controller = UsuarioController()
            resultado_desactivacion = usuario_controller.desactivar_login_totem(usuario_id)

            if not resultado_desactivacion.get('success'):
                logger.error(f"Error desactivando flags: {resultado_desactivacion.get('error')}")

            # 3. Verificación final
            try:
                response = self.db.table("usuarios").select("login_totem_activo").eq("id", usuario_id).execute()
                if response.data:
                    estado_final = response.data[0].get('login_totem_activo')
                    logger.info(f"📊 Estado final después del logout: login_totem_activo={estado_final}")
            except Exception as e:
                logger.error(f"Error en verificación final: {e}")

            return {'success': True, 'message': '✅ Salida registrada correctamente'}

        except Exception as e:
            logger.error(f"Error en procesar_logout_facial: {e}")
            return {'success': False, 'message': 'Error al registrar salida'}