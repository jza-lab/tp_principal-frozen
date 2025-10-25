from typing import Dict, TYPE_CHECKING
from flask import request, jsonify
from app.models.orden_compra_model import OrdenCompraItemModel, OrdenCompraModel
from app.models.orden_compra_model import OrdenCompra
from app.controllers.inventario_controller import InventarioController
from app.controllers.insumo_controller import InsumoController
from datetime import datetime, date
import logging
from app.utils import estados

logger = logging.getLogger(__name__)

# --- AÑADIR ESTE BLOQUE ---
# Esto permite usar el nombre para type hints sin causar importación circular
if TYPE_CHECKING:
    from app.controllers.orden_produccion_controller import OrdenProduccionController
# -------------------------

class OrdenCompraController:
    def __init__(self):
        self.model = OrdenCompraModel()
        self.inventario_controller = InventarioController()
        self.insumo_controller = InsumoController()


    def _parse_form_data(self, form_data):
        """
        Parsea los datos del formulario web o de un diccionario, calcula los totales
        y prepara los datos para la creación/actualización de la orden.
        """
        orden_data = {
            'proveedor_id': form_data.get('proveedor_id'),
            'fecha_emision': form_data.get('fecha_emision'),
            'fecha_estimada_entrega': form_data.get('fecha_estimada_entrega'),
            'prioridad': form_data.get('prioridad'),
            'observaciones': form_data.get('observaciones'),
            # >>> AÑADE ESTA LÍNEA CRÍTICA <<<
            'orden_produccion_id': form_data.get('orden_produccion_id'),
        }

        items_data = []
        subtotal_calculado = 0.0

        # Determinar si los datos vienen de un form de Flask o de un dict (ej. JSON)
        if hasattr(form_data, 'getlist'):
            insumo_ids = form_data.getlist('insumo_id[]')
            # Se busca 'cantidad_solicitada' y, si no existe, se usa 'cantidad_faltante' como fallback
            cantidades = form_data.getlist('cantidad_solicitada[]')
            if not cantidades:
                cantidades = form_data.getlist('cantidad_faltante[]')
            precios = form_data.getlist('precio_unitario[]')
        else:
            insumo_ids = form_data.get('insumo_id[]', [])
            cantidades = form_data.get('cantidad_solicitada[]', [])
            if not cantidades:
                cantidades = form_data.get('cantidad_faltante[]', [])
            precios = form_data.get('precio_unitario[]', [])

        for i in range(len(insumo_ids)):
            if insumo_ids[i]:
                try:
                    cantidad = float(cantidades[i] or 0)
                    precio = float(precios[i] or 0)
                    item_subtotal = cantidad * precio
                    subtotal_calculado += item_subtotal

                    items_data.append({
                        'insumo_id': insumo_ids[i],
                        'cantidad_solicitada': cantidad,
                        'precio_unitario': precio,
                        'cantidad_recibida': 0.0
                    })
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parseando item de orden de compra: {e}")
                    continue

        # Calcular IVA y Total
        iva_calculado = subtotal_calculado * 0.21
        total_calculado = subtotal_calculado + iva_calculado

        # Sobrescribir los valores en orden_data con los calculados en el backend
        orden_data['subtotal'] = round(subtotal_calculado, 2)
        orden_data['iva'] = round(iva_calculado, 2)
        orden_data['total'] = round(total_calculado, 2)

        return orden_data, items_data

    def crear_orden(self, form_data, usuario_id):
        """
        Crea una nueva orden de compra a partir de datos de un formulario web.
        """
        try:
            orden_data, items_data = self._parse_form_data(form_data)

            if not orden_data.get('proveedor_id') or not orden_data.get('fecha_emision'):
                return {'success': False, 'error': 'El proveedor y la fecha de emisión son obligatorios.'}

            orden_data['usuario_creador_id'] = usuario_id
            orden_data['codigo_oc'] = f"OC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            orden_data['estado'] = estados.OC_PENDIENTE

            result = self.model.create_with_items(orden_data, items_data)
            
            if result.get('success'):
                result['data'] = estados.traducir_objeto_a_cadena(result['data'])

            return result

        except Exception as e:
            logger.error(f"Error en el controlador al crear la orden: {e}")
            return {'success': False, 'error': str(e)}

    def actualizar_orden(self, orden_id, form_data):
        """
        Actualiza una orden de compra existente a partir de datos de un formulario web.
        """
        try:
            orden_data, items_data = self._parse_form_data(form_data)

            if not orden_data.get('proveedor_id') or not orden_data.get('fecha_emision'):
                return {'success': False, 'error': 'El proveedor y la fecha de emisión son obligatorios.'}

            result = self.model.update_with_items(orden_id, orden_data, items_data)
            
            if result.get('success'):
                result['data'] = estados.traducir_objeto_a_cadena(result['data'])

            return result

        except Exception as e:
            logger.error(f"Error en el controlador al actualizar la orden: {e}")
            return {'success': False, 'error': str(e)}

    def get_orden(self, orden_id):
        """
        Obtiene una orden de compra específica con todos los detalles.
        """
        try:
            result = self.model.get_one_with_details(orden_id)
            if result.get('success'):
                result['data'] = estados.traducir_objeto_a_cadena(result['data'])
                return result, 200
            else:
                return result, 404
        except Exception as e:
            logger.error(f"Error en el controlador al obtener la orden {orden_id}: {e}")
            return {'success': False, 'error': str(e)}, 500

    def get_orden_by_codigo(self, codigo_oc):
        try:
            result = self.model.find_by_codigo(codigo_oc)
            if result['success']:
                return jsonify({
                    'success': True,
                    'data': result['data']
                })
            else:
                return jsonify({'success': False, 'error': result['error']}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    def get_all_ordenes(self, filtros=None):
        """
        Obtiene todas las órdenes de compra, ahora con detalles del proveedor.
        """
        try:
            filters = filtros or {}
            # Si filtros no incluye ciertos campos, tomar de request.args
            if 'estado' not in filters and request.args.get('estado'):
                filters['estado'] = request.args.get('estado')
            
            if filters.get('estado'):
                filters['estado'] = estados.traducir_a_int(filters['estado'])

            if 'proveedor_id' not in filters and request.args.get('proveedor_id'):
                filters['proveedor_id'] = int(request.args.get('proveedor_id'))
            if 'prioridad' not in filters and request.args.get('prioridad'):
                filters['prioridad'] = request.args.get('prioridad')

            result = self.model.get_all(filters)

            if result['success']:
                result['data'] = estados.traducir_lista_a_cadena(result['data'])
                return result, 200
            else:
                return result, 400
        except Exception as e:
            logger.error(f"Error en el controlador al obtener todas las órdenes: {e}")
            return {'success': False, 'error': str(e)}, 500

    def update_orden(self, orden_id):
        try:
            data = request.get_json()
            
            if 'estado' in data:
                data['estado'] = estados.traducir_a_int(data['estado'])

            result = self.model.update(orden_id, data)
            if result['success']:
                result['data'] = estados.traducir_objeto_a_cadena(result['data'])
                return jsonify({
                    'success': True,
                    'data': result['data'],
                    'message': 'Orden de compra actualizada exitosamente'
                })
            else:
                return jsonify({'success': False, 'error': result['error']}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    def obtener_codigos_por_insumo(self, insumo_id):
        """
        Obtiene los códigos de OC asociados a un insumo.
        """
        try:
            result = self.model.find_codigos_by_insumo_id(insumo_id)
            if result.get('success'):
                return result, 200
            else:
                return result, 400
        except Exception as e:
            logger.error(f"Error en controlador al obtener códigos de OC por insumo: {e}")
            return {'success': False, 'error': str(e)}, 500

    def cancelar_orden(self, orden_id):
        """Endpoint específico para cancelar órdenes de compra"""
        try:
            data = request.get_json() or {}
            motivo = data.get('motivo', '')

            # 1. Primero verificar que la orden existe y puede cancelarse
            orden_actual = self.model.find_by_id(orden_id)
            if not orden_actual['success']:
                return jsonify({'success': False, 'error': 'Orden no encontrada'}), 404

            orden_data = orden_actual['data']
            estado_actual_int = orden_data.get('estado') # El modelo ya devuelve int
            estado_actual_str = estados.traducir_a_cadena(estado_actual_int)

            # 2. Validar que se puede cancelar (no cancelar órdenes ya completadas/canceladas)
            estados_no_cancelables = [estados.OC_COMPLETADA, estados.OC_CANCELADA] # Añadir VENCIDA si existe
            if estado_actual_int in estados_no_cancelables:
                return jsonify({
                    'success': False,
                    'error': f'No se puede cancelar una orden en estado {estado_actual_str}'
                }), 400

            # 3. Preparar datos para cancelación
            cancelacion_data = {
                'estado': estados.OC_CANCELADA,
                'updated_at': datetime.now().isoformat(),
                'observaciones': f"{orden_data.get('observaciones', '')} \\n--- CANCELADA ---\\nMotivo: {motivo} \\nFecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            }

            # 4. Si hay usuario autenticado, registrar quién cancela
            # (puedes obtener el usuario del token JWT)
            # cancelacion_data['usuario_aprobador_id'] = usuario_actual_id

            result = self.model.update(orden_id, cancelacion_data)

            if result['success']:
                return jsonify({
                    'success': True,
                    'data': result['data'],
                    'message': 'Orden de compra cancelada exitosamente'
                })
            else:
                return jsonify({'success': False, 'error': result['error']}), 400

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    def obtener_orden_por_id(self, orden_id):
        return self.get_orden(orden_id)

    def aprobar_orden(self, orden_id, usuario_id):
        """
        Aprueba una orden de compra.
        """
        try:
            update_data = {
                'estado': estados.OC_APROBADA,
                'usuario_aprobador_id': usuario_id,
                'updated_at': datetime.now().isoformat()
            }
            result = self.model.update(orden_id, update_data)
            
            if result.get('success'):
                result['data'] = estados.traducir_objeto_a_cadena(result['data'])

            return result
        except Exception as e:
            logger.error(f"Error aprobando orden {orden_id}: {e}")
            return {'success': False, 'error': str(e)}

    def marcar_en_transito(self, orden_id):
        """
        Marca una orden de compra como 'EN_TRANSITO'.
        """
        try:
            update_data = {
                'estado': estados.OC_EN_ESPERA_LLEGADA, # Suponiendo que este es el estado correcto
                'updated_at': datetime.now().isoformat()
            }
            result = self.model.update(orden_id, update_data)
            
            if result.get('success'):
                result['data'] = estados.traducir_objeto_a_cadena(result['data'])

            return result
        except Exception as e:
            logger.error(f"Error marcando la orden {orden_id} como EN TRANSITO: {e}")
            return {'success': False, 'error': str(e)}

    def rechazar_orden(self, orden_id, motivo):
        """
        Rechaza una orden de compra.
        """
        try:
            # Primero, obtenemos las observaciones actuales para no sobrescribirlas.
            orden_actual_result, _ = self.get_orden(orden_id)
            if not orden_actual_result.get('success'):
                return orden_actual_result

            observaciones_actuales = orden_actual_result['data'].get('observaciones', '')

            update_data = {
                'estado': estados.OC_RECHAZADA,
                'observaciones': f"{observaciones_actuales}\n\nRechazada por: {motivo}",
                'updated_at': datetime.now().isoformat()
            }
            result = self.model.update(orden_id, update_data)
            
            if result.get('success'):
                result['data'] = estados.traducir_objeto_a_cadena(result['data'])

            return result
        except Exception as e:
            logger.error(f"Error rechazando orden {orden_id}: {e}")
            return {'success': False, 'error': str(e)}

    def procesar_recepcion(self, orden_id, form_data, usuario_id, orden_produccion_controller: "OrdenProduccionController"):
        """
        Procesa la recepción de una OC, crea lotes, RESERVA INSUMOS y
        mueve la OP asociada a 'LISTA_PARA_INICIAR'.
        """
        try:
            accion = form_data.get('accion')
            observaciones = form_data.get('observaciones', '')

            if accion == 'aceptar':
                # --- GET PO DATA ---
                orden_result = self.model.find_by_id(orden_id)
                if not orden_result.get('success'):
                    return {'success': False, 'error': 'No se pudo encontrar la orden de compra.'}
                orden_data = orden_result['data']

                # --- RECEIVE ITEMS & CREATE LOTS ---
                item_ids = form_data.getlist('item_id[]')
                cantidades_recibidas = form_data.getlist('cantidad_recibida[]')
                if len(item_ids) != len(cantidades_recibidas):
                    return {'success': False, 'error': 'Datos de ítems inconsistentes.'}

                items_para_lote = []
                # 1. Update PO Items
                for i in range(len(item_ids)):
                    try:
                        item_id = int(item_ids[i])
                        cantidad = float(cantidades_recibidas[i]) if cantidades_recibidas[i] else 0
                        # Ensure item_model exists on self.model if using it like this
                        self.model.item_model.update(item_id, {'cantidad_recibida': cantidad})
                        if cantidad > 0:
                            item_info_result = self.model.item_model.find_by_id(item_id, 'id')
                            if item_info_result.get('success'):
                                items_para_lote.append({
                                    'data': item_info_result['data'],
                                    'cantidad_recibida': cantidad
                                })
                    except (ValueError, IndexError, AttributeError) as e:
                         logger.warning(f"Skipping item due to error during update/fetch: {e}")
                         continue # Skip this item if there's an issue

                # 2. Update PO Status
                orden_update_data = {
                    'estado': estados.OC_RECIBIDA, 'fecha_real_entrega': date.today().isoformat(),
                    'observaciones': observaciones, 'updated_at': datetime.now().isoformat()
                }
                self.model.update(orden_id, orden_update_data)

                # 3. Create Inventory Lots
                lotes_creados_count = 0; lotes_error_count = 0
                for item_lote in items_para_lote:
                    item_data = item_lote['data']
                    lote_data = {
                        'id_insumo': item_data['insumo_id'],
                        'id_proveedor': orden_data.get('proveedor_id'),
                        'cantidad_inicial': item_lote['cantidad_recibida'],
                        'precio_unitario': item_data.get('precio_unitario'),
                        'documento_ingreso': f"OC-{orden_data.get('codigo_oc', 'N/A')}",
                        'f_ingreso': date.today().isoformat()
                        # Add f_vencimiento here if captured
                    }
                    try:
                        # Ensure inventario_controller.crear_lote returns a dict {'success':...}
                        lote_result = self.inventario_controller.crear_lote(lote_data, usuario_id)
                        # If it returns a tuple (dict, status), use this:
                        # lote_result, _ = self.inventario_controller.crear_lote(lote_data, usuario_id)

                        if lote_result.get('success'): lotes_creados_count += 1
                        else:
                            logger.error(f"Failed to create lot for insumo {lote_data.get('id_insumo')}: {lote_result.get('error')}")
                            lotes_error_count += 1
                    except Exception as e_lote:
                        logger.error(f"Exception creating lot for insumo {lote_data.get('id_insumo')}: {e_lote}", exc_info=True)
                        lotes_error_count += 1

                # 4. Recalcular y actualizar los totales de la orden principal
                items_actualizados_result = self.model.item_model.find_by_orden_id(orden_id)
                if not items_actualizados_result.get('success'):
                    # Si no podemos recalcular, al menos dejamos un log
                    logger.error(f"No se pudieron obtener los ítems para recalcular los totales de la OC {orden_id}.")
                else:
                    items_actualizados = items_actualizados_result['data']
                    nuevo_subtotal = sum(float(item.get('subtotal') or 0) for item in items_actualizados)

                    nuevo_iva = 0
                    # Aseguramos que el valor de iva sea numérico antes de comparar
                    iva_original = float(orden_data.get('iva') or 0)
                    if iva_original > 0: # Respetar si la orden original tenía IVA
                        nuevo_iva = nuevo_subtotal * 0.21

                # --- RESERVE SUPPLIES & TRANSITION OP ---
                op_transition_message = ""
                if orden_data.get('orden_produccion_id'):
                    op_id = orden_data['orden_produccion_id']

                    # a. Get FULL OP data (needs linea_asignada)
                    op_result = orden_produccion_controller.obtener_orden_por_id(op_id)
                    if not op_result.get('success'):
                        op_error_msg = f"No se pudo encontrar la OP {op_id} asociada."
                        # Return error as we cannot proceed
                        logger.error(op_error_msg)
                        return {'success': False, 'error': op_error_msg}

                    orden_produccion = op_result['data']

                    # b. Proceed only if OP is 'EN ESPERA'
                    if orden_produccion.get('estado') == 'EN ESPERA':
                        logger.info(f"OP {op_id} is EN ESPERA. Attempting to reserve supplies after PO receipt.")

                        # c. Attempt to reserve supplies
                        reserva_result = self.inventario_controller.reservar_stock_insumos_para_op(orden_produccion, usuario_id)

                        if not reserva_result.get('success'):
                            op_error_msg = f"Supplies received but automatic reservation failed for OP {op_id}. Please check manually. Error: {reserva_result.get('error')}"
                            op_transition_message = f"ADVERTENCIA: {op_error_msg}"
                            logger.error(op_error_msg)
                        else:
                            # d. Set new state to LISTA_PARA_INICIAR
                            nuevo_estado_op = 'LISTA PARA PRODUCIR'

                            # e. Change OP state using the simple method
                            # Ensure op controller has cambiar_estado_orden_simple
                            op_update_result = orden_produccion_controller.cambiar_estado_orden_simple(op_id, nuevo_estado_op)

                            if not op_update_result.get('success'):
                                op_error_msg = op_update_result.get('error', 'Error desconocido.')
                                op_transition_message = f"ADVERTENCIA: Fallo al actualizar la OP {op_id} a {nuevo_estado_op}. Error: {op_error_msg}"
                                logger.error(op_transition_message)
                            else:
                                op_transition_message = f"Insumos reservados. La OP {op_id} asociada ha sido actualizada a '{nuevo_estado_op}'."
                                logger.info(f"OC {orden_id} recibida, OP {op_id} movida a '{nuevo_estado_op}'.")
                    else:
                         logger.info(f"OC {orden_id} received, but associated OP {op_id} was already in state '{orden_produccion.get('estado')}'. No changes made to OP.")
                         op_transition_message = f"La OP {op_id} no estaba 'EN ESPERA', no se modificó."
                # --- END IMPROVED LOGIC ---

                final_message = f'Recepción completada. {lotes_creados_count} lotes creados.'
                if lotes_error_count > 0: final_message += f' ({lotes_error_count} con error).'
                if op_transition_message: final_message += f" | {op_transition_message}"

                return {'success': True, 'message': final_message}

            elif accion == 'rechazar':
                 # Ensure rechazar_orden exists and works
                 return self.rechazar_orden(orden_id, f"Rechazada en recepción: {observaciones}")

            else:
                return {'success': False, 'error': 'Acción no válida.'}

        except Exception as e:
            logger.error(f"Error crítico procesando la recepción de la orden {orden_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}