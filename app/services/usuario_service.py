from datetime import datetime
from typing import Optional
from models.usuario import Usuario
from repositories.usuario_repository import UsuarioRepository

class UsuarioService:
    
    def __init__(self):
        self.repository = UsuarioRepository()
    
    def autenticar(self, email: str, password: str) -> Optional[Usuario]:
        """Autenticar usuario por email y contraseña"""
        usuario = self.repository.obtener_por_email(email)
        
        if usuario and usuario.check_password(password):
            return usuario
        
        return None
    
    def crear_usuario(self, username: str, email: str, password: str, 
                     nombre: str, apellido: str, rol: str) -> Usuario:
        """Crear nuevo usuario"""
        # Validar que no exista username
        if self.repository.obtener_por_username(username):
            raise ValueError("Username ya existe")
        
        usuario = Usuario(
            id=None,
            username=username,
            email=email,
            password_hash='',
            nombre=nombre,
            apellido=apellido,
            rol=rol,
            activo=True,
            created_at=datetime.now()
        )
        
        usuario.set_password(password) 
        return self.repository.crear(usuario)