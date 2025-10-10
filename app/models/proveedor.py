from app.models.base_model import BaseModel
from typing import Dict, Optional, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ProveedorModel(BaseModel):
    """Modelo para la tabla proveedores"""

    def _convert_item_dates(self, item: Dict) -> Dict:
        """Convierte campos de fecha de string a datetime para un solo item"""
        if item and item.get('created_at') and isinstance(item['created_at'], str):
            item['created_at'] = datetime.fromisoformat(item['created_at'])
        if item and item.get('updated_at') and isinstance(item['updated_at'], str):
            item['updated_at'] = datetime.fromisoformat(item['updated_at'])
        return item

    def _convert_dates(self, data: List[Dict]) -> List[Dict]:
        """Convierte campos de fecha de string a datetime"""
        return [self._convert_item_dates(item) for item in data]

    def get_table_name(self) -> str:
        return 'proveedores'

    def get_all(self) -> Dict:
        """Obtener todos los proveedores activos"""
        try:
            response = self.db.table(self.get_table_name()).select("*").execute()
            if response.data:
                response.data = self._convert_dates(response.data)
            return {'success': True, 'data': response.data}
        except Exception as e:
            logger.error(f"Error obteniendo proveedores activos: {e}")
            return {'success': False, 'error': str(e)}

    def get_all_activos(self) -> Dict:
        """Obtener todos los proveedores activos"""
        try:
            response = self.db.table(self.get_table_name()).select("*").eq("activo", True).execute()
            if response.data:
                response.data = self._convert_dates(response.data)
            return {'success': True, 'data': response.data}
        except Exception as e:
            logger.error(f"Error obteniendo proveedores activos: {e}")
            return {'success': False, 'error': str(e)}

    def find_by_id(self, id_value: str, id_field: str = 'id') -> Dict:
        """Buscar por ID y convertir fechas"""
        result = super().find_by_id(id_value, id_field)
        if result.get('success') and result.get('data'):
            result['data'] = self._convert_item_dates(result['data'])
        return result

    def buscar_por_email(self, email: str) -> Optional[Dict]:
        """Buscar proveedor por email"""
        try:
            response = self.db.table(self.get_table_name())\
                           .select("*")\
                           .eq("email", email.strip().lower())\
                           .execute()
            if response.data:
                item = self._convert_item_dates(response.data[0])
                return item, response.status_code
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
            if response.data:
                item = self._convert_item_dates(response.data[0])
                return item, 404
            return None, 404
        except Exception as e:
            logger.error(f"Error buscando proveedor por CUIT {cuit}: {e}")
            return None,500

    def buscar_por_identificacion(self, fila: Dict) -> Optional[Dict]:
        """
        Busca proveedor por email o CUIL/CUIT usando los métodos del modelo

        Args:
            fila: Diccionario con datos que pueden contener email_proveedor o cuil_proveedor

        Returns:
            Dict con datos del proveedor o None
        """
        try:
            # Por email (prioridad)
            if fila.get('email_proveedor'):
                proveedor = self.buscar_por_email(fila['email_proveedor'])
                if proveedor:
                    return proveedor

            # Por CUIL/CUIT (alternativa)
            if fila.get('cuil_proveedor'):
                proveedor = self.buscar_por_cuit(fila['cuil_proveedor'])
                if proveedor:
                    return proveedor

            return None

        except Exception as e:
            logger.error(f"Error buscando proveedor por identificación: {e}")
            return None
        
