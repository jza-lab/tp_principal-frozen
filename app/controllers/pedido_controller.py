# app/controllers/pedido_controller.py
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

            # Primero, obtenemos el diccionario anidado de la dirección.
            direccion_payload = form_data.get('direccion_entrega', {})
            
            # Ahora, extraemos los datos de ESE diccionario anidado.
            direccion_data = {
                'calle': direccion_payload.get('calle'),
                'altura': direccion_payload.get('altura'),
                'provincia': direccion_payload.get('provincia'),
                'localidad': direccion_payload.get('localidad'),
                'piso': direccion_payload.get('piso'),
                'depto': direccion_payload.get('depto'),
                'codigo_postal': direccion_payload.get('codigo_postal')
            }
            direccion_id = self._get_or_create_direccion(direccion_data)
            
            # Añadimos el id de la dirección al payload principal para la validación/creación.
            form_data['id_direccion_entrega'] = direccion_id
            form_data.pop('direccion_entrega', None)
            
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
                        return self.success_response(
                            data={**nuevo_pedido, 'estado_completado_inmediato': True}, # <--- INDICADOR ESPECIAL
                            message="Pedido creado, stock reservado y despachado con éxito.", 
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

    def aprobar_pedido(self, pedido_id: int, usuario_id: int) -> tuple:
        """
        Aprueba un pedido, realiza la lógica de stock y producción/compra requerida.
        (Ahora mueve a LISTO_PARA_ENTREGA si todo el stock está disponible).
        """
        try:
            # 1. Obtener pedido y verificar estado
            pedido_resp, _ = self.obtener_pedido_por_id(pedido_id)
            if not pedido_resp.get('success'):
                return self.error_response("Pedido no encontrado.", 404)
            pedido_actual = pedido_resp['data']
            if pedido_actual.get('estado') != 'PENDIENTE':
                return self.error_response("Este pedido ya ha sido aprobado o está en proceso.", 400)

            items_del_pedido = pedido_actual.get('items', [])
            ordenes_creadas_oc_branch = []
            insumos_faltantes_global = []

            # Diccionario para almacenar la cantidad faltante de producto para OP (solo para items que requieren OP)
            items_a_producir = {}

            # --- BUCLE DE VERIFICACIÓN (Dry Run: SOLO busca si necesita OC y guarda OP necesaria) ---
            for item in items_del_pedido:
                # 2. Verificar stock de PRODUCTO TERMINADO (sin reservarlo aún)
                stock_response, _ = self.lote_producto_controller.obtener_stock_producto(item['producto_id'])
                stock_disponible = stock_response.get('data', {}).get('stock_total', 0)
                cantidad_faltante_producto = item['cantidad'] - stock_disponible
                
                # Si no falta producto, continuamos.
                if cantidad_faltante_producto <= 0:
                    continue
                
                # Registrar el faltante para una posible OP
                items_a_producir[item['id']] = {
                    'cantidad': cantidad_faltante_producto,
                    'producto_id': item['producto_id'],
                    'item_id': item['id']
                }

                # 3. Si el PRODUCTO TERMINADO falta, chequear stock de INSUMOS.
                receta_result = self.receta_model.find_all({'producto_id': item['producto_id'], 'activa': True}, limit=1)
                if not receta_result.get('success') or not receta_result.get('data'):
                    logging.warning(f"Producto {item['producto_id']} sin receta. Imposible generar OP/OC.")
                    continue
                
                receta = receta_result['data'][0]
                
                # 3b. Simular OP para chequear insumos
                orden_simulada = {
                    'id': 0, # Placeholder
                    'receta_id': receta['id'],
                    'cantidad_planificada': cantidad_faltante_producto
                }
                verificacion_insumos = self.orden_produccion_controller.verificar_stock_para_op(orden_simulada) 

                if not verificacion_insumos.get('success'):
                    return self.error_response(f"Error del sistema al verificar stock de insumos para {item['producto_id']}.", 500)
                
                insumos_faltantes_item = verificacion_insumos['data']['insumos_faltantes']
                
                if insumos_faltantes_item:
                    # 4. Si FALTAN INSUMOS: Acumular la lista de faltantes
                    insumos_faltantes_global.extend(insumos_faltantes_item)
            
            # --- LÓGICA DE OC NECESARIA (Y CREACIÓN DE OP REQUERIDA) ---
            if insumos_faltantes_global:
                # 5. Consolidar insumos faltantes para una única OC
                # ... (código para consolidar insumos) ...
                insumos_consolidados_oc = {}
                for faltante in insumos_faltantes_global:
                    insumo_id = faltante['insumo_id']
                    if insumo_id in insumos_consolidados_oc:
                        insumos_consolidados_oc[insumo_id]['cantidad_faltante'] += faltante['cantidad_faltante']
                    else:
                        insumos_consolidados_oc[insumo_id] = faltante
                
                insumos_final_oc = list(insumos_consolidados_oc.values())

                # 6. Crear la Orden de Compra (OC)
                resultado_oc = self.orden_produccion_controller.generar_orden_de_compra_automatica(insumos_final_oc, usuario_id)

                # FIX DE ROBUSTEZ: Asegurarse de que el resultado de la OC sea un diccionario.
                resultado_oc_dict = resultado_oc[0] if isinstance(resultado_oc, tuple) else resultado_oc

                if not resultado_oc_dict.get('success'):
                    # Si falla, devolvemos el error de la OC
                    return self.error_response(f"Fallo al crear la Orden de Compra: {resultado_oc_dict.get('error')}", 500)
                
                orden_compra_creada = resultado_oc_dict.get('data')
                oc_codigo = orden_compra_creada.get('codigo_oc', 'N/A')

                # 7. CREAR LA ORDEN DE PRODUCCIÓN (OP) PARA TODOS LOS FALTANTES
                for item_id, data in items_a_producir.items():
                    # ... (código para crear OP y actualizar item a EN_PRODUCCION) ...
                    receta_result = self.receta_model.find_all({'producto_id': data['producto_id'], 'activa': True}, limit=1)
                    if not receta_result.get('success') or not receta_result.get('data'):
                        logging.warning(f"No se pudo crear OP para {data['producto_id']} - Receta no encontrada en el flujo OC.")
                        continue
                    
                    # Crear la Orden de Producción (OP) en estado PENDIENTE
                    datos_orden = {
                        'producto_id': data['producto_id'],
                        'cantidad': data['cantidad'],
                        'fecha_planificada': date.today().isoformat(),
                        'prioridad': 'ALTA' # Prioridad Alta por falta de stock
                    }
                    resultado_op = self.orden_produccion_controller.crear_orden(datos_orden, usuario_id)
                    resultado_op_dict = resultado_op[0] if isinstance(resultado_op, tuple) else resultado_op
                    
                    if resultado_op_dict.get('success'):
                        orden_creada = resultado_op_dict.get('data', {})
                        ordenes_creadas_oc_branch.append(orden_creada)
                        
                        # Actualizar el ítem de pedido para vincularlo a la OP (Estado EN_PRODUCCION)
                        self.model.update_item(data['item_id'], {
                            'estado': 'EN_PRODUCCION',
                            'orden_produccion_id': orden_creada.get('id')
                        })
                    else:
                        logging.error(f"Fallo al crear la OP para {data['producto_id']} en flujo OC: {resultado_op_dict.get('error')}")


                msg = f"Se generó la Orden de Compra {oc_codigo} y {len(ordenes_creadas_oc_branch)} Órdenes de Producción. El pedido de venta queda PENDIENTE."
                
                # 8. Devolver respuesta especial para OC (Status 202)
                return self.success_response(
                    data={'orden_compra_creada': orden_compra_creada, 'oc_generada': True, 'ordenes_produccion_creadas': ordenes_creadas_oc_branch},
                    message=msg,
                    status_code=202
                )

            # --- LÓGICA DE RESERVA FINAL (NO FALTARON INSUMOS) ---

            ordenes_creadas_op_branch = []
            todos_alistados = True
            
            for item in items_del_pedido:
                # Reserva de producto terminado
                reserva_result_final = self.lote_producto_controller.reservar_stock_para_item(
                    pedido_id=pedido_id,
                    pedido_item_id=item['id'],
                    producto_id=item['producto_id'],
                    cantidad_necesaria=item['cantidad'],
                    usuario_id=usuario_id
                )
                cantidad_faltante = reserva_result_final['data']['cantidad_faltante']
                
                if cantidad_faltante > 0:
                    todos_alistados = False # Falla en alistar
                    
                    # Producto falta, pero insumos OK (ya se comprobó) -> Crear OP
                    receta_result = self.receta_model.find_all({'producto_id': item['producto_id'], 'activa': True}, limit=1)
                    if not receta_result.get('success') or not receta_result.get('data'):
                        logging.warning(f"No se pudo crear OP para {item['producto_id']} - Receta no encontrada.")
                        self.model.update_item(item['id'], {'estado': 'PENDIENTE'})
                        continue
                    
                    # Crear la Orden de Producción (OP)
                    datos_orden = {
                        'producto_id': item['producto_id'],
                        'cantidad': cantidad_faltante,
                        'fecha_planificada': date.today().isoformat(),
                        'prioridad': 'NORMAL' 
                    }

                    resultado_op = self.orden_produccion_controller.crear_orden(datos_orden, usuario_id)

                    resultado_op_dict = resultado_op[0] if isinstance(resultado_op, tuple) else resultado_op
                    
                    if resultado_op_dict.get('success'):
                        orden_creada = resultado_op_dict.get('data', {})
                        ordenes_creadas_op_branch.append(orden_creada)
                        self.model.update_item(item['id'], {
                            'estado': 'EN_PRODUCCION',
                            'orden_produccion_id': orden_creada.get('id')
                        })
                    else:
                        logging.error(f"No se pudo crear la OP para el producto {item['producto_id']}. Error: {resultado_op_dict.get('error')}")
                        self.model.update_item(item['id'], {'estado': 'PENDIENTE'})
                        
                else:
                    # Todo en stock, item marcado como ALISTADO/RESERVADO
                    self.model.update_item(item['id'], {'estado': 'ALISTADO'})
            
            # 9. Determinar el estado final del pedido (CAMBIO CLAVE AQUÍ)
            if todos_alistados:
                 # Si todos los ítems fueron reservados, movemos a LISTO_PARA_ENTREGA
                nuevo_estado_pedido = 'LISTO_PARA_ENTREGA'
            elif ordenes_creadas_op_branch:
                # Si se crearon OPs, el pedido pasa a EN_PRODUCCION
                nuevo_estado_pedido = 'EN_PRODUCCION'
            else:
                 # Si no se pudo alistar todo y no se creó OP (ej. falta receta), pasa a APROBADO
                nuevo_estado_pedido = 'APROBADO'
                
            self.model.cambiar_estado(pedido_id, nuevo_estado_pedido) # Aplicar el nuevo estado


            msg = f"Pedido {nuevo_estado_pedido} con éxito."
            if ordenes_creadas_op_branch:
                msg += f" Se generaron {len(ordenes_creadas_op_branch)} Órdenes de Producción."

            return self.success_response(data={'ordenes_creadas': ordenes_creadas_op_branch}, message=msg) #

        except Exception as e:
            logging.error(f"Error en aprobar_pedido: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500) #

    def actualizar_pedido_con_items(self, pedido_id: int, form_data: Dict) -> tuple:
        """
        Valida y actualiza un pedido existente y sus items.
        """
        try:
            if 'items-TOTAL_FORMS' in form_data:
                form_data.pop('items-TOTAL_FORMS')
            if 'items' in form_data:
                form_data['items'] = self._consolidar_items(form_data['items'])

            items_data = form_data.pop('items')
            pedido_data = form_data
            
            direccion_payload = form_data.get('direccion_entrega', {})
            direccion_data = {
                'calle': direccion_payload.get('calle'),
                'altura': direccion_payload.get('altura'),
                'provincia': direccion_payload.get('provincia'),
                'localidad': direccion_payload.get('localidad'),
                'piso': direccion_payload.get('piso'),
                'depto': direccion_payload.get('depto'),
                'codigo_postal': direccion_payload.get('codigo_postal')
            }

            pedido_actual_resp, estado= self.obtener_pedido_por_id(pedido_id)
            pedido_actual = pedido_actual_resp.get('data')

            id_direccion_vieja = pedido_actual['id_direccion_entrega']
            

            if(id_direccion_vieja):
                cantidad_misma_direccion = self.model.contar_pedidos_direccion(id_direccion_vieja)

                if(cantidad_misma_direccion>1):
                    direccion_id = self._get_or_create_direccion(direccion_data)
                    if direccion_id:
                            pedido_data['direccion_id'] = direccion_id
                else:
                    self._actualizar_direccion(id_direccion_vieja, direccion_data)
                    pedido_data['direccion_id'] = id_direccion_vieja
            else:
                direccion_id = self._get_or_create_direccion(direccion_data)
                if direccion_id:
                    pedido_data['direccion_id'] = direccion_id
            
            form_data['id_direccion_entrega'] = direccion_id
            form_data.pop('direccion_entrega', None)
            
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
        
    def completar_pedido(self, pedido_id: int, usuario_id: int) -> tuple:
        """
        Completa el pedido, descontando el stock directamente de los lotes de producto
        y cambiando el estado a 'COMPLETADO', ignorando el registro de reservas.
        """
        try:
            # 1. Obtener pedido y verificar estado
            pedido_resp, _ = self.obtener_pedido_por_id(pedido_id) #
            if not pedido_resp.get('success'):
                return self.error_response("Pedido no encontrado.", 404)
            pedido_actual = pedido_resp['data']

            if pedido_actual.get('estado') == 'COMPLETADO':
                return self.error_response("El pedido ya está en estado 'COMPLETADO'.", 400) #

            if pedido_actual.get('estado') != 'LISTO_PARA_ENTREGA':
                return self.error_response(f"El pedido debe estar en estado 'LISTO PARA ENTREGA' (actual: {pedido_actual['estado']}) para ser completado.", 400) #

            # 2. Despachar/Consumir stock directamente de los lotes
            items_del_pedido = pedido_actual.get('items', [])
            
            # **CAMBIO CLAVE: Usar la nueva función de despacho directo**
            despacho_result = self.lote_producto_controller.despachar_stock_directo_por_pedido(
                pedido_id=pedido_id,
                items_del_pedido=items_del_pedido # Le pasamos los ítems del pedido
            ) 

            if not despacho_result.get('success'):
                 # Si el despacho falla, se detiene y reporta el error.
                return self.error_response(f"Fallo al despachar el stock: {despacho_result.get('error')}", 500) #

            # 3. Cambiar estado final
            result = self.model.cambiar_estado(pedido_id, 'COMPLETADO') #

            if result.get('success'):
                return self.success_response(
                    data=result.get('data'),
                    message="Pedido completado y stock despachado exitosamente."
                )
            else:
                return self.error_response(result.get('error', 'No se pudo completar el pedido.'), 500) #

        except Exception as e:
            logging.error(f"Error en completar_pedido: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)
        
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
