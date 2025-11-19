import logging
from datetime import datetime, date, timedelta
import copy

from flask import jsonify, request
from flask_jwt_extended import get_current_user
from app.controllers.base_controller import BaseController
from app.controllers.registro_controller import RegistroController
from app.utils.security import generate_signed_token
# --- IMPORTACIONES NUEVAS ---
from app.controllers.lote_producto_controller import LoteProductoController
from app.models.receta import RecetaModel
from decimal import Decimal
# -------------------------
from app.models.cliente import ClienteModel
from app.models.pedido import PedidoModel
from app.models.despacho import DespachoModel
from app.models.producto import ProductoModel
from app.models.direccion import DireccionModel
from app.models.nota_credito import NotaCreditoModel
from app.schemas.direccion_schema import DireccionSchema
from app.schemas.cliente_schema import ClienteSchema
from app.schemas.pedido_schema import PedidoSchema
from typing import Dict, Optional
from marshmallow import ValidationError
from app.config import Config
from app.models.reserva_producto import ReservaProductoModel # <--- AGREGAR ESTO
import time
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
        from app.controllers.storage_controller import StorageController
        self.storage_controller = StorageController()
        # --- INSTANCIAS NUEVAS ---
        self.lote_producto_controller = LoteProductoController()
        self.nota_credito_model = NotaCreditoModel()
        # -----------------------
        self.registro_controller = RegistroController()
        self.reserva_producto_model = ReservaProductoModel()

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
            result = self.model.get_one_with_items_and_op_status(pedido_id)

            if not result.get('success'):
                error_msg = result.get('error', 'Error desconocido.')
                status_code = 404 if "no encontrado" in str(error_msg).lower() else 500
                return self.error_response(error_msg, status_code)
            pedido_data = result.get('data')

            # 2. Obtener y adjuntar notas de crédito
            nc_result = self.nota_credito_model.find_all({'pedido_origen_id': pedido_id})
            notas_de_credito_completas = []
            if nc_result.get('success'):
                for nc in nc_result.get('data', []):
                    items = self.nota_credito_model.get_items_by_nc_id(nc['id'])
                    nc['items'] = items
                    notas_de_credito_completas.append(nc)

            pedido_data['notas_credito'] = notas_de_credito_completas

            return self.success_response(data=pedido_data)
        except Exception as e:
            # Mantener el log de error
            logger.error(f"Error interno obteniendo detalle de pedido {pedido_id}: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def crear_pedido_con_items(self, form_data: Dict, usuario_id: int) -> tuple:
        """
        Valida y crea un pedido. Implementa "reserva dura": descuenta stock disponible
        inmediatamente y divide los items si el cumplimiento es parcial (stock y producción).
        """
        try:
            # 1. PREPARACIÓN Y VALIDACIÓN INICIAL
            if 'items-TOTAL_FORMS' in form_data: form_data.pop('items-TOTAL_FORMS')
            if 'items' in form_data: form_data['items'] = self._consolidar_items(form_data['items'])

            items_data = form_data.pop('items', [])
            if not items_data:
                return self.error_response("El pedido debe contener al menos un producto.", 400)

            direccion_id = self._obtener_o_crear_direccion_para_pedido(form_data)
            if direccion_id is None:
                return self.error_response("Error procesando la dirección de entrega.", 400)
            form_data['id_direccion_entrega'] = direccion_id
            form_data.pop('direccion_entrega', None); form_data.pop('usar_direccion_alternativa', None)

            # Lógica de crédito y fechas (sin cambios)
            id_cliente = form_data.get('id_cliente')
            cliente_info = self.cliente_model.find_by_id(id_cliente)
            if cliente_info.get('success'):
                cliente_data = cliente_info['data']
                if cliente_data.get('estado_crediticio') == 'alertado' and form_data.get('condicion_venta') != 'contado':
                    return self.error_response("El cliente tiene un estado crediticio 'alertado' y solo puede realizar pedidos al contado.", 403)

            condicion_venta = form_data.get('condicion_venta', 'contado')
            if 'fecha_solicitud' in form_data:
                fecha_solicitud = datetime.fromisoformat(form_data['fecha_solicitud']).date()
                plazos = {'credito_30': 30, 'credito_90': 90}
                if plazo := plazos.get(condicion_venta):
                    form_data['fecha_vencimiento'] = fecha_solicitud + timedelta(days=plazo)
                else:
                    form_data['fecha_vencimiento'] = None

            # 2. GESTIÓN DE STOCK Y DIVISIÓN DE ITEMS
            items_para_crear = []
            auto_aprobar_produccion = True

            producto_ids_pedido = [item['producto_id'] for item in items_data]
            stock_global_resp, _ = self.lote_producto_controller.obtener_stock_disponible_real_para_productos(producto_ids_pedido)
            if not stock_global_resp.get('success'):
                return self.error_response("No se pudo verificar el stock para los productos del pedido.", 500)
            stock_global_map = stock_global_resp.get('data', {})

            for item in items_data:
                producto_id = item['producto_id']
                cantidad_solicitada = item['cantidad']

                producto_info_res = self.producto_model.find_by_id(producto_id, 'id')
                if not producto_info_res.get('success') or not producto_info_res.get('data'):
                    return self.error_response(f"Producto ID {producto_id} no encontrado.", 404)

                producto_data = producto_info_res['data']
                if (cantidad_max := float(producto_data.get('cantidad_maxima_x_pedido', 0))) > 0 and cantidad_solicitada > cantidad_max:
                    auto_aprobar_produccion = False

                stock_disponible = stock_global_map.get(producto_id, 0)

                # --- LÓGICA DE ARBITRAJE NUEVA ---
                # --- LÓGICA DE ARBITRAJE NUEVA ---
                if stock_disponible < cantidad_solicitada:
                    fecha_entrega_pedido = form_data.get('fecha_requerido')
                    if fecha_entrega_pedido:
                        fecha_obj = datetime.fromisoformat(fecha_entrega_pedido).date()

                        # Intentamos robar stock a pedidos futuros
                        faltante = cantidad_solicitada - stock_disponible
                        recuperado = self._intentar_reasignar_stock(producto_id, faltante, fecha_obj)

                        if recuperado > 0:
                            # Actualizamos el stock disponible localmente
                            stock_disponible += recuperado

                            # NUEVO: Pausa táctica para permitir consistencia en Supabase
                            logger.info("Stock liberado. Esperando consistencia de DB...")
                            time.sleep(1.5)

                if stock_disponible >= cantidad_solicitada:
                    item.update({'estado': 'PENDIENTE_DESCUENTO'})
                    items_para_crear.append(item)
                elif stock_disponible > 0:
                    item.update({
                        'estado': 'PARCIAL',
                        '_cantidad_stock': int(stock_disponible),
                        '_cantidad_produccion': int(cantidad_solicitada - stock_disponible)
                    })
                    items_para_crear.append(item)
                else:
                    item.update({'estado': 'PENDIENTE_PRODUCCION'})
                    items_para_crear.append(item)

            # 3. DECIDIR ESTADO INICIAL Y ACCIÓN
            hay_items_stock = any(it['estado'] in ['PENDIENTE_DESCUENTO', 'PARCIAL'] for it in items_para_crear)
            hay_items_produccion = any(it['estado'] in ['PENDIENTE_PRODUCCION', 'PARCIAL'] for it in items_para_crear)

            estado_inicial, accion_post_creacion = ('PENDIENTE', None)

            if hay_items_stock and not hay_items_produccion:
                estado_inicial, accion_post_creacion = 'LISTO_PARA_ENTREGA', 'DESCONTAR_STOCK'
            elif hay_items_stock and hay_items_produccion:
                estado_inicial, accion_post_creacion = 'EN_PROCESO', 'DESCONTAR_Y_PRODUCIR'
            elif not hay_items_stock and hay_items_produccion:
                if auto_aprobar_produccion:
                    accion_post_creacion = 'INICIAR_PROCESO_AUTO'

            form_data['estado'] = estado_inicial

            # 4. CREAR PEDIDO EN BD
            result = self.model.create_with_items(form_data, items_para_crear)
            if not result.get('success'):
                return self.error_response(result.get('error', 'No se pudo crear el pedido.'), 400)

            nuevo_pedido = result.get('data')
            pedido_id_creado = nuevo_pedido.get('id')
            mensaje_final = f"Pedido {pedido_id_creado} creado en estado '{estado_inicial}'."

            # 5. EJECUTAR ACCIÓN POST-CREACIÓN (RESERVA DURA Y/O PRODUCCIÓN)
            items_creados = nuevo_pedido.get('items', [])
            items_originales_map = {int(item['producto_id']): item for item in items_para_crear}

            items_a_descontar = []
            items_a_producir = []

            for item_creado in items_creados:
                estado = item_creado.get('estado')
                producto_id = int(item_creado.get('producto_id'))
                item_original = items_originales_map.get(producto_id)

                if estado == 'PENDIENTE_DESCUENTO':
                    items_a_descontar.append(item_creado)
                elif estado == 'PENDIENTE_PRODUCCION':
                    items_a_producir.append(item_creado)
                elif estado == 'PARCIAL' and item_original:
                    items_a_descontar.append({'id': item_creado['id'], 'producto_id': producto_id, 'cantidad': item_original['_cantidad_stock']})
                    items_a_producir.append({'id': item_creado['id'], 'producto_id': producto_id, 'cantidad': item_original['_cantidad_produccion']})

            if accion_post_creacion in ['DESCONTAR_STOCK', 'DESCONTAR_Y_PRODUCIR'] and items_a_descontar:
                reserva_result = self.lote_producto_controller.reservar_stock_para_pedido(pedido_id_creado, items_a_descontar, usuario_id)
                if not reserva_result.get('success'):
                    self.model.cambiar_estado(pedido_id_creado, 'PENDIENTE')
                    return self.error_response(f"Pedido creado, pero falló el descuento de stock: {reserva_result.get('error')}. Queda PENDIENTE.", 500)

                ids_completos = [i['id'] for i in items_a_descontar if i['id'] not in [p['id'] for p in items_a_producir]]
                for item_id in ids_completos:
                    self.model.update_item(item_id, {'estado': 'ALISTADO'})
                mensaje_final = f"Pedido {pedido_id_creado} creado y stock descontado."

            if accion_post_creacion in ['DESCONTAR_Y_PRODUCIR', 'INICIAR_PROCESO_AUTO'] and items_a_producir:
                inicio_resp, _ = self.iniciar_proceso_pedido(pedido_id_creado, usuario_id, items_a_producir=items_a_producir)
                if inicio_resp.get('success'):
                    nuevo_estado = self.model.find_by_id(pedido_id_creado, 'id')['data']['estado']
                    mensaje_final += f" Proceso de producción iniciado (Estado final: {nuevo_estado})."
                    nuevo_pedido['estado'] = nuevo_estado
                else:
                    mensaje_final += f" Fallo al iniciar producción: {inicio_resp.get('error')}"

            # Lógica post-creación (actualizar cliente, registro)
            self.registro_controller.crear_registro(get_current_user(), 'Ordenes de venta', 'Creación', f"Se creó el pedido de venta con ID: {pedido_id_creado}.")

            return self.success_response(data=nuevo_pedido, message=mensaje_final, status_code=201)

        except ValidationError as e:
            return self.error_response(f"Datos inválidos: {e.messages}", 400)
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

    def iniciar_proceso_pedido(self, pedido_id: int, usuario_id: int, items_a_producir: Optional[list] = None) -> tuple:
        """
        Pasa un pedido a 'EN PROCESO'. Crea OPs para los items especificados o
        para todos los que no tengan OP si no se especifica.
        """
        try:
            pedido_resp, _ = self.obtener_pedido_por_id(pedido_id)
            if not pedido_resp.get('success'):
                return self.error_response("Pedido no encontrado.", 404)

            pedido_actual = pedido_resp['data']
            if pedido_actual.get('estado') not in ['PENDIENTE', 'EN_PROCESO']:
                return self.error_response(f"El pedido debe estar en 'PENDIENTE' o 'EN PROCESO'. Estado actual: {pedido_actual.get('estado')}", 400)

            fecha_requerido_pedido = pedido_actual.get('fecha_requerido')

            items_para_op = items_a_producir if items_a_producir is not None else [
                item for item in pedido_actual.get('items', []) if item.get('orden_produccion_id') is None
            ]

            ordenes_creadas = []
            from app.controllers.orden_produccion_controller import OrdenProduccionController
            op_controller = OrdenProduccionController()

            for item in items_para_op:
                receta_result = self.receta_model.find_all({'producto_id': item['producto_id'], 'activa': True}, limit=1)
                if receta_result.get('success') and receta_result.get('data'):
                    datos_op = {
                        'producto_id': item['producto_id'],
                        'cantidad': item['cantidad'],
                        'fecha_planificada': date.today().isoformat(),
                        'prioridad': 'NORMAL',
                        'fecha_meta': fecha_requerido_pedido,
                        'productos': [{'id': item['producto_id'], 'cantidad': item['cantidad']}]
                    }

                    # --- MANEJO ROBUSTO DE LA RESPUESTA ---
                    # El método puede devolver una tupla (dict, status) o solo un dict
                    respuesta_op = op_controller.crear_orden(datos_op, usuario_id)
                    resultado_op = respuesta_op[0] if isinstance(respuesta_op, tuple) else respuesta_op

                    if isinstance(resultado_op, dict) and resultado_op.get('success'):
                        # La respuesta de crear_orden devuelve una lista en 'data'
                        if resultado_op.get('data'):
                            orden_creada = resultado_op['data'][0] # Tomamos la primera OP creada de la lista
                            ordenes_creadas.append(orden_creada)
                        self.model.update_item(item['id'], {'estado': 'EN_PRODUCCION', 'orden_produccion_id': orden_creada.get('id')})
                    else:
                        logging.error(f"No se pudo crear la OP para el producto {item['producto_id']}. Error: {resultado_op.get('error')}")
                else:
                    self.model.update_item(item['id'], {'estado': 'ALISTADO'})

            if ordenes_creadas:
                self.model.actualizar_estado_agregado(pedido_id)

            msg = f"Proceso iniciado. Se generaron {len(ordenes_creadas)} Órdenes de Producción."
            self.registro_controller.crear_registro(get_current_user(), 'Ordenes de venta', 'Inicio de Proceso', f"Se inició el proceso para el pedido {pedido_id}. Se generaron {len(ordenes_creadas)} OPs.")
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


            # --- LÓGICA DE CRÉDITO ---
            id_cliente = pedido_data.get('id_cliente')
            cliente_info = self.cliente_model.find_by_id(id_cliente)
            if cliente_info.get('success'):
                cliente_data = cliente_info['data']
                if cliente_data.get('estado_crediticio') == 'alertado' and pedido_data.get('condicion_venta') != 'contado':
                    return self.error_response("El cliente tiene un estado crediticio 'alertado' y solo puede realizar pedidos al contado.", 403)

            condicion_venta = pedido_data.get('condicion_venta', 'contado')
            if 'fecha_solicitud' in pedido_data:
                fecha_solicitud = datetime.fromisoformat(pedido_data['fecha_solicitud']).date()
                if condicion_venta == 'credito_30':
                    pedido_data['fecha_vencimiento'] = fecha_solicitud + timedelta(days=30)
                elif condicion_venta == 'credito_90':
                    pedido_data['fecha_vencimiento'] = fecha_solicitud + timedelta(days=90)
                else:
                    pedido_data['fecha_vencimiento'] = None
            # --- FIN LÓGICA DE CRÉDITO ---

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
                    from flask_jwt_extended import get_current_user
                    current_user = get_current_user()
                    if not current_user:
                        return self.error_response("Sesión de usuario no encontrada para crear OP.", 401)
                    usuario_id = current_user.id

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

            detalle = f"Se actualizó el pedido de venta con ID: {pedido_id}."
            self.registro_controller.crear_registro(get_current_user(), 'Ordenes de venta', 'Actualización', detalle)

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
                detalle = f"El pedido de venta con ID: {pedido_id} cambió de estado a {nuevo_estado}."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de venta', 'Cambio de Estado', detalle)
                logger.info(f"Pedido {pedido_id} cambiado a estado '{nuevo_estado}' con éxito.")
                return self.success_response(message=f"Pedido actualizado al estado '{nuevo_estado}'.")
            else:
                logger.error(f"Error al cambiar estado del pedido {pedido_id}: {result.get('error')}")
                return self.error_response(result.get('error', 'Error al actualizar el estado del pedido.'), 500)
        except Exception as e:
            logger.error(f"Error interno en cambiar_estado_pedido: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)


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

            # Obtener los items del pedido para la reserva.
            # 'items_del_pedido' ya contiene los IDs de los pedido_items, producto_id y cantidad.
            reserva_result = self.lote_producto_controller.reservar_stock_para_pedido(
                pedido_id=pedido_id,
                items=items_del_pedido, # Usar los items ya obtenidos del pedido
                usuario_id=usuario_id
            )
            if not reserva_result.get('success'):
                logger.error(f"Fallo la reserva de stock para el pedido {pedido_id} durante la preparación para entrega. Error: {reserva_result.get('error')}")
                return self.error_response(f"Error al reservar stock para el pedido: {reserva_result.get('error')}", 500)
            logger.info(f"Stock para el pedido {pedido_id} reservado con éxito durante la preparación para entrega.")

            # Cambiar estado del pedido y sus items
            self.model.cambiar_estado(pedido_id, 'LISTO_PARA_ENTREGA')
            self.model.update_items_by_pedido_id(pedido_id, {'estado': 'COMPLETADO'})
            logger.info(f"Pedido {pedido_id} marcado como LISTO_PARA_ENTREGA.")

            detalle = f"El pedido de venta con ID: {pedido_id} fue preparado para entrega."
            self.registro_controller.crear_registro(get_current_user(), 'Ordenes de venta', 'Preparado para Entrega', detalle)

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
                detalle = f"El pedido de venta con ID: {pedido_id} fue marcado como COMPLETADO."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de venta', 'Completado', detalle)
                return self.success_response(message="Pedido marcado como completado exitosamente.")
            else:
                logger.error(f"[Controlador] El modelo falló al actualizar el estado del pedido {pedido_id}.")
                return self.error_response("Fallo al actualizar el estado en la base de datos.", 500)

        except Exception as e:
            logger.error(f"Error crítico en marcar_como_completado para pedido {pedido_id}: {e}", exc_info=True)
            return self.error_response("Error interno del servidor.", 500)

    def cancelar_pedido(self, pedido_id: int) -> tuple:
        """
        Cambia el estado de un pedido a 'CANCELADO' y libera el stock previamente reservado.
        """
        try:
            # 1. Verificar que el pedido existe y no esté ya cancelado
            pedido_existente_resp = self.model.find_by_id(pedido_id, 'id')
            if not pedido_existente_resp.get('success') or not pedido_existente_resp.get('data'):
                 return self.error_response(f"Pedido con ID {pedido_id} no encontrado.", 404)

            pedido_actual = pedido_existente_resp.get('data')
            if pedido_actual.get('estado') == 'CANCELADO':
                return self.error_response("Este pedido ya ha sido cancelado.", 400)

            # 2. Liberar el stock reservado
            liberacion_result = self.lote_producto_controller.liberar_stock_por_cancelacion_de_pedido(pedido_id)
            if not liberacion_result.get('success'):
                error_msg = liberacion_result.get('error', 'Error desconocido al liberar el stock.')
                logger.error(f"Fallo crítico al cancelar pedido {pedido_id}: No se pudo liberar el stock. Error: {error_msg}")
                # A pesar del fallo, se continúa para marcar el pedido como cancelado, pero se advierte del problema.
                return self.error_response(f"No se pudo liberar el stock, pero el pedido se marcará como cancelado. Contacte a soporte. Error: {error_msg}", 500)

            # 3. Cambiar el estado del pedido a 'CANCELADO'
            result = self.model.cambiar_estado(pedido_id, 'CANCELADO')
            if result.get('success'):
                detalle = f"Se canceló el pedido de venta con ID: {pedido_id}."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de venta', 'Cancelación', detalle)
                return self.success_response(message="Pedido cancelado con éxito y stock liberado.")
            else:
                return self.error_response(result.get('error', 'El stock fue liberado, pero no se pudo cambiar el estado del pedido.'), 500)
        except Exception as e:
            logger.error(f"Error interno en cancelar_pedido: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def obtener_datos_para_formulario(self) -> tuple:
        """
        Obtiene los datos necesarios para popular los menús desplegables
        en el formulario de creación/edición de pedidos.
        Filtra para devolver solo los productos ACTIVOS.
        """
        try:
            # --- FIX: Añadir filtro para obtener solo productos activos ---
            productos_result = self.producto_model.find_all(filters={'activo': True}, order_by='nombre')
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
        Verifica si la cantidad total producida por las OPs (padre e hijas)
        cubre la cantidad requerida por el pedido y actualiza el estado en consecuencia.
        """
        from decimal import Decimal
        from app.models.orden_produccion import OrdenProduccionModel

        try:
            pedido_resp, _ = self.obtener_pedido_por_id(pedido_id)
            if not pedido_resp.get('success'):
                logger.error(f"No se pudo encontrar el pedido {pedido_id} para actualizar estado.")
                return

            logger.info(f"Verificando estado de producción para el pedido {pedido_id}.")
            pedido_data = pedido_resp.get('data')
            todos_los_items = pedido_data.get('items', [])

            if not todos_los_items:
                logger.info(f"El pedido {pedido_id} no tiene ítems. No se cambia el estado.")
                return
            
            # 1. Calcular la cantidad total requerida por el pedido.
            cantidad_total_requerida = sum(Decimal(item.get('cantidad', 0)) for item in todos_los_items if item.get('estado') != 'ALISTADO')

            # Si todos los items ya están alistados (de stock), no hay nada que producir.
            if cantidad_total_requerida == 0:
                if pedido_data.get('estado') not in ['LISTO_PARA_ENTREGA', 'EN_TRANSITO', 'COMPLETADO', 'CANCELADO']:
                     self.model.cambiar_estado(pedido_id, 'LISTO_PARA_ENTREGA')
                     logger.info(f"Todos los items del pedido {pedido_id} son de stock y están alistados. Pedido actualizado a 'LISTO PARA ENTREGAR'.")
                return

            # 2. Obtener todas las OPs padres únicas asociadas al pedido.
            op_padres_ids = {item['orden_produccion_id'] for item in todos_los_items if item.get('orden_produccion_id')}

            if not op_padres_ids:
                 logger.info(f"Pedido {pedido_id} no tiene OPs asociadas para verificar producción.")
                 return

            # 3. Calcular la cantidad total producida sumando las OPs padre y sus hijas.
            op_model = OrdenProduccionModel()
            cantidad_total_producida = Decimal('0')
            algun_item_en_proceso = False

            for op_padre_id in op_padres_ids:
                op_padre_res = op_model.find_by_id(op_padre_id)
                if op_padre_res.get('success') and op_padre_res.get('data'):
                    op_padre_data = op_padre_res['data']
                    cantidad_total_producida += Decimal(op_padre_data.get('cantidad_producida', '0'))
                    if op_padre_data.get('estado') not in ['PENDIENTE', 'COMPLETADA', 'CANCELADA']:
                        algun_item_en_proceso = True
                
                ops_hijas_res = op_model.find_all(filters={'id_op_padre': op_padre_id})
                if ops_hijas_res.get('success') and ops_hijas_res.get('data'):
                    for op_hija in ops_hijas_res['data']:
                        cantidad_total_producida += Decimal(op_hija.get('cantidad_producida', '0'))
                        if op_hija.get('estado') not in ['PENDIENTE', 'COMPLETADA', 'CANCELADA']:
                            algun_item_en_proceso = True

            logger.info(f"Pedido {pedido_id}: Cantidad Requerida={cantidad_total_requerida}, Cantidad Producida (total)={cantidad_total_producida}")

            # 4. Actualizar el estado del pedido basándose en las cantidades.
            if cantidad_total_producida >= cantidad_total_requerida:
                if pedido_data.get('estado') not in ['LISTO_PARA_ENTREGA', 'EN_TRANSITO', 'COMPLETADO', 'CANCELADO']:
                    self.model.cambiar_estado(pedido_id, 'LISTO_PARA_ENTREGA')
                    logger.info(f"La producción ha cubierto la demanda para el pedido {pedido_id}. Actualizado a 'LISTO_PARA_ENTREGA'.")
            else:
                if algun_item_en_proceso and pedido_data.get('estado') not in ['EN_PROCESO', 'LISTO_PARA_ENTREGA', 'EN_TRANSITO', 'COMPLETADO', 'CANCELADO']:
                    self.model.cambiar_estado(pedido_id, 'EN_PROCESO')
                    logger.info(f"La producción ha iniciado pero no es suficiente para el pedido {pedido_id}. Actualizado a 'EN_PROCESO'.")

        except Exception as e:
            logger.error(f"Error crítico actualizando el estado del pedido {pedido_id} según la cantidad producida: {e}", exc_info=True)

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
                detalle = f"El pedido de venta con ID: {pedido_id} fue planificado."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de venta', 'Planificación', detalle)
                return self.success_response(message="Pedido planificado con éxito.")
            else:
                logger.error(f"Error al planificar pedido {pedido_id}: {result.get('error')}")
                return self.error_response(result.get('error', 'Error al actualizar el estado del pedido.'), 500)
        except Exception as e:
            logger.error(f"Error interno en planificar_pedido: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def despachar_pedido(self, pedido_id: int, form_data: Optional[Dict] = None, dry_run: bool = False) -> tuple:
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

            # 2. Si se proveen datos de formulario (despacho individual), crear el registro de despacho.
            if form_data:
                nombre_transportista = form_data.get('conductor_nombre', '').strip()
                dni_transportista = form_data.get('conductor_dni', '').strip()
                patente_vehiculo = form_data.get('vehiculo_patente', '').strip()
                telefono_transportista = form_data.get('conductor_telefono', '').strip()
                observaciones = form_data.get('observaciones', '').strip()

                if not all([nombre_transportista, dni_transportista, patente_vehiculo, telefono_transportista]):
                     return self.error_response('Todos los campos del transportista y vehículo son requeridos.', 400)

                datos_despacho = {
                    'id_pedido': pedido_id,
                    'nombre_transportista': nombre_transportista,
                    'dni_transportista': dni_transportista,
                    'patente_vehiculo': patente_vehiculo,
                    'telefono_transportista': telefono_transportista,
                    'observaciones': observaciones if observaciones else None
                }
                resultado_despacho = self.despacho.create(datos_despacho)
                if not resultado_despacho.get('success'):
                    return self.error_response(resultado_despacho.get('error', 'Error al guardar los datos del despacho.'), 500)

            # 4. *** Consumir el stock reservado ANTES de cualquier otra acción ***
            logger.info(f"Consumiendo stock reservado para el pedido {pedido_id}...")
            consumo_result = self.lote_producto_controller.despachar_stock_reservado_por_pedido(pedido_id, dry_run=dry_run)

            if dry_run:
                # En modo dry_run, si el consumo fue exitoso, devolvemos éxito sin cambiar estado.
                return self.success_response(message="Verificación de stock exitosa.")

            if not consumo_result.get('success'):
                error_msg = consumo_result.get('error', 'No se pudo consumir el stock reservado.')
                logger.error(f"Fallo crítico al despachar pedido {pedido_id}: {error_msg}")
                # Si el consumo de stock falla, no se debe continuar con el despacho.
                return self.error_response(f"Error al despachar: {error_msg}", 500)

            logger.info(f"Stock para el pedido {pedido_id} consumido exitosamente.")

            # 6. Actualizar el estado del pedido a 'EN_TRANSITO'
            cambio_estado_result = self.model.cambiar_estado(pedido_id, 'EN_TRANSITO')

            if cambio_estado_result.get('success'):
                logger.info(f"Pedido {pedido_id} cambiado a estado 'EN_TRANSITO' con éxito.")
                # FIX: Usar el ID del pedido como fallback si codigo_ov no está disponible.
                identificador_pedido = pedido_actual.get('codigo_ov') or f'ID {pedido_id}'
                detalle = f"El pedido de venta {identificador_pedido} fue despachado."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de venta', 'Despacho', detalle)
                return self.success_response(message="Pedido despachado con éxito.")
            else:
                # En un caso real, aquí se debería considerar revertir la creación del despacho y el consumo de stock (transacción)
                error_msg_update = cambio_estado_result.get('error', 'Error desconocido al actualizar estado del pedido.')
                logger.error(f"Error al despachar pedido {pedido_id} después de guardar despacho: {error_msg_update}")
                return self.error_response(f"El despacho fue registrado y el stock consumido, pero no se pudo actualizar el estado del pedido. Error: {error_msg_update}", 500)


        except Exception as e:
            logger.error(f"Error interno en despachar_pedido: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def despachar_pedido_completo(self, pedido_id: int) -> tuple:
        """
        Orquesta el proceso completo de despacho de un pedido.
        1. Consume el stock reservado.
        2. Cambia el estado del pedido a 'EN_TRANSITO'.
        """
        # 1. Consumir stock reservado
        consumir_stock_response = self.lote_producto_controller.despachar_stock_reservado_por_pedido(pedido_id)
        if not consumir_stock_response.get('success'):
            return self.error_response(consumir_stock_response.get('error', 'No se pudo consumir el stock reservado.'), 500)

        # 2. Cambiar estado del pedido
        return self.cambiar_estado_pedido(pedido_id, 'EN_TRANSITO')

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

    def registrar_pago(self, pedido_id: int, pago_data: Dict, file) -> tuple:
        """
        Registra el pago de un pedido y recalcula el estado crediticio del cliente.
        """
        try:
            pedido_result = self.model.find_by_id(pedido_id, 'id')
            if not pedido_result.get('success'):
                return self.error_response("Pedido no encontrado.", 404)

            pedido = pedido_result['data']
            if pedido.get('estado_pago') == 'pagado':
                return self.error_response("Este pedido ya ha sido marcado como pagado.", 400)

            update_data = {'estado_pago': 'pagado'}

            if file:
                bucket_name = 'comprobantes-pago'
                destination_path = f"pedido_{pedido_id}/{file.filename}"
                upload_result, status_code = self.storage_controller.upload_file(file, bucket_name, destination_path)
                if status_code != 200:
                    return self.error_response("Error al subir el comprobante de pago.", 500)
                update_data['comprobante_pago_url'] = upload_result['url']


            update_result = self.model.update(pedido_id, update_data, 'id')

            if not update_result.get('success'):
                return self.error_response("Error al actualizar el estado del pago.", 500)

            id_cliente = pedido.get('id_cliente')
            if id_cliente:
                self._recalcular_estado_crediticio_cliente(id_cliente)

            return self.success_response(message="Pago registrado y estado crediticio actualizado.")

        except Exception as e:
            logger.error(f"Error registrando pago para el pedido {pedido_id}: {e}", exc_info=True)
            return self.error_response("Error interno del servidor.", 500)

    def _recalcular_estado_crediticio_cliente(self, cliente_id: int):
        """
        Recalcula el estado crediticio de un cliente basándose en sus pedidos vencidos.
        """
        try:
            pedidos_vencidos_result = self.model.find_all({'id_cliente': cliente_id, 'estado_pago': 'vencido'})
            if pedidos_vencidos_result.get('success'):
                conteo_vencidos = len(pedidos_vencidos_result['data'])

                umbral_alertado = Config.CREDIT_ALERT_THRESHOLD

                nuevo_estado = 'alertado' if conteo_vencidos > umbral_alertado else 'normal'

                cliente_actual = self.cliente_model.find_by_id(cliente_id)
                if cliente_actual.get('success') and cliente_actual['data'].get('estado_crediticio') != nuevo_estado:
                    self.cliente_model.update(cliente_id, {'estado_crediticio': nuevo_estado}, 'id')
                    logger.info(f"Estado crediticio del cliente {cliente_id} actualizado a '{nuevo_estado}'.")
        except Exception as e:
            logger.error(f"Error recalculando estado crediticio para el cliente {cliente_id}: {e}", exc_info=True)

    def marcar_pedidos_vencidos(self) -> int:
        """
        Busca todos los pedidos pendientes con fecha de vencimiento pasada y los marca como 'vencido'.
        Devuelve el número de pedidos actualizados.
        """
        try:
            today = date.today()
            # Supabase no soporta (o al menos no es directo) queries de actualización con filtros complejos.
            # Por lo tanto, obtenemos los IDs primero y luego actualizamos.
            pedidos_a_vencer_result = self.model.db.table(self.model.get_table_name()) \
                .select('id') \
                .eq('estado_pago', 'pendiente') \
                .lt('fecha_vencimiento', today.isoformat()) \
                .execute()

            if not pedidos_a_vencer_result.data:
                return 0

            ids_a_actualizar = [p['id'] for p in pedidos_a_vencer_result.data]

            if ids_a_actualizar:
                update_result = self.model.db.table(self.model.get_table_name()) \
                    .update({'estado_pago': 'vencido'}) \
                    .in_('id', ids_a_actualizar) \
                    .execute()
                return len(update_result.data)
            return 0
        except Exception as e:
            logger.error(f"Error marcando pedidos como vencidos: {e}", exc_info=True)
            return 0

    def generar_enlace_seguimiento(self, pedido_id: int) -> tuple:
        """
        Genera un enlace de seguimiento firmado para un pedido específico.
        """
        try:
            # El token contendrá el ID del pedido para verificarlo después
            token = generate_signed_token({'pedido_id': pedido_id})
            # La URL se construirá en el template con url_for, aquí solo devolvemos el token
            return self.success_response(data={'token': token})
        except Exception as e:
            logger.error(f"Error generando enlace de seguimiento para pedido {pedido_id}: {e}", exc_info=True)
            return self.error_response("No se pudo generar el enlace de seguimiento.", 500)

    def enviar_qr_por_email(self, pedido_id: int) -> tuple:
        """
        Genera un código QR para el seguimiento de un pedido y lo envía por correo al cliente.
        """
        from flask import render_template, url_for
        from app.services.email_service import send_email
        import qrcode
        import io
        import base64

        try:
            # 1. Obtener datos del pedido
            pedido_resp, _ = self.obtener_pedido_por_id(pedido_id)
            if not pedido_resp.get('success'):
                return self.error_response("Pedido no encontrado.", 404)
            pedido = pedido_resp.get('data')

            # 2. Obtener datos del cliente
            cliente_id = pedido.get('id_cliente')
            cliente_resp = self.cliente_model.find_by_id(cliente_id)
            if not cliente_resp.get('success'):
                return self.error_response("Cliente asociado al pedido no encontrado.", 404)
            cliente = cliente_resp.get('data')
            cliente_email = cliente.get('email')
            cliente_nombre = cliente.get('nombre', 'Cliente')

            if not cliente_email:
                return self.error_response("El cliente no tiene una dirección de correo electrónico registrada.", 400)

            # 3. Generar la URL de seguimiento público con Token
            token_resp, _ = self.generar_enlace_seguimiento(pedido_id)
            if not token_resp.get('success'):
                return self.error_response("No se pudo generar el token de seguimiento para el correo.", 500)

            token = token_resp['data']['token']
            # --- CORRECCIÓN: Construir la URL manualmente para evitar error de contexto ---
            base_url = request.host_url
            url_seguimiento = f"{base_url}public/seguimiento/{token}"

            # --- CÁLCULO DEL SUBTOTAL Y TOTAL ---
            total_pedido = 0
            for item in pedido.get('items', []):
                precio = item.get('producto_nombre', {}).get('precio_unitario', 0)
                cantidad = item.get('cantidad', 0)
                subtotal = precio * cantidad
                item['subtotal'] = subtotal
                total_pedido += subtotal

            # Añadir el total calculado al diccionario principal del pedido
            pedido['total'] = total_pedido
            # --- FIN CÁLCULO ---

            # 4. Generar el código QR en memoria
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
            qr.add_data(url_seguimiento)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            qr_data_uri = f"data:image/png;base64,{img_base64}"

            # 5. Formatear fecha y renderizar la plantilla del correo
            fecha_estimada = pedido.get('fecha_requerido')
            fecha_formateada = ''
            if fecha_estimada:
                try:
                    # La fecha viene como 'YYYY-MM-DD'
                    fecha_obj = datetime.strptime(fecha_estimada, '%Y-%m-%d')
                    fecha_formateada = fecha_obj.strftime('%d/%m/%Y')
                except (ValueError, TypeError):
                    fecha_formateada = fecha_estimada # Fallback por si el formato cambia

            body_html = render_template(
                'emails/qr_pedido_cliente.html',
                cliente_nombre=cliente_nombre,
                pedido=pedido,
                url_seguimiento=url_seguimiento,
                qr_data_uri=qr_data_uri,
                fecha_estimada_entrega=fecha_formateada,
                current_year=datetime.now().year
            )

            asunto = f"Seguimiento de tu pedido #{pedido.get('codigo_ov', pedido_id)}"

            # 6. Enviar el correo
            email_sent, email_error = send_email(cliente_email, asunto, body_html)

            if not email_sent:
                logger.error(f"Error al enviar email de seguimiento para pedido {pedido_id}: {email_error}")
                return self.error_response(f"No se pudo enviar el correo: {email_error}", 500)

            # 7. Registrar la acción
            self.registro_controller.crear_registro(
                get_current_user(),
                'Ordenes de venta',
                'Envío de QR',
                f"Se envió el código QR de seguimiento por email para el pedido ID: {pedido_id}."
            )

            return self.success_response(message="Correo con el código de seguimiento enviado exitosamente.")

        except Exception as e:
            logger.error(f"Error interno en enviar_qr_por_email para pedido {pedido_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    def actualizar_estado_segun_items(self, pedido_id: int):
        """
        Verifica si todos los items de un pedido han sido completamente asignados
        desde producción. Si es así, actualiza el estado del pedido.
        """
        try:
            items_res = self.model.find_all_items({'pedido_id': pedido_id})
            if not items_res.get('success') or not items_res.get('data'):
                logger.warning(f"No se encontraron items para el pedido {pedido_id} al verificar estado post-asignación.")
                return

            todos_los_items = items_res.get('data', [])
            if not todos_los_items:
                return # No hay items, no hay nada que hacer.

            from app.models.asignacion_pedido_model import AsignacionPedidoModel
            asignacion_model = AsignacionPedidoModel()

            todos_completos = True
            for item in todos_los_items:
                asignaciones_res = asignacion_model.find_all({'pedido_item_id': item['id']})
                total_asignado = sum(Decimal(a['cantidad_asignada']) for a in asignaciones_res.get('data', []))
                
                if total_asignado < Decimal(item['cantidad']):
                    todos_completos = False
                    break
            
            if todos_completos:
                pedido_actual = self.model.find_by_id(pedido_id, 'id')['data']
                if pedido_actual and pedido_actual.get('estado') not in ['LISTO_PARA_ENTREGA', 'EN_TRANSITO', 'COMPLETADO', 'CANCELADO']:
                    self.model.cambiar_estado(pedido_id, 'LISTO_PARA_ENTREGA')
                    logger.info(f"Todos los items del pedido {pedido_id} están completos. Estado actualizado a LISTO_PARA_ENTREGA.")

        except Exception as e:
            logger.error(f"Error al actualizar estado del pedido {pedido_id} según items: {e}", exc_info=True)
    def _intentar_reasignar_stock(self, producto_id: int, cantidad_necesaria: int, fecha_limite_urgente: date) -> int:
        """
        Intenta liberar stock de pedidos menos urgentes.
        """
        cantidad_recuperada = 0
        fecha_limite_str = fecha_limite_urgente.isoformat()

        logger.info("="*50)
        logger.info(f"[ARBITRAJE] INICIO para Producto ID: {producto_id}")
        logger.info(f"[ARBITRAJE] Objetivo: Recuperar {cantidad_necesaria} unidades.")
        logger.info(f"[ARBITRAJE] Condición: Robar a pedidos con fecha de entrega > {fecha_limite_str}")

        reservas_candidatas = []

        try:
            # Consulta directa a la base de datos
            # Buscamos reservas ACTIVAS (RESERVADO) de pedidos FUTUROS
            response = self.reserva_producto_model.db.table('reservas_productos') \
                .select('id, cantidad_reservada, pedido_id, pedido_item_id, lotes_productos!inner(producto_id), pedidos!inner(id, fecha_requerido)') \
                .eq('lotes_productos.producto_id', producto_id) \
                .eq('estado', 'RESERVADO') \
                .gt('pedidos.fecha_requerido', fecha_limite_str) \
                .order('fecha_requerido', desc=True, foreign_table='pedidos') \
                .execute()

            reservas_candidatas = response.data if response.data else []
            logger.info(f"[ARBITRAJE] Consulta DB Exitosa. Candidatos encontrados: {len(reservas_candidatas)}")

        except Exception as e:
            logger.error(f"[ARBITRAJE] ERROR CRÍTICO en la consulta DB: {e}", exc_info=True)
            return 0

        if not reservas_candidatas:
            logger.warning("[ARBITRAJE] No hay víctimas disponibles (nadie tiene fecha posterior a la urgente).")
            return 0

        # Iteramos las reservas encontradas
        for i, reserva in enumerate(reservas_candidatas):
            logger.info(f"--- Procesando Candidato #{i+1} ---")
            logger.info(f"Datos Reserva: {reserva}")

            # 1. Verificar si ya tenemos suficiente
            if cantidad_recuperada >= cantidad_necesaria:
                logger.info(f"[ARBITRAJE] Meta alcanzada ({cantidad_recuperada} >= {cantidad_necesaria}). Deteniendo robo.")
                break

            # --- CORRECCIÓN DE IDENTACIÓN AQUÍ ---
            # El código a continuación estaba dentro del 'if', por eso no se ejecutaba.

            cantidad_a_liberar = float(reserva.get('cantidad_reservada', 0))
            pedido_afectado_id = reserva.get('pedido_id')
            item_afectado_id = reserva.get('pedido_item_id')
            reserva_id = reserva.get('id')

            logger.info(f"[ARBITRAJE] Intentando quitar {cantidad_a_liberar} u. al Pedido {pedido_afectado_id} (Item {item_afectado_id})")

            # 2. Liberar la reserva
            exito_liberacion = self.lote_producto_controller.liberar_reserva_especifica(reserva_id)

            if exito_liberacion:
                cantidad_recuperada += cantidad_a_liberar
                logger.info(f"[ARBITRAJE] Liberación exitosa. Acumulado recuperado: {cantidad_recuperada}")

                # 3. Actualizar el pedido afectado (La Víctima)
                if item_afectado_id:
                    try:
                        # CORRECCIÓN BASADA EN TU SCHEMA:
                        # Tu tabla 'pedido_items' no tiene columnas para cantidades divididas.
                        # Solo cambiamos el estado. Al pasar a 'PENDIENTE_PRODUCCION',
                        # el sistema entenderá que la 'cantidad' total debe producirse (o buscarse de nuevo).

                        update_payload = {
                            'estado': 'PENDIENTE_PRODUCCION'
                        }

                        self.model.update_item(item_afectado_id, update_payload)
                        logger.info(f"[ARBITRAJE] VICTIMA ACTUALIZADA: Item {item_afectado_id} pasado a PENDIENTE_PRODUCCION.")

                    except Exception as update_error:
                         logger.error(f"[ARBITRAJE] Error actualizando item víctima {item_afectado_id}: {update_error}")
            else:
                logger.error(f"[ARBITRAJE] Falló la liberación de la reserva {reserva_id} en LoteProductoController.")

        logger.info(f"[ARBITRAJE] FIN DEL PROCESO. Total recuperado: {cantidad_recuperada}")
        logger.info("="*50)

        return cantidad_recuperada
