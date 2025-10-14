from .base_model import BaseModel
import logging


logger = logging.getLogger(__name__)

class ReservaProductoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de reservas de productos.
    Implementa el método abstracto requerido por BaseModel.
    """

    def get_table_name(self):
        """
        Devuelve el nombre de la tabla para cumplir con el contrato de BaseModel.
        """
        return 'reservas_productos'

    def get_all_with_details(self):
        """Obtiene todas las reservas de productos con detalles de producto, lote y pedido."""
        try:
            # --- CONSULTA CORREGIDA ---
            # Cambiamos 'codigo' por 'numero_lote', que es el nombre correcto de la columna.
            result = self.db.table(self.get_table_name()).select(
                '*, pedido:pedidos(id), lote_producto:lotes_productos(numero_lote, producto:productos(nombre))'
            ).order('fecha_reserva', desc=True).execute()

            flat_data = []
            for item in result.data:
                lote_info = item.get('lote_producto')
                if lote_info:
                    # También corregimos aquí para leer el campo correcto
                    item['lote_producto_codigo'] = lote_info.get('numero_lote')
                    producto_info = lote_info.get('producto')
                    if producto_info:
                        item['producto_nombre'] = producto_info.get('nombre')

                if 'lote_producto' in item: del item['lote_producto']
                if 'producto' in item: del item['producto']

                flat_data.append(item)

            return {'success': True, 'data': flat_data}
        except Exception as e:
            logger.error(f"Error obteniendo detalles de reservas de productos: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}