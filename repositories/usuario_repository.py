from typing import Optional, Dict, Any
from datetime import datetime
from models.usuario import Usuario
from .base_repository import BaseRepository

class UsuarioRepository(BaseRepository[Usuario]):

    @property
    def table_name(self) -> str:
        return 'usuarios'

    def _dict_to_model(self, data: Dict[str, Any]) -> Usuario:
        """Convierte un diccionario en una instancia del modelo Usuario."""
        return Usuario(
            id=data['id'],
            username=data['username'],
            email=data['email'],
            password_hash=data['password_hash'],
            nombre=data['nombre'],
            apellido=data['apellido'],
            rol=data['rol'],
            activo=data['activo'],
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None
        )

    def create(self, usuario: Usuario) -> Usuario:
        """
        Sobrescribe el método de creación base para asegurar que el password_hash se maneje correctamente.
        """
        data = usuario.to_dict()
        data.pop('id', None)
        data['password_hash'] = usuario.password_hash
        response = self.client.table(self.table_name).insert(data).execute()

        if not response.data:
            raise Exception("Error al crear usuario")

        return self._dict_to_model(response.data[0])

    def obtener_por_username(self, username: str) -> Optional[Usuario]:
        """Recupera un usuario por su nombre de usuario."""
        return self.get_by('username', username)

    def obtener_por_email(self, email: str) -> Optional[Usuario]:
        """Recupera un usuario por su dirección de correo electrónico."""
        return self.get_by('email', email)