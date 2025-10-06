from app.controllers.base_controller import BaseController
from app.models.usuario import UsuarioModel
from app.models.totem_sesion import TotemSesionModel
from app.models.sector import SectorModel
from app.models.usuario_sector import UsuarioSectorModel
from app.schemas.usuario_schema import UsuarioSchema
from typing import Dict, Optional, List
from marshmallow import ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import logging

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
        self.schema = UsuarioSchema()

    def crear_usuario(self, data: Dict) -> Dict:
        """Valida y crea un nuevo usuario con asignación de sectores."""
        try:
            sectores_ids = data.pop('sectores', [])
            validated_data = self.schema.load(data)

            # Verificar si el email ya existe
            if self.model.find_by_email(validated_data['email']).get('data'):
                return {'success': False, 'error': 'El correo electrónico ya está en uso.'}

            # Hashear la contraseña antes de guardarla
            password = validated_data.pop('password')
            validated_data['password_hash'] = generate_password_hash(password)

            # Crear el usuario
            resultado_creacion = self.model.create(validated_data)
            
            if not resultado_creacion.get('success'):
                return resultado_creacion

            usuario_creado = resultado_creacion['data']
            usuario_id = usuario_creado['id']

            # Asignar sectores si se proporcionaron
            if sectores_ids:
                resultado_sectores = self._asignar_sectores_usuario(usuario_id, sectores_ids)
                if not resultado_sectores.get('success'):
                    # Si falla la asignación de sectores, revertir la creación del usuario
                    self.model.db.table("usuarios").delete().eq("id", usuario_id).execute()
                    return resultado_sectores

            # Obtener el usuario completo con sectores
            usuario_completo = self.model.find_by_id(usuario_id, include_sectores=True)
            return usuario_completo

        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
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
        """Actualiza un usuario existente con gestión de sectores."""
        try:
            # Extraer sectores si vienen en los datos
            sectores_ids = data.pop('sectores', None)
            
            # Si se proporciona una nueva contraseña, hashearla
            if 'password' in data and data['password']:
                password = data.pop('password')
                data['password_hash'] = generate_password_hash(password)
            else:
                # Evitar que el campo de contraseña vacío se valide
                data.pop('password', None)

            validated_data = self.schema.load(data, partial=True)
            # Verificar unicidad del email si se está cambiando
            if 'email' in validated_data:
                existing = self.model.find_by_email(validated_data['email']).get('data')
                if existing and existing['id'] != usuario_id:
                    return {'success': False, 'error': 'El correo electrónico ya está en uso.'}

            # Actualizar datos básicos del usuario
            resultado_actualizacion = self.model.update(usuario_id, validated_data)
            if not resultado_actualizacion.get('success'):
                return resultado_actualizacion

            # Actualizar sectores si se proporcionaron
            if sectores_ids is not None:
                # Eliminar asignaciones existentes
                self.usuario_sector_model.eliminar_todas_asignaciones(usuario_id)
                
                # Asignar nuevos sectores
                if sectores_ids:
                    resultado_sectores = self._asignar_sectores_usuario(usuario_id, sectores_ids)
                    if not resultado_sectores.get('success'):
                        return resultado_sectores

            # Devolver usuario actualizado con sectores
            return self.model.find_by_id(usuario_id, include_sectores=True)

        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def obtener_usuario_por_id(self, usuario_id: int, include_sectores: bool = True) -> Optional[Dict]:
        """Obtiene un usuario por su ID con opción de incluir sectores."""
        result = self.model.find_by_id(usuario_id, include_sectores)
        return result.get('data')

    def obtener_todos_los_usuarios(self, filtros: Optional[Dict] = None, include_sectores: bool = True) -> List[Dict]:
        """Obtiene una lista de todos los usuarios con opción de incluir sectores."""
        result = self.model.find_all(filtros, include_sectores)
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
        """Verifica si un valor para un campo específico ya existe."""
        if field not in ['legajo', 'email']:
            return {'valid': False, 'error': 'Campo de validación no soportado.'}

        filters = {field: value}
        existing_user_result = self.model.find_all(filters, limit=1)

        if existing_user_result.get('success') and existing_user_result.get('data'):
            return {'valid': False, 'message': f'El {field} ya está en uso.'}
        elif not existing_user_result.get('success'):
            return {'valid': False, 'error': 'Error al realizar la validación.'}
        else:
            return {'valid': True}

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
    
    def obtener_todos_los_roles(self) -> List[Dict]:
        """Obtiene una lista de todos los roles disponibles."""
        try:
            response = self.db.table("roles").select("*").order("nivel").execute()
            return response.data
        except Exception as e:
            logger.error(f"Error obteniendo roles: {str(e)}")
            return []

    def obtener_rol_por_id(self, role_id: int) -> Optional[Dict]:
        """Obtiene un rol por su ID."""
        try:
            response = self.db.table("roles").select("*").eq("id", role_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error obteniendo rol por ID: {str(e)}")
            return None