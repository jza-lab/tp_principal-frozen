from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash

@dataclass
class Usuario:
    id: Optional[int]
    email: str
    password_hash: str
    nombre: str
    apellido: str
    rol: str
    activo: bool = True
    created_at: Optional[datetime] = None
    legajo: Optional[str] = None
    dni: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    fecha_ingreso: Optional[date] = None
    departamento: Optional[str] = None
    puesto: Optional[str] = None
    supervisor_id: Optional[int] = None
    turno: Optional[str] = None
    ultimo_login: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    facial_encoding: Optional[str] = None

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        """Convierte la instancia de dataclass a un diccionario, manejando objetos datetime y date."""
        d = asdict(self)
        for key, value in d.items():
            if isinstance(value, (datetime, date)):
                d[key] = value.isoformat() if value else None
        return d