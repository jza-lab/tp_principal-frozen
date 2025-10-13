from app.controllers.base_controller import BaseController
from app.models.orden_produccion import OrdenProduccionModel
from app.schemas.orden_produccion_schema import OrdenProduccionSchema
from typing import Dict, Optional, List
from marshmallow import ValidationError
from app.controllers.producto_controller import ProductoController
from app.controllers.receta_controller import RecetaController
from app.controllers.usuario_controller import UsuarioController
from datetime import datetime
import logging

# --- NUEVAS IMPORTACIONES Y DEPENDENCIAS ---
from app.controllers.inventario_controller import InventarioController
from app.controllers.orden_compra_controller import OrdenCompraController
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

# app/controllers/orden_produccion_controller.py

    def crear_orden(self, form_data: Dict, usuario_id: int) -> Dict:
        """
        Valida datos y crea una orden en estado PENDIENTE.
        """
        from app.models.receta import RecetaModel
        receta_model = RecetaModel()

        try:
            # --- INICIO DE LA CORRECCIÓN DE VALIDACIÓN ---

            # Si el supervisor_id está presente pero vacío, lo eliminamos
            # para que no cause un error de validación de tipo entero.
            if 'supervisor_responsable_id' in form_data and not form_data['supervisor_responsable_id']:
                form_data.pop('supervisor_responsable_id')

            # --- FIN DE LA CORRECCIÓN DE VALIDACIÓN ---

            # El resto de la lógica de búsqueda de receta que ya corregimos
            producto_id = form_data.get('producto_id')
            if not producto_id:
                return self.error_response('El campo producto_id es requerido.', 400)

            if 'cantidad' in form_data:
                form_data['cantidad_planificada'] = form_data.pop('cantidad')

            # ... resto de la lógica hasta la creación ...
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
##            if result.get('success'):
##                result['data'] = self.schema.dump(result['data'])
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

    def aprobar_orden(self, orden_id: int, usuario_id: int) -> Dict:
            """
            Aprueba una orden, reserva insumos y si faltan, crea una Orden de Compra.
            """
            try:
                # 1. Obtener la orden de producción completa
                orden_result = self.obtener_orden_por_id(orden_id)
                if not orden_result.get('success'):
                    return self.error_response("Orden de producción no encontrada.", 404)
                orden_produccion = orden_result['data']

                if orden_produccion['estado'] != 'PENDIENTE':
                    return self.error_response(f"La orden ya está en estado '{orden_produccion['estado']}'.", 400)

                # 2. Cambiar el estado a APROBADA
                self.cambiar_estado_orden(orden_id, 'APROBADA')

                # 3. Intentar reservar los insumos necesarios
                reserva_result = self.inventario_controller.reservar_stock_insumos_para_op(orden_produccion, usuario_id)

                if not reserva_result.get('success'):
                    # Si la reserva falla, podríamos revertir el estado o simplemente notificar
                    return self.error_response(f"Se aprobó la orden, pero falló la reserva de insumos: {reserva_result.get('error')}", 500)

                # 4. Verificar si hay insumos faltantes y crear Orden de Compra
                insumos_faltantes = reserva_result['data']['insumos_faltantes']
                orden_compra_creada = None

                if insumos_faltantes:
                    logger.info(f"Faltan insumos para la OP {orden_id}. Generando Orden de Compra automática.")
                    resultado_oc = self._generar_orden_de_compra_automatica(insumos_faltantes, usuario_id)
                    if resultado_oc.get('success'):
                        orden_compra_creada = resultado_oc.get('data')

                # 5. Devolver una respuesta completa
                message = "Orden de Producción aprobada y stock de insumos reservado."
                if orden_compra_creada:
                    message += f" Se generó la Orden de Compra {orden_compra_creada['codigo_oc']} para cubrir faltantes."

                return self.success_response({'orden_compra_generada': orden_compra_creada}, message)

            except Exception as e:
                logger.error(f"Error en el proceso de aprobación de OP {orden_id}: {e}", exc_info=True)
                return self.error_response(f"Error interno: {str(e)}", 500)

    def _generar_orden_de_compra_automatica(self, insumos_faltantes: List[Dict], usuario_id: int) -> Dict:
        """
        Helper para crear una OC a partir de una lista de insumos faltantes.
        NOTA: Esta es una implementación simple. Una versión avanzada podría agrupar por proveedor.
        """
        # Simplificación: Asumimos un proveedor por defecto o el primero que encontremos.
        # Aquí deberías implementar tu lógica para seleccionar al proveedor adecuado.
        proveedor_id_por_defecto = 1 # ¡¡IMPORTANTE: CAMBIAR ESTO!!

        items_oc = []
        for insumo in insumos_faltantes:
            items_oc.append({
                'insumo_id': insumo['insumo_id'],
                'cantidad_solicitada': insumo['cantidad_faltante'],
                'precio_unitario': 0  # El precio se deberá negociar/actualizar después
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
            'insumo_id[]': [item['insumo_id'] for item in items_oc],
            'cantidad_solicitada[]': [item['cantidad_solicitada'] for item in items_oc],
            'precio_unitario[]': [item['precio_unitario'] for item in items_oc]
        }

        return self.orden_compra_controller.crear_orden(form_data_simulado, usuario_id)

    def rechazar_orden(self, orden_id: int, motivo: str) -> Dict:
        """
        Rechaza una orden, cambiando su estado a CANCELADA.
        """
        return self.model.cambiar_estado(orden_id, 'CANCELADA', observaciones=f"Rechazada: {motivo}")

    def cambiar_estado_orden(self, orden_id: int, nuevo_estado: str) -> tuple:
        """
        Cambia el estado de una orden (ej. 'EN_PROCESO', 'COMPLETADA').
        Si el nuevo estado es 'EN_PROCESO', verifica el stock antes de cambiarlo.
        """
        try:
            if nuevo_estado == 'EN_PROCESO':
                # 1. Obtener la orden de producción completa
                orden_result = self.obtener_orden_por_id(orden_id)
                if not orden_result.get('success'):
                    return self.error_response("Orden de producción no encontrada.", 404)
                orden_produccion = orden_result['data']

                # Solo se puede iniciar si está APROBADA
                if orden_produccion['estado'] != 'APROBADA':
                    return self.error_response(f"La orden debe estar en estado 'APROBADA' para poder iniciarla. Estado actual: {orden_produccion['estado']}", 400)

                # 2. Verificar si hay stock suficiente
                verificacion_result = self.inventario_controller.verificar_stock_para_op(orden_produccion)
                if not verificacion_result.get('success'):
                    return self.error_response(f"No se pudo verificar el stock: {verificacion_result.get('error')}", 500)

                insumos_faltantes = verificacion_result['data']['insumos_faltantes']
                if insumos_faltantes:
                    mensaje_error = "No se puede iniciar la producción por falta de stock de los siguientes insumos: "
                    detalles = [f"{insumo['nombre']} (falta: {insumo['cantidad_faltante']})" for insumo in insumos_faltantes]
                    mensaje_error += ", ".join(detalles)
                    return self.error_response(mensaje_error, 409)

            # Si pasa la validación o el estado no es 'EN_PROCESO', cambiamos el estado.
            result = self.model.cambiar_estado(orden_id, nuevo_estado)

            if result.get('success'):
                return self.success_response(data=result.get('data'), message=result.get('message'))
            else:
                return self.error_response(result.get('error', 'Error al cambiar el estado.'), 500)

        except Exception as e:
            logger.error(f"Error en cambiar_estado_orden para la orden {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def crear_orden_desde_planificacion(self, producto_id: int, item_ids: List[int], usuario_id: int) -> Dict:
        """
        Orquesta la creación de una orden consolidada desde el módulo de planificación.
        CORREGIDO: Opera sobre item_ids y actualiza los ítems en lote.
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
                'prioridad': 'NORMAL'
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
            todos_los_usuarios = self.usuario_controller.obtener_todos()
            operarios = [u for u in todos_los_usuarios if u.get('rol') in ['OPERARIO', 'SUPERVISOR']]

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