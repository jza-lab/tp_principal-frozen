from flask import jsonify
from app.controllers.base_controller import BaseController
from app.models.reserva_producto import ReservaProductoModel
from app.models.reserva_insumo import ReservaInsumoModel
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ReservasController(BaseController):
    def __init__(self):
        """
        Constructor que inicializa los modelos necesarios.
        """
        super().__init__()
        self.reserva_producto_model = ReservaProductoModel()
        self.reserva_insumo_model = ReservaInsumoModel()

    def obtener_trazabilidad_reservas(self) -> tuple:
        """
        Obtiene y unifica las reservas de productos e insumos en una sola lista cronológica.
        """
        try:
            # 1. Obtener reservas de productos terminados (para Pedidos de Venta)
            reservas_productos_res = self.reserva_producto_model.get_all_with_details()

            # 2. Obtener reservas de insumos (para Órdenes de Producción)
            reservas_insumos_res = self.reserva_insumo_model.get_all_with_details()

            reservas_unificadas = []

            # 3. Procesar y unificar las reservas de productos
            if reservas_productos_res.get('success'):
                for r in reservas_productos_res['data']:
                    reservas_unificadas.append({
                        'tipo': 'PRODUCTO',
                        'fecha': datetime.fromisoformat(r.get('fecha_reserva')) if r.get('fecha_reserva') else None,
                        'item_nombre': r.get('producto_nombre'),
                        'cantidad': r.get('cantidad_reservada'),
                        'lote': r.get('lote_producto_codigo'),
                        'origen': f"Pedido Venta PED-{r.get('pedido_id')}",
                        'origen_url': f"/orden-venta/{r.get('pedido_id')}/detalle",
                        'estado': r.get('estado')
                    })

            # 4. Procesar y unificar las reservas de insumos
            if reservas_insumos_res.get('success'):
                for r in reservas_insumos_res['data']:
                    reservas_unificadas.append({
                        'tipo': 'INSUMO',
                        'fecha': datetime.fromisoformat(r.get('created_at')) if r.get('created_at') else None,
                        'item_nombre': r.get('insumo_nombre'),
                        'cantidad': r.get('cantidad_reservada'),
                        'lote': r.get('lote_inventario_codigo'),
                        'origen': f"Orden Prod. {r.get('orden_produccion_codigo')}",
                        'origen_url': f"/ordenes/{r.get('orden_produccion_id')}/detalle",
                        'estado': r.get('estado')
                    })

            # 5. Ordenar la lista final por fecha, de más reciente a más antigua
            reservas_unificadas.sort(key=lambda x: x['fecha'] or datetime.min, reverse=True)

            return self.success_response(data=reservas_unificadas)

        except Exception as e:
            logger.error(f"Error obteniendo trazabilidad de reservas: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)