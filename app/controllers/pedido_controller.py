# app/controllers/pedido_controller.py
import logging
from datetime import date
from app.controllers.base_controller import BaseController
# --- IMPORTACIONES NUEVAS ---
from app.controllers.lote_producto_controller import LoteProductoController
from app.controllers.orden_produccion_controller import OrdenProduccionController
# -------------------------
from app.models.pedido import PedidoModel
from app.models.producto import ProductoModel
from app.schemas.pedido_schema import PedidoSchema
from typing import Dict, Optional
from marshmallow import ValidationError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PedidoController(BaseController):
    """
    Controlador para la lógica de negocio de los Pedidos de Venta.
    """

    def __init__(self):
        super().__init__()
        self.model = PedidoModel()
        self.schema = PedidoSchema()
        self.producto_model = ProductoModel()
        # --- INSTANCIAS NUEVAS ---
        self.lote_producto_controller = LoteProductoController()
        self.orden_produccion_controller = OrdenProduccionController()
        # -----------------------

    def _consolidar_items(self, items_data: list) -> list:
        """
        Consolida una lista de items de pedido, sumando las cantidades de productos duplicados.
        """
        if not items_data:
            return []

        consolidados = {}
        for item in items_data:
            producto_id = item.get('producto_id')
            if not producto_id:
                continue

            try:
                # Las cantidades del formulario vienen como strings.
                cantidad = int(item.get('cantidad', 0))
            except (ValueError, TypeError):
                continue # Ignorar si la cantidad no es un número válido.

            if cantidad <= 0:
                continue # Ignorar items sin cantidad.

            if producto_id in consolidados:
                consolidados[producto_id]['cantidad'] += cantidad
            else:
                consolidados[producto_id] = {
                    'producto_id': producto_id,
                    'cantidad': cantidad
                }

        return list(consolidados.values())

    def obtener_pedidos(self, filtros: Optional[Dict] = None) -> tuple:
        """
        Obtiene una lista de pedidos, aplicando filtros.
        """
        try:
            result = self.model.get_all_with_items(filtros)
            if result.get('success'):
                return self.success_response(data=result.get('data', []))
            else:
                error_msg = result.get('error', 'Error desconocido al obtener pedidos.')
                return self.error_response(error_msg, 500)
        except Exception as e:
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def obtener_pedido_por_id(self, pedido_id: int) -> tuple:
        """
        Obtiene el detalle de un pedido específico con sus items.
        """
        try:
            result = self.model.get_one_with_items(pedido_id)
            if result.get('success'):
                return self.success_response(data=result.get('data'))
            else:
                error_msg = result.get('error', 'Error desconocido.')
                status_code = 404 if "no encontrado" in str(error_msg).lower() else 500
                return self.error_response(error_msg, status_code)
        except Exception as e:
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def crear_pedido_con_items(self, form_data: Dict) -> tuple:
        """
        Valida y crea un nuevo pedido con sus items, verificando el stock previamente.
        """
        try:
            if 'items-TOTAL_FORMS' in form_data:
                form_data.pop('items-TOTAL_FORMS')

            if 'items' in form_data:
                form_data['items'] = self._consolidar_items(form_data['items'])

            validated_data = self.schema.load(form_data)
            items_data = validated_data.pop('items')
            pedido_data = validated_data

            # --- INICIO: Verificación de Stock ---
            logging.info("Iniciando verificación de stock para nuevo pedido...")
            for item in items_data:
                producto_id = item['producto_id']
                cantidad_solicitada = item['cantidad']

                # Obtener nombre del producto para un log más claro
                producto_info = self.producto_model.find_by_id(producto_id, 'id')
                nombre_producto = producto_info['data']['nombre'] if producto_info.get('success') and producto_info.get('data') else f"ID {producto_id}"

                # Consultar stock disponible. Desempaquetamos la tupla (dict, status_code)
                stock_response, _ = self.lote_producto_controller.obtener_stock_producto(producto_id)

                if not stock_response.get('success'):
                    logging.error(f"No se pudo verificar el stock para el producto '{nombre_producto}'. Error: {stock_response.get('error')}")
                    continue

                stock_disponible = stock_response['data']['stock_total']

                if stock_disponible >= cantidad_solicitada:
                    logging.info(f"STOCK SUFICIENTE para '{nombre_producto}': Solicitados: {cantidad_solicitada}, Disponible: {stock_disponible}")
                else:
                    logging.warning(f"STOCK INSUFICIENTE para '{nombre_producto}': Solicitados: {cantidad_solicitada}, Disponible: {stock_disponible}")
            # --- FIN: Verificación de Stock ---

            if 'estado' not in pedido_data:
                pedido_data['estado'] = 'PENDIENTE'
            result = self.model.create_with_items(pedido_data, items_data)

            if result.get('success'):
                return self.success_response(data=result.get('data'), message="Pedido creado con éxito.", status_code=201)
            else:
                return self.error_response(result.get('error', 'No se pudo crear el pedido.'), 400)

        except ValidationError as e:
            if 'items' in e.messages and isinstance(e.messages['items'], list):
                error_message = e.messages['items'][0]
            else:
                error_message = "Por favor, revise los campos del formulario. Se encontraron errores de validación."

            return self.error_response(error_message, 400)
        except Exception as e:
            logging.error(f"Error interno en crear_pedido_con_items: {e}", exc_info=True)
            # La variable 'e' ya contiene el error original.
            return self.error_response(f'Error interno: {str(e)}', 500)


    def aprobar_pedido(self, pedido_id: int, usuario_id: int) -> tuple:
        """
        Aprueba un pedido, reserva stock, actualiza el estado de los ítems
        y genera OPs para el faltante.
        """
        try:
            # 1. Obtener pedido y verificar estado (sin cambios)
            pedido_resp, _ = self.obtener_pedido_por_id(pedido_id)
            if not pedido_resp.get('success'):
                return self.error_response("Pedido no encontrado.", 404)
            pedido_actual = pedido_resp['data']
            if pedido_actual.get('estado') == 'APROBADO':
                return self.error_response("Este pedido ya ha sido aprobado.", 400)

            # 2. Cambiar estado del pedido a APROBADO (sin cambios)
            self.model.cambiar_estado(pedido_id, 'APROBADO')

            items_del_pedido = pedido_actual.get('items', [])
            ordenes_creadas = []

            for item in items_del_pedido:
                # 3. Reservar stock (sin cambios)
                reserva_result = self.lote_producto_controller.reservar_stock_para_item(
                    pedido_id=pedido_id,
                    pedido_item_id=item['id'],
                    producto_id=item['producto_id'],
                    cantidad_necesaria=item['cantidad'],
                    usuario_id=usuario_id
                )
                if not reserva_result.get('success'):
                    logging.error(f"Falló la reserva para el pedido {pedido_id}. Motivo: {reserva_result.get('error')}")
                    continue

                cantidad_faltante = reserva_result['data']['cantidad_faltante']

                # --- INICIO DE LA LÓGICA DE ACTUALIZACIÓN DE ÍTEM ---
                if cantidad_faltante > 0:
                    # 4a. Si falta stock, crear OP y actualizar ítem a 'EN_PRODUCCION'
                    datos_orden = {
                        'producto_id': item['producto_id'],
                        'cantidad': cantidad_faltante,
                        'fecha_planificada': date.today().isoformat()
                    }
                    resultado_op = self.orden_produccion_controller.crear_orden(datos_orden, usuario_id)

                    if resultado_op.get('success'):
                        orden_creada = resultado_op['data']
                        ordenes_creadas.append(orden_creada)
                        # Asociamos el ítem con la nueva OP y actualizamos su estado
                        self.model.update_item(item['id'], {
                            'estado': 'EN_PRODUCCION',
                            'orden_produccion_id': orden_creada['id']
                        })
                    else:
                        logging.error(f"No se pudo crear la OP para el producto {item['producto_id']}. Error: {resultado_op.get('error')}")
                else:
                    # 4b. Si el stock fue suficiente, actualizar ítem a 'ALISTADO'
                    self.model.update_item(item['id'], {'estado': 'ALISTADO'})
                # --- FIN DE LA LÓGICA DE ACTUALIZACIÓN DE ÍTEM ---

            # 5. Devolver respuesta (sin cambios)
            msg = "Pedido aprobado con éxito."
            # ... (resto del método sin cambios)
            return self.success_response(data={'ordenes_creadas': ordenes_creadas}, message=msg)

        except Exception as e:
            logging.error(f"Error en aprobar_pedido: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def actualizar_pedido_con_items(self, pedido_id: int, form_data: Dict) -> tuple:
        """
        Valida y actualiza un pedido existente y sus items.
        """
        try:
            if 'items-TOTAL_FORMS' in form_data:
                form_data.pop('items-TOTAL_FORMS')
            if 'items' in form_data:
                form_data['items'] = self._consolidar_items(form_data['items'])
            validated_data = self.schema.load(form_data)
            items_data = validated_data.pop('items')
            pedido_data = validated_data
            result = self.model.update_with_items(pedido_id, pedido_data, items_data)

            if result.get('success'):
                return self.success_response(data=result.get('data'), message="Pedido actualizado con éxito.")
            else:
                return self.error_response(result.get('error', 'No se pudo actualizar el pedido.'), 400)

        except ValidationError as e:
            if 'items' in e.messages and isinstance(e.messages['items'], list):
                error_message = e.messages['items'][0]
            else:
                error_message = "Por favor, revise los campos del formulario. Se encontraron errores de validación."

            return self.error_response(error_message, 400)
        except Exception as e:
            return self.error_response(f'Error interno: {str(e)}', 500)

    def cancelar_pedido(self, pedido_id: int) -> tuple:
        """
        Cambia el estado de un pedido a 'CANCELADO'.
        """
        try:
            # Verificar que el pedido existe y obtener su estado actual.
            pedido_existente_resp = self.model.get_one_with_items(pedido_id)
            if not pedido_existente_resp.get('success'):
                 return self.error_response(f"Pedido con ID {pedido_id} no encontrado.", 404)

            pedido_actual = pedido_existente_resp.get('data')
            if pedido_actual and pedido_actual.get('estado') == 'CANCELADO':
                return self.error_response("Este pedido ya ha sido cancelado y no puede ser modificado.", 400)

            result = self.model.cambiar_estado(pedido_id, 'CANCELADO')
            if result.get('success'):
                return self.success_response(message="Pedido cancelado con éxito.")
            else:
                return self.error_response(result.get('error', 'Error al cancelar el pedido.'), 500)
        except Exception as e:
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_datos_para_formulario(self) -> tuple:
        """
        Obtiene los datos necesarios para popular los menús desplegables
        en el formulario de creación/edición de pedidos.
        """
        try:
            productos_result = self.producto_model.find_all(order_by='nombre')
            if productos_result.get('success'):
                productos = productos_result.get('data', [])
                return self.success_response(data={'productos': productos})
            else:
                return self.error_response("Error al obtener la lista de productos.", 500)
        except Exception as e:
            return self.error_response(f'Error interno obteniendo datos para el formulario: {str(e)}', 500)
