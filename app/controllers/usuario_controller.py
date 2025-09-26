from controllers.base_controller import BaseController
from models.usuario import UsuarioModel
from schemas.usuario_schema import UsuarioSchema
from typing import Dict, Optional, List
from marshmallow import ValidationError
from werkzeug.security import generate_password_hash, check_password_hash

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

    def autenticar_usuario(self, email: str, password: str) -> Optional[Dict]:
        """Autentica a un usuario por email y contraseña."""
        user_result = self.model.find_by_email(email)
        if user_result.get('success') and user_result.get('data'):
            user_data = user_result['data']
            if check_password_hash(user_data['password_hash'], password):
                return user_data
        return None

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