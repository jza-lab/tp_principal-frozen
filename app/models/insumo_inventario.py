from app.models.base_model import BaseModel
from typing import Dict, List
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)

class InsumoInventarioModel(BaseModel):
    """Modelo para la tabla insumos_inventario"""

    def get_table_name(self) -> str:
        return 'insumos_inventario'

    def get_stock_total_valorizado(self, fecha: date = None) -> Dict:
        """
        Calcula el valor total del inventario de insumos en una fecha específica.
        Si la fecha es None, calcula el valor actual.
        """
        try:
            # Por ahora, simplificamos y obtenemos el stock actual valorizado
            # ya que no tenemos un historial de movimientos para calcularlo a una fecha pasada.
            query = self.db.table(self.get_table_name()).select(
                'cantidad_actual, insumo:insumos_catalogo(precio_unitario)'
            ).gt('cantidad_actual', 0)

            result = query.execute()

            if not result.data:
                return {'success': True, 'total_valorizado': 0}

            total_valorizado = 0
            for lote in result.data:
                cantidad = lote.get('cantidad_actual', 0)
                precio = lote.get('insumo', {}).get('precio_unitario', 0)
                if cantidad is not None and precio is not None:
                    total_valorizado += cantidad * precio
            
            return {'success': True, 'total_valorizado': total_valorizado}
        except Exception as e:
            logger.error(f"Error calculando stock total valorizado de insumos: {str(e)}")
            return {'success': False, 'error': str(e), 'total_valorizado': 0}

    def get_stock_actual_por_insumo(self, insumo_id: str) -> Dict:
        """
        Obtiene el stock actual total para un insumo específico sumando todos sus lotes.
        """
        try:
            query = self.db.table(self.get_table_name()).select('cantidad_actual').eq('id_insumo', insumo_id)
            result = query.execute()
            
            if not result.data:
                return {'success': True, 'stock_actual': 0}

            stock_total = sum(item.get('cantidad_actual', 0) for item in result.data)
            return {'success': True, 'stock_actual': stock_total}
        except Exception as e:
            logger.error(f"Error obteniendo stock actual para el insumo {insumo_id}: {str(e)}")
            return {'success': False, 'error': str(e), 'stock_actual': 0}
