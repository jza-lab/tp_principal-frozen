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
from app.models.motivo_paro_model import MotivoParoModel
from app.models.motivo_desperdicio_model import MotivoDesperdicioModel
from app.models.registro_paro_model import RegistroParoModel
from app.models.registro_desperdicio_model import RegistroDesperdicioModel
from app.models.operacion_receta_model import OperacionRecetaModel
from app.controllers.op_cronometro_controller import OpCronometroController


logger = logging.getLogger(__name__)

class OrdenProduccionController(BaseController):
    """
    Controlador para la lógica de negocio de las Órdenes de Producción.
    """

    # region Inicialización
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
        self.operacion_receta_model = OperacionRecetaModel()
        self.op_cronometro_controller = OpCronometroController()
        self._planificacion_controller = None

    @property
    def planificacion_controller(self):
        """Lazy loader for PlanificacionController to prevent circular dependency."""
        if self._planificacion_controller is None:
            from app.controllers.planificacion_controller import PlanificacionController
            self._planificacion_controller = PlanificacionController()
        return self._planificacion_controller

    # endregion

    # region Métodos Públicos (API)

    def calcular_carga_op(self, op_data: Dict) -> Decimal:
        """ Calcula la carga total en minutos para una OP dada. """
        carga_total = Decimal(0)
        receta_id = op_data.get('receta_id')
        cantidad = Decimal(op_data.get('cantidad_planificada', 0))
        if not receta_id or cantidad <= 0: return carga_total

        operaciones = self._obtener_operaciones_receta(receta_id)
        if not operaciones: return carga_total

        for op_step in operaciones:
            t_prep = Decimal(op_step.get('tiempo_preparacion', 0))
            t_ejec_unit = Decimal(op_step.get('tiempo_ejecucion_unitario', 0))
            carga_total += t_prep + (t_ejec_unit * cantidad)
        return carga_total

    def _obtener_operaciones_receta(self, receta_id: int) -> List[Dict]:
        """ Obtiene las operaciones de una receta desde el modelo. """
        result = self.operacion_receta_model.find_by_receta_id(receta_id)
        return result.get('data', []) if result.get('success') else []

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
            # --- FIX: Convertir a mutable para poder modificarlo ---
            form_data = form_data.copy()
            # ----------------------------------------------------

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

            # --- FIX: Eliminar csrf_token antes de validar ---
            form_data.pop('csrf_token', None)
            # -----------------------------------------------

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
        Orquesta el proceso de aprobación de una orden PENDIENTE, delegando la
        lógica a helpers según la disponibilidad de stock.
        """
        try:
            orden_produccion, error_response = self._validar_estado_para_aprobacion(orden_id)
            if error_response:
                return error_response

            verificacion_result = self.inventario_controller.verificar_stock_para_op(orden_produccion)
            if not verificacion_result.get('success'):
                return self.error_response(f"Error al verificar stock: {verificacion_result.get('error')}", 500)

            insumos_faltantes = verificacion_result['data']['insumos_faltantes']

            if insumos_faltantes:
                return self._gestionar_stock_faltante(orden_produccion, insumos_faltantes, usuario_id)
            else:
                return self._gestionar_stock_disponible(orden_produccion, usuario_id)

        except Exception as e:
            logger.error(f"Error en el proceso de aprobación de OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def _generar_orden_de_compra_automatica(self, insumos_faltantes: List[Dict], usuario_id: int, orden_produccion_id: int) -> Dict:
        from collections import defaultdict
        
        items_por_proveedor = defaultdict(list)
        
        # 1. Agrupar insumos por proveedor
        for insumo in insumos_faltantes:
            try:
                insumo_id = insumo['insumo_id']
                insumo_data_res, _ = self.insumo_controller.obtener_insumo_por_id(insumo_id)
                if not insumo_data_res.get('success'):
                    return {'success': False, 'error': f"No se encontró el insumo con ID {insumo_id}."}
                
                insumo_data = insumo_data_res['data']
                proveedor_id = insumo_data.get('id_proveedor')
                if not proveedor_id:
                    return {'success': False, 'error': f"El insumo '{insumo_data.get('nombre')}' no tiene un proveedor asociado."}

                cantidad_redondeada = math.ceil(insumo['cantidad_faltante'])
                if cantidad_redondeada <= 0: continue

                items_por_proveedor[proveedor_id].append({
                    'insumo_id': insumo_id,
                    'cantidad_solicitada': cantidad_redondeada,
                    'precio_unitario': float(insumo_data.get('precio_unitario', 0))
                })
            except Exception as e:
                logger.error(f"Error procesando insumo faltante {insumo.get('insumo_id')}: {e}")
                return {'success': False, 'error': f"Error al procesar insumo {insumo.get('insumo_id')}: {e}"}

        if not items_por_proveedor:
            return {'success': False, 'error': 'No hay insumos válidos para generar órdenes de compra.'}

        # 2. Crear una OC por cada proveedor
        resultados_creacion = []
        for proveedor_id, items in items_por_proveedor.items():
            subtotal = sum(item['cantidad_solicitada'] * item['precio_unitario'] for item in items)
            iva = subtotal * 0.21
            total = subtotal + iva

            datos_oc = {
                'proveedor_id': proveedor_id,
                'fecha_emision': date.today().isoformat(),
                'prioridad': 'ALTA',
                'observaciones': f"Generada automáticamente para OP ID: {orden_produccion_id}",
                'orden_produccion_id': orden_produccion_id,
                'subtotal': round(subtotal, 2),
                'iva': round(iva, 2),
                'total': round(total, 2)
            }
            
            items_para_crear = [{'insumo_id': i['insumo_id'], 'cantidad_solicitada': i['cantidad_solicitada'], 'precio_unitario': i['precio_unitario'], 'cantidad_recibida': 0.0} for i in items]

            resultado = self.orden_compra_controller.crear_orden(datos_oc, items_para_crear, usuario_id)
            if resultado.get('success'):
                resultados_creacion.append(resultado['data'])
            else:
                # Si una falla, se retorna el error de esa OC. En un sistema más complejo, se podría implementar un rollback.
                return {'success': False, 'error': f"Fallo al crear OC para proveedor {proveedor_id}: {resultado.get('error')}"}

        return {'success': True, 'data': resultados_creacion, 'message': f'Se crearon {len(resultados_creacion)} órdenes de compra.'}

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
            from flask_jwt_extended import get_jwt_identity

            orden_result = self.obtener_orden_por_id(orden_id)
            if not orden_result.get('success'):
                return self.error_response("Orden de producción no encontrada.", 404)
            orden_produccion = orden_result['data']
            estado_actual = orden_produccion['estado']

            if nuevo_estado == 'COMPLETADA':
                usuario_id_actual = get_jwt_identity()
                self.model.update(orden_id, {'supervisor_calidad_id': usuario_id_actual}, 'id')
                if not estado_actual or estado_actual.strip() != 'CONTROL_DE_CALIDAD':
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
                # La lógica del cronómetro se ha movido a otros métodos para evitar la doble detención.
                # El cronómetro ahora se detiene cuando se reporta el 100% o cuando se pausa.

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
        Orquesta la fusión de varias OPs en una Super OP, delegando cada
        paso a métodos auxiliares privados.
        """
        try:
            ops_originales, error = self._validar_y_obtener_ops_para_consolidar(op_ids)
            if error:
                return error

            super_op_data = self._calcular_datos_super_op(ops_originales, op_ids)

            resultado_creacion = self.crear_orden(super_op_data, usuario_id)
            if not resultado_creacion.get('success'):
                return resultado_creacion

            nueva_super_op = resultado_creacion['data']

            relink_result = self._relinkear_items_pedido(op_ids, nueva_super_op['id'])
            if not relink_result.get('success'):
                # NOTA: En un sistema real, aquí se debería intentar revertir la creación de la Super OP.
                return relink_result

            self._actualizar_ops_originales(op_ids, nueva_super_op['id'])

            return {'success': True, 'data': nueva_super_op}
        except Exception as e:
            logger.error(f"Error en consolidar_ordenes_produccion: {e}", exc_info=True)
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
        2. Asigna automáticamente un supervisor de producción.
        3. Ejecuta la lógica de aprobación (verificar stock, reservar/crear OC, cambiar estado).
        """
        try:
            from datetime import time, datetime
            fecha_inicio_confirmada = data.get('fecha_inicio_planificada')
            if not fecha_inicio_confirmada:
                return self.error_response("Debe seleccionar una fecha de inicio.", 400)

            update_data = {'fecha_inicio_planificada': fecha_inicio_confirmada}

            # --- LÓGICA DE ASIGNACIÓN AUTOMÁTICA DE SUPERVISOR ---
            supervisores_resp, status_code = self.usuario_controller.obtener_usuarios_por_rol(['SUPERVISOR'])

            if status_code != 200:
                # Si falla la obtención de supervisores, no es un error fatal.
                # Se registra una advertencia y se procede sin asignar supervisor.
                error_message = supervisores_resp.get('error', 'Error desconocido') if isinstance(supervisores_resp, dict) else str(supervisores_resp)
                logger.warning(f"No se pudieron obtener supervisores para asignación automática: {error_message}. La orden se aprobará sin supervisor.")
                supervisores = [] # Asegurarse de que la lista esté vacía para continuar
            else:
                supervisores = supervisores_resp.get('data', [])
            
            # TODO: Usar la hora real de la OP si está disponible. Por ahora, asumimos el inicio del turno de la mañana.
            target_time = time(8, 0, 0) 
            assigned_supervisor_id = None

            for supervisor in supervisores:
                in_produccion = any(s and s.get('codigo') == 'PRODUCCION' for s in supervisor.get('sectores', []))
                if not in_produccion:
                    continue

                turno = supervisor.get('turno')
                if turno and turno.get('hora_inicio') and turno.get('hora_fin'):
                    try:
                        hora_inicio = time.fromisoformat(turno['hora_inicio'])
                        hora_fin = time.fromisoformat(turno['hora_fin'])
                        
                        if hora_inicio <= hora_fin:
                            if hora_inicio <= target_time < hora_fin:
                                assigned_supervisor_id = supervisor.get('id')
                                break
                        else:
                            if target_time >= hora_inicio or target_time < hora_fin:
                                assigned_supervisor_id = supervisor.get('id')
                                break
                    except (ValueError, TypeError) as e:
                        logger.warning(f"No se pudo parsear el turno para supervisor {supervisor.get('id')}: {e}")

            if assigned_supervisor_id:
                update_data['supervisor_responsable_id'] = assigned_supervisor_id
                logger.info(f"Supervisor {assigned_supervisor_id} asignado automáticamente a la OP {orden_id}.")
            # --- FIN DE LA LÓGICA DE ASIGNACIÓN ---

            update_result = self.model.update(orden_id, update_data, 'id')
            if not update_result.get('success'):
                return self.error_response(f"Error al guardar fecha y supervisor: {update_result.get('error')}", 500)

            aprobacion_dict, aprobacion_status_code = self.aprobar_orden(orden_id, usuario_id)

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

    def obtener_datos_para_tablero(self) -> Dict:
        """
        Prepara los datos necesarios para el tablero Kanban de producción.
        """
        from collections import defaultdict
        from datetime import datetime, timedelta

        try:
            # 1. Definir las columnas del tablero
            columnas = {
                'EN ESPERA': 'En Espera',
                'LISTA PARA PRODUCIR': 'Lista para producir',
                'EN_LINEA_1': 'Línea 1',
                'EN_LINEA_2': 'Línea 2',
                'EN_EMPAQUETADO': 'Empaquetado',
                'CONTROL_DE_CALIDAD': 'Control de Calidad',
            }

            # 2. Obtener todas las órdenes de producción relevantes
            response, status_code = self.obtener_ordenes({'estado.neq': 'CANCELADA'})
            ordenes = []
            if status_code == 200 and response.get('success'):
                ordenes = response.get('data', [])

            # 3. Agrupar órdenes por estado
            ordenes_por_estado = defaultdict(list)

            for orden in ordenes:
                estado = orden.get('estado')
                if estado in columnas:
                    ordenes_por_estado[estado].append(orden)

            # 4. Obtener datos para los modales (supervisores y operarios)
            todos_los_usuarios = self.usuario_controller.obtener_todos_los_usuarios()
            supervisores = [u for u in todos_los_usuarios if u.get('roles', {}).get('codigo') == 'SUPERVISOR']
            operarios = [u for u in todos_los_usuarios if u.get('roles', {}).get('codigo') == 'OPERARIO']

            return {
                'columnas': columnas,
                'ordenes_por_estado': dict(ordenes_por_estado),
                'supervisores': supervisores,
                'operarios': operarios,
                'now': datetime.now(),
                'timedelta': timedelta
            }
        except Exception as e:
            logger.error(f"Error en obtener_datos_para_tablero: {e}", exc_info=True)
            return {
                'columnas': {}, 'ordenes_por_estado': {}, 'supervisores': [], 'operarios': [],
                'now': datetime.now(), 'timedelta': timedelta, 'error': str(e)
            }

    def obtener_datos_para_vista_foco(self, orden_id: int) -> tuple:
        """
        Prepara todos los datos necesarios para la vista de foco de una orden de producción.
        """
        try:
            # 1. Obtener los datos principales de la orden
            orden_result = self.obtener_orden_por_id(orden_id)
            if not orden_result.get('success'):
                return self.error_response("Orden de producción no encontrada.", 404)
            orden_data = orden_result['data']

            # 2. Obtener los ingredientes de la receta
            receta_id = orden_data.get('receta_id')
            ingredientes = []
            if receta_id:
                receta_model = RecetaModel()
                ingredientes_result = receta_model.get_ingredientes(receta_id)
                if ingredientes_result.get('success'):
                    ingredientes = ingredientes_result.get('data', [])

            # 3. Calcular Ritmo Objetivo
            orden_data['ritmo_objetivo'] = self._calcular_ritmo_objetivo(orden_data)

            # 3. Obtener los motivos de paro y desperdicio
            motivo_paro_model = MotivoParoModel()
            motivos_paro_result = motivo_paro_model.find_all()
            motivos_paro = motivos_paro_result.get('data', []) if motivos_paro_result.get('success') else []

            motivo_desperdicio_model = MotivoDesperdicioModel()
            motivos_desperdicio_result = motivo_desperdicio_model.find_all()
            motivos_desperdicio = motivos_desperdicio_result.get('data', []) if motivos_desperdicio_result.get('success') else []

            # 4. Ensamblar todos los datos
            datos_completos = {
                'orden': orden_data,
                'ingredientes': ingredientes,
                'motivos_paro': motivos_paro,
                'motivos_desperdicio': motivos_desperdicio
            }

            return self.success_response(data=datos_completos)

        except Exception as e:
            logger.error(f"Error en obtener_datos_para_vista_foco para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    # endregion

    # region Helpers de Aprobación

    def _validar_estado_para_aprobacion(self, orden_id: int) -> tuple:
        """Obtiene una OP y valida que su estado sea 'PENDIENTE'."""
        orden_result = self.obtener_orden_por_id(orden_id)
        if not orden_result.get('success'):
            return None, self.error_response("Orden de producción no encontrada.", 404)

        orden_produccion = orden_result['data']
        if orden_produccion['estado'] != 'PENDIENTE':
            return None, self.error_response(f"La orden ya está en estado '{orden_produccion['estado']}'.", 400)

        return orden_produccion, None

    def _gestionar_stock_faltante(self, orden_produccion: Dict, insumos_faltantes: List[Dict], usuario_id: int) -> tuple:
        """Gestiona el caso donde falta stock, generando una OC y actualizando el estado de la OP."""
        orden_id = orden_produccion['id']
        logger.info(f"Stock insuficiente para OP {orden_id}. Generando OC...")
        oc_result = self._generar_orden_de_compra_automatica(insumos_faltantes, usuario_id, orden_id)
        if not oc_result.get('success'):
            return self.error_response(f"Stock insuficiente, pero no se pudo generar la OC: {oc_result.get('error')}", 500)

        oc_data = oc_result.get('data', {})
        created_oc_id = oc_data.get('id')
        if created_oc_id:
            logger.info(f"OC {oc_data.get('codigo_oc', created_oc_id)} creada. Vinculando a OP {orden_id}...")
            self.model.update(orden_id, {'orden_compra_id': created_oc_id}, 'id')
        else:
            logger.error(f"OC creada para OP {orden_id}, pero no se recibió el ID de la OC!")

        logger.info(f"Cambiando estado de OP {orden_id} a EN ESPERA.")
        self.model.cambiar_estado(orden_id, 'EN ESPERA')

        return self.success_response(
            data={'oc_generada': True, 'oc_codigo': oc_data.get('codigo_oc'), 'oc_id': created_oc_id},
            message="Stock insuficiente. Se generó OC y la OP está 'En Espera'."
        )

    def _gestionar_stock_disponible(self, orden_produccion: Dict, usuario_id: int) -> tuple:
        """Gestiona el caso donde hay stock disponible, reservando y actualizando el estado."""
        orden_id = orden_produccion['id']
        logger.info(f"Stock disponible para OP {orden_id}. Reservando insumos...")
        reserva_result = self.inventario_controller.reservar_stock_insumos_para_op(orden_produccion, usuario_id)
        if not reserva_result.get('success'):
            return self.error_response(f"Fallo crítico al reservar insumos: {reserva_result.get('error')}", 500)

        nuevo_estado_op = 'LISTA PARA PRODUCIR'
        logger.info(f"Cambiando estado de OP {orden_id} a {nuevo_estado_op}.")
        estado_change_result = self.model.cambiar_estado(orden_id, nuevo_estado_op)
        if not estado_change_result.get('success'):
            logger.error(f"Error al cambiar estado a {nuevo_estado_op} para OP {orden_id}: {estado_change_result.get('error')}")
            return self.error_response(f"Error al cambiar estado a {nuevo_estado_op}: {estado_change_result.get('error')}", 500)

        return self.success_response(
            message=f"Stock disponible. La orden está '{nuevo_estado_op}' y los insumos reservados."
        )

    # endregion

    # region Helpers de Consolidación

    def _validar_y_obtener_ops_para_consolidar(self, op_ids: List[int]) -> tuple:
        """Valida que las OPs existan, sean del mismo producto y estén en estado 'PENDIENTE'."""
        ops_a_consolidar_res = self.model.find_by_ids(op_ids)
        if not ops_a_consolidar_res.get('success') or not ops_a_consolidar_res.get('data'):
            return None, {'success': False, 'error': 'Una o más órdenes no fueron encontradas.'}

        ops_originales = ops_a_consolidar_res['data']
        if len(ops_originales) != len(op_ids):
            return None, {'success': False, 'error': 'Algunas órdenes no pudieron ser cargadas.'}

        primer_producto_id = ops_originales[0]['producto_id']
        if not all(op['producto_id'] == primer_producto_id for op in ops_originales):
            return None, {'success': False, 'error': 'Todas las órdenes deben ser del mismo producto.'}

        return ops_originales, None

    def _calcular_datos_super_op(self, ops_originales: List[Dict], op_ids: List[int]) -> Dict:
        """Calcula los datos consolidados para la nueva Super OP."""
        cantidad_total = sum(Decimal(op['cantidad_planificada']) for op in ops_originales)
        primera_op = ops_originales[0]

        fechas_meta_originales = []
        for op in ops_originales:
            fecha_meta_str = op.get('fecha_meta')
            if fecha_meta_str:
                try:
                    # --- ¡CORRECCIÓN ROBUSTA! ---
                    fecha_meta_solo_str = fecha_meta_str.split('T')[0].split(' ')[0]
                    fechas_meta_originales.append(date.fromisoformat(fecha_meta_solo_str))
                    # --- FIN CORRECCIÓN ---
                except ValueError:
                    logger.warning(f"Formato de fecha meta inválido en OP {op.get('id')}: {fecha_meta_str}")

        fecha_meta_mas_temprana = min(fechas_meta_originales) if fechas_meta_originales else None

        return {
            'producto_id': primera_op['producto_id'],
            'cantidad_planificada': str(cantidad_total),
            'fecha_planificada': primera_op.get('fecha_planificada'),
            'receta_id': primera_op['receta_id'],
            'fecha_meta': fecha_meta_mas_temprana.isoformat() if fecha_meta_mas_temprana else None,
            'prioridad': 'ALTA',
            'observaciones': f'Super OP consolidada desde las OPs: {", ".join(map(str, op_ids))}',
            'estado': 'PENDIENTE'
        }

    def _relinkear_items_pedido(self, op_ids: List[int], super_op_id: int) -> dict:
        """Actualiza los items de pedido de las OPs originales para que apunten a la nueva Super OP."""
        try:
            self.pedido_model.db.table('pedido_items').update({
                'orden_produccion_id': super_op_id
            }).in_('orden_produccion_id', op_ids).execute()
            logger.info(f"Relinkeo de items de pedido a Super OP {super_op_id} completado.")
            return {'success': True}
        except Exception as e:
            logger.error(f"CRÍTICO: Fallo al re-linkear items de pedido a Super OP {super_op_id}. Error: {e}", exc_info=True)
            return {'success': False, 'error': f'La Super OP fue creada, pero falló la asignación de pedidos. Contacte a soporte. Error: {str(e)}'}

    def _actualizar_ops_originales(self, op_ids: List[int], super_op_id: int):
        """Marca las OPs originales como 'CONSOLIDADA' y las vincula a la Super OP."""
        update_data = {
            'estado': 'CONSOLIDADA'
            # 'super_op_id': super_op_id # <-- Columna no existe, comentado
        }
        for op_id in op_ids:
            self.model.update(id_value=op_id, data=update_data, id_field='id')
        logger.info(f"OPs originales {op_ids} actualizadas a estado CONSOLIDADA.")

    def _obtener_capacidad_linea(self, linea_asignada: int, fecha: date) -> Decimal:
        """
        Obtiene la capacidad neta de una línea (en minutos) para una fecha específica.
        """
        if not linea_asignada:
            return Decimal('0.0')

        capacidad_data = self.planificacion_controller.obtener_capacidad_disponible(
            [linea_asignada], fecha, fecha
        )

        capacidad_en_minutos = capacidad_data.get(linea_asignada, {}).get(fecha.isoformat(), 0.0)
        return Decimal(str(capacidad_en_minutos))

    def _calcular_ritmo_objetivo(self, orden: Dict) -> Decimal:
        """
        Calcula el ritmo objetivo en kg/h basado en tiempo disponible y capacidad.
        """
        from datetime import datetime, date

        ritmo_necesario = Decimal('0.0')

        # Método 1: Basado en tiempo disponible hasta la fecha meta
        try:
            fecha_meta_str = orden.get('fecha_meta')
            if fecha_meta_str:
                fecha_meta = date.fromisoformat(fecha_meta_str)
                dias_disponibles = (fecha_meta - date.today()).days

                if dias_disponibles > 0:
                    capacidad_total_horizonte_minutos = Decimal('0.0')
                    for i in range(dias_disponibles):
                        fecha_a_consultar = date.today() + timedelta(days=i)
                        capacidad_total_horizonte_minutos += self._obtener_capacidad_linea(
                            orden.get('linea_asignada'), fecha_a_consultar
                        )

                    horas_disponibles = capacidad_total_horizonte_minutos / Decimal('60.0')
                    cantidad_planificada = Decimal(orden.get('cantidad_planificada', '0.0'))

                    if horas_disponibles > 0:
                        ritmo_necesario = cantidad_planificada / horas_disponibles
        except Exception as e:
            logger.warning(f"No se pudo calcular el ritmo necesario por tiempo para OP {orden.get('id')}: {e}")

        # Método 2: Basado en capacidad de la línea para el día de hoy (como referencia)
        capacidad_linea_hoy_minutos = self._obtener_capacidad_linea(orden.get('linea_asignada'), date.today())

        ritmo_por_capacidad = Decimal('0.0')
        if capacidad_linea_hoy_minutos > 0:
            # Para obtener kg/h, necesitamos saber cuántos kg se pueden hacer en esos minutos.
            # Esto depende del tiempo de producción unitario de la receta.
            receta_result = self.receta_model.find_by_id(orden.get('receta_id'), 'id')
            if receta_result.get('success'):
                receta = receta_result['data']
                campo_tiempo = f"tiempo_prod_unidad_linea{orden.get('linea_asignada')}"
                tiempo_por_unidad = Decimal(receta.get(campo_tiempo, '0.0'))

                if tiempo_por_unidad > 0:
                    unidades_por_hora = Decimal('60.0') / tiempo_por_unidad
                    # Asumiendo que 1 unidad = 1 kg. Esto podría necesitar ajuste.
                    ritmo_por_capacidad = unidades_por_hora

        # Usar el mayor de los dos (más exigente) o un default de 5 si ambos fallan
        ritmo_final = max(ritmo_necesario, ritmo_por_capacidad)

        return round(ritmo_final, 2) if ritmo_final > 0 else Decimal('5.00')


    # endregion

    def reportar_avance(self, orden_id: int, data: Dict, usuario_id: int) -> tuple:
        """
        Registra el avance de producción para una orden, incluyendo desperdicios,
        y opcionalmente finaliza la orden.
        """
        try:
            cantidad_buena = Decimal(data.get('cantidad_buena', 0))
            cantidad_desperdicio = Decimal(data.get('cantidad_desperdicio', 0))
            motivo_desperdicio_id = data.get('motivo_desperdicio_id')
            finalizar_orden = data.get('finalizar_orden', False)

            # 1. Validar datos
            if cantidad_buena < 0 or cantidad_desperdicio < 0:
                return self.error_response("Las cantidades no pueden ser negativas.", 400)
            if cantidad_desperdicio > 0 and not motivo_desperdicio_id:
                return self.error_response("Se requiere un motivo para el desperdicio.", 400)

            # 2. Registrar desperdicio si existe
            if cantidad_desperdicio > 0:
                desperdicio_model = RegistroDesperdicioModel()
                desperdicio_data = {
                    'orden_produccion_id': orden_id,
                    'motivo_desperdicio_id': int(motivo_desperdicio_id),
                    'cantidad': cantidad_desperdicio,
                    'usuario_id': usuario_id
                }
                desperdicio_model.create(desperdicio_data)

            # 3. Actualizar la cantidad producida en la orden
            orden_actual_res = self.model.find_by_id(orden_id)
            if not orden_actual_res.get('success'):
                return self.error_response("Orden de producción no encontrada.", 404)

            orden_actual = orden_actual_res.get('data', {})
            cantidad_planificada = Decimal(orden_actual.get('cantidad_planificada', 0))
            cantidad_producida_actual = Decimal(orden_actual.get('cantidad_producida', 0))
            nueva_cantidad_producida = cantidad_producida_actual + cantidad_buena

            # --- VALIDACIÓN DE CANTIDAD MÁXIMA (CON TOLERANCIA) ---
            # Se usa una pequeña tolerancia para evitar errores de punto flotante
            TOLERANCIA = Decimal('0.001')
            if nueva_cantidad_producida > cantidad_planificada + TOLERANCIA:
                return self.error_response(f"La cantidad reportada ({cantidad_buena}) excede la cantidad pendiente ({cantidad_planificada - cantidad_producida_actual}).", 400)

            # Asegurarse de no sobrepasar el límite planificado debido a la tolerancia
            update_data = {'cantidad_producida': min(nueva_cantidad_producida, cantidad_planificada)}

            # --- LÓGICA DE TRANSICIÓN DE ESTADO ---
            # Si se finaliza O la nueva cantidad alcanza el total, mover a Control de Calidad
            if finalizar_orden or nueva_cantidad_producida >= cantidad_planificada:
                update_data['estado'] = 'CONTROL_DE_CALIDAD'
                # También se debería registrar la fecha_fin
                update_data['fecha_fin'] = datetime.now().isoformat()

            self.model.update(orden_id, update_data)

            return self.success_response(message="Avance reportado correctamente.")

        except Exception as e:
            logger.error(f"Error en reportar_avance para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    def pausar_produccion(self, orden_id: int, motivo_id: int, usuario_id: int) -> tuple:
        """
        Pausa una orden de producción, cambiando su estado y registrando el paro.
        Es idempotente: si ya está pausada, devuelve éxito.
        """
        try:
            # 1. Obtener la orden y verificar su estado
            orden_result = self.obtener_orden_por_id(orden_id)
            if not orden_result.get('success'):
                return self.error_response("Orden de producción no encontrada.", 404)
            orden = orden_result['data']

            if orden.get('estado') == 'PAUSADA':
                return self.success_response(message="La orden ya se encontraba pausada.")

            if orden.get('estado') != 'EN_PROCESO':
                return self.error_response(f"No se puede pausar una orden que no está 'EN PROCESO'. Estado actual: {orden.get('estado')}", 409)

            # 2. Cambiar el estado de la orden a PAUSADA
            cambio_estado_result = self.model.cambiar_estado(orden_id, 'PAUSADA')
            if not cambio_estado_result.get('success'):
                return self.error_response(f"Error al cambiar el estado de la orden a PAUSADA: {cambio_estado_result.get('error')}", 500)

            # 3. Crear el registro de paro
            paro_model = RegistroParoModel()
            datos_pausa = {
                'orden_produccion_id': orden_id,
                'motivo_paro_id': motivo_id,
                'usuario_id': usuario_id,
                'fecha_inicio': datetime.now().isoformat()
            }
            paro_model.create(datos_pausa)

            # Pausar el cronómetro
            self.op_cronometro_controller.registrar_fin(orden_id)

            return self.success_response(message="Producción pausada correctamente.")

        except Exception as e:
            logger.error(f"Error en pausar_produccion para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    def reanudar_produccion(self, orden_id: int, usuario_id: int) -> tuple:
        """
        Reanuda una orden de producción, cambiando su estado a EN_PROCESO y
        cerrando el registro de paro activo.
        """
        try:
            # 1. Obtener la orden y verificar su estado
            orden_result = self.obtener_orden_por_id(orden_id)
            if not orden_result.get('success'):
                return self.error_response("Orden de producción no encontrada.", 404)
            orden = orden_result['data']

            if orden.get('estado') == 'EN_PROCESO':
                return self.success_response(message="La orden ya se encontraba en proceso.")

            if orden.get('estado') != 'PAUSADA':
                return self.error_response(f"No se puede reanudar una orden que no está 'PAUSADA'. Estado actual: {orden.get('estado')}", 409)

            # 2. Encontrar y cerrar el registro de paro activo
            paro_model = RegistroParoModel()
            pausa_activa_result = paro_model.find_all({'orden_produccion_id': orden_id, 'fecha_fin': 'is.null'}, limit=1)

            if not pausa_activa_result.get('data'):
                # Si no hay pausa activa pero el estado es PAUSADA, es una inconsistencia.
                # Forzamos la reanudación para desbloquear al usuario.
                logger.warning(f"Inconsistencia: OP {orden_id} está PAUSADA pero no tiene registro de paro activo. Se reanudará de todas formas.")
            else:
                pausa_activa = pausa_activa_result['data'][0]
                id_registro_paro = pausa_activa['id']
                update_data = {'fecha_fin': datetime.now().isoformat()}
                paro_model.update(id_registro_paro, update_data)

            # 3. Cambiar el estado de la orden de vuelta a EN_PROCESO
            cambio_estado_result = self.model.cambiar_estado(orden_id, 'EN_PROCESO')
            if not cambio_estado_result.get('success'):
                # Si esto falla, la OP podría quedar bloqueada en PAUSADA. Es un estado crítico.
                logger.error(f"CRÍTICO: La OP {orden_id} no pudo ser reanudada a EN_PROCESO y podría estar bloqueada.")
                return self.error_response(f"Error crítico al reanudar la orden: {cambio_estado_result.get('error')}", 500)

            # Reanudar el cronómetro
            self.op_cronometro_controller.registrar_inicio(orden_id)

            return self.success_response(message="Producción reanudada correctamente.")

        except Exception as e:
            logger.error(f"Error en reanudar_produccion para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    def obtener_ordenes_para_kanban_hoy(self) -> tuple:
        """
        Obtiene las órdenes de producción relevantes para el tablero Kanban del día.
        Esto incluye OPs que comienzan hoy y aquellas que ya están en producción.
        """
        try:
            result = self.model.get_for_kanban_hoy()

            if result.get('success'):
                return self.success_response(data=result.get('data', []))
            else:
                error_msg = result.get('error', 'Error desconocido al obtener órdenes para el Kanban de hoy.')
                return self.error_response(error_msg, 500)
        except Exception as e:
            logger.error(f"Error crítico en obtener_ordenes_para_kanban_hoy: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def iniciar_trabajo_op(self, orden_id: int, usuario_id: int) -> tuple:
        """
        Asigna una orden a un operario y cambia su estado a EN_PROCESO.
        Esta acción es idempotente: si la orden ya está asignada al usuario y en proceso, no hace nada.
        """
        try:
            # 1. Obtener la orden de producción
            orden_result = self.obtener_orden_por_id(orden_id)
            if not orden_result.get('success'):
                return self.error_response("Orden de producción no encontrada.", 404)
            orden = orden_result['data']

            # 2. Validar estado
            estado_actual = orden.get('estado')
            operario_actual = orden.get('operario_asignado_id')

            # Si ya está en proceso y asignada al mismo usuario, no hacer nada (éxito idempotente)
            if estado_actual == 'EN_PROCESO' and operario_actual == usuario_id:
                return self.success_response(message="El trabajo ya fue iniciado por este usuario.")

            # Solo se puede iniciar si está en "LISTA PARA PRODUCIR" (aceptamos ambos formatos por inconsistencia en DB)
            if estado_actual not in ['LISTA PARA PRODUCIR', 'LISTA_PARA_PRODUCIR']:
                return self.error_response(f"No se puede iniciar el trabajo. La orden está en estado '{estado_actual}'.", 409) # 409 Conflict

            # 3. Preparar y ejecutar la actualización
            update_data = {
                'operario_asignado_id': usuario_id,
                'estado': 'EN_PROCESO',
                'fecha_inicio': datetime.now().isoformat() # Registrar cuándo empezó realmente
            }

            update_result = self.model.update(orden_id, update_data)

            if update_result.get('success'):
                # Iniciar el cronómetro
                self.op_cronometro_controller.registrar_inicio(orden_id)
                return self.success_response(data=update_result.get('data'), message="Trabajo iniciado correctamente.")
            else:
                return self.error_response(f"Error al actualizar la orden: {update_result.get('error')}", 500)

        except Exception as e:
            logger.error(f"Error en iniciar_trabajo_op para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    # endregion

    # region Helpers de Aprobación

    def _validar_estado_para_aprobacion(self, orden_id: int) -> tuple:
        """Obtiene una OP y valida que su estado sea 'PENDIENTE'."""
        orden_result = self.obtener_orden_por_id(orden_id)
        if not orden_result.get('success'):
            return None, self.error_response("Orden de producción no encontrada.", 404)

        orden_produccion = orden_result['data']
        if orden_produccion['estado'] != 'PENDIENTE':
            return None, self.error_response(f"La orden ya está en estado '{orden_produccion['estado']}'.", 400)

        return orden_produccion, None

    def _gestionar_stock_faltante(self, orden_produccion: Dict, insumos_faltantes: List[Dict], usuario_id: int) -> tuple:
        """Gestiona el caso donde falta stock, generando una OC y actualizando el estado de la OP."""
        orden_id = orden_produccion['id']
        logger.info(f"Stock insuficiente para OP {orden_id}. Generando OC...")
        oc_result = self._generar_orden_de_compra_automatica(insumos_faltantes, usuario_id, orden_id)
        if not oc_result.get('success'):
            return self.error_response(f"Stock insuficiente, pero no se pudo generar la OC: {oc_result.get('error')}", 500)

        oc_data = oc_result.get('data', {})
        created_oc_id = oc_data.get('id')
        if created_oc_id:
            logger.info(f"OC {oc_data.get('codigo_oc', created_oc_id)} creada. Vinculando a OP {orden_id}...")
            self.model.update(orden_id, {'orden_compra_id': created_oc_id}, 'id')
        else:
            logger.error(f"OC creada para OP {orden_id}, pero no se recibió el ID de la OC!")

        logger.info(f"Cambiando estado de OP {orden_id} a EN ESPERA.")
        self.model.cambiar_estado(orden_id, 'EN ESPERA')

        return self.success_response(
            data={'oc_generada': True, 'oc_codigo': oc_data.get('codigo_oc'), 'oc_id': created_oc_id},
            message="Stock insuficiente. Se generó OC y la OP está 'En Espera'."
        )

    def _gestionar_stock_disponible(self, orden_produccion: Dict, usuario_id: int) -> tuple:
        """Gestiona el caso donde hay stock disponible, reservando y actualizando el estado."""
        orden_id = orden_produccion['id']
        logger.info(f"Stock disponible para OP {orden_id}. Reservando insumos...")
        reserva_result = self.inventario_controller.reservar_stock_insumos_para_op(orden_produccion, usuario_id)
        if not reserva_result.get('success'):
            return self.error_response(f"Fallo crítico al reservar insumos: {reserva_result.get('error')}", 500)

        nuevo_estado_op = 'LISTA PARA PRODUCIR'
        logger.info(f"Cambiando estado de OP {orden_id} a {nuevo_estado_op}.")
        estado_change_result = self.model.cambiar_estado(orden_id, nuevo_estado_op)
        if not estado_change_result.get('success'):
            logger.error(f"Error al cambiar estado a {nuevo_estado_op} para OP {orden_id}: {estado_change_result.get('error')}")
            return self.error_response(f"Error al cambiar estado a {nuevo_estado_op}: {estado_change_result.get('error')}", 500)

        return self.success_response(
            message=f"Stock disponible. La orden está '{nuevo_estado_op}' y los insumos reservados."
        )

    # endregion

    # region Helpers de Consolidación

    def _validar_y_obtener_ops_para_consolidar(self, op_ids: List[int]) -> tuple:
        """Valida que las OPs existan, sean del mismo producto y estén en estado 'PENDIENTE'."""
        ops_a_consolidar_res = self.model.find_by_ids(op_ids)
        if not ops_a_consolidar_res.get('success') or not ops_a_consolidar_res.get('data'):
            return None, {'success': False, 'error': 'Una o más órdenes no fueron encontradas.'}

        ops_originales = ops_a_consolidar_res['data']
        if len(ops_originales) != len(op_ids):
            return None, {'success': False, 'error': 'Algunas órdenes no pudieron ser cargadas.'}

        primer_producto_id = ops_originales[0]['producto_id']
        if not all(op['producto_id'] == primer_producto_id for op in ops_originales):
            return None, {'success': False, 'error': 'Todas las órdenes deben ser del mismo producto.'}

        return ops_originales, None

    def _calcular_datos_super_op(self, ops_originales: List[Dict], op_ids: List[int]) -> Dict:
        """Calcula los datos consolidados para la nueva Super OP."""
        cantidad_total = sum(Decimal(op['cantidad_planificada']) for op in ops_originales)
        primera_op = ops_originales[0]

        fechas_meta_originales = []
        for op in ops_originales:
            fecha_meta_str = op.get('fecha_meta')
            if fecha_meta_str:
                try:
                    fechas_meta_originales.append(date.fromisoformat(fecha_meta_str))
                except ValueError:
                    logger.warning(f"Formato de fecha meta inválido en OP {op.get('id')}: {fecha_meta_str}")

        fecha_meta_mas_temprana = min(fechas_meta_originales) if fechas_meta_originales else None

        return {
            'producto_id': primera_op['producto_id'],
            'cantidad_planificada': str(cantidad_total),
            'fecha_planificada': primera_op.get('fecha_planificada'),
            'receta_id': primera_op['receta_id'],
            'fecha_meta': fecha_meta_mas_temprana.isoformat() if fecha_meta_mas_temprana else None,
            'prioridad': 'ALTA',
            'observaciones': f'Super OP consolidada desde las OPs: {", ".join(map(str, op_ids))}',
            'estado': 'PENDIENTE'
        }

    def _relinkear_items_pedido(self, op_ids: List[int], super_op_id: int) -> dict:
        """Actualiza los items de pedido de las OPs originales para que apunten a la nueva Super OP."""
        try:
            self.pedido_model.db.table('pedido_items').update({
                'orden_produccion_id': super_op_id
            }).in_('orden_produccion_id', op_ids).execute()
            logger.info(f"Relinkeo de items de pedido a Super OP {super_op_id} completado.")
            return {'success': True}
        except Exception as e:
            logger.error(f"CRÍTICO: Fallo al re-linkear items de pedido a Super OP {super_op_id}. Error: {e}", exc_info=True)
            return {'success': False, 'error': f'La Super OP fue creada, pero falló la asignación de pedidos. Contacte a soporte. Error: {str(e)}'}

    def _actualizar_ops_originales(self, op_ids: List[int], super_op_id: int):
        """Marca las OPs originales como 'CONSOLIDADA' y las vincula a la Super OP."""
        update_data = {
            'estado': 'CONSOLIDADA'
            # 'super_op_id': super_op_id
        }
        for op_id in op_ids:
            self.model.update(id_value=op_id, data=update_data, id_field='id')
        logger.info(f"OPs originales {op_ids} actualizadas a estado CONSOLIDADA.")

    def obtener_estado_produccion_op(self, op_id: int) -> tuple:
        """
        Obtiene el estado de producción en tiempo real para una OP específica.
        Calcula el avance y devuelve datos clave.
        """
        try:
            # 1. Obtener la orden de producción
            op_result = self.obtener_orden_por_id(op_id)
            if not op_result.get('success'):
                return self.error_response("Orden de Producción no encontrada.", 404)

            orden = op_result['data']

            # 2. Extraer cantidades y calcular avance
            cantidad_planificada = Decimal(orden.get('cantidad_planificada', 0))
            cantidad_producida = Decimal(orden.get('cantidad_producida', 0))

            avance_porcentaje = 0
            if cantidad_planificada > 0:
                avance_porcentaje = round((cantidad_producida / cantidad_planificada) * 100, 2)

            # 3. Preparar la respuesta
            estado_produccion = {
                'cantidad_planificada': float(cantidad_planificada),
                'cantidad_producida': float(cantidad_producida),
                'avance_porcentaje': float(avance_porcentaje),
                'estado_actual': orden.get('estado')
            }

            return self.success_response(data=estado_produccion)

        except Exception as e:
            logger.error(f"Error al obtener estado de producción para OP {op_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def obtener_ordenes_para_planificacion(self, inicio_semana: date, fin_semana: date, horizonte_dias: int) -> tuple:
        """
        Realiza una consulta unificada para obtener todas las OPs necesarias para la
        vista de planificación, abarcando las pendientes en el horizonte y las
        planificadas en la semana.
        """
        try:
            # Calcular fechas límite para los filtros
            hoy = date.today()
            fecha_fin_horizonte = hoy + timedelta(days=horizonte_dias)
            dias_previos_margen = 14
            fecha_inicio_filtro_semanal = inicio_semana - timedelta(days=dias_previos_margen)

            # Llamar a un nuevo método en el modelo que combina las consultas
            result = self.model.get_all_for_planificacion(
                fecha_fin_horizonte=fecha_fin_horizonte,
                fecha_inicio_semanal=fecha_inicio_filtro_semanal,
                fecha_fin_semanal=fin_semana
            )

            if result.get('success'):
                return self.success_response(data=result.get('data', []))
            else:
                return self.error_response(result.get('error', 'Error al obtener órdenes para planificación.'), 500)

        except Exception as e:
            logger.error(f"Error crítico en obtener_ordenes_para_planificacion: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)
    # endregion