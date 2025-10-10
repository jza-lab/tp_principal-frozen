from app.models.base_model import BaseModel
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ClienteModel(BaseModel):
    """Modelo para la tabla clientes"""

    def get_table_name(self) -> str:
        return 'clientes'

    def get_all(self, include_direccion: bool = False) -> Dict:
        """Obtener todos los clientes, opcionalmente con su dirección."""
        try:
            query = "*, direccion:direccion_id(*)" if include_direccion else "*"
            response = self.db.table(self.get_table_name()).select(query).execute()
            return {'success': True, 'data': response.data}
        except Exception as e:
            logger.error(f"Error obteniendo clientes: {e}")
            return {'success': False, 'error': str(e)}

    def get_all_activos(self, include_direccion: bool = False) -> Dict:
        """Obtener todos los clientes activos, opcionalmente con su dirección."""
        try:
            query = "*, direccion:direccion_id(*)" if include_direccion else "*"
            response = self.db.table(self.get_table_name()).select(query).eq("activo", True).execute()
            return {'success': True, 'data': response.data}
        except Exception as e:
            logger.error(f"Error obteniendo clientes activos: {e}")
            return {'success': False, 'error': str(e)}

    def find_by_id(self, cliente_id: int, include_direccion: bool = False) -> Dict:
        """Busca un cliente por su ID, opcionalmente incluyendo la dirección."""
        try:
            query = "*, direccion:direccion_id(*)" if include_direccion else "*"
            response = self.db.table(self.get_table_name()).select(query).eq('id', cliente_id).single().execute()
            
            if response.data:
                return {'success': True, 'data': response.data}
            return {'success': False, 'error': 'Cliente no encontrado'}
        except Exception as e:
            logger.error(f"Error buscando cliente por ID {cliente_id}: {e}")
            return {'success': False, 'error': str(e)}

    def buscar_por_email(self, email: str) -> Optional[Dict]:
        """Buscar cliente por email"""
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
            logger.error(f"Error buscando cliente por email {email}: {e}")
            return None, 500

    def buscar_por_cuit(self, cuit: str) -> Optional[Dict]:
        """Buscar cliente por CUIT/CUIL"""
        try:
            response = self.db.table(self.get_table_name())\
                           .select("*")\
                           .eq("cuit", cuit.strip())\
                           .execute()
            if response.data:
                return response.data[0], response.status_code
            else:
                return None, 404
        except Exception as e:
            logger.error(f"Error buscando cliente por CUIT {cuit}: {e}")
            return None,500