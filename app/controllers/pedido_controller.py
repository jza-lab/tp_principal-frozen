import logging
from datetime import datetime, date, timedelta

from flask import jsonify
from app.controllers.base_controller import BaseController
# --- IMPORTACIONES NUEVAS ---
from app.controllers.lote_producto_controller import LoteProductoController
from app.models.receta import RecetaModel

# -------------------------
from app.models.cliente import ClienteModel
from app.models.pedido import PedidoModel
from app.models.producto import ProductoModel
from app.models.direccion import DireccionModel
from app.schemas.direccion_schema import DireccionSchema
from app.schemas.cliente_schema import ClienteSchema
from app.schemas.pedido_schema import PedidoSchema
from typing import Dict, Optional
from marshmallow import ValidationError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

class PedidoController(BaseController):
    """
    Controlador para la lógica de negocio de los Pedidos de Venta.
    """

    def __init__(self):
        super().__init__()
        self.model = PedidoModel()
        self.schema = PedidoSchema()
        self.producto_model = ProductoModel()
        self.cliente_model = ClienteModel()
        self.direccion_model= DireccionModel()
        self.dcliente_schema = ClienteSchema()
        self.direccion_schema= DireccionSchema()
        self.receta_model = RecetaModel()
        # --- INSTANCIAS NUEVAS ---
        self.lote_producto_controller = LoteProductoController()
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

    # Reemplaza el método obtener_pedido_por_id existente
    def obtener_pedido_por_id(self, pedido_id: int) -> tuple:
        """
        Obtiene el detalle de un pedido específico con sus items
        Y AÑADE información sobre el estado de las OPs vinculadas.
        """
        try:
            # --- CAMBIO: Llamar al nuevo método del modelo ---
            result = self.model.get_one_with_items_and_op_status(pedido_id)
            # -----------------------------------------------

            if result.get('success'):
                return self.success_response(data=result.get('data'))
            else:
                error_msg = result.get('error', 'Error desconocido.')
                status_code = 404 if "no encontrado" in str(error_msg).lower() else 500
                return self.error_response(error_msg, status_code)
        except Exception as e:
            # Mantener el log de error
            logger.error(f"Error interno obteniendo detalle de pedido {pedido_id}: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def crear_pedido_con_items(self, form_data: Dict, usuario_id: int) -> tuple:
        """
        Valida y crea un nuevo pedido con sus items, verificando el stock previamente.
        Si todo el stock está disponible, lo marca como 'COMPLETADO' y despacha el stock.
        """
        try:
            if 'items-TOTAL_FORMS' in form_data:
                form_data.pop('items-TOTAL_FORMS')

            if 'items' in form_data:
                form_data['items'] = self._consolidar_items(form_data['items'])

            direccion_id = None
            usar_alternativa = form_data.get('usar_direccion_alternativa')

            if usar_alternativa:
                # El usuario quiere usar una dirección temporal, validamos que la haya provisto.
                direccion_payload = form_data.get('direccion_entrega', {})
                direccion_data = {
                    'calle': direccion_payload.get('calle'), 'altura': direccion_payload.get('altura'),
                    'provincia': direccion_payload.get('provincia'), 'localidad': direccion_payload.get('localidad'),
                    'piso': direccion_payload.get('piso'), 'depto': direccion_payload.get('depto'),
                    'codigo_postal': direccion_payload.get('codigo_postal')
                }
                if not all(direccion_data.get(k) for k in ['calle', 'altura', 'localidad', 'provincia']):
                    return self.error_response("Debe completar todos los campos de la dirección de entrega alternativa.", 400)

                direccion_id = self._get_or_create_direccion(direccion_data)
                if not direccion_id:
                    return self.error_response("No se pudo procesar la dirección de entrega alternativa.", 500)
            else:
                # El usuario quiere usar la dirección principal del cliente, verificamos que exista.
                id_cliente = form_data.get('id_cliente')
                if not id_cliente:
                    return self.error_response("No se ha especificado un cliente.", 400)

                cliente_result = self.cliente_model.find_by_id(id_cliente, 'id')
                if not cliente_result.get('success') or not cliente_result.get('data'):
                    return self.error_response("Cliente no encontrado.", 404)

                direccion_id = cliente_result['data'].get('direccion_id')

                if not direccion_id:
                    return self.error_response("El cliente no tiene una dirección principal. Por favor, marque la opción 'Enviar a una dirección de entrega distinta' y complete los campos.", 400)

            # Añadimos el id de la dirección al payload principal para la validación/creación.
            form_data['id_direccion_entrega'] = direccion_id
            form_data.pop('direccion_entrega', None)
            form_data.pop('usar_direccion_alternativa', None)

            # FIX: Se elimina el intento de añadir el ID del creador al modelo `pedidos`
            # La tabla `pedidos` no tiene esta columna, causando el error PGRST204.

            items_data = form_data.pop('items')
            pedido_data = form_data

            # --- NUEVA LÓGICA: Verificación de Stock (Dry Run) y determinación de estado ---
            all_in_stock = True # Indicador para la nueva lógica

            for item in items_data:
                producto_id = item['producto_id']
                cantidad_solicitada = item['cantidad']

                producto_info = self.producto_model.find_by_id(producto_id, 'id')
                nombre_producto = producto_info['data']['nombre'] if producto_info.get('success') and producto_info.get('data') else f"ID {producto_id}"

                stock_response, _ = self.lote_producto_controller.obtener_stock_producto(producto_id)

                if not stock_response.get('success'):
                    logging.error(f"No se pudo verificar el stock para el producto '{nombre_producto}'. Error: {stock_response.get('error')}")
                    all_in_stock = False # Si no se puede verificar, asumimos que no hay stock
                    continue

                stock_disponible = stock_response['data']['stock_total']

                if stock_disponible >= cantidad_solicitada:
                    logging.info(f"STOCK SUFICIENTE para '{nombre_producto}': Solicitados: {cantidad_solicitada}, Disponible: {stock_disponible}")
                else:
                    logging.warning(f"STOCK INSUFICIENTE para '{nombre_producto}': Solicitados: {cantidad_solicitada}, Disponible: {stock_disponible}")
                    all_in_stock = False # Marcar como insuficiente

            # Definir el estado inicial basado en la verificación
            if all_in_stock:
                # Si todo está en stock, el estado inicial es LISTO_PARA_ENTREGA
                pedido_data['estado'] = 'LISTO_PARA_ENTREGA'
                # Y cada item se marca como ALISTADO, ya que el stock está disponible.
                for item in items_data:
                    item['estado'] = 'ALISTADO'
                logging.info("Todo el stock disponible. El pedido se creará en estado LISTO_PARA_ENTREGA y los items como ALISTADO.")
            elif 'estado' not in pedido_data:
                # Si falta stock, el estado inicial es PENDIENTE
                pedido_data['estado'] = 'PENDIENTE'
                logging.warning("Stock insuficiente para uno o más items. El pedido se creará en estado PENDIENTE.")


            result = self.model.create_with_items(pedido_data, items_data)

            if result.get('success'):
                nuevo_pedido = result.get('data')
                message = "Pedido creado con éxito."
                if all_in_stock:
                    message = "Stock disponible para todos los productos. El pedido se ha creado en estado 'LISTO PARA ENTREGAR'."
                return self.success_response(data=nuevo_pedido, message=message, status_code=201)
            else:
                return self.error_response(result.get('error', 'No se pudo crear el pedido.'), 400)

        except ValidationError as e:
            return self.error_response(str(e.messages), 400)

        except Exception as e:
            logging.error(f"Error interno en crear_pedido_con_items: {e}", exc_info=True)
            return self.error_response(f'Error interno: {str(e)}', 500)


    def iniciar_proceso_pedido(self, pedido_id: int, usuario_id: int) -> tuple:
        """
        Pasa un pedido de 'PLANIFICACION' a 'EN PROCESO'.
        Crea las Órdenes de Producción (OPs) necesarias en este paso.
        """
        try:
            # 1. Validar estado y datos
            pedido_resp, _ = self.obtener_pedido_por_id(pedido_id)
            if not pedido_resp.get('success'):
                return self.error_response("Pedido no encontrado.", 404)

            pedido_actual = pedido_resp['data']
            if pedido_actual.get('estado') != 'PENDIENTE':
                return self.error_response("Solo los pedidos en 'PENDIENTE' pueden pasar a 'EN PROCESO'.", 400)

            # Extraer la fecha requerida del pedido
            fecha_requerido_pedido = pedido_actual.get('fecha_requerido')

            # 2. Lógica de creación de OPs
            items_del_pedido = pedido_actual.get('items', [])
            ordenes_creadas = []
            for item in items_del_pedido:
                # Solo crear OP si el producto tiene receta
                receta_result = self.receta_model.find_all({'producto_id': item['producto_id'], 'activa': True}, limit=1)
                if receta_result.get('success') and receta_result.get('data'):
                    datos_op = {
                        'producto_id': item['producto_id'],
                        'cantidad': item['cantidad'],
                        'fecha_planificada': date.today().isoformat(),
                        'prioridad': 'NORMAL',
                        # --- AÑADIR FECHA META AQUÍ ---
                        'fecha_meta': fecha_requerido_pedido
                        # ---------------------------------
                    }
                    from app.controllers.orden_produccion_controller import OrdenProduccionController
                    orden_produccion_controller = OrdenProduccionController()
                    # --- FIX: Manejo defensivo de la respuesta ---
                    resultado_op_tuple = orden_produccion_controller.crear_orden(datos_op, usuario_id)
                    resultado_op = resultado_op_tuple[0] if isinstance(resultado_op_tuple, tuple) else resultado_op_tuple

                    if resultado_op.get('success'):
                        orden_creada = resultado_op.get('data', {})
                        ordenes_creadas.append(orden_creada)
                        self.model.update_item(item['id'], {'estado': 'EN_PRODUCCION', 'orden_produccion_id': orden_creada.get('id')})
                    else:
                        logging.error(f"No se pudo crear la OP para el producto {item['producto_id']}. Error: {resultado_op.get('error')}")
                else:
                    # Si no hay receta, el item se considera listo para el siguiente paso.
                    self.model.update_item(item['id'], {'estado': 'ALISTADO'})

            # 3. Actualizar estado del pedido
            self.model.actualizar_estado_agregado(pedido_id) # Esto lo pasará a EN_PROCESO si se creó alguna OP

            msg = f"Pedido enviado a producción. Se generaron {len(ordenes_creadas)} Órdenes de Producción."
            return self.success_response(data={'ordenes_creadas': ordenes_creadas}, message=msg)

        except Exception as e:
            logging.error(f"Error en iniciar_proceso_pedido: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def _get_or_create_direccion(self, direccion_data: Dict) -> Optional[int]:
        """
        Busca una dirección por sus componentes. Si no existe, la crea.
        Devuelve el ID de la dirección.
        """
        try:
            # Normalizar datos para la búsqueda
            calle = direccion_data.get('calle')
            altura = direccion_data.get('altura')
            localidad = direccion_data.get('localidad')
            provincia = direccion_data.get('provincia')
            piso = direccion_data.get('piso')
            depto = direccion_data.get('depto')

            # Buscar si la dirección ya existe
            existing_address = self.direccion_model.find_by_full_address(
                calle, altura, piso, depto, localidad, provincia
            )

            if existing_address.get('success'):
                return existing_address['data']['id']
            else:
                # Si no existe, crear una nueva
                # Validar que los campos requeridos no sean None
                required_fields = {
                    'calle': calle, 'altura': altura, 'localidad': localidad, 'provincia': provincia,
                    'codigo_postal': direccion_data.get('codigo_postal')
                }
                if not all(required_fields.values()):
                    logging.error(f"Faltan datos para crear la dirección: {required_fields}")
                    return None

                new_address_res = self.direccion_model.create(direccion_data)
                if new_address_res.get('success'):
                    return new_address_res['data']['id']
                else:
                    logging.error(f"Error al crear la dirección: {new_address_res.get('error')}")
                    return None
        except Exception as e:
            logging.error(f"Error en _get_or_create_direccion: {e}", exc_info=True)
            return None

    def _actualizar_direccion(self, direccion_id: int, direccion_data: Dict) -> bool:
        """
        Actualiza una dirección existente. Devuelve True si fue exitoso.
        """
        try:
            update_res = self.direccion_model.update(direccion_id, direccion_data)
            return update_res.get('success', False)
        except Exception as e:
            logging.error(f"Error en _actualizar_direccion: {e}", exc_info=True)
            return False

    def actualizar_pedido_con_items(self, pedido_id: int, form_data: Dict, estado_original: str) -> tuple:
        """
        Valida y actualiza un pedido y sus items. Si el pedido estaba 'EN_PROCESO',
        crea OPs para los nuevos items sin stock.
        """
        try:
            # Obtener el estado y datos del pedido antes de cualquier cambio.
            pedido_actual_resp, _ = self.obtener_pedido_por_id(pedido_id)
            if not pedido_actual_resp.get('success'):
                return self.error_response("No se pudo cargar el pedido original para actualizar.", 404)
            pedido_actual = pedido_actual_resp.get('data')

            # Consolidar y preparar datos
            if 'items' in form_data:
                form_data['items'] = self._consolidar_items(form_data['items'])
            items_data = form_data.pop('items', [])
            pedido_data = form_data

            direccion_id = None
            usar_alternativa = form_data.get('usar_direccion_alternativa')

            if usar_alternativa:
                # El usuario quiere usar una dirección temporal, validamos que la haya provisto.
                direccion_payload = form_data.get('direccion_entrega', {})
                direccion_data = {
                    'calle': direccion_payload.get('calle'), 'altura': direccion_payload.get('altura'),
                    'provincia': direccion_payload.get('provincia'), 'localidad': direccion_payload.get('localidad'),
                    'piso': direccion_payload.get('piso'), 'depto': direccion_payload.get('depto'),
                    'codigo_postal': direccion_payload.get('codigo_postal')
                }
                if not all(direccion_data.get(k) for k in ['calle', 'altura', 'localidad', 'provincia', 'codigo_postal']):
                    return self.error_response("Debe completar todos los campos de la dirección de entrega alternativa.", 400)

                direccion_id = self._get_or_create_direccion(direccion_data)
                if not direccion_id:
                    return self.error_response("No se pudo procesar la dirección de entrega alternativa.", 500)
            else:
                # El usuario quiere usar la dirección principal del cliente, verificamos que exista.
                id_cliente = form_data.get('id_cliente')
                if not id_cliente:
                    return self.error_response("No se ha especificado un cliente.", 400)

                cliente_result = self.cliente_model.find_by_id(id_cliente, 'id')
                if not cliente_result.get('success') or not cliente_result.get('data'):
                    return self.error_response("Cliente no encontrado.", 404)

                direccion_id = cliente_result['data'].get('direccion_id')

                if not direccion_id:
                    return self.error_response("El cliente no tiene una dirección principal. Por favor, marque la opción 'Enviar a una dirección de entrega distinta' y complete los campos.", 400)

            pedido_data['id_direccion_entrega'] = direccion_id
            pedido_data.pop('direccion_entrega', None)
            pedido_data.pop('usar_direccion_alternativa', None)

            # Actualizar el pedido y obtener los items nuevos
            result = self.model.update_with_items(pedido_id, pedido_data, items_data)

            if not result.get('success'):
                return self.error_response(result.get('error', 'No se pudo actualizar el pedido.'), 400)

            # --- Lógica para crear OP si el estado era 'EN_PROCESO' ---
            if estado_original == 'EN_PROCESO':
                nuevos_items = result.get('data', {}).get('nuevos_items', [])
                if nuevos_items:
                    # Necesitamos el ID del usuario para crear la OP
                    from flask import session
                    usuario_id = session.get('usuario_id')
                    if not usuario_id:
                        return self.error_response("Sesión de usuario no encontrada para crear OP.", 401)

                    for item in nuevos_items:
                        producto_id = item['producto_id']
                        cantidad_solicitada = item['cantidad']

                        # 1. Verificar si tiene receta
                        receta_result = self.receta_model.find_all({'producto_id': producto_id, 'activa': True}, limit=1)
                        if not receta_result.get('success') or not receta_result.get('data'):
                            logging.warning(f"Nuevo item (ID: {item['id']}) del producto {producto_id} no tiene receta activa. No se generará OP.")
                            continue # Pasar al siguiente item

                        # 2. Verificar stock
                        stock_response, _ = self.lote_producto_controller.obtener_stock_producto(producto_id)
                        stock_disponible = stock_response.get('data', {}).get('stock_total', 0)

                        # Extraer la fecha requerida del pedido
                        fecha_requerido_pedido = pedido_actual.get('fecha_requerido')

                        if cantidad_solicitada > stock_disponible:
                            cantidad_a_producir = cantidad_solicitada - stock_disponible
                            logging.info(f"Stock insuficiente para nuevo item. Solicitado: {cantidad_solicitada}, Disponible: {stock_disponible}. Se creará OP por {cantidad_a_producir}.")

                            # 3. Crear OP
                            datos_orden = {
                                'producto_id': producto_id,
                                'cantidad': cantidad_a_producir,
                                'fecha_planificada': date.today().isoformat(),
                                'prioridad': 'NORMAL',
                                # --- AÑADIR FECHA META AQUÍ ---
                                'fecha_meta': fecha_requerido_pedido
                                # ---------------------------------
                            }
                            resultado_op, _ = self.orden_produccion_controller.crear_orden(datos_orden, usuario_id)

                            if resultado_op.get('success'):
                                orden_creada = resultado_op.get('data', {})
                                # 4. Actualizar el item del pedido
                                self.model.update_item(item['id'], {
                                    'estado': 'EN_PRODUCCION',
                                    'orden_produccion_id': orden_creada.get('id')
                                })
                                logging.info(f"OP {orden_creada.get('id')} creada para el item {item['id']}.")
                            else:
                                logging.error(f"No se pudo crear la OP para el nuevo item {item['id']}. Error: {resultado_op.get('error')}")

            # Actualizar el estado general del pedido después de los cambios
            self.model.actualizar_estado_agregado(pedido_id)

            return self.success_response(data=result.get('data'), message="Pedido actualizado con éxito.")

        except ValidationError as e:
            if 'items' in e.messages and isinstance(e.messages['items'], list):
                error_message = e.messages['items'][0]
            else:
                error_message = "Por favor, revise los campos del formulario. Se encontraron errores de validación."

            return self.error_response(error_message, 400)
        except Exception as e:
            return self.error_response(f'Error interno: {str(e)}', 500)

    def cambiar_estado_pedido(self, pedido_id: int, nuevo_estado: str) -> tuple:
        """
        Cambia el estado de un pedido a un nuevo estado especificado.
        Realiza validaciones básicas sobre la transición de estado.
        """
        logger.info(f"Intento de cambiar estado del pedido {pedido_id} a '{nuevo_estado}'")
        try:
            # Validar que el nuevo estado sea uno de los conocidos (opcional pero recomendado)
            from app.utils.estados import OV_MAP_STRING_TO_INT
            if nuevo_estado not in OV_MAP_STRING_TO_INT:
                return self.error_response(f"Estado '{nuevo_estado}' no es válido.", 400)

            # Verificar que el pedido existe
            pedido_existente_resp = self.model.find_by_id(pedido_id, 'id')
            if not pedido_existente_resp.get('success'):
                return self.error_response(f"Pedido con ID {pedido_id} no encontrado.", 404)

            # Lógica de transición (Aquí se pueden añadir reglas más complejas)
            # Por ahora, simplemente cambiamos el estado.
            result = self.model.cambiar_estado(pedido_id, nuevo_estado)
            if result.get('success'):
                logger.info(f"Pedido {pedido_id} cambiado a estado '{nuevo_estado}' con éxito.")
                return self.success_response(message=f"Pedido actualizado al estado '{nuevo_estado}'.")
            else:
                logger.error(f"Error al cambiar estado del pedido {pedido_id}: {result.get('error')}")
                return self.error_response(result.get('error', 'Error al actualizar el estado del pedido.'), 500)
        except Exception as e:
            logger.error(f"Error interno en cambiar_estado_pedido: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)


    # --- MÉTODO CORREGIDO ---
    def preparar_para_entrega(self, pedido_id: int, usuario_id: int) -> tuple:
        """
        Marca un pedido como listo para entregar, SIEMPRE Y CUANDO todas las OPs
        asociadas estén completadas. Consume el stock reservado.
        """
        try:
            # 1. Obtener Pedido con items
            pedido_resp, _ = self.obtener_pedido_por_id(pedido_id)
            if not pedido_resp.get('success'):
                return self.error_response("Pedido no encontrado.", 404)
            pedido_data = pedido_resp.get('data')
            items_del_pedido = pedido_data.get('items', [])

            # 2. *** NUEVA VERIFICACIÓN: Estado de OPs vinculadas ***
            from app.controllers.orden_produccion_controller import OrdenProduccionController
            op_controller = OrdenProduccionController() # Acceso al controlador de OPs
            for item in items_del_pedido:
                op_id = item.get('orden_produccion_id')
                # Solo verificar si el item está vinculado a una OP
                if op_id:
                    logger.info(f"Verificando estado de OP ID: {op_id} para item {item.get('id')}")
                    # Usamos el método obtener_orden_por_id que devuelve un diccionario
                    op_resp = op_controller.obtener_orden_por_id(op_id)

                    if not op_resp or not op_resp.get('success'):
                        # Error crítico: OP vinculada pero no encontrada
                        logger.error(f"Error: OP vinculada (ID: {op_id}) al item {item.get('id')} no fue encontrada.")
                        return self.error_response(f"Error: OP vinculada (ID: {op_id}) no encontrada. No se puede preparar el pedido.", 500)

                    op_data = op_resp.get('data')
                    op_estado = op_data.get('estado')
                    logger.info(f"Estado de OP ID {op_id}: {op_estado}")

                    # Si CUALQUIER OP vinculada NO está completada, detener el proceso
                    if op_estado != 'COMPLETADA':
                        error_msg = (f"No se puede preparar para entrega. La Orden de Producción "
                                     f"'{op_data.get('codigo', op_id)}' (vinculada al producto '{item.get('producto_nombre', 'N/A')}') "
                                     f"aún no está completada (Estado actual: {op_estado}).")
                        logger.warning(error_msg)
                        return self.error_response(error_msg, 400) # 400 Bad Request: Acción no permitida aún

            # 3. Si todas las OPs están OK (o no había OPs), proceder con el despacho y cambio de estado
            logger.info(f"Todas las OPs para el pedido {pedido_id} están completadas. Procediendo a despachar stock.")
            despacho_result = self.lote_producto_controller.despachar_stock_reservado_por_pedido(pedido_id)

            if not despacho_result.get('success'):
                logger.error(f"Fallo al despachar stock para pedido {pedido_id}: {despacho_result.get('error')}")
                return self.error_response(f"No se pudo preparar el pedido: {despacho_result.get('error')}", 400)

            # Cambiar estado del pedido y sus items
            self.model.cambiar_estado(pedido_id, 'LISTO_PARA_ENTREGA')
            self.model.update_items_by_pedido_id(pedido_id, {'estado': 'COMPLETADO'})
            logger.info(f"Pedido {pedido_id} marcado como LISTO_PARA_ENTREGA y stock despachado.")

            return self.success_response(message="Pedido preparado para entrega. El stock ha sido despachado.")

        except Exception as e:
            logger.error(f"Error preparando para entrega el pedido {pedido_id}: {e}", exc_info=True)
            return self.error_response("Error interno al procesar el pedido.", 500)

    def marcar_como_completado(self, pedido_id: int, usuario_id: int) -> tuple:
        """
        Marca un pedido como COMPLETADO. Se asume que la entrega ya fue realizada.
        """
        logger.info(f"[Controlador] Iniciando 'marcar_como_completado' para Pedido ID: {pedido_id}")
        try:
            # 1. Obtener el estado actual del pedido para validación
            pedido_actual_res = self.model.find_by_id(pedido_id, 'id')
            if not pedido_actual_res.get('success'):
                return self.error_response('Pedido no encontrado.', 404)

            estado_actual = pedido_actual_res['data'].get('estado')
            logger.info(f"[Controlador] Estado actual del pedido: '{estado_actual}'")

            # 2. Condición de seguridad: Solo se puede completar si está 'EN_TRANSITO'
            if estado_actual != 'EN_TRANSITO':
                error_msg = f"El pedido no se puede marcar como completado porque no está 'EN TRANSITO'. Estado actual: {estado_actual}"
                logger.warning(f"[Controlador] {error_msg}")
                return self.error_response(error_msg, 400)

            # 3. Llamar al modelo para cambiar el estado a 'COMPLETADO'
            logger.info(f"[Controlador] El estado es correcto. Llamando al modelo para cambiar a 'COMPLETADO'...")
            resultado_update = self.model.cambiar_estado(pedido_id, 'COMPLETADO')

            if resultado_update.get('success'):
                logger.info(f"[Controlador] Pedido {pedido_id} marcado como COMPLETADO con éxito.")
                return self.success_response(message="Pedido marcado como completado exitosamente.")
            else:
                logger.error(f"[Controlador] El modelo falló al actualizar el estado del pedido {pedido_id}.")
                return self.error_response("Fallo al actualizar el estado en la base de datos.", 500)

        except Exception as e:
            logger.error(f"Error crítico en marcar_como_completado para pedido {pedido_id}: {e}", exc_info=True)
            return self.error_response("Error interno del servidor.", 500)

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


    def get_ordenes_by_cliente(self, id_cliente):
        try:
            result = self.model.find_by_cliente(id_cliente)
            if result['success']:
                return self.success_response(
                    data=result.get('data'),
                    message="Pedidos por cliente cargados"
                )
            else:
                return self.error_response(result.get('error', 'No se pudo cargar los pedidos.'),404)
        except Exception as e:
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)


    def obtener_pedidos_por_orden_produccion(self, id_orden_produccion: int) -> tuple:

        try:

            id_result = self.model.devolver_pedidos_segun_orden(id_orden_produccion)

            if not id_result['success']:
                error_msg = id_result.get('error', 'Error al obtener IDs de pedidos de la OP.')
                return self.error_response(error_msg, 500)

            pedido_ids = id_result['data']

            if not pedido_ids:
                return self.success_response(data=[])


            result = self.model.find_by_id_list(pedido_ids)

            if result.get('success'):
                return self.success_response(data=result.get('data', []))
            else:
                error_msg = result.get('error', 'Error al obtener detalles de los pedidos.')
                return self.error_response(error_msg, 500)

        except Exception as e:
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def actualizar_estado_segun_ops(self, pedido_id: int):
        """
        Verifica los estados de todas las OPs asociadas a un pedido y actualiza el estado del pedido.
        """
        logger.info(f"Verificando estado de OPs para el pedido {pedido_id}")
        try:
            pedido_resp, _ = self.obtener_pedido_por_id(pedido_id)
            if not pedido_resp.get('success'):
                logger.error(f"No se pudo encontrar el pedido {pedido_id} para actualizar estado según OPs.")
                return

            pedido_data = pedido_resp.get('data')
            items_con_op = [item for item in pedido_data.get('items', []) if item.get('orden_produccion_id')]

            if not items_con_op:
                logger.info(f"El pedido {pedido_id} no tiene items con OPs asociadas. No se cambia el estado.")
                return

            estados_ops = [item.get('op_estado') for item in items_con_op]

            todas_completadas = all(estado == 'COMPLETADA' for estado in estados_ops)
            todas_en_proceso_o_mas = all(estado in ['EN_PRODUCCION', 'CONTROL_DE_CALIDAD', 'COMPLETADA'] for estado in estados_ops)

            if todas_completadas:
                self.model.cambiar_estado(pedido_id, 'LISTO_PARA_ENTREGAR')
                logger.info(f"Todas las OPs del pedido {pedido_id} están completadas. Pedido actualizado a 'LISTO_PARA_ENTREGAR'.")
            elif todas_en_proceso_o_mas:
                if pedido_data.get('estado') not in ['EN_PROCESO', 'LISTO_PARA_ENTREGAR']:
                    self.model.cambiar_estado(pedido_id, 'EN_PROCESO')
                    logger.info(f"Todas las OPs del pedido {pedido_id} han iniciado. Pedido actualizado a 'EN_PROCESO'.")
            
        except Exception as e:
            logger.error(f"Error actualizando el estado del pedido {pedido_id} según OPs: {e}", exc_info=True)

    def planificar_pedido(self, pedido_id: int) -> tuple:
        """
        Cambia el estado de un pedido a 'PLANIFICADA'.
        """
        logger.info(f"Intento de planificar el pedido {pedido_id}")
        try:
            pedido_existente_resp = self.model.find_by_id(pedido_id, 'id')
            if not pedido_existente_resp.get('success'):
                return self.error_response(f"Pedido con ID {pedido_id} no encontrado.", 404)

            pedido_actual = pedido_existente_resp.get('data')
            if pedido_actual.get('estado') != 'PENDIENTE':
                return self.error_response("Solo se pueden planificar pedidos en estado 'PENDIENTE'.", 400)

            result = self.model.cambiar_estado(pedido_id, 'PLANIFICADA')
            if result.get('success'):
                logger.info(f"Pedido {pedido_id} cambiado a estado 'PLANIFICADA' con éxito.")
                return self.success_response(message="Pedido planificado con éxito.")
            else:
                logger.error(f"Error al planificar pedido {pedido_id}: {result.get('error')}")
                return self.error_response(result.get('error', 'Error al actualizar el estado del pedido.'), 500)
        except Exception as e:
            logger.error(f"Error interno en planificar_pedido: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def despachar_pedido(self, pedido_id: int, form_data: Dict) -> tuple:
        """
        Cambia el estado de un pedido a 'EN_TRANSITO' y guarda los datos
        del despacho en el campo de observaciones.
        """
        logger.info(f"Intento de despachar el pedido {pedido_id}")
        try:
            # 1. Validar que el pedido se pueda despachar
            pedido_existente_resp, _ = self.obtener_pedido_por_id(pedido_id)
            if not pedido_existente_resp.get('success'):
                return self.error_response(f"Pedido con ID {pedido_id} no encontrado.", 404)
            pedido_actual = pedido_existente_resp.get('data')
            if pedido_actual.get('estado') != 'LISTO_PARA_ENTREGAR':
                return self.error_response("Solo se pueden despachar pedidos en estado 'LISTO_PARA_ENTREGAR'.", 400)

            # 2. Recolectar y validar datos del formulario
            conductor_nombre = form_data.get('conductor_nombre', '').strip()
            if not conductor_nombre:
                return self.error_response('El nombre del conductor es requerido.', 400)
            if any(char.isdigit() for char in conductor_nombre):
                return self.error_response('El nombre del conductor no puede contener números.', 400)

            conductor_dni = form_data.get('conductor_dni', '').strip()
            if not conductor_dni:
                return self.error_response('El DNI del conductor es requerido.', 400)
            if not conductor_dni.isdigit():
                return self.error_response('El DNI solo puede contener números.', 400)

            conductor_telefono = form_data.get('conductor_telefono', '').strip()
            if not conductor_telefono:
                return self.error_response('El teléfono del conductor es requerido.', 400)
            if not conductor_telefono.isdigit():
                return self.error_response('El teléfono solo puede contener números.', 400)

            vehiculo_tipo = form_data.get('vehiculo_tipo', '').strip()
            if not vehiculo_tipo:
                return self.error_response('El tipo de vehículo es requerido.', 400)

            vehiculo_patente = form_data.get('vehiculo_patente', '').strip()
            if not vehiculo_patente:
                return self.error_response('La patente del vehículo es requerida.', 400)

            # 3. Construir el texto estructurado para las observaciones
            observaciones_despacho = (
                f"**Información de Despacho**\n"
                f"---------------------------\n"
                f"**Hora de Partida:** {form_data.get('hora_partida', 'N/A')}\n\n"
                f"**Conductor:**\n"
                f"- **Nombre:** {conductor_nombre}\n"
                f"- **DNI:** {conductor_dni}\n"
                f"- **Teléfono:** {form_data.get('conductor_telefono', 'N/A')}\n\n"
                f"**Vehículo:**\n"
                f"- **Tipo:** {form_data.get('vehiculo_tipo', 'N/A')}\n"
                f"- **Patente:** {vehiculo_patente}\n\n"
                f"**Observaciones Adicionales:**\n"
                f"{form_data.get('observaciones', 'Sin observaciones.')}"
            )

            # 4. Actualizar el pedido
            update_data = {
                'estado': 'EN_TRANSITO',
                'observaciones': observaciones_despacho
                # Ya no guardamos transportista_id
            }

            result = self.model.update(pedido_id, update_data)
            if result.get('success'):
                logger.info(f"Pedido {pedido_id} cambiado a estado 'EN_TRANSITO' con éxito.")
                return self.success_response(message="Pedido despachado con éxito.")
            else:
                logger.error(f"Error al despachar pedido {pedido_id}: {result.get('error')}")
                return self.error_response(result.get('error', 'Error al actualizar el estado del pedido.'), 500)
        except Exception as e:
            logger.error(f"Error interno en despachar_pedido: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def obtener_cantidad_pedidos_estado(self, estado: str, fecha: Optional[str] = None) -> Optional[Dict]:
        filtros = {'estado': estado} if estado else {}

        response, status_code = self.obtener_pedidos(filtros)
        if(response.get('success')):
            ordenes=response.get('data', [])
            cantidad= len(ordenes)
            return self.success_response(data={'cantidad': cantidad})
        else:
            error_msg =response.get('error', 'No se pudo contar las ordenes planificadas')
            status_code = 404 if "no encontradas" in str(error_msg).lower() else 500
            return self.error_response(error_msg, status_code)

    def obtener_cantidad_pedidos_rechazados_recientes(self) -> tuple:
        """
        Obtiene la cantidad de pedidos rechazados en los últimos 30 días.
        """
        try:
            fecha_hasta = date.today()
            fecha_desde = fecha_hasta - timedelta(days=30)
            
            filtros = {
                'estado': 'CANCELADO',
                'fecha_desde': fecha_desde.isoformat(),
                'fecha_hasta': fecha_hasta.isoformat()
            }
            
            response, _ = self.obtener_pedidos(filtros)
            
            if response.get('success'):
                cantidad = len(response.get('data', []))
                return self.success_response(data={'cantidad': cantidad})
            else:
                error_msg = response.get('error', 'No se pudo contar los pedidos rechazados.')
                return self.error_response(error_msg, 500)
        except Exception as e:
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)
