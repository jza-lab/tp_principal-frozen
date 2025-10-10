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
from app.models.direccion import DireccionModel

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
        self.direccion_model = DireccionModel()

    def _handle_direccion(self, data: Dict) -> Dict:
        """
        Helper privado para manejar la normalización y almacenamiento de direcciones.
        """
        address_fields = ['calle', 'altura', 'piso', 'depto', 'localidad', 'provincia', 'codigo_postal']
        direccion_data = {field: data.get(field) for field in address_fields}

        if not all([direccion_data['calle'], direccion_data['altura'], direccion_data['localidad'],
                    direccion_data['provincia']]):
            return {'success': True, 'direccion_id': None}  # Not enough data to process, skip

        full_street = f"{direccion_data['calle']} {direccion_data['altura']}"
        norm_result = self.usuario_direccion_controller.normalizar_direccion(
            direccion=full_street,
            localidad=direccion_data['localidad'],
            provincia=direccion_data['provincia']
        )

        if not norm_result.get('success'):
            logger.warning(f"GEOREF normalization failed: {norm_result.get('message')}. Using user-provided address.")
            db_address_data = direccion_data
        else:
            norm_data = norm_result['data']
            db_address_data = {
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

        existing_address = self.direccion_model.find_by_full_address(
            calle=db_address_data['calle'],
            altura=db_address_data['altura'],
            piso=db_address_data.get('piso'),
            depto=db_address_data.get('depto'),
            localidad=db_address_data['localidad'],
            provincia=db_address_data['provincia']
        )

        if existing_address.get('success'):
            return {'success': True, 'direccion_id': existing_address['data']['id']}

        new_address_result = self.direccion_model.create(db_address_data)
        if not new_address_result.get('success'):
            return {'success': False, 'error': 'Failed to save the normalized address.'}

        return {'success': True, 'direccion_id': new_address_result['data']['id']}

    def crear_usuario(self, data: Dict) -> Dict:
        """Valida y crea un nuevo usuario, incluyendo dirección y sectores."""
        try:
            direccion_result = self._handle_direccion(data)
            if not direccion_result.get('success'):
                return direccion_result
            direccion_id = direccion_result.get('direccion_id')

            sectores_ids = data.pop('sectores', [])
            
            address_fields = ['calle', 'altura', 'piso', 'depto', 'localidad', 'provincia', 'codigo_postal']
            user_data_for_validation = {k: v for k, v in data.items() if k not in address_fields}

            validated_data = self.schema.load(user_data_for_validation)

            if self.model.find_by_email(validated_data['email']).get('data'):
                return {'success': False, 'error': 'El correo electrónico ya está en uso.'}

            password = validated_data.pop('password')
            validated_data['password_hash'] = generate_password_hash(password)

            if direccion_id:
                validated_data['direccion_id'] = direccion_id

            resultado_creacion = self.model.create(validated_data)
            if not resultado_creacion.get('success'):
                if self.direccion_model.find_by_id(direccion_id):
                     pass
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
                    # Si falla alguna asignación, eliminar todas las asignaciones
                    self.usuario_sector_model.eliminar_todas_asignaciones(usuario_id)
                    return {'success': False, 'error': f'Error asignando sector ID {sector_id}'}
            
            return {'success': True, 'message': 'Sectores asignados correctamente'}
        except Exception as e:
            logger.error(f"Error asignando sectores: {str(e)}")
            return {'success': False, 'error': str(e)}

    def actualizar_usuario(self, usuario_id: int, data: Dict) -> Dict:
        """Updates an existing user, including address and sector management."""
        try:
            direccion_result = self._handle_direccion(data)
            if not direccion_result.get('success'):
                return direccion_result
            direccion_id = direccion_result.get('direccion_id')

            sectores_ids = data.pop('sectores', None)
            
            if 'password' in data and data['password']:
                password = data.pop('password')
                data['password_hash'] = generate_password_hash(password)
            else:
                data.pop('password', None)
            
            address_fields = ['calle', 'altura', 'piso', 'depto', 'localidad', 'provincia', 'codigo_postal']
            user_data_for_validation = {k: v for k, v in data.items() if k not in address_fields}

            validated_data = self.schema.load(user_data_for_validation, partial=True)
            
            if 'email' in validated_data:
                existing = self.model.find_by_email(validated_data['email']).get('data')
                if existing and existing['id'] != usuario_id:
                    return {'success': False, 'error': 'El correo electrónico ya está en uso.'}

            if direccion_id:
                validated_data['direccion_id'] = direccion_id

            resultado_actualizacion = self.model.update(usuario_id, validated_data)
            if not resultado_actualizacion.get('success'):
                return resultado_actualizacion

            if sectores_ids is not None:
                self.usuario_sector_model.eliminar_todas_asignaciones(usuario_id)
                if sectores_ids:
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