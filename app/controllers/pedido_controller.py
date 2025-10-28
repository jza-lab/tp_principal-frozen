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
from app.models.despacho import DespachoModel
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
        self.despacho = DespachoModel()
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

    def crear_pedido_con_items(self, form_data: Dict, usuario_id: int) -> tuple: # <-- Aceptar usuario_id
        """
        Valida y crea pedido. Verifica stock/mínimo y puede iniciar proceso auto.
        Recibe usuario_id como parámetro.
        """
        try:
            # Consolidar items y manejar dirección
            if 'items-TOTAL_FORMS' in form_data: form_data.pop('items-TOTAL_FORMS')
            if 'items' in form_data: form_data['items'] = self._consolidar_items(form_data['items'])

            direccion_id = self._obtener_o_crear_direccion_para_pedido(form_data)
            if direccion_id is None:
                 return self.error_response("Error procesando la dirección de entrega.", 400)
            form_data['id_direccion_entrega'] = direccion_id
            form_data.pop('direccion_entrega', None); form_data.pop('usar_direccion_alternativa', None)

            items_data = form_data.pop('items', [])
            pedido_data = form_data

            # --- VERIFICACIÓN DE STOCK Y UMBRAL ---
            all_in_stock = True
            produccion_requerida = False
            auto_aprobar_produccion = True

            if not items_data:
                 return self.error_response("El pedido debe contener al menos un producto.", 400)

            for item in items_data:
                producto_id = item['producto_id']
                cantidad_solicitada = item['cantidad']

                producto_info_res = self.producto_model.find_by_id(producto_id, 'id')
                if not producto_info_res.get('success') or not producto_info_res.get('data'):
                    return self.error_response(f"Producto ID {producto_id} no encontrado.", 404)

                producto_data = producto_info_res['data']
                nombre_producto = producto_data.get('nombre', f"ID {producto_id}")
                stock_min = float(producto_data.get('stock_min_produccion', 0)) 
                cantidad_max = float (producto_data.get('cantidad_maxima_x_pedido',0))

                stock_response, _ = self.lote_producto_controller.obtener_stock_producto(producto_id)
                if not stock_response.get('success'):
                    logger.error(f"Fallo al verificar stock para '{nombre_producto}'. Asumiendo insuficiente.")
                    all_in_stock = False; produccion_requerida = True; continue

                stock_disponible = stock_response['data']['stock_total']

                if stock_disponible < cantidad_solicitada:
                    all_in_stock = False; produccion_requerida = True
                    logger.warning(f"STOCK INSUFICIENTE para '{nombre_producto}': Sol: {cantidad_solicitada}, Disp: {stock_disponible}")
                elif (stock_disponible - cantidad_solicitada) < stock_min:
                    produccion_requerida = True
                    logger.warning(f"STOCK BAJARÍA DEL MÍNIMO ({stock_min}) para '{nombre_producto}'. Producción requerida.")

                if cantidad_solicitada > cantidad_max and cantidad_max > 0:
                    auto_aprobar_produccion = False
                    logger.info(f"Cantidad ({cantidad_solicitada}) para '{nombre_producto}' supera el máximo por pedido ({cantidad_max}). Requiere aprobación manual.")
                else:
                    auto_aprobar_produccion = True
                    logger.info(f"Cantidad ({cantidad_solicitada}) para '{nombre_producto}' NO supera el máximo por pedido ({cantidad_max}).")
            # --- DECIDIR ESTADO INICIAL Y ACCIÓN ---
            estado_inicial = 'PENDIENTE'
            accion_post_creacion = None

            if not produccion_requerida and all_in_stock:
                estado_inicial = 'LISTO_PARA_ENTREGA'
                accion_post_creacion = 'DESPACHAR_Y_COMPLETAR'
                for item in items_data: item['estado'] = 'ALISTADO'
                logger.info("Stock OK. Estado inicial: LISTO_PARA_ENTREGA.")
            elif produccion_requerida and auto_aprobar_produccion:
                 estado_inicial = 'PENDIENTE' # Inicia PENDIENTE
                 accion_post_creacion = 'INICIAR_PROCESO_AUTO'
                 logger.info("Producción requerida (cant. pequeña). Estado inicial: PENDIENTE, se intentará iniciar proceso auto.")
            else: # Producción requerida, cantidad grande
                 logger.info("Producción requerida (cant. grande). Estado inicial: PENDIENTE (espera aprobación manual).")

            pedido_data['estado'] = estado_inicial
            # ----------------------------------------

            # Crear el pedido en la BD
            result = self.model.create_with_items(pedido_data, items_data)
            if not result.get('success'):
                return self.error_response(result.get('error', 'No se pudo crear el pedido.'), 400)

            nuevo_pedido = result.get('data')
            pedido_id_creado = nuevo_pedido.get('id')
            mensaje_final = f"Pedido {pedido_id_creado} creado en estado '{estado_inicial}'."

            # --- EJECUTAR ACCIÓN POST-CREACIÓN ---
            if accion_post_creacion == 'DESPACHAR_Y_COMPLETAR':
                logger.info(f"Intentando despachar y completar pedido {pedido_id_creado}...")
                pedido_con_items_resp = self.model.get_one_with_items(pedido_id_creado)
                if pedido_con_items_resp.get('success'):
                    items_del_pedido_con_id = pedido_con_items_resp.get('data', {}).get('items', [])
                    despacho_result = self.lote_producto_controller.despachar_stock_directo_por_pedido(
                        pedido_id=pedido_id_creado, items_del_pedido=items_del_pedido_con_id
                    )
                    if despacho_result.get('success'):
                        self.model.cambiar_estado(pedido_id_creado, 'COMPLETADO')
                        mensaje_final = f"Pedido {pedido_id_creado} COMPLETADO automáticamente (stock disponible y despachado)."
                        nuevo_pedido['estado'] = 'COMPLETADO'
                    else:
                        self.model.cambiar_estado(pedido_id_creado, 'PENDIENTE')
                        logger.error(f"Fallo despacho en creación pedido {pedido_id_creado}. Revirtiendo a PENDIENTE. Error: {despacho_result.get('error')}")
                        return self.error_response(f"Pedido creado, pero falló despacho: {despacho_result.get('error')}", 500)
                else:
                    logger.error(f"No se pudieron obtener items para despachar pedido {pedido_id_creado}. Dejado en LISTO_PARA_ENTREGA.")

            elif accion_post_creacion == 'INICIAR_PROCESO_AUTO':
                logger.info(f"Intentando iniciar proceso automáticamente para pedido {pedido_id_creado}...")
                # --- USAR usuario_id RECIBIDO ---
                if usuario_id is None or int(usuario_id) < 0:
                     logger.error(f"No se pudo iniciar proceso auto para pedido {pedido_id_creado}: Usuario ID no válido proporcionado.")
                     mensaje_final += " (No se pudo iniciar proceso automáticamente por falta de usuario)."
                else:
                    # Llamar a iniciar_proceso_pedido usando el usuario_id del parámetro
                    inicio_resp, inicio_status = self.iniciar_proceso_pedido(pedido_id_creado, usuario_id)
                    if inicio_resp.get('success'):
                        # Consultar estado final después de iniciar proceso
                        nuevo_estado_despues_inicio = self.model.find_by_id(pedido_id_creado, 'id')['data']['estado']
                        mensaje_final = f"Pedido {pedido_id_creado} creado y proceso iniciado automáticamente (Estado final: {nuevo_estado_despues_inicio}). {inicio_resp.get('message', '')}"
                        nuevo_pedido['estado'] = nuevo_estado_despues_inicio # Actualizar estado para la respuesta
                    else:
                         logger.error(f"Fallo al iniciar proceso auto para pedido {pedido_id_creado}: {inicio_resp.get('error')}")
                         mensaje_final += f" (Fallo al iniciar proceso automáticamente: {inicio_resp.get('error')})"
                # --- FIN USO usuario_id ---

            # --- FIN EJECUCIÓN ACCIÓN ---

            # Actualizar condición de venta del cliente
            id_cliente = nuevo_pedido.get('id_cliente')
            if id_cliente:
                pedidos_previos,_ = self.obtener_pedidos(filtros={'id_cliente': id_cliente})
                pedidos_validos = [p for p in pedidos_previos.get('data', []) if p.get('estado') != 'CANCELADO']
                num_pedidos = len(pedidos_validos)
                if num_pedidos == 1: self.cliente_model.update(id_cliente, {'condicion_venta': 2})
                elif num_pedidos == 2: self.cliente_model.update(id_cliente, {'condicion_venta': 3})

            return self.success_response(data=nuevo_pedido, message=mensaje_final, status_code=201)

        except ValidationError as e:
            error_msg = str(e.messages)
            logger.warning(f"Error de validación al crear pedido: {error_msg}")
            return self.error_response(f"Datos inválidos: {error_msg}", 400)
        except Exception as e:
            logging.error(f"Error interno en crear_pedido_con_items: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    # --- NUEVO HELPER para Dirección ---
    def _obtener_o_crear_direccion_para_pedido(self, form_data: Dict) -> Optional[int]:
         """ Centraliza la lógica de obtener/crear dirección para un pedido. """
         direccion_id = None
         usar_alternativa = form_data.get('usar_direccion_alternativa')
         try:
             if usar_alternativa:
                 direccion_payload = form_data.get('direccion_entrega', {})
                 direccion_data = {k: direccion_payload.get(k) for k in ['calle', 'altura', 'provincia', 'localidad', 'piso', 'depto', 'codigo_postal']}
                 if not all(direccion_data.get(k) for k in ['calle', 'altura', 'localidad', 'provincia']):
                     logger.error("Faltan campos en dirección alternativa.")
                     return None # Error
                 direccion_id = self._get_or_create_direccion(direccion_data) # Llama al helper existente
                 if not direccion_id:
                      logger.error("No se pudo obtener/crear dirección alternativa.")
                      return None # Error
             else:
                 id_cliente = form_data.get('id_cliente')
                 if not id_cliente:
                     logger.error("Cliente no especificado para dirección principal.")
                     return None # Error
                 cliente_result = self.cliente_model.find_by_id(id_cliente, 'id')
                 if not cliente_result.get('success') or not cliente_result.get('data'):
                     logger.error(f"Cliente {id_cliente} no encontrado.")
                     return None # Error
                 direccion_id = cliente_result['data'].get('direccion_id')
                 if not direccion_id:
                     logger.error(f"Cliente {id_cliente} sin dirección principal.")
                     return None # Error
             return direccion_id
         except Exception as e:
             logger.error(f"Excepción en _obtener_o_crear_direccion_para_pedido: {e}", exc_info=True)
             return None

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

            # 3. Si todas las OPs están OK (o no había OPs), proceder con el cambio de estado
            logger.info(f"Todas las OPs para el pedido {pedido_id} están completadas. El pedido está listo para ser despachado.")

            # Cambiar estado del pedido y sus items
            self.model.cambiar_estado(pedido_id, 'LISTO_PARA_ENTREGA')
            self.model.update_items_by_pedido_id(pedido_id, {'estado': 'COMPLETADO'})
            logger.info(f"Pedido {pedido_id} marcado como LISTO_PARA_ENTREGA.")

            return self.success_response(message="Pedido preparado para entrega.")

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

    def obtener_pedidos_por_cliente(self, cliente_id: int) -> tuple:
        """
        Obtiene todos los pedidos de un cliente específico.
        """
        try:
            result = self.model.get_all_with_items({'id_cliente': cliente_id})
            if result.get('success'):
                return self.success_response(data=result.get('data', []))
            else:
                error_msg = result.get('error', 'Error desconocido al obtener los pedidos del cliente.')
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
                self.model.cambiar_estado(pedido_id, 'LISTO_PARA_ENTREGA')
                logger.info(f"Todas las OPs del pedido {pedido_id} están completadas. Pedido actualizado a 'LISTO_PARA_ENTREGA'.")
            elif todas_en_proceso_o_mas:
                if pedido_data.get('estado') not in ['EN_PROCESO', 'LISTO_PARA_ENTREGA']:
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
        del despacho en la nueva tabla 'despachos'.
        """
        logger.info(f"Intento de despachar el pedido {pedido_id}")
        try:
            # 1. Validar que el pedido se pueda despachar
            pedido_existente_resp, _ = self.obtener_pedido_por_id(pedido_id)
            if not pedido_existente_resp.get('success'):
                return self.error_response(f"Pedido con ID {pedido_id} no encontrado.", 404)

            pedido_actual = pedido_existente_resp.get('data')
            if pedido_actual.get('estado') != 'LISTO_PARA_ENTREGA':
                return self.error_response("Solo se pueden despachar pedidos en estado 'LISTO_PARA_ENTREGA'.", 400)

            # 2. Recolectar y validar datos del formulario
            nombre_transportista = form_data.get('conductor_nombre', '').strip()
            dni_transportista = form_data.get('conductor_dni', '').strip()
            patente_vehiculo = form_data.get('vehiculo_patente', '').strip()
            telefono_transportista = form_data.get('conductor_telefono', '').strip()
            observaciones = form_data.get('observaciones', '').strip()

            # (Aquí se pueden agregar validaciones más estrictas si es necesario)
            if not all([nombre_transportista, dni_transportista, patente_vehiculo, telefono_transportista]):
                 return self.error_response('Todos los campos del transportista y vehículo son requeridos.', 400)

            # 3. Preparar datos para el nuevo modelo de despacho
            datos_despacho = {
                'id_pedido': pedido_id,
                'nombre_transportista': nombre_transportista,
                'dni_transportista': dni_transportista,
                'patente_vehiculo': patente_vehiculo,
                'telefono_transportista': telefono_transportista,
                'observaciones': observaciones if observaciones else None
            }

            # 4. *** Consumir el stock reservado ANTES de cualquier otra acción ***
            logger.info(f"Consumiendo stock reservado para el pedido {pedido_id}...")
            consumo_result = self.lote_producto_controller.despachar_stock_reservado_por_pedido(pedido_id)

            if not consumo_result.get('success'):
                error_msg = consumo_result.get('error', 'No se pudo consumir el stock reservado.')
                logger.error(f"Fallo crítico al despachar pedido {pedido_id}: {error_msg}")
                # Si el consumo de stock falla, no se debe continuar con el despacho.
                return self.error_response(f"Error al despachar: {error_msg}", 500)

            logger.info(f"Stock para el pedido {pedido_id} consumido exitosamente.")

            # 5. Crear el registro de despacho
            resultado_despacho = self.despacho.create(datos_despacho)
            if not resultado_despacho.get('success'):
                error_msg = resultado_despacho.get('error', 'Error desconocido al guardar los datos del despacho.')
                logger.error(f"Error al crear registro de despacho para pedido {pedido_id}: {error_msg}")
                # En un escenario real, aquí se debería intentar revertir el consumo de stock.
                return self.error_response(f"{error_msg} (Advertencia: El stock ya fue consumido)", 500)

            # 6. Actualizar el estado del pedido
            update_data = {'estado': 'EN_TRANSITO'}
            result = self.model.update(pedido_id, update_data)

            if result.get('success'):
                logger.info(f"Pedido {pedido_id} cambiado a estado 'EN_TRANSITO' con éxito.")
                return self.success_response(message="Pedido despachado con éxito.")
            else:
                # En un caso real, aquí se debería considerar revertir la creación del despacho (transacción)
                logger.error(f"Error al despachar pedido {pedido_id} después de guardar despacho: {result.get('error')}")
                return self.error_response(result.get('error', 'El despacho fue registrado, pero no se pudo actualizar el estado del pedido.'), 500)

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
