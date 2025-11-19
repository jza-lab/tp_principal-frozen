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

    def find_less_urgent_reservations(self, lote_producto_id: int, fecha_limite_str: str) -> list:
        """
        Busca reservas activas de pedidos cuya fecha de entrega sea POSTERIOR a la fecha límite.
        NOTA: Supone que buscas por 'lote_producto_id' según tu esquema,
        o si necesitas buscar por producto genérico, habría que adaptar el JOIN.
        """
        try:
            # CORRECCIÓN 2: Usar 'pedido_item_id' (tu esquema) en vez de 'item_pedido_id'
            # CORRECCIÓN 3: Buscar estado 'RESERVADO' (tu constraint) en vez de 'ACTIVO'

            # Nota: Asumimos que 'lote_producto_id' es lo que usamos para buscar disponibilidad.
            # Si tu lógica busca por ID de producto global, necesitarás hacer un join con lotes_productos.
            # Aquí asumo que pasas el ID del lote o que adaptas el filtro.

            response = self.db.table(self.table_name) \
                .select('id, cantidad_reservada, pedido_id, pedido_item_id, pedidos!inner(fecha_requerido)') \
                .eq('lote_producto_id', lote_producto_id) \
                .eq('estado', 'RESERVADO') \
                .gt('pedidos.fecha_requerido', fecha_limite_str) \
                .order('fecha_requerido', desc=True, foreign_table='pedidos') \
                .execute()

            datos = response.data if response.data else []
            logger.info(f"[ReservaModel] Buscando víctimas para Lote {lote_producto_id} con fecha > {fecha_limite_str}. Encontrados: {len(datos)}")
            return datos

        except Exception as e:
            logger.error(f"Error buscando reservas menos urgentes: {e}")
            return []