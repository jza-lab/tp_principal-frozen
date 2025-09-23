from datetime import datetime
from dataclasses import dataclass
from supabase_auth import Optional
from werkzeug.security import generate_password_hash, check_password_hash

@dataclass
class Usuario:
    id: Optional[int]
    username: str
    email: str
    password_hash: str
    nombre: str
    apellido: str
    rol: str
    activo: bool = True
    created_at: Optional[datetime] = None
    
    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'nombre': self.nombre,
            'apellido': self.apellido,
            'rol': self.rol,
            'activo': self.activo,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }