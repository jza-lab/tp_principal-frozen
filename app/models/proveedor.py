from app.models.base_model import BaseModel
from typing import Dict, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ProveedorModel(BaseModel):
    """Modelo para la tabla proveedores"""

    def get_table_name(self) -> str:
        return 'proveedores'

    def _convert_timestamps(self, data):
        """Convierte campos de fecha de string a datetime para un registro o una lista."""
        if not data:
            return data

        records = data if isinstance(data, list) else [data]
        for record in records:
            if record.get('created_at') and isinstance(record['created_at'], str):
                record['created_at'] = datetime.fromisoformat(record['created_at'])
            if record.get('updated_at') and isinstance(record['updated_at'], str):
                record['updated_at'] = datetime.fromisoformat(record['updated_at'])
        return data

    def get_all(self) -> Dict:
        """Obtener todos los proveedores"""
        try:
            response = self.db.table(self.get_table_name()).select("*").execute()
            return {'success': True, 'data': self._convert_timestamps(response.data)}
        except Exception as e:
            logger.error(f"Error obteniendo proveedores: {e}")
            return {'success': False, 'error': str(e)}

    def get_all_activos(self) -> Dict:
        """Obtener todos los proveedores activos"""
        try:
            response = self.db.table(self.get_table_name()).select("*").eq("activo", True).execute()
            return {'success': True, 'data': self._convert_timestamps(response.data)}
        except Exception as e:
            logger.error(f"Error obteniendo proveedores activos: {e}")
            return {'success': False, 'error': str(e)}

    def find_by_id(self, id_value: str, id_field: str = 'id') -> Dict:
        """Sobrescribe find_by_id para convertir timestamps."""
        result = super().find_by_id(id_value, id_field)
        if result.get('success'):
            result['data'] = self._convert_timestamps(result['data'])
        return result

    def buscar_por_email(self, email: str) -> Optional[tuple]:
        """Buscar proveedor por email"""
        try:
            response = self.db.table(self.get_table_name())\
                           .select("*")\
                           .eq("email", email.strip().lower())\
                           .execute()
            if response.data:
                return self._convert_timestamps(response.data[0]), response.status_code
            else:
                return None, 404
        except Exception as e:
            logger.error(f"Error buscando proveedor por email {email}: {e}")
            return None, 500

    def buscar_por_cuit(self, cuit: str) -> Optional[tuple]:
        """Buscar proveedor por CUIT/CUIL"""
        try:
            response = self.db.table(self.get_table_name())\
                           .select("*")\
                           .eq("cuit", cuit.strip())\
                           .execute()
            if response.data:
                return self._convert_timestamps(response.data[0]), 404
            return None, 404
        except Exception as e:
            logger.error(f"Error buscando proveedor por CUIT {cuit}: {e}")
            return None,500

    def buscar_por_identificacion(self, fila: Dict) -> Optional[Dict]:
        """
        Busca proveedor por email o CUIL/CUIT usando los métodos del modelo
        """
        try:
            if fila.get('email_proveedor'):
                proveedor, status = self.buscar_por_email(fila['email_proveedor'])
                if proveedor:
                    return proveedor

            if fila.get('cuil_proveedor'):
                proveedor, status = self.buscar_por_cuit(fila['cuil_proveedor'])
                if proveedor:
                    return proveedor

            return None

        except Exception as e:
            logger.error(f"Error buscando proveedor por identificación: {e}")
            return None