from .base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

class ReservaInsumoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de reservas de insumos.
    Hereda de BaseModel e implementa el método abstracto requerido.
    """

    def get_table_name(self) -> str:
        """
        Devuelve el nombre de la tabla para que el BaseModel sepa con qué tabla trabajar.
        """
        return 'reservas_insumos'

    def get_all_with_details(self):
        """Obtiene todas las reservas de insumos con detalles anidados."""
        try:
            # --- CONSULTA CORREGIDA ---
            result = self.db.table(self.get_table_name()).select(
                '*, orden_produccion:ordenes_produccion(id, codigo), lote_inventario:lotes_inventario(numero_lote_proveedor, insumo:insumos_catalogo(nombre))'
            ).order('created_at', desc=True).execute()

            flat_data = []
            for item in result.data:
                lote_info = item.get('lote_inventario')
                if lote_info:
                    item['lote_inventario_codigo'] = lote_info.get('numero_lote_proveedor')
                    insumo_info = lote_info.get('insumo')
                    if insumo_info:
                        item['insumo_nombre'] = insumo_info.get('nombre')

                orden_info = item.get('orden_produccion')
                if orden_info:
                    item['orden_produccion_codigo'] = orden_info.get('codigo')

                # Limpiar objetos anidados
                if 'lote_inventario' in item: del item['lote_inventario']
                if 'insumo' in item: del item['insumo']
                if 'orden_produccion' in item: del item['orden_produccion']

                flat_data.append(item)

            return {'success': True, 'data': flat_data}
        except Exception as e:
            logger.error(f"Error obteniendo detalles de reservas de insumos: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    
    def get_by_orden_produccion_id(self, orden_produccion_id: int):
        """Obtiene todas las reservas de insumos para una orden de producción específica."""
        try:
            result = self.db.table(self.get_table_name()).select(
                '*, lote_inventario:insumos_inventario(*, insumo:insumos_catalogo(nombre))'
            ).eq('orden_produccion_id', orden_produccion_id).execute()

            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error obteniendo reservas por ID de orden de producción: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}