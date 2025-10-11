from dataclasses import dataclass, asdict
from typing import Optional, Dict, List
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
    role_id: int
    activo: bool = True
    created_at: Optional[datetime] = None
    legajo: Optional[str] = None
    cuil_cuit: Optional[str] = None
    telefono: Optional[str] = None
    direccion_id: Optional[int] = None
    fecha_nacimiento: Optional[date] = None
    fecha_ingreso: Optional[date] = None
    supervisor_id: Optional[int] = None
    turno: Optional[str] = None
    ultimo_login_web: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    facial_encoding: Optional[str] = None
    sectores: Optional[List[Dict]] = None

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

    def tiene_sector(self, sector_codigo: str) -> bool:
        """Verifica si el usuario tiene un sector específico"""
        if not self.sectores:
            return False
        return any(sector.get('codigo') == sector_codigo for sector in self.sectores)


class UsuarioModel(BaseModel):
    """
    Modelo actualizado para interactuar con la tabla de usuarios.
    """

    def get_table_name(self) -> str:
        return 'usuarios'

    def contar_usuarios_direccion(self,direccion_id: int) -> int:
        """
        Cuenta el número de usuarios que tienen asignada una dirección específica.
        """
        try:
            response = self.db.table(self.get_table_name()) \
                .select('id', count='exact') \
                .eq('direccion_id', direccion_id) \
                .execute()

            return response.count if response.count is not None else 0

        except Exception as e:
            logger.error(f"Error contando usuarios por direccion_id {direccion_id}: {e}")
            return 0

    def _find_by(self, field: str, value, include_sectores: bool = False, include_direccion: bool = False) -> Dict:
        """
        Método genérico y privado para buscar un usuario por un campo específico.
        """
        try:
            select_query = "*, roles(codigo, nombre, nivel), turno:turno_id(nombre)"
            if include_direccion:
                select_query += ", direccion:usuario_direccion(*)"

            query = self.db.table(self.get_table_name()).select(select_query).eq(field, value)
            result = query.execute()

            if not result.data:
                return {'success': False, 'error': 'Usuario no encontrado'}

            usuario_data = result.data[0]

            if include_sectores:
                from app.models.usuario_sector import UsuarioSectorModel
                usuario_sector_model = UsuarioSectorModel()
                sectores_result = usuario_sector_model.find_by_usuario(usuario_data['id'])

                if sectores_result.get('success'):
                    sectores = [item['sectores'] for item in sectores_result['data'] if item.get('sectores')]
                    usuario_data['sectores'] = sectores
                else:
                    usuario_data['sectores'] = []

            return {'success': True, 'data': usuario_data}

        except Exception as e:
            logger.error(f"Error buscando usuario por {field}: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def find_by_email(self, email: str, include_sectores: bool = False, include_direccion: bool = False) -> Dict:
        """Busca un usuario por email"""
        return self._find_by('email', email, include_sectores, include_direccion)

    def find_by_id(self, usuario_id: int, include_sectores: bool = False, include_direccion: bool = False) -> Dict:
        """Busca un usuario por su ID"""
        return self._find_by('id', usuario_id, include_sectores, include_direccion)

    def find_by_legajo(self, legajo: str, include_sectores: bool = False, include_direccion: bool = False) -> Dict:
        """Busca un usuario por su legajo"""
        return self._find_by('legajo', legajo, include_sectores, include_direccion)

    def find_by_cuil(self, cuil_cuit: str, include_sectores: bool = False, include_direccion: bool = False) -> Dict:
        """Busca un usuario por su CUIL/CUIT"""
        return self._find_by('cuil_cuit', cuil_cuit, include_sectores, include_direccion)

    def find_by_telefono(self, telefono: str, include_sectores: bool = False, include_direccion: bool = False) -> Dict:
        """Busca un usuario por su teléfono"""
        return self._find_by('telefono', telefono, include_sectores, include_direccion)

    def find_all(self, filtros: Dict = None, include_sectores: bool = False, include_direccion: bool = False) -> Dict:
        """Obtiene todos los usuarios con opción de incluir sectores y dirección."""
        try:
            select_query = "*, roles(codigo, nombre, nivel), turno:turno_id(nombre)"
            if include_direccion:
                select_query += ", direccion:usuario_direccion(*)"

            query = self.db.table(self.get_table_name()).select(select_query)

            if filtros:
                for key, value in filtros.items():
                    query = query.eq(key, value)

            response = query.execute()
            usuarios = response.data

            if include_sectores and usuarios:
                from app.models.usuario_sector import UsuarioSectorModel
                usuario_sector_model = UsuarioSectorModel()

                for usuario in usuarios:
                    sectores_result = usuario_sector_model.find_by_usuario(usuario['id'])
                    if sectores_result.get('success'):
                        sectores = [item['sectores'] for item in sectores_result['data'] if item.get('sectores')]
                        usuario['sectores'] = sectores
                    else:
                        usuario['sectores'] = []

            return {'success': True, 'data': usuarios}

        except Exception as e:
            logger.error(f"Error obteniendo usuarios: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

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

    def find_by_web_login_today(self) -> Dict:
        """
        Encuentra a todos los usuarios que han iniciado sesión en la web hoy.
        """
        try:
            from datetime import date, datetime, time
            hoy = date.today()
            start_of_day = datetime.combine(hoy, time.min).isoformat()
            end_of_day = datetime.combine(hoy, time.max).isoformat()

            response = self.db.table(self.get_table_name())\
                .select("id, nombre, apellido, legajo, ultimo_login_web, roles(nombre)")\
                .gte('ultimo_login_web', start_of_day)\
                .lte('ultimo_login_web', end_of_day)\
                .order('ultimo_login_web', desc=True)\
                .execute()

            if response.data:
                return {'success': True, 'data': response.data}
            
            return {'success': True, 'data': []}

        except Exception as e:
            logger.error(f"Error buscando usuarios con login web hoy: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}