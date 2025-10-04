from app.models.base_model import BaseModel
from typing import Dict, Optional
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


    def buscar_por_email(self, email: str) -> Optional[Dict]:
        """Buscar proveedor por email"""
        try:
            response = self.db.table(self.get_table_name())\
                           .select("*")\
                           .eq("email", email.strip().lower())\
                           .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error buscando proveedor por email {email}: {e}")
            return None

    def buscar_por_cuit(self, cuit: str) -> Optional[Dict]:
        """Buscar proveedor por CUIT/CUIL"""
        try:
            response = self.db.table(self.get_table_name())\
                           .select("*")\
                           .eq("cuit", cuit.strip())\
                           .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error buscando proveedor por CUIT {cuit}: {e}")
            return None

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