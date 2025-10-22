import logging
from datetime import datetime, date

from flask import jsonify
from app.controllers.base_controller import BaseController
# --- IMPORTACIONES NUEVAS ---
from app.controllers.lote_producto_controller import LoteProductoController
from app.controllers.orden_produccion_controller import OrdenProduccionController
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
                # Si todo está en stock, el estado inicial es COMPLETADO
                pedido_data['estado'] = 'COMPLETADO'
                logging.info("Todo el stock disponible. El pedido se creará en estado COMPLETADO.")
            elif 'estado' not in pedido_data:
                # Si falta stock, el estado inicial es PENDIENTE
                pedido_data['estado'] = 'PENDIENTE'
                logging.warning("Stock insuficiente para uno o más items. El pedido se creará en estado PENDIENTE.")


            result = self.model.create_with_items(pedido_data, items_data)

            if result.get('success'):
                nuevo_pedido = result.get('data')

                if all_in_stock:
                    # --- Lógica de Despacho/Consumo Inmediato (Solo si all_in_stock es True) ---

                    # 1. Recuperar el pedido con IDs de item para el despacho
                    pedido_con_items_resp = self.model.get_one_with_items(nuevo_pedido.get('id'))
                    if pedido_con_items_resp.get('success'):
                        items_del_pedido_con_id = pedido_con_items_resp.get('data', {}).get('items', [])

                        # 2. ** Despacho/Consumo de Stock **
                        despacho_result = self.lote_producto_controller.despachar_stock_directo_por_pedido(
                            pedido_id=nuevo_pedido.get('id'),
                            items_del_pedido=items_del_pedido_con_id
                        )

                        if not despacho_result.get('success'):
                            # Si falla el despacho, revertimos el estado a PENDIENTE
                            self.model.cambiar_estado(nuevo_pedido.get('id'), 'PENDIENTE')
                            logging.error(f"Fallo al despachar stock en la creación. Revirtiendo a PENDIENTE. Error: {despacho_result.get('error')}")
                            # Devolvemos un 500 para indicar un fallo en la transacción
                            return self.error_response(f"Pedido creado, pero falló el despacho de stock: {despacho_result.get('error')}", 500)

                        # 3. Éxito en la creación y el despacho. Enviamos un indicador.
                        nuevo_pedido['estado'] = 'COMPLETADO'
                        # === CAMBIO SOLICITADO: Mensaje explícito de stock encontrado y completado ===
                        return self.success_response(
                            data={**nuevo_pedido, 'estado_completado_inmediato': True}, # <--- INDICADOR ESPECIAL
                            message="El pedido ha sido puesto en estado COMPLETADO automáticamente porque se encontró stock disponible para despachar todos los ítems.",
                            status_code=201
                        )

                # Caso de éxito normal (all_in_stock era False)
                return self.success_response(data=nuevo_pedido, message="Pedido creado con éxito.", status_code=201)
            else:
                return self.error_response(result.get('error', 'No se pudo crear el pedido.'), 400)

        except ValidationError as e:
            return self.error_response(str(e.messages), 400)

        except Exception as e:
            logging.error(f"Error interno en crear_pedido_con_items: {e}", exc_info=True)
            return self.error_response(f'Error interno: {str(e)}', 500)

    def planificar_pedido(self, pedido_id: int, fecha_estimativa: str) -> tuple:
        """
        Pasa un pedido del estado 'PENDIENTE' a 'PLANIFICACION' y guarda la fecha estimada.
        """
        try:
            pedido_resp, _ = self.obtener_pedido_por_id(pedido_id)
            if not pedido_resp.get('success'):
                return self.error_response("Pedido no encontrado.", 404)

            pedido_actual = pedido_resp['data']
            if pedido_actual.get('estado') != 'PENDIENTE':
                return self.error_response("Solo los pedidos en estado 'PENDIENTE' pueden ser planificados.", 400)

            # Actualizar estado y fecha estimada en un solo paso
            update_data = {
                'estado': 'PLANIFICACION',
                'fecha_estimativa_proceso': fecha_estimativa
            }
            result = self.model.update(id_value=pedido_id, data=update_data, id_field='id')

            if result.get('success'):
                return self.success_response(message="Pedido pasado a estado de PLANIFICACIÓN.")
            else:
                return self.error_response(result.get('error', 'Error al planificar el pedido.'), 500)
        except Exception as e:
            logging.error(f"Error en planificar_pedido: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

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
            if pedido_actual.get('estado') != 'PLANIFICACION':
                return self.error_response("Solo los pedidos en 'PLANIFICACION' pueden pasar a 'EN PROCESO'.", 400)

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
                    # --- FIX: Manejo defensivo de la respuesta ---
                    resultado_op_tuple = self.orden_produccion_controller.crear_orden(datos_op, usuario_id)
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

    def preparar_para_entrega(self, pedido_id: int, usuario_id: int) -> tuple:
        """
        Marca un pedido como listo para entregar, consumiendo el stock reservado.
        """
        try:
            # La lógica interna no cambia, solo la firma del método
            despacho_result = self.lote_producto_controller.despachar_stock_reservado_por_pedido(pedido_id)

            if not despacho_result.get('success'):
                return self.error_response(f"No se pudo preparar el pedido: {despacho_result.get('error')}", 400)

            self.model.cambiar_estado(pedido_id, 'LISTO_PARA_ENTREGA')
            self.model.update_items_by_pedido_id(pedido_id, {'estado': 'COMPLETADO'})

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

            # 2. Condición de seguridad: Solo se puede completar si está 'LISTO_PARA_ENTREGA'
            if estado_actual != 'LISTO_PARA_ENTREGA':
                error_msg = f"El pedido no se puede marcar como completado porque no está 'LISTO PARA ENTREGAR'. Estado actual: {estado_actual}"
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
