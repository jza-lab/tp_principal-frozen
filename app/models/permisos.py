from app.models.base_model import BaseModel
from typing import List, Dict, Any, Optional

class PermisosModel(BaseModel):
    """
    Modelo para gestionar los permisos que relacionan roles, sectores y acciones.
    """

    def get_table_name(self) -> str:
        """Retorna el nombre de la tabla para este modelo."""
        return 'usuario_permisos'

    def check_permission(self, role_id: int, sector_id: int, accion: str) -> bool:
        """
        Verifica si un rol tiene permiso para una acción en un sector específico.

        Args:
            role_id (int): El ID del rol a verificar.
            sector_id (int): El ID del sector a verificar.
            accion (str): El código de la acción a verificar (e.g., 'crear', 'leer').

        Returns:
            bool: True si el permiso existe, False en caso contrario.
        """
        try:
            query = self.db.table(self.get_table_name()).select("count", count='exact').eq("role_id", role_id).eq("sector_id", sector_id).eq("accion", accion).execute()
            
            if query.count > 0:
                return True
            return False
        except Exception as e:
            # En caso de error, es más seguro denegar el permiso
            print(f"Error al verificar permiso: {e}")
            return False

    def get_user_permissions(self, role_id: int) -> Dict[str, List[str]]:
        """
        Obtiene todos los permisos de un usuario agrupados por sector.

        Args:
            role_id (int): El ID del rol del usuario.

        Returns:
            Dict[str, List[str]]: Un diccionario donde las claves son los códigos de sector
                                 y los valores son listas de acciones permitidas.
                                 Ej: {'PRODUCCION': ['leer', 'crear'], 'LOGISTICA': ['leer']}
        """
        try:
            # Usamos una vista o un join para obtener los códigos de sector
            query = self.db.table(self.get_table_name())\
                .select('accion, sectores(codigo)')\
                .eq('role_id', role_id)\
                .execute()

            permissions = {}
            if query.data:
                for p in query.data:
                    sector_codigo = p.get('sectores', {}).get('codigo')
                    if sector_codigo:
                        if sector_codigo not in permissions:
                            permissions[sector_codigo] = []
                        permissions[sector_codigo].append(p['accion'])
            
            return permissions
        except Exception as e:
            print(f"Error al obtener permisos del usuario: {e}")
            return {}

    def grant_permission(self, role_id: int, sector_id: int, accion: str) -> Dict[str, Any]:
        """Otorga un permiso específico a un rol en un sector."""
        try:
            # Verificar si ya existe para no duplicar
            if self.check_permission(role_id, sector_id, accion):
                return {'success': True, 'message': 'El permiso ya existía.'}
            
            data_to_insert = {
                "role_id": role_id,
                "sector_id": sector_id,
                "accion": accion
            }
            result = self.create(data_to_insert)
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def revoke_permission(self, role_id: int, sector_id: int, accion: str) -> Dict[str, Any]:
        """Revoca un permiso específico."""
        try:
            query = self.db.table(self.get_table_name())\
                .delete()\
                .eq("role_id", role_id)\
                .eq("sector_id", sector_id)\
                .eq("accion", accion)\
                .execute()
            
            return {'success': True, 'data': query.data}
        except Exception as e:
            return {'success': False, 'error': str(e)}