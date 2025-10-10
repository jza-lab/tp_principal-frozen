# app/models/lote_producto.py
from app.models.base_model import BaseModel
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class LoteProductoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de lotes_productos.
    """

    def get_table_name(self) -> str:
        return 'lotes_productos'

    def find_by_numero_lote(self, numero_lote: str) -> Dict:
        """Busca un lote por su número de lote único."""
        try:
            result = self.db.table(self.get_table_name()).select('*').eq('numero_lote', numero_lote).single().execute()
            if result.data:
                return {'success': True, 'data': result.data}
            else:
                return {'success': False, 'error': 'Lote no encontrado'}
        except Exception as e:
            if "Missing data" in str(e):
                 return {'success': False, 'error': 'Lote no encontrado'}
            logger.error(f"Error buscando lote por número: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_by_producto_id(self, producto_id: int) -> Dict:
        """Busca todos los lotes de un producto específico."""
        try:
            result = self.db.table(self.get_table_name()).select('*').eq('producto_id', producto_id).execute()
            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error buscando lotes por producto: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_lotes_disponibles(self) -> Dict:
        """Busca lotes disponibles (no vencidos y con stock)."""
        try:
            result = (
                self.db.table(self.get_table_name())
                .select('*')
                .eq('estado', 'DISPONIBLE')
                .gt('cantidad_actual', 0)
                .execute()
            )
            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error buscando lotes disponibles: {str(e)}")
            return {'success': False, 'error': str(e)}