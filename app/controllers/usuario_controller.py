from app.controllers.base_controller import BaseController
from app.models.usuario import UsuarioModel
from app.schemas.usuario_schema import UsuarioSchema
from typing import Dict, Optional, List
from marshmallow import ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import logging


logger = logging.getLogger(__name__)

class UsuarioController(BaseController):
    """
    Controlador para la lógica de negocio de los usuarios.
    """

    def __init__(self):
        super().__init__()
        self.model = UsuarioModel()
        self.schema = UsuarioSchema()

    def crear_usuario(self, data: Dict) -> Dict:
        """Valida y crea un nuevo usuario."""
        try:
            # Validar con el esquema
            validated_data = self.schema.load(data)

            # Verificar si el email ya existe
            if self.model.find_by_email(validated_data['email']).get('data'):
                return {'success': False, 'error': 'El correo electrónico ya está en uso.'}

            # Hashear la contraseña antes de guardarla
            password = validated_data.pop('password')
            validated_data['password_hash'] = generate_password_hash(password)

            return self.model.create(validated_data)
        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def autenticar_usuario(self, legajo: str, password: str) -> Optional[Dict]:
        """Autentica a un usuario por legajo y contraseña."""
        user_result = self.model.find_by_legajo(legajo)
        if user_result.get('success') and user_result.get('data'):
            user_data = user_result['data']
            if check_password_hash(user_data['password_hash'], password):
                return user_data
        return None

    ##GONZA

    def autenticar_usuario_V2(self, legajo: str, password: str) -> Dict:
        """
        Autentica a un usuario por legajo y contraseña.
        VERIFICA que tenga login activo en tótem.
        """
        user_result = self.model.find_by_legajo_v2(legajo)

        if not user_result.get('success') or not user_result.get('data'):
            return {'success': False, 'error': 'Credenciales inválidas'}

        user_data = user_result['data']
        logger.info(f"🔍 Usuario encontrado: {user_data.get('email')}")

        # 1. Verificar contraseña
        if not check_password_hash(user_data['password_hash'], password):
            return {'success': False, 'error': 'Credenciales inválidas'}

        # 2. Verificar que el usuario esté activo
        if not user_data.get('activo', True):
            return {'success': False, 'error': 'Usuario desactivado'}

        # 3. DEBUG: Mostrar estado actual del usuario
        logger.info(f"📊 Estado del usuario:")
        logger.info(f"   - login_totem_activo: {user_data.get('login_totem_activo')}")
        logger.info(f"   - ultimo_login_totem: {user_data.get('ultimo_login_totem')}")
        logger.info(f"   - activo: {user_data.get('activo')}")

        # 4. VERIFICACIÓN CLAVE: ¿Tiene login activo en tótem hoy?
        verificacion_totem = self._verificar_login_totem_activo(user_data)
        logger.info(f"✅ Resultado verificación tótem: {verificacion_totem}")

        if not verificacion_totem:
            return {
                'success': False,
                'error': 'Debe registrar su entrada en el tótem primero para acceder por web'
            }

        # 5. Actualizar último acceso web
        update_result = self.model.update(user_data['id'], {
            'ultimo_login_web': datetime.now().isoformat()
        })

        if not update_result.get('success'):
            logger.error(f"Error actualizando último login web: {update_result.get('error')}")

        return {
            'success': True,
            'data': user_data,
            'message': 'Autenticación exitosa'
        }

    def _verificar_login_totem_activo(self, user_data: Dict) -> bool:
        """Verifica si el usuario tiene login activo en tómet para hoy"""
        login_totem_activo = user_data.get('login_totem_activo')
        ultimo_login_totem = user_data.get('ultimo_login_totem')

        if not login_totem_activo:
            return False

        if not ultimo_login_totem:
            return False

        try:
            # Múltiples formatos de fecha posibles
            if isinstance(ultimo_login_totem, str):
                # Intentar diferentes formatos
                formats_to_try = [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%dT%H:%M:%S',
                    '%Y-%m-%dT%H:%M:%S.%f',
                    '%Y-%m-%dT%H:%M:%S.%fZ',
                    '%Y-%m-%d %H:%M:%S.%f'
                ]

                login_date = None
                for fmt in formats_to_try:
                    try:
                        if fmt.endswith('Z') and 'Z' in ultimo_login_totem:
                            login_date = datetime.strptime(ultimo_login_totem, fmt).date()
                        else:
                            login_date = datetime.strptime(ultimo_login_totem.split('.')[0], fmt).date()
                        break
                    except ValueError:
                        continue

                if not login_date:
                    # Último intento con fromisoformat
                    try:
                        if 'Z' in ultimo_login_totem:
                            login_date = datetime.fromisoformat(ultimo_login_totem.replace('Z', '+00:00')).date()
                        else:
                            login_date = datetime.fromisoformat(ultimo_login_totem).date()
                    except ValueError:
                        return False
            else:
                login_date = ultimo_login_totem.date()

            hoy = date.today()
            return login_date == hoy

        except (ValueError, AttributeError, TypeError) as e:
            logger.error(f"Error parseando fecha '{ultimo_login_totem}': {e}")
            return False

    def activar_login_totem(self, usuario_id: int) -> Dict:
        """
        Activa el flag de login en tótem para un usuario.
        """
        try:
            update_data = {
                'login_totem_activo': True,
                'ultimo_login_totem': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Formato explícito
                'totem_session_id': self._generar_session_id()
            }

            logger.info(f"🔄 Activando login tótem con datos: {update_data}")

            result = self.model.update(usuario_id, update_data)

            if result.get('success'):
                # Verificar inmediatamente después de actualizar
                user_updated = self.model.find_by_id(usuario_id)
                if user_updated.get('success') and user_updated.get('data'):
                    user_data = user_updated['data']
                    logger.info(f"✅ Usuario actualizado:")
                    logger.info(f"   - login_totem_activo: {user_data.get('login_totem_activo')}")
                    logger.info(f"   - ultimo_login_totem: {user_data.get('ultimo_login_totem')}")

                    # Verificar la verificación
                    verificacion = self._verificar_login_totem_activo(user_data)
                    logger.info(f"   - Verificación inmediata: {verificacion}")

                return {'success': True, 'session_id': update_data['totem_session_id']}
            else:
                return {'success': False, 'error': 'Error activando login tótem'}

        except Exception as e:
            logger.error(f"Error en activar_login_totem: {str(e)}")
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def desactivar_login_totem(self, usuario_id: int) -> Dict:
        """
        Desactiva el flag de login en tótem (al hacer logout).
        """
        try:
            logger.info(f"🔒 Desactivando login tótem para usuario ID: {usuario_id}")

            update_data = {
                'login_totem_activo': False,
                'totem_session_id': None
                # NOTA: No modificamos ultimo_login_totem para mantener el registro histórico
            }

            logger.info(f"📋 Datos a actualizar: {update_data}")

            # Usar actualización directa para evitar problemas con el model
            try:
                response = self.model.db.table("usuarios").update(update_data).eq("id", usuario_id).execute()
                logger.info(f"📡 Respuesta de Supabase: {response}")

                if response.data:
                    logger.info("✅ Flags desactivados correctamente en la base de datos")
                    return {'success': True}
                else:
                    logger.error("❌ No se pudo actualizar el usuario")
                    return {'success': False, 'error': 'Usuario no encontrado'}

            except Exception as e:
                logger.error(f"❌ Error en actualización directa: {e}")
                return {'success': False, 'error': f'Error de base de datos: {str(e)}'}

        except Exception as e:
            logger.error(f"❌ Error en desactivar_login_totem: {str(e)}")
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def _generar_session_id(self) -> str:
        """Genera un ID único para la sesión del tótem"""
        import secrets
        return secrets.token_urlsafe(32)

    def verificar_acceso_web(self, usuario_id: int) -> Dict:
        """
        Verifica si un usuario puede acceder por web.
        Para usar en middlewares o antes de permitir acceso a rutas web.
        """
        user_result = self.model.find_by_id(usuario_id)

        if not user_result.get('success') or not user_result.get('data'):
            return {'success': False, 'error': 'Usuario no encontrado'}

        user_data = user_result['data']

        if not self._verificar_login_totem_activo(user_data):
            return {
                'success': False,
                'error': 'Acceso web no permitido. Registre entrada en tótem.'
            }

        return {'success': True, 'data': user_data}

    def obtener_estado_acceso(self, usuario_id: int) -> Dict:
        """Obtiene el estado completo de acceso de un usuario"""
        user_result = self.model.find_by_id(usuario_id)

        if not user_result.get('success') or not user_result.get('data'):
            return {'success': False, 'error': 'Usuario no encontrado'}

        user_data = user_result['data']

        estado = {
            'usuario_id': usuario_id,
            'nombre': user_data.get('nombre'),
            'email': user_data.get('email'),
            'login_totem_activo': user_data.get('login_totem_activo', False),
            'ultimo_login_totem': user_data.get('ultimo_login_totem'),
            'ultimo_login_web': user_data.get('ultimo_login_web'),
            'puede_acceder_web': self._verificar_login_totem_activo(user_data)
        }

        return {'success': True, 'data': estado}
    ## ____________________________________________________________________________
    def obtener_usuario_por_id(self, usuario_id: int) -> Optional[Dict]:
        """Obtiene un usuario por su ID."""
        result = self.model.find_by_id(usuario_id)
        return result.get('data')

    def obtener_todos_los_usuarios(self, filtros: Optional[Dict] = None) -> List[Dict]:
        """Obtiene una lista de todos los usuarios."""
        result = self.model.find_all(filtros)
        return result.get('data', [])

    def actualizar_usuario(self, usuario_id: int, data: Dict) -> Dict:
        """Actualiza un usuario existente."""
        try:
            # Si se proporciona una nueva contraseña, hashearla.
            if 'password' in data and data['password']:
                password = data.pop('password')
                data['password_hash'] = generate_password_hash(password)
            else:
                # Evitar que el campo de contraseña vacío se valide
                data.pop('password', None)

            # Validar con el esquema (parcial)
            validated_data = self.schema.load(data, partial=True)

            # Verificar unicidad del email si se está cambiando
            if 'email' in validated_data:
                existing = self.model.find_by_email(validated_data['email']).get('data')
                if existing and existing['id'] != usuario_id:
                    return {'success': False, 'error': 'El correo electrónico ya está en uso.'}

            return self.model.update(usuario_id, validated_data)
        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def eliminar_usuario(self, usuario_id: int) -> Dict:
        """
        Desactiva un usuario (eliminación lógica).
        No se elimina físicamente para mantener la integridad referencial.
        """
        return self.model.update(usuario_id, {'activo': False})