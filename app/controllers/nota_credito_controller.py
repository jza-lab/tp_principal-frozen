from app.controllers.base_controller import BaseController
from app.models.nota_credito import NotaCreditoModel
from app.models.alerta_riesgo import AlertaRiesgoModel
from app.models.pedido import PedidoModel
from app.schemas.nota_credito_schema import NotaCreditoSchema
from marshmallow import ValidationError
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class NotaCreditoController(BaseController):
    def __init__(self):
        super().__init__()
        self.model = NotaCreditoModel()
        self.schema = NotaCreditoSchema()
        self.alerta_model = AlertaRiesgoModel()
        self.pedido_model = PedidoModel()

    def crear_notas_credito_para_pedidos_afectados(self, alerta_id, pedidos_ids, motivo, detalle):
        """
        Lógica de negocio para crear una o más notas de crédito a partir de una alerta.
        """
        lotes_producto_afectados = self.alerta_model.obtener_lotes_producto_afectados_por_alerta(alerta_id)
        lotes_afectados_ids = {lp['lote_producto_id'] for lp in lotes_producto_afectados}

        nc_creadas_count = 0
        errors = []

        for pedido_id in pedidos_ids:
            try:
                pedido_res = self.pedido_model.find_by_id(int(pedido_id), id_field='id')
                if not pedido_res.get('success') or not pedido_res.get('data'):
                    errors.append(f"Pedido ID {pedido_id} no encontrado.")
                    continue
                
                pedido = pedido_res.get('data')[0]
                items_pedido = self.pedido_model.get_items(pedido['id'])

                # Calcular el monto a acreditar
                monto_total_afectado = Decimal(0.0)
                items_afectados_detalle = []

                for item in items_pedido:
                    reservas_item = self.pedido_model.get_reservas_for_item(item['id'])
                    for reserva in reservas_item:
                        if reserva['lote_producto_id'] in lotes_afectados_ids:
                            # Este item está afectado. Añadir su valor a la NC.
                            precio_unitario = Decimal(item.get('precio_unitario', '0.0'))
                            cantidad_afectada = Decimal(reserva.get('cantidad', '0.0'))
                            monto_total_afectado += precio_unitario * cantidad_afectada
                            items_afectados_detalle.append(f"Producto ID {item['producto_id']} (Lote ID {reserva['lote_producto_id']})")
                
                if monto_total_afectado <= 0:
                    errors.append(f"Pedido ID {pedido_id} no tiene items visiblemente afectados para acreditar.")
                    continue

                # Crear la Nota de Crédito
                nc_data = {
                    'pedido_origen_id': pedido['id'],
                    'cliente_id': pedido['cliente_id'],
                    'monto': str(monto_total_afectado),
                    'motivo': f"Alerta de Riesgo: {motivo}",
                    'detalle': f"Afectación por alerta. Detalles: {detalle}. Items afectados: {', '.join(items_afectados_detalle)}",
                    'alerta_riesgo_id': alerta_id
                }

                validated_data = self.schema.load(nc_data)
                self.model.create(validated_data)
                nc_creadas_count += 1

            except Exception as e:
                logger.error(f"Error procesando NC para Pedido ID {pedido_id}: {e}", exc_info=True)
                errors.append(f"Error interno al procesar Pedido ID {pedido_id}.")

        if nc_creadas_count > 0:
            return {"success": True, "count": nc_creadas_count, "errors": errors}
        else:
            return {"success": False, "errors": errors}

    def obtener_detalle_nc_por_alerta(self, alerta_id):
        """
        Obtiene los detalles de todas las NC generadas por una alerta específica.
        """
        try:
            ncs_res = self.model.find_by('alerta_riesgo_id', alerta_id)
            if not ncs_res.get('success'):
                return {"success": False, "error": "No se encontraron notas de crédito para esta alerta."}, 404
            
            return {"success": True, "data": ncs_res.get('data')}, 200
        except Exception as e:
            logger.error(f"Error al obtener detalle de NCs por alerta {alerta_id}: {e}", exc_info=True)
            return {"success": False, "error": "Error interno del servidor."}, 500
