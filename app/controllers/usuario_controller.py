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
from app.controllers.direccion_controller import GeorefController
from app.models.autorizacion_ingreso import AutorizacionIngresoModel

logger = logging.getLogger(__name__)


class UsuarioController(BaseController):
    """
    Controlador actualizado para la lógica de negocio de los usuarios con gestión de sectores.
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

    def _normalizar_y_preparar_direccion(self, direccion_data: Dict) -> Optional[Dict]:
        """
        Helper privado para normalizar datos de dirección usando GeorefController.
        Devuelve un diccionario con la dirección lista para ser guardada en la BD.
        """
        if not all(direccion_data.get(k) for k in ['calle', 'altura', 'localidad', 'provincia']):
            logger.warning("Datos de dirección insuficientes para normalizar.")
            return direccion_data

        # Construir la dirección completa incluyendo piso y depto si existen
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
            logger.warning(f"GEOREF normalization failed: {norm_result.get('message')}. Using user-provided address.")
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

    def crear_usuario(self, data: Dict) -> Dict:
        """Valida y crea un nuevo usuario, incluyendo dirección y sectores."""
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

            return self.model.find_by_id(usuario_id, include_sectores=True, include_direccion=True)

        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def _asignar_sectores_usuario(self, usuario_id: int, sectores_ids: List[int]) -> Dict:
        """Asigna sectores a un usuario"""
        try:
            for sector_id in sectores_ids:
                resultado = self.usuario_sector_model.asignar_sector(usuario_id, sector_id)
                if not resultado.get('success'):
                    self.usuario_sector_model.eliminar_todas_asignaciones(usuario_id)
                    return {'success': False, 'error': f'Error asignando sector ID {sector_id}'}
            
            return {'success': True, 'message': 'Sectores asignados correctamente'}
        except Exception as e:
            logger.error(f"Error asignando sectores: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _actualizar_datos_principales(self, usuario_id: int, user_data: Dict, existing_user: Dict, new_direccion_id: int) -> Dict:
        """Valida y actualiza los campos principales de un usuario."""
        # Comparar con datos existentes para ver si hay cambios
        user_data_changed = any(str(user_data.get(k) or '') != str(existing_user.get(k) or '') for k in user_data)
        
        if not user_data_changed and new_direccion_id == existing_user.get('direccion_id'):
            return {'success': True}

        # Validar los datos que se van a cargar
        loadable_fields = {k for k, v in self.schema.fields.items() if not v.dump_only}
        user_data_for_validation = {k: v for k, v in user_data.items() if k in loadable_fields}
        
        try:
            validated_data = self.schema.load(user_data_for_validation, partial=True)
        except ValidationError as e:
            return {'success': False, 'error': f"Datos de usuario inválidos: {e.messages}"}

        # Manejar password
        if 'password' in validated_data and validated_data['password']:
            validated_data['password_hash'] = generate_password_hash(validated_data.pop('password'))
        else:
            validated_data.pop('password', None)

        # Validar email único
        if 'email' in validated_data:
            existing_email = self.model.find_by_email(validated_data['email']).get('data')
            if existing_email and existing_email['id'] != usuario_id:
                return {'success': False, 'error': 'El correo electrónico ya está en uso.'}

        # Añadir el ID de la dirección si ha cambiado
        validated_data['direccion_id'] = new_direccion_id
        
        # Actualizar en la BD
        return self.model.update(usuario_id, validated_data)

    def _actualizar_direccion_usuario(self, usuario_id: int, direccion_data: Dict, existing_user: Dict) -> Dict:
        """
        Actualiza la dirección de un usuario de forma inteligente:
        - Si la dirección no cambia, no hace nada.
        - Si cambia y la dirección original no es compartida, la actualiza .
        - Si cambia y la dirección original es compartida, busca o crea una nueva.
        """
        # 1. Preparar y validar datos de entrada
        if 'altura' in direccion_data and direccion_data['altura'] == '':
            direccion_data['altura'] = None
        
        has_new_address_data = all(direccion_data.get(f) for f in ['calle', 'altura', 'localidad', 'provincia'])
        original_direccion_id = existing_user.get('direccion_id')

        # Si no hay datos de dirección nuevos y el usuario ya tenía una, no hay cambios.
        if not has_new_address_data and original_direccion_id:
            return {'success': True, 'direccion_id': original_direccion_id}
        # Si no hay datos nuevos y el usuario no tenía dirección, no hay nada que hacer.
        if not has_new_address_data:
            return {'success': True, 'direccion_id': None}

        # 2. Verificar si la dirección realmente ha cambiado
        existing_address = existing_user.get('direccion') or {}
        address_changed = any(str(direccion_data.get(k) or '') != str(existing_address.get(k) or '') for k in direccion_data)

        if not address_changed:
            return {'success': True, 'direccion_id': original_direccion_id}

        # 3. Normalizar la nueva dirección
        direccion_normalizada = self._normalizar_y_preparar_direccion(direccion_data)
        if not direccion_normalizada:
            return {'success': False, 'error': "No se pudo normalizar la dirección."}

        # 4. Decidir si actualizar  o buscar/crear una nueva
        # Si el usuario tenía una dirección y no es compartida por nadie más...
        if original_direccion_id and not self.direccion_model.is_address_shared(original_direccion_id, excluding_user_id=usuario_id):
            # ...actualizamos la dirección existente en lugar de crear una nueva.
            logger.info(f"Dirección ID {original_direccion_id} no es compartida. Actualizando .")
            update_result = self.direccion_model.update(original_direccion_id, direccion_normalizada)
            if update_result.get('success'):
                return {'success': True, 'direccion_id': original_direccion_id}
            else:
                logger.error(f"Error actualizando dirección : {update_result.get('error')}")
                # Si falla la actualización, recurrimos a crear/buscar para no bloquear al usuario.
                pass
        
        # 5. Si la dirección es compartida o no existía, buscamos una coincidencia o creamos una nueva.
        logger.info("La dirección es compartida o nueva. Buscando/Creando...")
        new_direccion_id = self._get_or_create_direccion(direccion_normalizada)
        if new_direccion_id:
            return {'success': True, 'direccion_id': new_direccion_id}

        return {'success': False, 'error': "No se pudo procesar la nueva dirección."}

    def _actualizar_sectores_usuario(self, usuario_id: int, sectores_ids: List[int], existing_user: Dict) -> Dict:
        """Actualiza los sectores de un usuario si han cambiado."""
        if sectores_ids is None:
            return {'success': True}

        existing_sector_ids = {s['id'] for s in existing_user.get('sectores', [])}
        if set(sectores_ids) == existing_sector_ids:
            return {'success': True}

        self.usuario_sector_model.eliminar_todas_asignaciones(usuario_id)
        if sectores_ids:
            resultado = self._asignar_sectores_usuario(usuario_id, sectores_ids)
            if not resultado.get('success'):
                return resultado
        
        return {'success': True}

    def actualizar_usuario(self, usuario_id: int, data: Dict) -> Dict:
        """
        Orquesta la actualización de un usuario, delegando a métodos especializados.
        """
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

            # 1. Sanear datos de entrada
            fields_to_sanitize = ['telefono', 'cuil_cuit', 'fecha_nacimiento', 'fecha_ingreso', 'turno_id', 'piso', 'depto', 'codigo_postal']
            for field in fields_to_sanitize:
                if field in data and (data[field] == '' or data[field] == 'None'):
                    data[field] = None

            # 2. Obtener estado actual del usuario
            existing_result = self.model.find_by_id(usuario_id, include_sectores=True, include_direccion=True)
            if not existing_result.get('success'):
                return existing_result
            existing_user = existing_result['data']

            # 3. Preparar y separar los datos de entrada
            sectores_ids = data.pop('sectores', None)
            if isinstance(sectores_ids, str):
                try:
                    sectores_ids = json.loads(sectores_ids)
                except json.JSONDecodeError:
                    return {'success': False, 'error': 'El formato de sectores es inválido.'}

            address_fields = ['calle', 'altura', 'piso', 'depto', 'localidad', 'provincia', 'codigo_postal']
            direccion_data = {field: data.get(field) for field in address_fields}
            user_data = {k: v for k, v in data.items() if k not in address_fields}

            # 4. Orquestar las actualizaciones
            # Actualizar sectores
            sectores_result = self._actualizar_sectores_usuario(usuario_id, sectores_ids, existing_user)
            if not sectores_result.get('success'):
                return sectores_result

            # Actualizar dirección
            direccion_result = self._actualizar_direccion_usuario(usuario_id, direccion_data, existing_user)
            if not direccion_result.get('success'):
                return direccion_result
            new_direccion_id = direccion_result.get('direccion_id')

            # Actualizar datos principales del usuario
            user_result = self._actualizar_datos_principales(usuario_id, user_data, existing_user, new_direccion_id)
            if not user_result.get('success'):
                return user_result

            # 5. Devolver el estado final del usuario
            return self.model.find_by_id(usuario_id, include_sectores=True, include_direccion=True)

        except Exception as e:
            logger.error(f"Error en la orquestación de actualizar_usuario: {str(e)}", exc_info=True)
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def obtener_usuario_por_id(self, usuario_id: int, include_sectores: bool = True, include_direccion: bool = False) -> Optional[Dict]:
        """Obtiene un usuario por su ID con opción de incluir sectores y dirección."""
        result = self.model.find_by_id(usuario_id, include_sectores, include_direccion)
        return result.get('data')

    def obtener_todos_los_usuarios(self, filtros: Optional[Dict] = None, include_sectores: bool = True, include_direccion: bool = False) -> List[Dict]:
        """Obtiene una lista de todos los usuarios con opción de incluir sectores y dirección."""
        result = self.model.find_all(filtros, include_sectores, include_direccion)
        return result.get('data', [])

    def obtener_todos_los_sectores(self) -> List[Dict]:
        """Obtiene todos los sectores disponibles."""
        try:
            resultado = self.sector_model.find_all()
            return resultado.get('data', [])
        except Exception as e:
            logger.error(f"Error obteniendo sectores: {str(e)}")
            return []

    def obtener_sectores_usuario(self, usuario_id: int) -> List[Dict]:
        """Obtiene los sectores de un usuario específico."""
        try:
            resultado = self.usuario_sector_model.find_by_usuario(usuario_id)
            if resultado.get('success'):
                # Extraer solo la información del sector
                sectores = []
                for item in resultado['data']:
                    if item.get('sectores'):
                        sectores.append(item['sectores'])
                return sectores
            return []
        except Exception as e:
            logger.error(f"Error obteniendo sectores del usuario: {str(e)}")
            return []

    def autenticar_usuario_web(self, legajo: str, password: str) -> Dict:
        """
        Autentica a un usuario para el acceso web incluyendo sectores en la respuesta.
        """
        # Paso 1: Autenticación de credenciales base
        auth_result = self._autenticar_credenciales_base(legajo, password)
        if not auth_result.get('success'):
            return auth_result

        user_data = auth_result['data']
        logger.info(f"🔍 Credenciales válidas para: {user_data.get('email')}")

        # Paso 2: Verificación específica para web (sesión de tótem)
        tiene_sesion_activa = self.totem_sesion.verificar_sesion_activa_hoy(user_data['id'])
        logger.info(f"✅ Usuario tiene sesión activa hoy: {tiene_sesion_activa}")

        if not tiene_sesion_activa:
            return {
                'success': False,
                'error': 'Debe registrar su entrada en el tótem primero para acceder por web'
            }

        # Paso 3: Cargar sectores del usuario
        usuario_completo_result = self.model.find_by_id(user_data['id'], include_sectores=True)
        if not usuario_completo_result.get('success'):
            return usuario_completo_result

        usuario_completo = usuario_completo_result['data']

        # Paso 4: Actualizar último login web y devolver éxito
        self.model.update(user_data['id'], {'ultimo_login_web': datetime.now().isoformat()})

        return {
            'success': True,
            'data': usuario_completo,
            'message': 'Autenticación exitosa'
        }

    def _autenticar_credenciales_base(self, legajo: str, password: str) -> Dict:
        """
        Método base para autenticar un usuario por legajo y contraseña.
        Utilizado tanto para acceso web como para tótem.
        """
        try:
            usuario_result = self.model.find_by_legajo(legajo) 
            
            if not usuario_result.get('success') or not usuario_result.get('data'):
                logger.warning(f"❌ Intento de login fallido: Legajo {legajo} no encontrado.")
                return {'success': False, 'error': 'Legajo o contraseña incorrectos.'}
            
            user_data = usuario_result['data']
            
            if not user_data.get('activo', True):
                 logger.warning(f"❌ Intento de login fallido: Usuario {user_data.get('email')} desactivado.")
                 return {'success': False, 'error': 'Usuario inactivo. Contacte al administrador.'}

            if not check_password_hash(user_data['password_hash'], password):
                logger.warning(f"❌ Intento de login fallido: Contraseña incorrecta para {user_data.get('email')}.")
                return {'success': False, 'error': 'Legajo o contraseña incorrectos.'}

            return {'success': True, 'data': user_data}

        except Exception as e:
            logger.error(f"Error en _autenticar_credenciales_base: {str(e)}")
            return {'success': False, 'error': f'Error interno de autenticación: {str(e)}'}

    def autenticar_usuario_para_totem(self, legajo: str, password: str) -> Dict:
        """
        Autentica a un usuario para uso exclusivo del tótem (solo credenciales).
        """
        logger.info(f"🔍 Autenticando usuario para tótem con legajo: {legajo}")
        return self._autenticar_credenciales_base(legajo, password)

    def autenticar_usuario_facial_web(self, image_data_url: str) -> Dict:
        """
        Autentica a un usuario por rostro para el login web.
        VERIFICA que tenga sesión activa en tótem.
        """
        from app.controllers.facial_controller import FacialController
        facial_controller = FacialController()        
        resultado_identificacion = facial_controller.identificar_rostro(image_data_url)
        if not resultado_identificacion.get('success'):
            return resultado_identificacion
        
        user_data = resultado_identificacion['usuario']
        if not user_data.get('activo', True):
            return {'success': False, 'message': 'Este usuario se encuentra desactivado.'}
        
        # Verificar sesión activa en tótem
        tiene_sesion_activa = self.totem_sesion.verificar_sesion_activa_hoy(user_data['id'])
        if not tiene_sesion_activa:
            return {
                'success': False,
                'message': 'Acceso Web denegado. Por favor, registre su ingreso en el tótem antes de continuar.'
            }
        
        # Actualizar último login web
        self.model.update(user_data['id'], {'ultimo_login_web': datetime.now().isoformat()})
        return {
            'success': True,
            'data': user_data,
            'message': 'Autenticación exitosa'
        }

    def activar_login_totem(self, usuario_id: int, metodo_acceso: str = 'FACIAL') -> Dict:
        """
        Crea una nueva sesión de tótem para un usuario (reemplaza el flag anterior).
        """
        try:
            logger.info(f"🔄 Creando sesión de tótem para usuario ID: {usuario_id}")

            # Crear sesión en la nueva tabla
            resultado = self.totem_sesion.crear_sesion(
                usuario_id=usuario_id,
                metodo_acceso=metodo_acceso,
                dispositivo_totem='TOTEM_PRINCIPAL'
            )

            if resultado.get('success'):
                logger.info("✅ Sesión de tótem creada correctamente")
                return {
                    'success': True, 
                    'session_id': resultado['data']['session_id'],
                    'message': 'Acceso registrado correctamente'
                }
            else:
                logger.error(f"❌ Error creando sesión: {resultado.get('error')}")
                return {'success': False, 'error': 'Error registrando acceso en tótem'}

        except Exception as e:
            logger.error(f"Error en activar_login_totem: {str(e)}")
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def desactivar_login_totem(self, usuario_id: int) -> Dict:
        """
        Cierra la sesión activa de tótem para un usuario (reemplaza el flag anterior).
        """
        try:
            logger.info(f"🔒 Cerrando sesión de tótem para usuario ID: {usuario_id}")

            # Cerrar sesión en la nueva tabla
            resultado = self.totem_sesion.cerrar_sesion(usuario_id)

            if resultado.get('success'):
                logger.info("✅ Sesión de tótem cerrada correctamente")
                return {'success': True, 'message': 'Salida registrada correctamente'}
            else:
                logger.warning(f"⚠️  No se encontró sesión activa para usuario {usuario_id}")
                return {'success': True, 'message': 'No había sesión activa'}

        except Exception as e:
            logger.error(f"❌ Error en desactivar_login_totem: {str(e)}")
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def verificar_acceso_web(self, usuario_id: int) -> Dict:
        """
        Verifica si un usuario puede acceder por web.
        Para usar en middlewares o antes de permitir acceso a rutas web.
        """
        user_result = self.model.find_by_id(usuario_id)

        if not user_result.get('success') or not user_result.get('data'):
            return {'success': False, 'error': 'Usuario no encontrado'}

        user_data = user_result['data']

        # Verificar sesión activa en tótem
        tiene_sesion_activa = self.totem_sesion.verificar_sesion_activa_hoy(usuario_id)
        if not tiene_sesion_activa:
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
        
        # Verificar sesión activa
        tiene_sesion_activa = self.totem_sesion.verificar_sesion_activa_hoy(usuario_id)
        sesion_activa = self.totem_sesion.obtener_sesion_activa(usuario_id)

        estado = {
            'usuario_id': usuario_id,
            'nombre': user_data.get('nombre'),
            'email': user_data.get('email'),
            'sesion_totem_activa': tiene_sesion_activa,
            'detalle_sesion': sesion_activa.get('data') if sesion_activa.get('success') else None,
            'ultimo_login_web': user_data.get('ultimo_login_web'),
            'puede_acceder_web': tiene_sesion_activa
        }

        return {'success': True, 'data': estado}

    def eliminar_usuario(self, usuario_id: int) -> Dict:
        """Desactiva un usuario (eliminación lógica)."""
        return self.model.update(usuario_id, {'activo': False})

    def habilitar_usuario(self, usuario_id: int) -> Dict:
        """Reactiva un usuario que fue desactivado lógicamente."""
        return self.model.update(usuario_id, {'activo': True})

    def validar_campo_unico(self, field: str, value: str, user_id: Optional[int] = None) -> Dict:
        """
        Verifica si un valor para un campo específico ya existe (legajo, email, cuil_cuit, telefono),
        excluyendo el ID de usuario actual si se proporciona.
        """
        field_map = {
            'legajo': 'Legajo',
            'email': 'Email',
            'cuil_cuit': 'CUIL/CUIT',
            'telefono': 'Teléfono'
        }
        user_friendly_field = field_map.get(field, field)

        find_methods = {
            'legajo': self.model.find_by_legajo,
            'email': self.model.find_by_email,
            'cuil_cuit': self.model.find_by_cuil,
            'telefono': self.model.find_by_telefono
        }

        find_method = find_methods.get(field)

        if not find_method:
            return {'valid': False, 'error': 'Campo de validación no soportado.'}

        try:
            result = find_method(value)

            if result.get('success'):
                if user_id:
                    found_user_id = result['data']['id']
                    if str(found_user_id) != str(user_id):
                        return {'valid': False, 'message': f'El {user_friendly_field} ingresado ya está en uso por otro usuario.'}
                else:
                    return {'valid': False, 'message': f'El {user_friendly_field} ingresado ya está en uso.'}

            return {'valid': True}

        except Exception as e:
            logger.error(f"Exception during field validation for '{field}': {str(e)}", exc_info=True)
            return {'valid': False, 'error': 'Error interno del servidor durante la validación.'}

    def obtener_porcentaje_asistencia(self) -> float:
        """
        Calcula el porcentaje de usuarios activos que tienen una sesión de tótem activa hoy.
        """
        todos_activos = self.model.find_all({'activo': True})

        if not todos_activos.get('success') or not todos_activos.get('data'):
            return 0.0

        usuarios_activos = todos_activos['data']
        total_usuarios_activos = len(usuarios_activos)

        if total_usuarios_activos == 0:
            return 0.0
        
        cant_en_empresa = 0
        for usuario in usuarios_activos:
            if self.totem_sesion.verificar_sesion_activa_hoy(usuario['id']):
                cant_en_empresa += 1

        porcentaje = int((cant_en_empresa / total_usuarios_activos) * 100)
        
        return round(porcentaje, 0)
    
    def obtener_actividad_totem(self, filtros: Optional[Dict] = None) -> Dict:
        """
        Obtiene la lista de actividad del tótem (ingresos/egresos), potencialmente filtrada.
        """
        try:
            resultado = self.totem_sesion.obtener_actividad_filtrada(filtros)
            return resultado
        except Exception as e:
            logger.error(f"Error obteniendo actividad del tótem: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def obtener_actividad_web(self, filtros: Optional[Dict] = None) -> Dict:
        """
        Obtiene la lista de usuarios que iniciaron sesión en la web, potencialmente filtrada.
        """
        try:
            resultado = self.model.find_by_web_login_filtrado(filtros)
            return resultado
        except Exception as e:
            logger.error(f"Error obteniendo actividad web: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def obtener_todos_los_roles(self) -> List[Dict]:
        """Obtiene una lista de todos los roles disponibles."""
        resultado = self.role_model.find_all()
        return resultado.get('data', [])

    def obtener_rol_por_id(self, role_id: int) -> Optional[Dict]:
        """Obtiene un rol por su ID."""
        try:
            response = self.db.table("roles").select("*").eq("id", role_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error obteniendo rol por ID: {str(e)}")
            return None

    def obtener_todos_los_turnos(self, usuario_id: Optional[int] = None) -> List[Dict]:
        """
        Obtiene una lista de turnos de trabajo. Si se proporciona un ID de usuario,
        aplica la lógica de negocio (gerentes ven todo, el resto su turno).
        Si no, devuelve todos los turnos (útil para formularios de creación).
        """
        if usuario_id:
            resultado = self.model.get_turnos_para_usuario(usuario_id)
        else:
            resultado = self.turno_model.find_all()
            
        return resultado.get('data', [])

    def verificar_acceso_por_horario(self, usuario: dict) -> dict:
        """
        Verifica si el login es válido según la ventana de fichaje del turno o una autorización.
        Regla: 15 mins antes hasta 15 mins después del inicio del turno.
        """
        if not usuario or usuario.get('roles', {}).get('codigo') == 'GERENTE':
            return {'success': True}

        hora_actual = datetime.now().time()
        autorizacion_model = AutorizacionIngresoModel()

        # 1. Verificar la ventana de fichaje normal
        turno_info = usuario.get('turno')
        if turno_info and 'hora_inicio' in turno_info:
            try:
                hora_inicio = datetime.strptime(turno_info['hora_inicio'], '%H:%M:%S').time()
                dt_inicio = datetime.combine(datetime.today(), hora_inicio)
                inicio_permitido = (dt_inicio - timedelta(minutes=15)).time()
                fin_permitido = (dt_inicio + timedelta(minutes=15)).time()

                if fin_permitido < inicio_permitido: # Turno transnoche
                    if hora_actual >= inicio_permitido or hora_actual <= fin_permitido:
                        return {'success': True}
                else: # Turno normal
                    if inicio_permitido <= hora_actual <= fin_permitido:
                        return {'success': True}
            except (ValueError, TypeError):
                logger.warning(f"No se pudo parsear la hora de inicio del turno para el usuario {usuario.get('legajo')}")
                pass # Continuar para verificar autorizaciones

        # 2. Si se está fuera de la ventana, buscar autorizaciones APROBADAS para hoy
        usuario_id = usuario.get('id')
        hoy = datetime.today().date()
        auth_result = autorizacion_model.find_by_usuario_and_fecha(usuario_id, hoy, estado='APROBADA')

        if not auth_result.get('success'):
            return {'success': False, 'error': 'Fichaje fuera de horario. Se requiere una autorización.'}

        # 3. Iterar sobre las autorizaciones y aplicar la lógica correcta para cada tipo
        for autorizacion in auth_result.get('data', []):
            auth_turno = autorizacion.get('turno')
            auth_tipo = autorizacion.get('tipo')

            if not all(k in auth_turno for k in ['hora_inicio', 'hora_fin']):
                logger.warning(f"Autorización ID {autorizacion.get('id')} para usuario {usuario_id} no tiene horas de turno válidas.")
                continue

            try:
                auth_inicio = datetime.strptime(auth_turno['hora_inicio'], '%H:%M:%S').time()
                auth_fin = datetime.strptime(auth_turno['hora_fin'], '%H:%M:%S').time()

                # Lógica específica por tipo de autorización
                if auth_tipo == 'LLEGADA_TARDIA':
                    # Válido desde el inicio del turno autorizado hasta el fin del mismo
                    if auth_inicio <= hora_actual <= auth_fin:
                        logger.info(f"Acceso permitido para {usuario.get('legajo')} por autorización de LLEGADA_TARDIA.")
                        return {'success': True}
                
                elif auth_tipo == 'HORAS_EXTRAS':
                    # Válido desde 15 mins antes del inicio de las horas extras hasta el fin de las mismas
                    inicio_ventana_he = (datetime.combine(date.today(), auth_inicio) - timedelta(minutes=15)).time()
                    fin_ventana_he = auth_fin

                    if fin_ventana_he < inicio_ventana_he: # Horas extras transnoche
                        if hora_actual >= inicio_ventana_he or hora_actual <= fin_ventana_he:
                            logger.info(f"Acceso permitido para {usuario.get('legajo')} por autorización de HORAS_EXTRAS (transnoche).")
                            return {'success': True}
                    else: # Horas extras en el mismo día
                        if inicio_ventana_he <= hora_actual <= fin_ventana_he:
                            logger.info(f"Acceso permitido para {usuario.get('legajo')} por autorización de HORAS_EXTRAS.")
                            return {'success': True}
                
                # Puedes añadir más tipos de autorización aquí si es necesario
                # elif auth_tipo == 'SALIDA_ANTICIPADA': ...

            except (ValueError, TypeError) as e:
                logger.warning(f"Error al procesar turno de autorización para {usuario.get('legajo')}: {e}")
                continue
        
        # 4. Si ninguna autorización coincide
        return {'success': False, 'error': 'Fichaje fuera de horario y sin autorización válida para este momento.'}