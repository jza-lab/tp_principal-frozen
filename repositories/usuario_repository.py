from typing import Optional, Dict, Any
from datetime import datetime, date
from models.usuario import Usuario
from .base_repository import BaseRepository

class UsuarioRepository(BaseRepository[Usuario]):

    @property
    def table_name(self) -> str:
        return 'usuarios'

    def _dict_to_model(self, data: Dict[str, Any]) -> Usuario:
        """Convierte un diccionario en una instancia del modelo Usuario v2."""
        # Para convertir strings a date/datetime de forma segura
        def to_datetime(val):
            return datetime.fromisoformat(val) if val else None
        
        def to_date(val):
            return date.fromisoformat(val) if val else None

        return Usuario(
            id=data.get('id'),
            email=data.get('email'),
            password_hash=data.get('password_hash'),
            nombre=data.get('nombre'),
            apellido=data.get('apellido'),
            rol=data.get('rol'),
            activo=data.get('activo', True),
            created_at=to_datetime(data.get('created_at')),
            numero_empleado=data.get('numero_empleado'),
            dni=data.get('dni'),
            telefono=data.get('telefono'),
            direccion=data.get('direccion'),
            fecha_nacimiento=to_date(data.get('fecha_nacimiento')),
            fecha_ingreso=to_date(data.get('fecha_ingreso')),
            departamento=data.get('departamento'),
            puesto=data.get('puesto'),
            supervisor_id=data.get('supervisor_id'),
            turno=data.get('turno'),
            ultimo_login=to_datetime(data.get('ultimo_login')),
            updated_at=to_datetime(data.get('updated_at'))
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

    def obtener_por_dni(self, dni: str) -> Optional[Usuario]:
        """Busca y recupera un usuario por su número de DNI."""
        return self.get_by('dni', dni)