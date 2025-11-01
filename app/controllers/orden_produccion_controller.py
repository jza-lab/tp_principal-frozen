from app.controllers.base_controller import BaseController
from app.models.orden_produccion import OrdenProduccionModel
from app.schemas.orden_produccion_schema import OrdenProduccionSchema
from typing import Dict, Optional, List
from decimal import Decimal
from marshmallow import ValidationError
from app.controllers.producto_controller import ProductoController
from app.controllers.receta_controller import RecetaController
from app.controllers.usuario_controller import UsuarioController
from datetime import datetime, timedelta
import logging
import math # <--- IMPORTACIÓN NECESARIA PARA math.ceil()

# --- NUEVAS IMPORTACIONES Y DEPENDENCIAS ---
from app.controllers.inventario_controller import InventarioController
from app.controllers.orden_compra_controller import OrdenCompraController
from app.controllers.insumo_controller import InsumoController
from app.controllers.lote_producto_controller import LoteProductoController
from app.models.pedido import PedidoModel
from datetime import date
from app.models.receta import RecetaModel
from app.models.insumo import InsumoModel # Asegúrate de importar esto

logger = logging.getLogger(__name__)

class OrdenProduccionController(BaseController):
    """
    Controlador para la lógica de negocio de las Órdenes de Producción.
    """

    def __init__(self):
        super().__init__()
        self.model = OrdenProduccionModel()
        self.schema = OrdenProduccionSchema()
        self.producto_controller = ProductoController()
        self.receta_controller = RecetaController()
        self.usuario_controller = UsuarioController()
        # --- NUEVOS CONTROLADORES ---
        self.inventario_controller = InventarioController()
        self.orden_compra_controller = OrdenCompraController()
        self.insumo_controller = InsumoController()
        self.lote_producto_controller = LoteProductoController()
        self.pedido_model = PedidoModel()
        self.receta_model = RecetaModel()
        self.insumo_model = InsumoModel()


    def obtener_ordenes(self, filtros: Optional[Dict] = None) -> tuple:
        """
        Obtiene una lista de órdenes de producción, aplicando filtros.
        Devuelve una tupla en formato (datos, http_status_code).
        """
        try:
            result = self.model.get_all_enriched(filtros)

            if result.get('success'):
                return self.success_response(data=result.get('data', []))
            else:
                error_msg = result.get('error', 'Error desconocido al obtener órdenes.')
                status_code = 404 if "no encontradas" in str(error_msg).lower() else 500
                return self.error_response(error_msg, status_code)
        except Exception as e:
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def obtener_cantidad_ordenes_estado(self, estado: str, fecha: Optional[str] = None) -> Optional[Dict]:
        filtros = {'estado': estado} if estado else {}

        if fecha:
            filtros['fecha_planificada'] = fecha

        response, status_code = self.obtener_ordenes(filtros)
        if(response.get('success')):
            ordenes=response.get('data', [])
            cantidad= len(ordenes)
            return self.success_response(data={'cantidad': cantidad})
        else:
            error_msg =response.get('error', 'No se pudo contar las ordenes planificadas')
            status_code = 404 if "no encontradas" in str(error_msg).lower() else 500
            return self.error_response(error_msg, status_code)



    def obtener_orden_por_id(self, orden_id: int) -> Optional[Dict]:
        """
        Obtiene el detalle de una orden de producción específica.
        """
        result = self.model.get_one_enriched(orden_id)
        return result

    def obtener_desglose_origen(self, orden_id: int) -> Dict:
        """
        Obtiene los items de pedido que componen una orden de producción.
        """
        return self.model.obtener_desglose_origen(orden_id)

    def crear_orden(self, form_data: Dict, usuario_id: int) -> Dict:
        """
        Valida datos y crea una orden.
        MODIFICADO: Espera 'fecha_meta' en lugar de 'fecha_planificada' desde el formulario.
        """
        from app.models.receta import RecetaModel # Mover importación local si es necesario
        receta_model = RecetaModel()

        try:
            # Limpiar supervisor si viene vacío
            if 'supervisor_responsable_id' in form_data and not form_data['supervisor_responsable_id']:
                form_data.pop('supervisor_responsable_id')

            producto_id = form_data.get('producto_id')
            if not producto_id:
                return {'success': False, 'error': 'El campo producto_id es requerido.'}

            # Renombrar 'cantidad' a 'cantidad_planificada' para el schema/modelo
            if 'cantidad' in form_data:
                form_data['cantidad_planificada'] = form_data.pop('cantidad')

            # --- AJUSTE PARA FECHA META ---
            # Si 'fecha_meta' viene del formulario, usarla.
            # No establecer 'fecha_planificada' por defecto en este flujo.
            if 'fecha_meta' not in form_data or not form_data.get('fecha_meta'):
                 # Podrías poner una fecha meta por defecto si lo deseas, o marcarla como requerida en el form
                 # return {'success': False, 'error': 'La Fecha Meta es requerida.'}
                 # Por ahora, si no viene, seguirá sin fecha meta (depende de tu schema/DB)
                 pass # Opcional: añadir lógica si la fecha meta es obligatoria

            # Eliminar fecha_planificada si existe en los datos del form (no debería con el cambio HTML)
            form_data.pop('fecha_planificada', None)
            # -----------------------------

            # Buscar receta si no se provee (sin cambios)
            if not form_data.get('receta_id'):
                receta_result = receta_model.find_all({'producto_id': int(producto_id), 'activa': True}, limit=1)
                if not receta_result.get('success') or not receta_result.get('data'):
                    return {'success': False, 'error': f'No se encontró una receta activa para el producto ID: {producto_id}.'}
                receta = receta_result['data'][0]
                form_data['receta_id'] = receta['id']

            # Estado por defecto PENDIENTE (sin cambios)
            if 'estado' not in form_data or not form_data['estado']:
                form_data['estado'] = 'PENDIENTE'

            # Validar con el Schema (Asegúrate que tu schema acepte 'fecha_meta')
            validated_data = self.schema.load(form_data)
            validated_data['codigo'] = f"OP-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            validated_data['usuario_creador_id'] = usuario_id

            # Crear en la base de datos
            return self.model.create(validated_data)

        except ValidationError as e:
            logger.error(f"Error de validación al crear orden: {e.messages}")
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            logger.error(f"Error inesperado en crear_orden: {e}", exc_info=True)
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def asignar_supervisor(self, orden_id: int, supervisor_id: int) -> tuple:
            """
            Asigna un supervisor a una orden de producción existente.
            """
            try:
                if not supervisor_id:
                    return self.error_response("El ID del supervisor es requerido.", 400)

                update_data = {'supervisor_responsable_id': int(supervisor_id)}
                result = self.model.update(id_value=orden_id, data=update_data, id_field='id')

                if result.get('success'):
                    return self.success_response(data=result.get('data'), message="Supervisor asignado correctamente.")
                else:
                    return self.error_response('Error al asignar supervisor.', 500)
            except Exception as e:
                return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    # --- WRAPPER PARA DELEGAR VERIFICACIÓN DE STOCK (FIX de AttributeError) ---
    def verificar_stock_para_op(self, orden_simulada: Dict) -> Dict:
        """
        Wrapper que delega la verificación de stock de insumos al controlador de inventario.
        """
        return self.inventario_controller.verificar_stock_para_op(orden_simulada)

    # --- MÉTODO CORREGIDO ---
    def aprobar_orden_con_oc(self, orden_id: int, usuario_id: int, oc_id: int) -> tuple:
        """
        Vincula una OC (conocida) a una OP PENDIENTE (flujo manual).
        NO cambia el estado de la OP.
        """
        try:
            # 1. Asocia la OC a la OP (Descomentado)
            # Asegúrate que tu modelo OP tenga el campo 'orden_compra_id'
            update_oc_result = self.model.update(orden_id, {'orden_compra_id': oc_id}, 'id')
            if not update_oc_result.get('success'):
                 # Si falla la vinculación, devolvemos error
                 logger.error(f"Fallo al vincular OP {orden_id} con OC {oc_id}: {update_oc_result.get('error')}")
                 return self.error_response(f"Fallo al vincular la OP con la OC: {update_oc_result.get('error')}", 500)

            # 2. La OP permanece en PENDIENTE
            logger.info(f"OP {orden_id} vinculada exitosamente con OC {oc_id}. Estado permanece PENDIENTE.")
            return self.success_response(
                data=update_oc_result.get('data'), # Devuelve la OP actualizada
                message="Orden de Compra vinculada. La Orden de Producción sigue PENDIENTE."
            )
        except Exception as e:
            logger.error(f"Error en aprobar_orden_con_oc para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    # --- MÉTODO CORREGIDO ---
    def aprobar_orden(self, orden_id: int, usuario_id: int) -> tuple:
        """
        Inicia el proceso de una orden PENDIENTE.
        - Si hay stock, reserva y pasa a 'LISTA PARA PRODUCIR'.
        - Si no hay stock, genera OC, la VINCULA a la OP y pasa a 'EN ESPERA'.
        """
        try:
            # 1. Obtener OP y validar estado
            orden_result = self.obtener_orden_por_id(orden_id)
            if not orden_result.get('success'):
                return self.error_response("Orden de producción no encontrada.", 404)
            orden_produccion = orden_result['data']

            if orden_produccion['estado'] != 'PENDIENTE':
                return self.error_response(f"La orden ya está en estado '{orden_produccion['estado']}'.", 400)

            # 2. Verificar stock
            verificacion_result = self.inventario_controller.verificar_stock_para_op(orden_produccion)
            if not verificacion_result.get('success'):
                return self.error_response(f"Error al verificar stock: {verificacion_result.get('error')}", 500)

            insumos_faltantes = verificacion_result['data']['insumos_faltantes']

            # 3. Manejar según disponibilidad de stock
            if insumos_faltantes:
                # --- CASO: FALTA STOCK ---
                logger.info(f"Stock insuficiente para OP {orden_id}. Generando OC...")
                oc_result = self._generar_orden_de_compra_automatica(insumos_faltantes, usuario_id, orden_id)
                if not oc_result.get('success'):
                    # Si falla la creación de OC, la OP sigue PENDIENTE pero informamos el error
                    return self.error_response(f"Stock insuficiente, pero no se pudo generar la OC: {oc_result.get('error')}", 500)

                # --- ¡NUEVO!: Vincular la OC creada a la OP ---
                oc_data = oc_result.get('data', {})
                created_oc_id = oc_data.get('id') # Asume que el ID de OC está en 'id'
                if created_oc_id:
                    logger.info(f"OC {oc_data.get('codigo_oc', created_oc_id)} creada. Vinculando a OP {orden_id}...")
                    update_op_oc_result = self.model.update(orden_id, {'orden_compra_id': created_oc_id}, 'id')
                    if not update_op_oc_result.get('success'):
                         # Loggear advertencia si falla la vinculación, pero continuar
                         logger.warning(f"OC creada ({created_oc_id}), pero falló la vinculación con OP {orden_id}: {update_op_oc_result.get('error')}")
                    else:
                         logger.info(f"OP {orden_id} vinculada exitosamente con OC {created_oc_id}.")
                else:
                     logger.error(f"OC creada para OP {orden_id}, ¡pero no se recibió el ID de la OC!")
                     # Considerar devolver error aquí si la vinculación es crítica

                # Cambiar estado OP a 'EN ESPERA'
                logger.info(f"Cambiando estado de OP {orden_id} a EN ESPERA.")
                estado_change_result = self.model.cambiar_estado(orden_id, 'EN ESPERA')
                if not estado_change_result.get('success'):
                    # Loggear error si falla el cambio de estado, pero ya creamos la OC
                    logger.error(f"Error al cambiar estado a EN ESPERA para OP {orden_id}: {estado_change_result.get('error')}")
                    # Podríamos intentar revertir la OC aquí si fuera transaccional

                return self.success_response(
                    data={'oc_generada': True, 'oc_codigo': oc_data.get('codigo_oc'), 'oc_id': created_oc_id},
                    message="Stock insuficiente. Se generó OC y la OP está 'En Espera'."
                )
            else:
                # --- CASO: STOCK DISPONIBLE ---
                logger.info(f"Stock disponible para OP {orden_id}. Reservando insumos...")
                reserva_result = self.inventario_controller.reservar_stock_insumos_para_op(orden_produccion, usuario_id)
                if not reserva_result.get('success'):
                    return self.error_response(f"Fallo crítico al reservar insumos: {reserva_result.get('error')}", 500)

                nuevo_estado_op = 'LISTA PARA PRODUCIR'
                logger.info(f"Cambiando estado de OP {orden_id} a {nuevo_estado_op}.")
                estado_change_result = self.model.cambiar_estado(orden_id, nuevo_estado_op)
                if not estado_change_result.get('success'):
                    # Si falla el cambio de estado, ¿deberíamos cancelar la reserva? (Complejo sin transacciones)
                    logger.error(f"Error al cambiar estado a {nuevo_estado_op} para OP {orden_id}: {estado_change_result.get('error')}")
                    return self.error_response(f"Error al cambiar estado a {nuevo_estado_op}: {estado_change_result.get('error')}", 500)

                return self.success_response(
                    message=f"Stock disponible. La orden está '{nuevo_estado_op}' y los insumos reservados."
                )

        except Exception as e:
            logger.error(f"Error en el proceso de aprobación de OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def _generar_orden_de_compra_automatica(self, insumos_faltantes: List[Dict], usuario_id: int, orden_produccion_id: int) -> Dict:
        """
        Helper para crear una OC a partir de una lista de insumos faltantes.
        """
        proveedor_id_por_defecto = 1
        items_oc_para_datos = [] # Renombrar para claridad

        # Preparar lista de items para la OC (sin cambios)
        for insumo in insumos_faltantes:
            cantidad_redondeada = math.ceil(insumo['cantidad_faltante'])
            if cantidad_redondeada <= 0: continue

            precio = 0
            try:
                response_data, status_code = self.insumo_controller.obtener_insumo_por_id(insumo['insumo_id'])
                if status_code < 400 and response_data.get('success'):
                    precio = response_data['data'].get('precio_unitario', 0)
                else: logger.warning(f"No se pudo obtener precio para insumo {insumo.get('insumo_id')}. Usando 0.")
            except Exception as e: logger.error(f"Error obteniendo precio para insumo {insumo.get('insumo_id')}: {e}")

            items_oc_para_datos.append({ # Añadir a la lista correcta
                'insumo_id': insumo['insumo_id'],
                'cantidad_solicitada': cantidad_redondeada, # Usar cantidad_solicitada como espera crear_orden
                'precio_unitario': precio,
                'cantidad_recibida': 0.0 # Inicializar cantidad recibida
            })

        if not items_oc_para_datos:
             logger.warning(f"No se generó OC para OP {orden_produccion_id} (sin items válidos).")
             return {'success': False, 'error': 'No hay insumos válidos para generar la OC.'}

        # Preparar datos principales de la OC (sin cambios)
        datos_oc_principales = {
            'proveedor_id': proveedor_id_por_defecto,
            'fecha_emision': date.today().isoformat(),
            'prioridad': 'ALTA',
            'observaciones': f"Generada automáticamente para OP ID: {orden_produccion_id}",
            'orden_produccion_id': orden_produccion_id
        }

        # Calcular totales (subtotal, iva, total) - Necesario para crear_orden
        subtotal_calculado = sum(float(item.get('cantidad_solicitada', 0)) * float(item.get('precio_unitario', 0)) for item in items_oc_para_datos)
        iva_calculado = subtotal_calculado * 0.21 # Asumiendo 21%
        total_calculado = subtotal_calculado + iva_calculado

        datos_oc_principales['subtotal'] = round(subtotal_calculado, 2)
        datos_oc_principales['iva'] = round(iva_calculado, 2)
        datos_oc_principales['total'] = round(total_calculado, 2)

        # --- CORRECCIÓN EN LA LLAMADA ---
        # Llamar a crear_orden pasando orden_data, items_data y usuario_id
        return self.orden_compra_controller.crear_orden(
            orden_data=datos_oc_principales,
            items_data=items_oc_para_datos,
            usuario_id=usuario_id
        )
        # --------------------------------

    def generar_orden_de_compra_automatica(self, insumos_faltantes: List[Dict], usuario_id: int, orden_produccion_id: int) -> Dict:
        """Wrapper publico para el helper privado _generar_orden_de_compra_automatica."""
        return self._generar_orden_de_compra_automatica(insumos_faltantes, usuario_id, orden_produccion_id)


    def rechazar_orden(self, orden_id: int, motivo: str) -> Dict:
        """
        Rechaza una orden, cambiando su estado a CANCELADA.
        """
        return self.model.cambiar_estado(orden_id, 'CANCELADA', observaciones=f"Rechazada: {motivo}")

    def cambiar_estado_orden(self, orden_id: int, nuevo_estado: str) -> tuple:
        """
        Cambia el estado de una orden.
        Si es 'COMPLETADA', crea el lote y lo deja 'RESERVADO' si está
        vinculado a un pedido, o 'DISPONIBLE' si es para stock general.
        """
        try:
            orden_result = self.obtener_orden_por_id(orden_id)
            if not orden_result.get('success'):
                return self.error_response("Orden de producción no encontrada.", 404)
            orden_produccion = orden_result['data']
            estado_actual = orden_produccion['estado']

            if nuevo_estado == 'COMPLETADA':
                if estado_actual != 'CONTROL_DE_CALIDAD':
                    return self.error_response("La orden debe estar en 'CONTROL DE CALIDAD' para ser completada.", 400)

                # 1. Verificar si la OP está vinculada a ítems de pedido
                items_a_surtir_res = self.pedido_model.find_all_items({'orden_produccion_id': orden_id})
                items_vinculados = items_a_surtir_res.get('data', []) if items_a_surtir_res.get('success') else []

                # 2. Decidir el estado inicial del lote
                estado_lote_inicial = 'RESERVADO' if items_vinculados else 'DISPONIBLE'

                # 3. Preparar y crear el lote con el estado decidido
                datos_lote = {
                    'producto_id': orden_produccion['producto_id'],
                    'cantidad_inicial': orden_produccion['cantidad_planificada'],
                    'orden_produccion_id': orden_id,
                    'fecha_produccion': date.today().isoformat(),
                    'fecha_vencimiento': (date.today() + timedelta(days=90)).isoformat(),
                    'estado': estado_lote_inicial # <-- Pasamos el estado decidido
                }
                resultado_lote, status_lote = self.lote_producto_controller.crear_lote_desde_formulario(
                    datos_lote, usuario_id=orden_produccion.get('usuario_creador_id', 1)
                )
                if status_lote >= 400:
                    return self.error_response(f"Fallo al registrar el lote de producto: {resultado_lote.get('error')}", 500)

                lote_creado = resultado_lote['data']
                message_to_use = f"Orden completada. Lote N° {lote_creado['numero_lote']} creado como '{estado_lote_inicial}'."

                # 4. Si el lote se creó como RESERVADO, crear los registros de reserva
                if estado_lote_inicial == 'RESERVADO':
                    for item in items_vinculados:
                        datos_reserva = {
                            'lote_producto_id': lote_creado['id_lote'],
                            'pedido_id': item['pedido_id'],
                            'pedido_item_id': item['id'],
                            'cantidad_reservada': float(item['cantidad']), # Asumimos que la OP cubre la cantidad del item
                            'usuario_reserva_id': orden_produccion.get('usuario_creador_id', 1)
                        }
                        # Creamos la reserva directamente, sin descontar stock
                        self.lote_producto_controller.reserva_model.create(
                            self.lote_producto_controller.reserva_schema.load(datos_reserva)
                        )
                    logger.info(f"Registros de reserva creados para el lote {lote_creado['numero_lote']}.")
                    message_to_use += " y vinculado a los pedidos correspondientes."

            # 5. Cambiar el estado de la OP en la base de datos (se ejecuta siempre)
            result = self.model.cambiar_estado(orden_id, nuevo_estado)
            if result.get('success'):
                from app.controllers.pedido_controller import PedidoController
                pedido_controller = PedidoController()
                # Después de cambiar el estado de la OP, verificamos si el estado del pedido de venta debe cambiar.
                items_asociados_res = self.pedido_model.find_all_items({'orden_produccion_id': orden_id})
                if items_asociados_res.get('success') and items_asociados_res.get('data'):
                    # Usamos un set para no verificar el mismo pedido varias veces si una OP surte varios items del mismo pedido.
                    pedido_ids_a_verificar = {item['pedido_id'] for item in items_asociados_res['data']}
                    for pedido_id in pedido_ids_a_verificar:
                        pedido_controller.actualizar_estado_segun_ops(pedido_id)

                if nuevo_estado != 'COMPLETADA':
                    message_to_use = f"Estado actualizado a {nuevo_estado.replace('_', ' ')}."
                return self.success_response(data=result.get('data'), message=message_to_use)
            else:
                return self.error_response(result.get('error', 'Error al cambiar el estado.'), 500)

        except Exception as e:
            logger.error(f"Error en cambiar_estado_orden para la orden {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def crear_orden_desde_planificacion(self, producto_id: int, item_ids: List[int], usuario_id: int) -> Dict:
        """
        Orquesta la creación de una orden consolidada desde el módulo de planificación.
        """
        from app.models.pedido import PedidoModel
        from app.models.receta import RecetaModel
        from datetime import date

        pedido_model = PedidoModel()
        receta_model = RecetaModel()

        try:
            # 1. Obtener los ítems y calcular la cantidad total
            items_result = pedido_model.find_all_items(filters={'id': ('in', item_ids)})
            if not items_result.get('success') or not items_result.get('data'):
                return {'success': False, 'error': 'No se encontraron los ítems de pedido para consolidar.'}

            items = items_result['data']
            cantidad_total = sum(item['cantidad'] for item in items)

            # --- NUEVA LÓGICA: Obtener el ID del Pedido (Orden de Venta) de referencia ---
            # Se toma el ID del primer ítem como referencia principal para el campo.
            primer_pedido_id = items[0].get('pedido_id') if items else None
            # ---------------------------------------------------------------------------

            # 2. Encontrar receta activa
            receta_result = receta_model.find_all({'producto_id': producto_id, 'activa': True}, limit=1)
            if not receta_result.get('data'):
                return {'success': False, 'error': f'No se encontró una receta activa para el producto ID {producto_id}.'}
            receta = receta_result['data'][0]

            # 3. Crear la orden de producción
            datos_orden = {
                'producto_id': producto_id,
                'cantidad_planificada': cantidad_total,
                'fecha_planificada': date.today().isoformat(),
                'receta_id': receta['id'],
                'prioridad': 'NORMAL',
                # --- INCLUIR EL CAMPO pedido_id EN LOS DATOS ---
                'pedido_id': primer_pedido_id
                # -----------------------------------------------
            }
            resultado_creacion = self.crear_orden(datos_orden, usuario_id)

            if not resultado_creacion.get('success'):
                return resultado_creacion

            # 4. Actualizar los ítems de pedido en lote
            orden_creada = resultado_creacion['data']
            update_data = {
                'estado': 'PLANIFICADO',
                'orden_produccion_id': orden_creada['id']
            }
            pedido_model.update_items(item_ids, update_data)

            return {'success': True, 'data': orden_creada}

        except Exception as e:
            return {'success': False, 'error': f'Error en el proceso de consolidación: {str(e)}'}

    def obtener_datos_para_formulario(self) -> Dict:
        """
        Obtiene los datos necesarios para popular los menús desplegables
        en el formulario de creación/edición de órdenes, usando los nuevos controladores.
        """
        try:
            productos = self.producto_controller.obtener_todos_los_productos()
            recetas = self.receta_controller.obtener_recetas({'activa': True})
            todos_los_usuarios = self.usuario_controller.obtener_todos_los_usuarios()
            operarios = [u for u in todos_los_usuarios if u.get('roles', {}).get('codigo') in ['OPERARIO', 'SUPERVISOR']]

            return {
                'productos': productos,
                'recetas': recetas,
                'operarios': operarios
            }
        except Exception as e:
            return {
                'productos': [], 'recetas': [], 'operarios': [],
                'error': f'Error obteniendo datos para el formulario: {str(e)}'
            }

    def consolidar_ordenes_produccion(self, op_ids: List[int], usuario_id: int) -> Dict:
        """
        Lógica de negocio para fusionar varias OPs en una Super OP.
        1. Valida las OPs.
        2. Calcula totales.
        3. Crea la nueva Super OP.
        4. Actualiza las OPs originales.
        """
        try:
            # 1. Obtener las OPs originales desde el modelo
            ops_a_consolidar_res = self.model.find_by_ids(op_ids) # Necesitarás crear este método en tu modelo
            if not ops_a_consolidar_res.get('success') or not ops_a_consolidar_res.get('data'):
                return {'success': False, 'error': 'Una o más órdenes no fueron encontradas.'}

            ops_originales = ops_a_consolidar_res['data']

            # Validación extra en el backend
            if len(ops_originales) != len(op_ids):
                return {'success': False, 'error': 'Algunas órdenes no pudieron ser cargadas.'}

            primer_producto_id = ops_originales[0]['producto_id']
            if not all(op['producto_id'] == primer_producto_id for op in ops_originales):
                return {'success': False, 'error': 'Todas las órdenes deben ser del mismo producto.'}

            # 2. Calcular la cantidad total
            cantidad_total = sum(Decimal(op['cantidad_planificada']) for op in ops_originales)
            primera_op = ops_originales[0]

                # --- NUEVO: Encontrar la fecha meta más temprana ---
            fechas_meta_originales = []
            for op in ops_originales:
                fecha_meta_str = op.get('fecha_meta')
                if fecha_meta_str:
                    try:
                        fechas_meta_originales.append(date.fromisoformat(fecha_meta_str))
                    except ValueError:
                        logger.warning(f"Formato de fecha meta inválido encontrado en OP {op.get('id')}: {fecha_meta_str}")

            fecha_meta_mas_temprana = min(fechas_meta_originales) if fechas_meta_originales else None
            # --------------------------------------------------

            # 3. Crear la nueva Super OP (reutilizando la lógica de `crear_orden`)
            super_op_data = {
                'producto_id': primera_op['producto_id'],
                'cantidad_planificada': str(cantidad_total),
                'fecha_planificada': primera_op['fecha_planificada'],
                'receta_id': primera_op['receta_id'],
                'fecha_meta': fecha_meta_mas_temprana.isoformat() if fecha_meta_mas_temprana else None, # Guardar la fecha meta más temprana
                'prioridad': 'ALTA', # Las super OPs suelen ser prioritarias
                'observaciones': f'Super OP consolidada desde las OPs: {", ".join(map(str, op_ids))}',
                'estado': 'PENDIENTE' # La Super OP nace lista
            }

            resultado_creacion = self.crear_orden(super_op_data, usuario_id)
            if not resultado_creacion.get('success'):
                return resultado_creacion

            nueva_super_op = resultado_creacion['data']
            super_op_id = nueva_super_op['id']

            # 4. Re-linkear los items de pedido de las OPs originales a la nueva Super OP
            try:
                # Usamos el cliente de base de datos directamente para una operación de actualización en lote
                update_result = self.pedido_model.db.table('pedido_items').update({
                    'orden_produccion_id': super_op_id
                }).in_('orden_produccion_id', op_ids).execute()

                logger.info(f"Relinkeo de items de pedido a Super OP {super_op_id} completado.")

            except Exception as e_relink:
                # Si esto falla, la Super OP ya fue creada. Es un estado inconsistente.
                # Devolvemos un error crítico y loggeamos la situación.
                logger.error(f"CRÍTICO: Fallo al re-linkear items de pedido a Super OP {super_op_id}. Error: {e_relink}", exc_info=True)
                # En un sistema transaccional, aquí se haría un rollback.
                # Por ahora, devolvemos el error para que el frontend lo sepa.
                return {'success': False, 'error': f'La Super OP fue creada, pero falló la asignación de pedidos. Contacte a soporte. Error: {str(e_relink)}'}

            # 5. Actualizar las OPs originales (antes era el paso 4)
            update_data = {
                'estado': 'CONSOLIDADA',
                'super_op_id': super_op_id
            }
            for op_id in op_ids:
                self.model.update(id_value=op_id, data=update_data, id_field='id')

            return {'success': True, 'data': nueva_super_op}

        except Exception as e:
            logger.error(f"Error en consolidar_ordenes_produccion: {e}", exc_info=True)
            # Aquí idealmente implementarías un rollback de la transacción
            return {'success': False, 'error': f'Error interno del servidor: {str(e)}'}

    def cambiar_estado_orden_simple(self, orden_id: int, nuevo_estado: str) -> Dict:
        """
        Cambia el estado de una orden de producción. Ideal para el Kanban.
        Reutiliza la lógica robusta del modelo.
        """
        try:
            # Validación simple de estados (opcional pero recomendado)
            orden_result = self.obtener_orden_por_id(orden_id)
            if not orden_result.get('success'):
                return {'success': False, 'error': "Orden de producción no encontrada."}

            # Aquí podrías añadir reglas de negocio, ej:
            # "No se puede mover de 'EN LINEA 1' a 'LISTA PARA PRODUCIR'"

            # Llamamos al método del modelo que ya sabe cómo cambiar estados y fechas
            result = self.model.cambiar_estado(orden_id, nuevo_estado)
            return result

        except Exception as e:
            logger.error(f"Error en cambiar_estado_orden_simple para OP {orden_id}: {e}", exc_info=True)
            return {'success': False, 'error': f"Error interno: {str(e)}"}

    def sugerir_fecha_inicio(self, orden_id: int, usuario_id: int) -> tuple:
        """
        Calcula fecha de inicio sugerida, considerando la línea de producción
        óptima y su eficiencia para la cantidad dada.
        """
        try:
            # 1. Obtener OP y Fecha Meta (sin cambios)
            op_result = self.obtener_orden_por_id(orden_id)
            if not op_result.get('success'):
                return self.error_response("OP no encontrada.", 404)
            op_data = op_result['data']
            fecha_meta_str = op_data.get('fecha_meta')
            if not fecha_meta_str:
                return self.error_response("OP sin fecha meta.", 400)
            fecha_meta = date.fromisoformat(fecha_meta_str)
            cantidad = float(op_data['cantidad_planificada'])

            # 2. Obtener Receta y determinar Línea Óptima y Tiempo de Producción
            receta_model = RecetaModel()
            receta_res = receta_model.find_by_id(op_data['receta_id'], 'id')
            if not receta_res.get('success'):
                return self.error_response("Receta no encontrada.", 404)
            receta = receta_res['data']

            linea_compatible = receta.get('linea_compatible', '2').split(',') # Default a línea 2 si no está definido
            tiempo_prep = receta.get('tiempo_preparacion_minutos', 0)
            tiempo_l1 = receta.get('tiempo_prod_unidad_linea1', 0)
            tiempo_l2 = receta.get('tiempo_prod_unidad_linea2', 0)

            linea_sugerida = 0
            tiempo_prod_unit_elegido = 0

            # --- Lógica de Selección de Línea ---
            # Define tu umbral para considerar "gran cantidad" y justificar la línea 1
            UMBRAL_CANTIDAD_LINEA_1 = 50

            puede_l1 = '1' in linea_compatible and tiempo_l1 > 0
            puede_l2 = '2' in linea_compatible and tiempo_l2 > 0

            if puede_l1 and puede_l2: # Compatible con ambas
                if cantidad >= UMBRAL_CANTIDAD_LINEA_1:
                    linea_sugerida = 1 # Grande -> Línea 1
                    tiempo_prod_unit_elegido = tiempo_l1
                else:
                    linea_sugerida = 2 # Pequeña -> Línea 2 (más barata)
                    tiempo_prod_unit_elegido = tiempo_l2
            elif puede_l1: # Solo compatible con Línea 1
                linea_sugerida = 1
                tiempo_prod_unit_elegido = tiempo_l1
            elif puede_l2: # Solo compatible con Línea 2
                linea_sugerida = 2
                tiempo_prod_unit_elegido = tiempo_l2
            else:
                return self.error_response("La receta no tiene tiempos válidos o compatibilidad de línea definida.", 400)

            # Calcular T_Prod basado en la línea elegida
            t_prod_minutos = tiempo_prep + (tiempo_prod_unit_elegido * cantidad)
            t_prod_dias = math.ceil(t_prod_minutos / 480) # Asumiendo jornada de 8h

            # --- 3. Calcular Tiempo de Aprovisionamiento (T_Proc) (sin cambios) ---
            verificacion_res = self.inventario_controller.verificar_stock_para_op(op_data)
            # ... (la lógica para calcular t_proc_dias se mantiene igual) ...
            insumos_faltantes = verificacion_res['data']['insumos_faltantes']
            t_proc_dias = 0
            if insumos_faltantes:
                # ... (buscar el max(tiempo_entrega_dias)) ...
                 insumo_model = InsumoModel()
                 tiempos_entrega = []
                 for insumo in insumos_faltantes:
                     insumo_data_res = insumo_model.find_by_id(insumo['insumo_id'], 'id_insumo')
                     if insumo_data_res.get('success'):
                         tiempo = insumo_data_res['data'].get('tiempo_entrega_dias', 0)
                         tiempos_entrega.append(tiempo)
                 t_proc_dias = max(tiempos_entrega) if tiempos_entrega else 0


            # --- 4. Calcular Fecha de Inicio Sugerida (sin cambios) ---
            plazo_total_dias = t_prod_dias + t_proc_dias
            fecha_inicio_sugerida = fecha_meta - timedelta(days=plazo_total_dias)

            # --- 5. Añadir Recomendación de Eficiencia ---
            recomendacion_eficiencia = ""
            # Si se sugiere la línea 1 pero la cantidad es baja...
            if linea_sugerida == 1 and cantidad < UMBRAL_CANTIDAD_LINEA_1:
                recomendacion_eficiencia = (f"¡Atención! La cantidad ({cantidad}) es baja para la Línea 1. "
                                            f"Considere si es eficiente encenderla o si puede agrupar con otras OPs.")
            # Si solo es compatible con la 1 y la cantidad es baja...
            elif linea_sugerida == 1 and not puede_l2 and cantidad < UMBRAL_CANTIDAD_LINEA_1:
                 recomendacion_eficiencia = (f"La cantidad ({cantidad}) es baja, pero esta receta solo es compatible con la Línea 1.")


            # 6. Preparar la respuesta detallada
            detalle = {
            'fecha_meta': fecha_meta.isoformat(),
            'linea_sugerida': linea_sugerida,
            'plazo_total_dias': plazo_total_dias,
            't_produccion_dias': t_prod_dias,
            't_aprovisionamiento_dias': t_proc_dias,
            'fecha_inicio_sugerida': fecha_inicio_sugerida.isoformat(),
            'recomendacion_eficiencia': recomendacion_eficiencia,
            'insumos_faltantes': insumos_faltantes
            }

            # --- INICIO NUEVA LÓGICA: GUARDAR SUGERENCIA ---
            datos_para_guardar = {
                'sugerencia_fecha_inicio': detalle['fecha_inicio_sugerida'],
                'sugerencia_plazo_total_dias': detalle['plazo_total_dias'],
                'sugerencia_t_produccion_dias': detalle['t_produccion_dias'],
                'sugerencia_t_aprovisionamiento_dias': detalle['t_aprovisionamiento_dias'],
                'sugerencia_linea': detalle['linea_sugerida']
            }
            # Actualizamos la OP en la base de datos con estos datos
            update_result = self.model.update(orden_id, datos_para_guardar, 'id')
            if not update_result.get('success'):
                # Si falla el guardado, no es crítico, pero sí loggeamos/advertimos
                logger.warning(f"No se pudo guardar la sugerencia calculada para OP {orden_id}. Error: {update_result.get('error')}")
            # --- FIN NUEVA LÓGICA ---

            # 7. Devolver la respuesta detallada (sin cambios)
            return self.success_response(data=detalle)

        except Exception as e:
            logger.error(f"Error en sugerir_fecha_inicio para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)



    def pre_asignar_recursos(self, orden_id: int, data: Dict, usuario_id: int) -> tuple:
        """
        1. Valida compatibilidad de línea.
        2. GUARDA la línea, supervisor y operario asignados.
        3. NO cambia el estado ni aprueba la orden todavía.
        """
        try:
            # 0. Obtener OP y Receta (sin cambios)
            op_result = self.obtener_orden_por_id(orden_id)
            if not op_result.get('success'): return self.error_response("OP no encontrada.", 404)
            op_data = op_result['data']; receta_id = op_data.get('receta_id')

            # 1. Validar datos de entrada (sin cambios)
            linea_asignada = data.get('linea_asignada'); supervisor_id = data.get('supervisor_responsable_id')
            operario_id = data.get('operario_asignado_id')
            if not linea_asignada or linea_asignada not in [1, 2]:
                return self.error_response("Línea inválida.", 400)

            # Validar compatibilidad de línea (sin cambios)
            receta_model = RecetaModel()
            receta_res = receta_model.find_by_id(receta_id, 'id')
            # ... (código de validación de compatibilidad) ...
            if not receta_res.get('success'):
                return self.error_response(f"Receta no encontrada (ID: {receta_id}).", 404)
            receta_data = receta_res['data']
            lineas_compatibles = receta_data.get('linea_compatible', '2').split(',')
            if str(linea_asignada) not in lineas_compatibles:
                return self.error_response(f"Línea {linea_asignada} incompatible. Permitidas: {', '.join(lineas_compatibles)}.", 400)


            # 2. Preparar y actualizar la OP con las asignaciones
            update_data = {
                'linea_asignada': linea_asignada,
                'supervisor_responsable_id': supervisor_id,
                'operario_asignado_id': operario_id
            }
            update_result = self.model.update(orden_id, update_data, 'id')
            if not update_result.get('success'):
                return self.error_response(f"Error al asignar recursos: {update_result.get('error')}", 500)

            # 3. Devolver éxito SIN llamar a aprobar_orden
            # Devolvemos los datos actualizados para referencia
            return self.success_response(data=update_result.get('data'), message="Recursos pre-asignados. Confirme la fecha de inicio.")

        except Exception as e:
            logger.error(f"Error crítico en pre_asignar_recursos para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)


    def confirmar_inicio_y_aprobar(self, orden_id: int, data: Dict, usuario_id: int) -> tuple:
        """
        1. Guarda la fecha de inicio planificada confirmada.
        2. Ejecuta la lógica de aprobación (verificar stock, reservar/crear OC, cambiar estado).
        """
        try:
            fecha_inicio_confirmada = data.get('fecha_inicio_planificada')
            if not fecha_inicio_confirmada:
                return self.error_response("Debe seleccionar una fecha de inicio.", 400)

            # 1. Guardar la fecha de inicio confirmada
            update_data = {'fecha_inicio_planificada': fecha_inicio_confirmada}
            update_result = self.model.update(orden_id, update_data, 'id')
            if not update_result.get('success'):
                return self.error_response(f"Error al guardar fecha de inicio: {update_result.get('error')}", 500)

            # 2. Ejecutar la lógica de aprobación que ya tenías
            # Esta función devuelve (dict, status_code)
            aprobacion_dict, aprobacion_status_code = self.aprobar_orden(orden_id, usuario_id)

            # Ajustar mensaje si fue exitoso
            if aprobacion_dict.get('success'):
                 aprobacion_dict['message'] = f"Inicio confirmado para {fecha_inicio_confirmada}. {aprobacion_dict.get('message', '')}"

            return aprobacion_dict, aprobacion_status_code

        except Exception as e:
            logger.error(f"Error crítico en confirmar_inicio_y_aprobar para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def obtener_conteo_ordenes_reabiertas(self) -> int:
        """Obtiene el conteo de órdenes en estado de reproceso."""
        try:
            result = self.model.find_all(filters={'estado': 'REPROCESO'})
            if result.get('success'):
                return len(result.get('data', []))
            return 0
        except Exception as e:
            logger.error(f"Error contando órdenes en reproceso: {str(e)}")
            return 0