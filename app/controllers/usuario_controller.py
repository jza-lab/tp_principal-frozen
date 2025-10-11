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
from datetime import datetime, date
import logging
from app.controllers.direccion_controller import GeorefController

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

        full_street = f"{direccion_data['calle']} {direccion_data['altura']}"
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

    def actualizar_usuario(self, usuario_id: int, data: Dict) -> Dict:
        """Actualiza un usuario existente, incluyendo la gestión de dirección y sectores."""
        try:
            fields_to_sanitize = ['telefono', 'cuil_cuit', 'fecha_nacimiento', 'fecha_ingreso', 'turno_id', 'piso', 'depto', 'codigo_postal']
            for field in fields_to_sanitize:
                if field in data and data[field] == '':
                    data[field] = None
            

            existing = self.model.find_by_id(usuario_id)
            if not existing.get('success'):
                return {'success': False, 'error': 'Usuario no encontrado'}

            # --- 1. Separar datos: dirección, sectores y datos de usuario ---
            address_fields = ['calle', 'altura', 'piso', 'depto', 'localidad', 'provincia', 'codigo_postal']
            direccion_data_raw = {field: data.get(field) for field in address_fields}
            sectores_ids = data.get('sectores') # No lo quitamos de `data` todavía

            # --- 2. Filtrar datos del usuario para validación ---
            # Solo incluimos campos que el schema puede cargar (no dump_only)
            loadable_fields = {k for k, v in self.schema.fields.items() if not v.dump_only}
            user_data_for_validation = {k: v for k, v in data.items() if k in loadable_fields}

            # --- 3. Validar los datos filtrados ---
            validated_data = self.schema.load(user_data_for_validation, partial=True)
            
            # --- 4. Manejar el password POST-validación ---
            if 'password' in validated_data and validated_data['password']:
                password = validated_data.pop('password')
                validated_data['password_hash'] = generate_password_hash(password)
            else:
                validated_data.pop('password', None) # Asegurarse de quitarlo si está vacío

            # --- 5. Validaciones de negocio (ej. email único) ---
            if 'email' in validated_data:
                existing_email = self.model.find_by_email(validated_data['email']).get('data')
                if existing_email and existing_email['id'] != usuario_id:
                    return {'success': False, 'error': 'El correo electrónico ya está en uso.'}

            # --- 6. Procesar la dirección ---
            if 'altura' in direccion_data_raw and direccion_data_raw['altura'] == '':
                direccion_data_raw['altura'] = None
            has_address_data = all(direccion_data_raw.get(f) for f in ['calle', 'altura', 'localidad', 'provincia'])

            if has_address_data:
                direccion_normalizada = self._normalizar_y_preparar_direccion(direccion_data_raw)
                if direccion_normalizada:
                    id_direccion_vieja = existing['data'].get('direccion_id')
                    if id_direccion_vieja:
                        cantidad_misma_direccion = self.model.contar_usuarios_direccion(id_direccion_vieja)
                        
                        if cantidad_misma_direccion > 1:
                            id_nueva_direccion = self._get_or_create_direccion(direccion_normalizada)
                            if id_nueva_direccion:
                                validated_data['direccion_id'] = id_nueva_direccion
                        else:                     
                            # Actualizar la dirección existente y VERIFICAR el resultado
                            actualizacion_exitosa = self._actualizar_direccion(id_direccion_vieja, direccion_normalizada)
                            if not actualizacion_exitosa: # <-- AHORA COMPRUEBA EL BOOLEANO DIRECTAMENTE
                                # Si la actualización de la dirección falla, detener todo y devolver el error.
                                return {'success': False, 'error': "Ocurrió un error al intentar actualizar la dirección."}
                    else:
                        id_nueva_direccion = self._get_or_create_direccion(direccion_normalizada)
                        if id_nueva_direccion:
                            validated_data['direccion_id'] = id_nueva_direccion

            # --- 7. Actualizar el usuario en la BD ---
            resultado_actualizacion = self.model.update(usuario_id, validated_data)
            if not resultado_actualizacion.get('success'):
                return resultado_actualizacion

            # --- 8. Procesar los sectores ---
            if sectores_ids is not None:
                self.usuario_sector_model.eliminar_todas_asignaciones(usuario_id)
                if sectores_ids:
                    # 'sectores' viene de la ruta como lista de ints
                    resultado_sectores = self._asignar_sectores_usuario(usuario_id, sectores_ids)
                    if not resultado_sectores.get('success'):
                        return resultado_sectores

            return self.model.find_by_id(usuario_id, include_sectores=True, include_direccion=True)

        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
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

    def validar_campo_unico(self, field: str, value: str) -> Dict:
        """Verifica si un valor para un campo específico ya existe (legajo, email, cuil_cuit, telefono)."""
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
                return {'valid': False, 'message': f'El valor ingresado para {field} ya está en uso.'}

            error_msg = result.get('error', '')
            if 'no encontrado' in error_msg:
                return {'valid': True}

            logger.error(f"Validation error for field '{field}': {error_msg}")
            return {'valid': False, 'error': 'Error al realizar la validación.'}

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
    
    def obtener_actividad_totem(self) -> Dict:
        """
        Obtiene la lista de actividad del tótem (ingresos/egresos) de hoy.
        """
        try:
            resultado = self.totem_sesion.obtener_actividad_totem_hoy()
            return resultado
        except Exception as e:
            logger.error(f"Error obteniendo actividad del tótem: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def obtener_actividad_web(self) -> Dict:
        """
        Obtiene la lista de usuarios que iniciaron sesión en la web hoy.
        """
        try:
            resultado = self.model.find_by_web_login_today()
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

    def obtener_todos_los_turnos(self) -> List[Dict]:
        """Obtiene una lista de todos los turnos de trabajo disponibles."""
        resultado = self.turno_model.find_all()
        return resultado.get('data', [])