from app.models.base_model import BaseModel
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class RoleModel(BaseModel):
    """
    Modelo para interactuar con la tabla de roles.
    """
    def get_table_name(self) -> str:
        return 'roles'

    def find_all(self, filters: dict = None) -> Dict:
        """
        Obtiene todos los roles del sistema, con opción de aplicar filtros.
        """
        try:
            query = self.db.table(self.get_table_name()).select('*')

            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            
            query = query.order('nombre')
            response = query.execute()

            if not response.data:
                return {'success': True, 'data': []}
            
            return {'success': True, 'data': response.data}
            
        except Exception as e:
            logger.error(f"Error obteniendo todos los roles: {str(e)}")
            return {'success': False, 'error': str(e), 'data': []}