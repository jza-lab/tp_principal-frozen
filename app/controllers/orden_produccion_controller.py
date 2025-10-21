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
        MODIFICADO: Este método ahora siempre devuelve un diccionario.
        """
        from app.models.receta import RecetaModel
        receta_model = RecetaModel()

        try:
            if 'supervisor_responsable_id' in form_data and not form_data['supervisor_responsable_id']:
                form_data.pop('supervisor_responsable_id')

            producto_id = form_data.get('producto_id')
            if not producto_id:
                return {'success': False, 'error': 'El campo producto_id es requerido.'}

            if 'cantidad' in form_data:
                form_data['cantidad_planificada'] = form_data.pop('cantidad')

            # Si no se provee receta_id, la buscamos (lógica clave para la Super OP)
            if not form_data.get('receta_id'):
                receta_result = receta_model.find_all({'producto_id': int(producto_id), 'activa': True}, limit=1)
                if not receta_result.get('success') or not receta_result.get('data'):
                    return {'success': False, 'error': f'No se encontró una receta activa para el producto ID: {producto_id}.'}
                receta = receta_result['data'][0]
                form_data['receta_id'] = receta['id']

            if 'estado' not in form_data or not form_data['estado']:
                form_data['estado'] = 'PENDIENTE'
            # ------------------------------------

            validated_data = self.schema.load(form_data)
            validated_data['codigo'] = f"OP-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            validated_data['usuario_creador_id'] = usuario_id

            return self.model.create(validated_data)

        except ValidationError as e:
            # --- CORRECCIÓN AQUÍ ---
            # En lugar de devolver una tupla, devolvemos el diccionario de error.
            logger.error(f"Error de validación al crear orden: {e.messages}")
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            # --- CORRECCIÓN AQUÍ ---
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

    # --- MÉTODO PARA APROBACIÓN FORZADA (VINCULACIÓN OC) ---
    def aprobar_orden_con_oc(self, orden_id: int, usuario_id: int, oc_id: int) -> tuple:
        """
        Aprueba la OP cuando se sabe que se ha generado la OC (flujo manual).

        MODIFICADO: Este método solo vincula la OC (si es necesario) y mantiene
        el estado en PENDIENTE, a la espera de la recepción de los insumos.
        La aprobación formal a 'APROBADA' debe ocurrir en otro flujo.
        """
        try:
            # Opcional: Si el modelo de OP tiene un campo para vincular la OC
            # 1. Asocia la OC a la OP (Descomentar si el modelo de OP soporta orden_compra_id)
            # update_oc = self.model.update(orden_id, {'orden_compra_id': oc_id}, 'id')
            # if not update_oc.get('success'):
            #     return self.error_response("Fallo al vincular la OP con la OC.", 500)

            # 2. **CAMBIO CLAVE: Se ELIMINA el cambio de estado a 'APROBADA'**
            # y se ELIMINA la reserva de stock.
            # La OP permanece en PENDIENTE hasta que se reciba la OC/Stock.

            # NOTA: Si se desea registrar que la OC ya fue generada para esta OP:
            # Se podría cambiar a un estado intermedio como 'OC_GENERADA' o añadir una bandera,
            # pero si se pide que se quede en PENDIENTE, se respeta la lógica.

            return self.success_response(None, "Orden de Compra vinculada (o generada). La Orden de Producción permanece en PENDIENTE a la espera de la recepción de insumos.")

        except Exception as e:
            logger.error(f"Error en aprobar_orden_con_oc para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def aprobar_orden(self, orden_id: int, usuario_id: int) -> Dict:
        """
        Inicia el proceso de una orden PENDIENTE.
        - Si hay stock, la pasa a 'LISTA PARA PRODUCIR' y reserva insumos.
        - Si no hay stock, la pasa a 'EN ESPERA' y genera una OC.
        """
        try:
            orden_result = self.obtener_orden_por_id(orden_id)
            if not orden_result.get('success'):
                return self.error_response("Orden de producción no encontrada.", 404)
            orden_produccion = orden_result['data']

            if orden_produccion['estado'] != 'PENDIENTE':
                return self.error_response(f"La orden ya está en estado '{orden_produccion['estado']}'.", 400)

            verificacion_result = self.inventario_controller.verificar_stock_para_op(orden_produccion)
            if not verificacion_result.get('success'):
                return self.error_response(f"Error al verificar stock: {verificacion_result.get('error')}", 500)

            insumos_faltantes = verificacion_result['data']['insumos_faltantes']

            if insumos_faltantes:
                # --- CASO: FALTA STOCK ---
                # 1. Generar OC automática
                oc_result = self._generar_orden_de_compra_automatica(insumos_faltantes, usuario_id, orden_id)
                if not oc_result.get('success'):
                    return self.error_response(f"No se pudo generar la orden de compra: {oc_result.get('error')}", 500)

                # 2. Cambiar estado de OP a 'EN ESPERA'
                self.model.cambiar_estado(orden_id, 'EN ESPERA')

                return self.success_response(
                    data={'oc_generada': True, 'oc_codigo': oc_result['data']['codigo_oc']},
                    message="Stock insuficiente. Se generó la Orden de Compra y la OP está 'En Espera'."
                )
            else:
                # --- CASO: HAY STOCK ---
                # 1. Reservar insumos
                reserva_result = self.inventario_controller.reservar_stock_insumos_para_op(orden_produccion, usuario_id)
                if not reserva_result.get('success'):
                    return self.error_response(f"Fallo crítico al reservar insumos: {reserva_result.get('error')}", 500)

                # 2. Cambiar estado a 'LISTA PARA PRODUCIR'
                self.model.cambiar_estado(orden_id, 'LISTA PARA PRODUCIR')

                return self.success_response(message="Stock disponible. La orden está 'Lista para Producir' y los insumos han sido reservados.")

        except Exception as e:
            logger.error(f"Error en el proceso de aprobación de OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def _generar_orden_de_compra_automatica(self, insumos_faltantes: List[Dict], usuario_id: int, orden_produccion_id: int) -> Dict:
        """
        Helper para crear una OC a partir de una lista de insumos faltantes.
        Aplica redondeo hacia arriba (ceil) en las cantidades solicitadas.
        """
        # Simplificación: Asumimos un proveedor por defecto o el primero que encontremos.
        proveedor_id_por_defecto = 1

        items_oc_para_form = []
        for insumo in insumos_faltantes:
            # FIX: Aplicar math.ceil() al faltante
            cantidad_redondeada = math.ceil(insumo['cantidad_faltante'])

            if cantidad_redondeada == 0:
                continue

            try:
                response_data, status_code = self.insumo_controller.obtener_insumo_por_id(insumo['insumo_id'])
                precio = response_data['data']['precio_unitario'] if status_code < 400 else 0
            except Exception as e:
                 logger.error(f"Error obteniendo precio para insumo {insumo.get('insumo_id')}: {e}")
                 precio = 0

            items_oc_para_form.append({
                'insumo_id': insumo['insumo_id'],
                'cantidad_faltante': cantidad_redondeada, # Usamos la cantidad redondeada
                'precio_unitario': precio
            })

        datos_oc = {
            'proveedor_id': proveedor_id_por_defecto,
            'fecha_emision': date.today().isoformat(),
            'prioridad': 'ALTA',
            'observaciones': f"Orden de Compra generada automáticamente para la OP ID: {orden_produccion_id}",
            'orden_produccion_id': orden_produccion_id
        }

        # Simulamos los datos como si vinieran de un form para reusar el método del controlador
        form_data_simulado = {
            **datos_oc,
            'insumo_id[]': [item['insumo_id'] for item in items_oc_para_form],
            'cantidad_faltante[]': [item['cantidad_faltante'] for item in items_oc_para_form],
            'precio_unitario[]': [item['precio_unitario'] for item in items_oc_para_form]
        }

        return self.orden_compra_controller.crear_orden(form_data_simulado, usuario_id)

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
                    return self.error_response(f"La orden debe estar en 'CONTROL DE CALIDAD' para ser completada.", 400)

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

            # 3. Crear la nueva Super OP (reutilizando la lógica de `crear_orden`)
            super_op_data = {
                'producto_id': primera_op['producto_id'],
                'cantidad_planificada': str(cantidad_total),
                'fecha_planificada': primera_op['fecha_planificada'],
                'receta_id': primera_op['receta_id'],
                'prioridad': 'ALTA', # Las super OPs suelen ser prioritarias
                'observaciones': f'Super OP consolidada desde las OPs: {", ".join(map(str, op_ids))}',
                'estado': 'LISTA PARA PRODUCIR' # La Super OP nace lista
            }

            resultado_creacion = self.crear_orden(super_op_data, usuario_id)
            if not resultado_creacion.get('success'):
                return resultado_creacion

            nueva_super_op = resultado_creacion['data']
            super_op_id = nueva_super_op['id']

            # 4. Actualizar las OPs originales
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
            if not op_result.get('success'): return self.error_response("OP no encontrada.", 404)
            op_data = op_result['data']
            fecha_meta_str = op_data.get('fecha_meta')
            if not fecha_meta_str: return self.error_response("OP sin fecha meta.", 400)
            fecha_meta = date.fromisoformat(fecha_meta_str)
            cantidad = float(op_data['cantidad_planificada'])

            # 2. Obtener Receta y determinar Línea Óptima y Tiempo de Producción
            receta_model = RecetaModel()
            receta_res = receta_model.find_by_id(op_data['receta_id'], 'id')
            if not receta_res.get('success'): return self.error_response("Receta no encontrada.", 404)
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
            if not linea_asignada or linea_asignada not in [1, 2]: return self.error_response("Línea inválida.", 400)

            # Validar compatibilidad de línea (sin cambios)
            receta_model = RecetaModel()
            receta_res = receta_model.find_by_id(receta_id, 'id')
            # ... (código de validación de compatibilidad) ...
            if not receta_res.get('success'): return self.error_response(f"Receta no encontrada (ID: {receta_id}).", 404)
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