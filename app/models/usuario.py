from dataclasses import dataclass, asdict
from typing import Optional, Dict, List
from datetime import datetime, date, time
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

    def _find_by(self, field: str, value, include_direccion: bool = False) -> Dict:
        """
        Método genérico y optimizado para buscar un usuario, incluyendo siempre
        sus relaciones (rol, turno, sectores) en una única consulta.
        """
        try:
            select_query = "*, roles(*), turno:turno_id(*), sectores:usuario_sectores(sectores(*))"
            if include_direccion:
                select_query += ", direccion:direccion_id(*)"

            query = self.db.table(self.get_table_name()).select(select_query).eq(field, value).limit(1)
            result = query.execute()

            if not result.data:
                return {'success': False, 'error': 'Usuario no encontrado'}

            usuario_data = result.data[0]
            
            # Aplanar la estructura de sectores para que sea más fácil de usar
            if 'sectores' in usuario_data:
                usuario_data['sectores'] = [s['sectores'] for s in usuario_data['sectores'] if s.get('sectores')]

            return {'success': True, 'data': usuario_data}

        except Exception as e:
            logger.error(f"Error buscando usuario por {field}: {str(e)}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}

    def find_by_email(self, email: str, include_direccion: bool = False) -> Dict:
        """Busca un usuario por email, siempre incluyendo sus relaciones."""
        return self._find_by('email', email, include_direccion)

    def find_by_id(self, usuario_id: int, include_direccion: bool = False) -> Dict:
        """Busca un usuario por su ID, siempre incluyendo sus relaciones."""
        return self._find_by('id', usuario_id, include_direccion)

    def find_by_legajo(self, legajo: str, include_direccion: bool = False) -> Dict:
        """Busca un usuario por su legajo, siempre incluyendo sus relaciones."""
        return self._find_by('legajo', legajo, include_direccion)

    def find_by_cuil(self, cuil_cuit: str, include_direccion: bool = False) -> Dict:
        """Busca un usuario por su CUIL/CUIT, siempre incluyendo sus relaciones."""
        return self._find_by('cuil_cuit', cuil_cuit, include_direccion)

    def find_by_telefono(self, telefono: str, include_direccion: bool = False) -> Dict:
        """Busca un usuario por su teléfono, siempre incluyendo sus relaciones."""
        return self._find_by('telefono', telefono, include_direccion)

    def find_all(self, filtros: Dict = None, include_direccion: bool = False) -> Dict:
        """
        Obtiene todos los usuarios, incluyendo siempre sus relaciones (rol, turno, sectores)
        en una única consulta optimizada por cada usuario.
        """
        try:
            select_query = "*, roles(*), turno:turno_id(*), sectores:usuario_sectores(sectores(*))"
            if include_direccion:
                select_query += ", direccion:direccion_id(*)"

            query = self.db.table(self.get_table_name()).select(select_query.replace("turno:turno_id(*)", "turno:turno_id(*)"))

            if filtros:
                for key, value in filtros.items():
                    query = query.eq(key, value)

            response = query.execute()
            usuarios = response.data

            # Aplanar la estructura de sectores para cada usuario
            for usuario in usuarios:
                if 'sectores' in usuario:
                    usuario['sectores'] = [s['sectores'] for s in usuario['sectores'] if s.get('sectores')]

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

    def find_by_web_login_filtrado(self, filtros: Optional[Dict] = None) -> Dict:
        """
        Encuentra usuarios que han iniciado sesión en la web, con filtros opcionales.
        Filtros: 'fecha_desde', 'fecha_hasta', 'sector_id'.
        """
        try:            
            query = self.db.table(self.get_table_name())\
                .select("id, nombre, apellido, legajo, ultimo_login_web, roles(nombre), sectores:usuario_sectores(sectores(nombre))")

            if filtros:
                if filtros.get('fecha_desde'):
                    fecha_desde_obj = datetime.fromisoformat(filtros['fecha_desde']).date()
                    start_date = datetime.combine(fecha_desde_obj, time.min)
                    query = query.gte('ultimo_login_web', start_date.isoformat())
                if filtros.get('fecha_hasta'):
                    fecha_hasta_obj = datetime.fromisoformat(filtros['fecha_hasta']).date()
                    end_date = datetime.combine(fecha_hasta_obj, time.max)
                    query = query.lte('ultimo_login_web', end_date.isoformat())
                
                if filtros.get('sector_id'):
                    user_ids_in_sector = self.db.table('usuario_sectores')\
                        .select('usuario_id')\
                        .eq('sector_id', filtros['sector_id'])\
                        .execute()
                    
                    if user_ids_in_sector.data:
                        user_ids = [item['usuario_id'] for item in user_ids_in_sector.data]
                        query = query.in_('id', user_ids)
                    else:
                        return {'success': True, 'data': []}

            response = query.order('ultimo_login_web', desc=True).execute()

            return {'success': True, 'data': response.data or []}

        except Exception as e:
            logger.error(f"Error buscando usuarios con login web (filtrado): {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def get_turnos_para_usuario(self, usuario_id: int) -> Dict:
        """
        Obtiene los turnos para un usuario específico.
        Si el usuario es GERENTE, devuelve todos los turnos.
        De lo contrario, devuelve solo el turno asignado al usuario.
        """
        try:
            usuario_result = self.find_by_id(usuario_id)
            if not usuario_result.get('success'):
                return usuario_result

            usuario_data = usuario_result['data']
            
            turno_asignado = usuario_data.get('turno')
            if turno_asignado:
                # El formato de find_all devuelve una lista de dicts, lo emulamos
                return {'success': True, 'data': [turno_asignado]}
            
            # Si no tiene turno asignado, devuelve lista vacía
            return {'success': True, 'data': []}

        except Exception as e:
            logger.error(f"Error obteniendo turnos para el usuario {usuario_id}: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}