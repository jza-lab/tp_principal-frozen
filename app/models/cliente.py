from app.models.base_model import BaseModel
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ClienteModel(BaseModel):
    """Modelo para la tabla clientes"""

    def get_table_name(self) -> str:
        return 'clientes'

    def get_all(self) -> Dict:
        """Obtener todos los clientes"""
        try:
            response = self.db.table(self.get_table_name()).select("*").execute()
            return {'success': True, 'data': response.data}
        except Exception as e:
            logger.error(f"Error obteniendo clientes activos: {e}")
            return {'success': False, 'error': str(e)}

    def get_all_activos(self) -> Dict:
        """Obtener todos los clientes activos"""
        try:
            response = self.db.table(self.get_table_name()).select("*").eq("activo", True).execute()
            return {'success': True, 'data': response.data}
        except Exception as e:
            logger.error(f"Error obteniendo clientes activos: {e}")
            return {'success': False, 'error': str(e)}

    def buscar_por_email(self, email: str) -> Optional[Dict]:
        """Buscar proveedor por email"""
        try:
            response = self.db.table(self.get_table_name())\
                           .select("*")\
                           .eq("email", email.strip().lower())\
                           .execute()
            if response.data:
                return response.data[0], response.status_code
            else:
                return None, 404
        except Exception as e:
            logger.error(f"Error buscando proveedor por email {email}: {e}")
            return None, 500

    def buscar_por_cuit(self, cuit: str) -> Optional[Dict]:
        """Buscar proveedor por CUIT/CUIL"""
        try:
            response = self.db.table(self.get_table_name())\
                           .select("*")\
                           .eq("cuit", cuit.strip())\
                           .execute()
            return response.data[0] if response.data else None,404
        except Exception as e:
            logger.error(f"Error buscando proveedor por CUIT {cuit}: {e}")
            return None,500

