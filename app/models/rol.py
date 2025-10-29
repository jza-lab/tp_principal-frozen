from app.models.base_model import BaseModel
from typing import Dict
from app.utils.permission_map import CANONICAL_PERMISSION_MAP
import logging

logger = logging.getLogger(__name__)

class RoleModel(BaseModel):
    """
    Modelo para interactuar con la tabla de roles.
    """
    def get_table_name(self) -> str:
        return 'roles'

    def find_all(self) -> Dict:
        """
        Obtiene todos los roles del sistema.
        """
        try:
            query = self.db.table(self.get_table_name()).select('*').order('nombre')
            response = query.execute()
            
            if not response.data:
                return {'success': True, 'data': []}
            
            return {'success': True, 'data': response.data}
            
        except Exception as e:
            logger.error(f"Error obteniendo todos los roles: {str(e)}")
            return {'success': False, 'error': str(e), 'data': []}

    def find_by_codigo(self, codigo: str) -> Dict:
        """
        Busca un rol por su código.
        """
        try:
            result = self.db.table(self.get_table_name()).select('*').eq('codigo', codigo).maybe_single().execute()
            if result.data:
                return {'success': True, 'data': result.data}
            else:
                return {'success': False, 'error': 'Rol no encontrado'}
        except Exception as e:
            logger.error(f"Error buscando rol por código '{codigo}': {e}")
            return {'success': False, 'error': str(e)}

    @classmethod
    def get_permission_map(cls) -> Dict:
        """
        Devuelve el mapa canónico de permisos para todos los roles.
        """
        return CANONICAL_PERMISSION_MAP

    @classmethod
    def check_permission(cls, rol_codigo: str, accion: str) -> bool:
        """
        Verifica si un rol específico tiene permiso para una acción.
        """
        if not rol_codigo:
            return False
            
        # El rol 'DEV' siempre tiene permiso para todo.
        if rol_codigo == 'DEV':
            return True
            
        permission_map = cls.get_permission_map()
        # --- LÓGICA CORREGIDA ---
        # Obtener la lista de roles permitidos para la ACCIÓN dada.
        allowed_roles_for_action = permission_map.get(accion, [])
        # Verificar si el ROL del usuario está en esa lista.
        return rol_codigo in allowed_roles_for_action