from dataclasses import dataclass, asdict
from typing import Optional, Dict
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from models.base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

@dataclass
class Usuario:
    """
    Dataclass que representa la estructura de un usuario del sistema.
    """
    id: Optional[int]
    email: str
    password_hash: str
    nombre: str
    apellido: str
    rol: str
    activo: bool = True
    created_at: Optional[datetime] = None
    numero_empleado: Optional[str] = None
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
        d = asdict(self)
        for key, value in d.items():
            if isinstance(value, (datetime, date)):
                d[key] = value.isoformat() if value else None
        return d


class UsuarioModel(BaseModel):
    """
    Modelo para interactuar con la tabla de usuarios en la base de datos.
    """
    def get_table_name(self) -> str:
        return 'usuarios'

    def find_by_email(self, email: str) -> Dict:
        """
        Busca un usuario por su dirección de correo electrónico.
        """
        try:
            result = self.db.table(self.get_table_name()).select('*').eq('email', email).execute()
            if result.data:
                return {'success': True, 'data': result.data[0]}
            else:
                return {'success': False, 'error': 'Usuario no encontrado'}
        except Exception as e:
            logger.error(f"Error buscando usuario por email: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_by_legajo(self, legajo: str) -> Dict:
        """
        Busca un usuario por su número de legajo.
        """
        try:
            result = self.db.table(self.get_table_name()).select('*').eq('numero_empleado', legajo).execute()
            if result.data:
                return {'success': True, 'data': result.data[0]}
            else:
                return {'success': False, 'error': 'Usuario no encontrado'}
        except Exception as e:
            logger.error(f"Error buscando usuario por legajo: {str(e)}")
            return {'success': False, 'error': str(e)}