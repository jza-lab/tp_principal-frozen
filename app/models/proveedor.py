from app.models.base_model import BaseModel
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class ProveedorModel(BaseModel):
    """Modelo para la tabla proveedores"""

    def get_table_name(self) -> str:
        return 'proveedores'

    def get_all_activos(self) -> Dict:
        """Obtener todos los proveedores activos"""
        try:
            response = self.db.table(self.get_table_name()).select("*").eq("activo", True).execute()
            return {'success': True, 'data': response.data}
        except Exception as e:
            logger.error(f"Error obteniendo proveedores activos: {e}")
            return {'success': False, 'error': str(e)}