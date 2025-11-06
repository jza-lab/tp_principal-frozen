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
        self.pedido_model = PedidoModel()

    def crear_notas_credito_para_pedidos_afectados(self, alerta_id, pedidos_ids, motivo, detalle, lotes_producto_afectados_ids):
        """
        Lógica de negocio para crear una o más notas de crédito a partir de una alerta.
        """

        nc_creadas_count = 0
        errors = []
        avisos = []

        for pedido_id in pedidos_ids:
            try:
                pedido_res = self.pedido_model.get_one_with_items(int(pedido_id))
                if not pedido_res.get('success') or not pedido_res.get('data'):
                    errors.append(f"Pedido ID {pedido_id} no encontrado.")
                    continue

                pedido = pedido_res.get('data')
                items_pedido = pedido.get('items', [])

                # Calcular el monto a acreditar
                monto_total_afectado = Decimal(0.0)
                pedido_total = Decimal(pedido_res['data'].get('monto_total', '0.0'))
                items_afectados_detalle = []

                for item in items_pedido:
                    precio_unitario = Decimal(item.get('precio_unitario', '0.0'))
                    cantidad_item = Decimal(item.get('cantidad', '0.0'))
                    pedido_total += precio_unitario * cantidad_item

                    reservas_item = self.pedido_model.get_reservas_for_item(item['id'])
                    for reserva in reservas_item:
                        if reserva['lote_producto_id'] in lotes_producto_afectados_ids:
                            cantidad_afectada = Decimal(reserva.get('cantidad_reservada', '0.0'))
                            monto_total_afectado += precio_unitario * cantidad_afectada
                            items_afectados_detalle.append(f"Producto ID {item['producto_id']} (Lote ID {reserva['lote_producto_id']})")
                
                if monto_total_afectado <= 0:
                    errors.append(f"Pedido ID {pedido['codigo']} no tiene items visiblemente afectados para acreditar.")
                    continue

                # Comprobar si la NC cubre el total
                # Usar una pequeña tolerancia para la comparación de decimales
                if monto_total_afectado >= pedido_total - Decimal('0.01'):
                    avisos.append(f"La Nota de Crédito para el Pedido {pedido['codigo']} cubre el monto total.")

                nc_data = {
                    'pedido_origen_id': pedido['id'],
                    'cliente_id': pedido['id_cliente'],
                    'monto': str(monto_total_afectado),
                    'motivo': f"Alerta de Riesgo: {motivo}",
                    'detalle': f"Afectación por alerta. Detalles: {detalle}. Items afectados: {', '.join(items_afectados_detalle)}",
                    'alerta_riesgo_id': alerta_id
                }

                validated_data = self.schema.load(nc_data)
                create_res = self.model.create(validated_data)
                if create_res.get('success'):
                    nc_creadas_count += 1
                else:
                    errors.append(f"No se pudo guardar la NC para el pedido {pedido['codigo']}.")


            except Exception as e:
                logger.error(f"Error procesando NC para Pedido ID {pedido_id}: {e}", exc_info=True)
                errors.append(f"Error interno al procesar Pedido ID {pedido_id}.")

        if nc_creadas_count > 0:
            return {"success": True, "count": nc_creadas_count, "errors": errors, "avisos": avisos}
        else:
            return {"success": False, "errors": errors, "avisos": avisos}

    def obtener_detalle_nc_por_alerta(self, alerta_id):
        """
        Obtiene los detalles de todas las NC generadas por una alerta específica.
        """
        try:
            ncs_res = self.model.find_by('alerta_riesgo_id', alerta_id)
            if not ncs_res.get('success') or not ncs_res.get('data'):
                return {"success": False, "error": "No se encontraron notas de crédito para esta alerta."}, 404
            
            ncs_data = ncs_res.get('data', [])
            for nc in ncs_data:
                items = self.model.get_items_by_nc_id(nc['id'])
                # Formatear para la vista
                nc['items'] = [
                    {
                        'producto_nombre': item.get('productos', {}).get('nombre', 'N/A'),
                        'lote_numero': item.get('lotes_productos', {}).get('numero_lote', 'N/A'),
                        'cantidad': item.get('cantidad'),
                        'precio_unitario': item.get('precio_unitario'),
                        'subtotal': item.get('subtotal')
                    } for item in items
                ]
            
            return {"success": True, "data": ncs_data}, 200
        except Exception as e:
            logger.error(f"Error al obtener detalle de NCs por alerta {alerta_id}: {e}", exc_info=True)
            return {"success": False, "error": "Error interno del servidor."}, 500

    def obtener_detalles_para_pdf(self, nc_id):
        """
        Obtiene todos los detalles de una NC específica para generar un PDF.
        """
        try:
            nc_res = self.model.find_by_id(nc_id)
            if not nc_res.get('success') or not nc_res.get('data'):
                return {"success": False, "error": "Nota de Crédito no encontrada."}, 404
            
            nc_data = nc_res.get('data')
            items = self.model.get_items_by_nc_id(nc_data['id'])
            
            # Necesitamos más detalles del cliente y pedido
            pedido_info = self.pedido_model.find_by_id(nc_data['pedido_origen_id']).get('data', {})
            cliente_info = self.db.table('clientes').select('razon_social, cuit').eq('id', nc_data['cliente_id']).single().execute().data or {}

            nc_data['pedido_codigo'] = pedido_info.get('codigo', 'N/A')
            nc_data['cliente_razon_social'] = cliente_info.get('razon_social', 'N/A')
            nc_data['cliente_cuit'] = cliente_info.get('cuit', 'N/A')
            
            nc_data['items'] = [
                {
                    'producto_nombre': item.get('productos', {}).get('nombre', 'N/A'),
                    'lote_numero': item.get('lotes_productos', {}).get('numero_lote', 'N/A'),
                    'cantidad': item.get('cantidad'),
                    'precio_unitario': item.get('precio_unitario'),
                    'subtotal': item.get('subtotal')
                } for item in items
            ]
            return {"success": True, "data": nc_data}, 200

        except Exception as e:
            logger.error(f"Error al obtener detalles de NC {nc_id} para PDF: {e}", exc_info=True)
            return {"success": False, "error": "Error interno del servidor."}, 500