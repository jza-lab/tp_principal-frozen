from app.controllers.base_controller import BaseController
from app.models.orden_produccion import OrdenProduccionModel
from app.schemas.orden_produccion_schema import OrdenProduccionSchema
from typing import Dict, Optional, List
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
from datetime import date

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
        Valida datos y crea una orden en estado PENDIENTE.
        """
        from app.models.receta import RecetaModel
        receta_model = RecetaModel()

        try:
            # Si el supervisor_responsable_id está presente pero vacío, lo eliminamos
            if 'supervisor_responsable_id' in form_data and not form_data['supervisor_responsable_id']:
                form_data.pop('supervisor_responsable_id')

            producto_id = form_data.get('producto_id')
            if not producto_id:
                return self.error_response('El campo producto_id es requerido.', 400)

            if 'cantidad' in form_data:
                form_data['cantidad_planificada'] = form_data.pop('cantidad')

            receta_result = receta_model.find_all({'producto_id': int(producto_id), 'activa': True}, limit=1)
            if not receta_result.get('success') or not receta_result.get('data'):
                return self.error_response(f'No se encontró una receta activa para el producto seleccionado (ID: {producto_id}).', 404)
            receta = receta_result['data'][0]
            form_data['receta_id'] = receta['id']

            validated_data = self.schema.load(form_data)
            validated_data['codigo'] = f"OP-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            validated_data['estado'] = 'PENDIENTE'
            validated_data['usuario_creador_id'] = usuario_id

            result = self.model.create(validated_data)
            return result

        except ValidationError as e:
            return self.error_response(f"Datos inválidos: {e.messages}", 400)
        except Exception as e:
            logger.error(f"Error inesperado en crear_orden: {e}", exc_info=True)
            return self.error_response(f'Error interno: {str(e)}', 500)

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
        Aprueba una orden SOLO SI HAY STOCK SUFICIENTE. Si no hay, retorna un error
        indicando la acción de crear OC.
        """
        try:
            # 1. Obtener la orden de producción completa
            orden_result = self.obtener_orden_por_id(orden_id)
            if not orden_result.get('success'):
                return self.error_response("Orden de producción no encontrada.", 404)
            orden_produccion = orden_result['data']

            if orden_produccion['estado'] != 'PENDIENTE':
                return self.error_response(f"La orden ya está en estado '{orden_produccion['estado']}'.", 400)

            # 2. Dry Run: Verificar si hay stock suficiente SIN RESERVAR NADA
            verificacion_result = self.inventario_controller.verificar_stock_para_op(orden_produccion)
            
            if not verificacion_result.get('success'):
                return self.error_response(f"Error del sistema al verificar stock: {verificacion_result.get('error')}", 500)

            insumos_faltantes = verificacion_result['data']['insumos_faltantes']
            
            # 3. SI HAY FALTANTES: Detener y retornar un código especial (409) con los datos.
            if insumos_faltantes:
                mensaje_error = "No se puede aprobar la producción por **falta de stock** de los siguientes insumos:"
                detalles = [f"{insumo['nombre']} (falta: {insumo['cantidad_faltante']})" for insumo in insumos_faltantes]
                
                # Prepara el mensaje de error para el frontend (con saltos de línea y guiones)
                mensaje_error += " - " + " - ".join(detalles)
                
                # Retorno directo del diccionario de error con los datos necesarios
                return (
                    {
                        'success': False,
                        'error': mensaje_error,
                        'data': {'insumos_faltantes': insumos_faltantes} 
                    }, 
                    409
                )
                
            # 4. SI NO HAY FALTANTES: Continuar con la aprobación y reserva.
            
            # A. Cambiar el estado a APROBADA (Esto actualiza fechas de aprobación y estimadas)
            cambio_estado_result, status_code = self.cambiar_estado_orden(orden_id, 'APROBADA')
            
            if status_code != 200:
                 return cambio_estado_result, status_code

            # B. Intentar reservar los insumos necesarios (Reserva real)
            reserva_result = self.inventario_controller.reservar_stock_insumos_para_op(orden_produccion, usuario_id)

            if not reserva_result.get('success'):
                # Error crítico: la verificación pasó, pero la reserva falló.
                return self.error_response(f"Fallo crítico: La orden se aprobó pero la reserva de insumos falló: {reserva_result.get('error')}", 500)
                
            # Se ha aprobado y reservado.
            return self.success_response(None, "Orden aprobada y stock de insumos reservado.")

        except Exception as e:
            logger.error(f"Error en el proceso de aprobación de OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def _generar_orden_de_compra_automatica(self, insumos_faltantes: List[Dict], usuario_id: int) -> Dict:
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
            'observaciones': 'Orden de Compra generada automáticamente para cubrir faltante de producción.',
        }

        # Simulamos los datos como si vinieran de un form para reusar el método del controlador
        form_data_simulado = {
            **datos_oc,
            'insumo_id[]': [item['insumo_id'] for item in items_oc_para_form],
            'cantidad_solicitada[]': [item['cantidad_faltante'] for item in items_oc_para_form],
            'precio_unitario[]': [item['precio_unitario'] for item in items_oc_para_form]
        }

        return self.orden_compra_controller.crear_orden(form_data_simulado, usuario_id)
    
    def generar_orden_de_compra_automatica(self, insumos_faltantes: List[Dict], usuario_id: int) -> Dict:
        """Wrapper publico para el helper privado _generar_orden_de_compra_automatica."""
        return self._generar_orden_de_compra_automatica(insumos_faltantes, usuario_id)


    def rechazar_orden(self, orden_id: int, motivo: str) -> Dict:
        """
        Rechaza una orden, cambiando su estado a CANCELADA.
        """
        return self.model.cambiar_estado(orden_id, 'CANCELADA', observaciones=f"Rechazada: {motivo}")

    def cambiar_estado_orden(self, orden_id: int, nuevo_estado: str) -> tuple:
            """
            Cambia el estado de una orden.
            Si el estado es 'COMPLETADA', genera el lote de producto terminado.
            """
            try:
                orden_result = self.obtener_orden_por_id(orden_id)
                if not orden_result.get('success'):
                    return self.error_response("Orden de producción no encontrada.", 404)
                orden_produccion = orden_result['data']
                
                # 1. Validación de estado para INICIAR
                if nuevo_estado == 'EN_PROCESO':
                    if orden_produccion['estado'] != 'APROBADA':
                        return self.error_response(f"La orden debe estar en estado 'APROBADA' para poder iniciarla. Estado actual: {orden_produccion['estado']}", 400)
                    # Lógica de reserva/verificación de stock eliminada.

                # 2. Lógica para COMPLETAR la OP
                if nuevo_estado == 'COMPLETADA':
                    if orden_produccion['estado'] != 'EN_PROCESO':
                        return self.error_response(f"La orden debe estar en estado 'EN_PROCESO' para poder completarla. Estado actual: {orden_produccion['estado']}", 400)
                    
                    # A. Obtener el origen de la orden para la trazabilidad del lote
                    # El campo 'pedido_id' en la OP es nuestra referencia principal (si existe).
                    referencia_pedido_id = orden_produccion.get('pedido_id') 
                    
                    # B. Determinar la fuente del lote (Pedido vs. Stock)
                    if referencia_pedido_id:
                        origen_lote = f"Pedido PED-{referencia_pedido_id}"
                    else:
                        origen_lote = "Stock Interno"

                    # C. Preparar los datos del nuevo lote
                    datos_lote = {
                        'producto_id': orden_produccion['producto_id'],
                        'cantidad_inicial': orden_produccion['cantidad_planificada'],
                        'orden_produccion_id': orden_id,
                        'fecha_produccion': date.today().isoformat(),
                        'observaciones': f"Origen: {origen_lote}. " + (orden_produccion.get('observaciones') or ''),
                        # Se asume una vida útil por defecto si el producto no la tiene o el modelo de lote la infiere.
                        'fecha_vencimiento': (date.today() + timedelta(days=90)).isoformat() # Usamos 90 días por defecto
                    }
                    
                    # D. Crear el lote de producto terminado
                    # El método `crear_lote` de LoteProductoController espera {cantidad_inicial, producto_id, etc.}
                    resultado_lote, status_lote = self.lote_producto_controller.crear_lote_desde_formulario(
                        datos_lote,
                        usuario_id=orden_produccion.get('usuario_creador_id', 1) # Usar ID del creador o 1 si es None
                    )

                    if status_lote >= 400:
                        # Detener el cambio de estado si falla la creación del lote
                        return self.error_response(f"Fallo al registrar el lote de producto terminado: {resultado_lote.get('error', 'Error desconocido')}", 500)
                    
                # 3. Cambiar el estado en la base de datos (y actualizar fechas)
                result = self.model.cambiar_estado(orden_id, nuevo_estado)

                if result.get('success'):
                    # Inyectar un mensaje más informativo para el frontend
                    if nuevo_estado == 'COMPLETADA' and 'resultado_lote' in locals() and resultado_lote.get('success'):
                        message_to_use = f"Orden completada. Lote N° {resultado_lote['data']['numero_lote']} registrado en Inventario de Productos ({origen_lote})."
                    elif nuevo_estado == 'EN_PROCESO':
                        message_to_use = "Producción iniciada correctamente. Insumos reservados."
                    else:
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