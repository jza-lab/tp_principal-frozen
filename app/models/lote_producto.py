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


    # --- MÉTODO NUEVO A AÑADIR ---
    def get_all_lotes_for_view(self):
        """
        Obtiene todos los lotes de productos con datos enriquecidos (nombre del producto)
        para ser mostrados en la vista de listado.
        """
        try:
            result = self.db.table(self.get_table_name()).select(
                '*, producto:productos(nombre)'
            ).order('created_at', desc=True).execute()

            # Aplanar los resultados para un uso más fácil en la plantilla
            flat_data = []
            for item in result.data:
                if item.get('producto'):
                    item['producto_nombre'] = item['producto']['nombre']
                else:
                    item['producto_nombre'] = 'Producto no encontrado'
                del item['producto']
                flat_data.append(item)

            return {'success': True, 'data': flat_data}
        except Exception as e:
            logger.error(f"Error obteniendo lotes de productos para la vista: {e}")
            return {'success': False, 'error': str(e)}

    def get_lote_detail_for_view(self, id_lote: int):
        """
        Obtiene el detalle de un lote de producto con datos enriquecidos.
        """
        try:
            # --- LÍNEA CORREGIDA ---
            # Cambiamos 'id' por 'id_lote' para que coincida con la columna de la base de datos.
            result = self.db.table(self.get_table_name()).select(
                '*, producto:productos(nombre, codigo)'
            ).eq('id_lote', id_lote).single().execute()
            # ------------------------

            if result.data:
                item = result.data
                if item.get('producto'):
                    item['producto_nombre'] = item['producto']['nombre']
                    item['producto_codigo'] = item['producto']['codigo']
                else:
                    item['producto_nombre'] = 'Producto no encontrado'
                    item['producto_codigo'] = 'N/A'
                del item['producto']
                return {'success': True, 'data': item}
            else:
                return {'success': False, 'error': 'Lote no encontrado'}
        except Exception as e:
            logger.error(f"Error obteniendo detalle de lote de producto {id_lote}: {e}")
            return {'success': False, 'error': str(e)}