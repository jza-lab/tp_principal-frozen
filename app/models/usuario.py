from dataclasses import dataclass, asdict
from typing import Optional, Dict
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

@dataclass
class Usuario:
    """
    Dataclass que representa la estructura actualizada de un usuario del sistema.
    """
    id: Optional[int]
    email: str
    password_hash: str
    nombre: str
    apellido: str
    role_id: int  # Cambiamos rol por role_id
    activo: bool = True
    created_at: Optional[datetime] = None
    legajo: Optional[str] = None
    dni: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    fecha_ingreso: Optional[date] = None
    supervisor_id: Optional[int] = None
    turno: Optional[str] = None
    ultimo_login_web: Optional[datetime] = None  # Mantenemos solo este
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
    Modelo actualizado para interactuar con la tabla de usuarios.
    """
    def get_table_name(self) -> str:
        return 'usuarios'

    def _find_by(self, field: str, value) -> Dict:
        """
        Método genérico y privado para buscar un usuario por un campo específico.
        """
        try:
            # La consulta siempre incluye la información del rol
            result = self.db.table(self.get_table_name()).select('*, roles(*)').eq(field, value).execute()
            if result.data:
                return {'success': True, 'data': result.data[0]}
            else:
                return {'success': False, 'error': 'Usuario no encontrado'}
        except Exception as e:
            logger.error(f"Error buscando usuario por {field}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_by_email(self, email: str) -> Dict:
        """Busca un usuario por email con información de rol"""
        return self._find_by('email', email)

    def find_by_id(self, usuario_id: int) -> Dict:
        """Busca un usuario por su ID con información de rol"""
        return self._find_by('id', usuario_id)

    def find_by_legajo(self, legajo: str) -> Dict:
        """Busca un usuario por su legajo con información de rol"""
        return self._find_by('legajo', legajo)

    def update(self, usuario_id: int, data: Dict) -> Dict:
        """Actualiza un usuario"""
        try:
            response = self.db.table("usuarios").update(data).eq("id", usuario_id).execute()
            if response.data:
                return {'success': True, 'data': response.data[0]}
            else:
                return {'success': False, 'error': 'Usuario no encontrado'}
        except Exception as e:
            logger.error(f"Error actualizando en usuarios: {e}")
            return {'success': False, 'error': str(e)}