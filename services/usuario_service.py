from datetime import datetime
from typing import Optional
from models.usuario import Usuario
from repositories.usuario_repository import UsuarioRepository

class UsuarioService:
    
    def __init__(self):
        self.repository = UsuarioRepository()
    
    def autenticar(self, dni: str, password: str) -> Optional[Usuario]:
        """Autenticar usuario por DNI y contraseña."""
        usuario = self.repository.obtener_por_dni(dni)

        if usuario and usuario.activo and usuario.check_password(password):
            # Opcional: Actualizar 'ultimo_login' al autenticar
            # self.repository.update(usuario.id, {'ultimo_login': datetime.now()})
            return usuario
        
        return None

    def crear_usuario(self, email: str, dni: str, password: str,
                     nombre: str, apellido: str, rol: str, **kwargs) -> Usuario:
        """
        Crear un nuevo usuario con campos adicionales opcionales.
        **Puede contener: numero_empleado, dni, telefono, direccion, etc.
        """
        if self.repository.obtener_por_dni(dni):
            raise ValueError(f"El DNI '{dni}' ya está en uso.")

        usuario = Usuario(
            id=None,
            email=email,
            password_hash='', # Se generará con set_password
            nombre=nombre,
            apellido=apellido,
            rol=rol,
            activo=True,
            created_at=datetime.now(),
            numero_empleado=kwargs.get('numero_empleado'),
            dni=kwargs.get('dni'),
            telefono=kwargs.get('telefono'),
            direccion=kwargs.get('direccion'),
            fecha_nacimiento=kwargs.get('fecha_nacimiento'),
            fecha_ingreso=kwargs.get('fecha_ingreso'),
            departamento=kwargs.get('departamento'),
            puesto=kwargs.get('puesto'),
            supervisor_id=kwargs.get('supervisor_id'),
            turno=kwargs.get('turno')
        )
        
        usuario.set_password(password)
        
        return self.repository.create(usuario)

    def obtener_por_id(self, usuario_id: int) -> Optional[Usuario]:
        """Obtener un usuario por su ID."""
        return self.repository.get_by_id(usuario_id)

    def obtener_todos(self):
        """Obtener todos los usuarios (generalmente filtrando por activos)."""
        return self.repository.get_all()