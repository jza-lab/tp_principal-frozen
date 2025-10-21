from typing import Dict
from flask import request, jsonify
from app.models.orden_compra_model import OrdenCompraItemModel, OrdenCompraModel
from app.models.orden_compra_model import OrdenCompra
from app.controllers.inventario_controller import InventarioController
from app.controllers.insumo_controller import InsumoController
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

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
            orden_data['estado'] = 'PENDIENTE'

            result = self.model.create_with_items(orden_data, items_data)

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
            if 'proveedor_id' not in filters and request.args.get('proveedor_id'):
                filters['proveedor_id'] = int(request.args.get('proveedor_id'))
            if 'prioridad' not in filters and request.args.get('prioridad'):
                filters['prioridad'] = request.args.get('prioridad')

            result = self.model.get_all(filters)

            if result['success']:
                return result, 200
            else:
                return result, 400
        except Exception as e:
            logger.error(f"Error en el controlador al obtener todas las órdenes: {e}")
            return {'success': False, 'error': str(e)}, 500

    def update_orden(self, orden_id):
        try:
            data = request.get_json()

            result = self.model.update(orden_id, data)
            if result['success']:
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
            estado_actual = orden_data.get('estado', 'PENDIENTE')

            # 2. Validar que se puede cancelar (no cancelar órdenes ya completadas/canceladas)
            estados_no_cancelables = ['COMPLETADA', 'CANCELADA', 'VENCIDA']
            if estado_actual in estados_no_cancelables:
                return jsonify({
                    'success': False,
                    'error': f'No se puede cancelar una orden en estado {estado_actual}'
                }), 400

            # 3. Preparar datos para cancelación
            cancelacion_data = {
                'estado': 'CANCELADA',
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
                'estado': 'APROBADA',
                'usuario_aprobador_id': usuario_id,
                'updated_at': datetime.now().isoformat()
            }
            result = self.model.update(orden_id, update_data)
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
                'estado': 'EN_TRANSITO',
                'updated_at': datetime.now().isoformat()
            }
            result = self.model.update(orden_id, update_data)
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
                'estado': 'RECHAZADA',
                'observaciones': f"{observaciones_actuales}\n\nRechazada por: {motivo}",
                'updated_at': datetime.now().isoformat()
            }
            result = self.model.update(orden_id, update_data)
            return result
        except Exception as e:
            logger.error(f"Error rechazando orden {orden_id}: {e}")
            return {'success': False, 'error': str(e)}

    def procesar_recepcion(self, orden_id, form_data, usuario_id, orden_produccion_controller):
        """
        Procesa la recepción de una OC, crea lotes, RESERVA INSUMOS para la OP asociada
        y finalmente actualiza el estado de la OP.
        """
        try:
            accion = form_data.get('accion')
            observaciones = form_data.get('observaciones', '')

            if accion == 'aceptar':
                orden_result = self.model.find_by_id(orden_id)
                if not orden_result.get('success'):
                    return {'success': False, 'error': 'No se pudo encontrar la orden de compra.'}
                orden_data = orden_result['data']

                item_ids = form_data.getlist('item_id[]')
                cantidades_recibidas = form_data.getlist('cantidad_recibida[]')
                precios_unitarios = form_data.getlist('precio_unitario[]')

                if not (len(item_ids) == len(cantidades_recibidas) == len(precios_unitarios)):
                    return {'success': False, 'error': 'Los datos de los ítems recibidos son inconsistentes.'}

                lotes_creados_count = 0
                lotes_error_count = 0
                errores_detalle = []

                # Bucle transaccional para procesar cada ítem
                for i in range(len(item_ids)):
                    try:
                        item_id = int(item_ids[i])
                        cantidad = float(cantidades_recibidas[i])
                        precio = float(precios_unitarios[i])

                        # Obtener información original del ítem para tener el insumo_id
                        item_info_result = self.model.item_model.find_by_id(item_id, 'id')
                        if not item_info_result.get('success'):
                            errores_detalle.append(f"No se encontró el ítem con ID {item_id}.")
                            lotes_error_count += 1
                            continue
                        
                        item_data = item_info_result['data']
                        insumo_id = item_data['insumo_id']

                        # 1. Actualizar el ítem de la orden de compra (cantidad y nuevo precio)
                        subtotal_item = cantidad * precio
                        update_item_data = {
                            'cantidad_recibida': cantidad,
                            'precio_unitario': precio,
                            'subtotal': subtotal_item
                        }
                        
                        # Pasamos el item_id y los datos al modelo para que actualice la BD
                        update_result = self.model.item_model.update(item_id, update_item_data)
                        if not update_result.get('success'):
                             errores_detalle.append(f"Error al actualizar el ítem ID {item_id}: {update_result.get('error')}")
                             lotes_error_count += 1
                             continue

                        # 2. Crear lote en inventario solo si se recibió una cantidad > 0
                        if cantidad > 0:
                            lote_data = {
                                'id_insumo': insumo_id,
                                'id_proveedor': orden_data.get('proveedor_id'),
                                'cantidad_inicial': cantidad,
                                'precio_unitario': precio, # <-- Usar el nuevo precio del formulario
                                'documento_ingreso': f"OC-{orden_data.get('codigo_oc', 'N/A')}",
                                'f_ingreso': date.today().isoformat()
                            }
                            
                            lote_result, status_code = self.inventario_controller.crear_lote(lote_data, usuario_id)
                            if not lote_result.get('success'):
                                errores_detalle.append(f"Error al crear lote para insumo ID {insumo_id}: {lote_result.get('error')}")
                                lotes_error_count += 1
                                continue # Continuar al siguiente item aunque este falle
                            else:
                                lotes_creados_count += 1
                        
                        # 3. Actualizar el precio en el catálogo principal de insumos
                        precio_update_result, _ = self.insumo_controller.actualizar_precio(insumo_id, precio)
                        if not precio_update_result.get('success'):
                            logger.warning(f"No se pudo actualizar el precio en el catálogo para el insumo {insumo_id}. Esto no detiene el proceso.")

                    except (ValueError, IndexError) as e:
                        errores_detalle.append(f"Error de datos procesando un ítem: {e}")
                        lotes_error_count += 1
                        continue

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

                    nuevo_total = nuevo_subtotal + nuevo_iva

                    orden_update_data = {
                        'subtotal': round(nuevo_subtotal, 2),
                        'iva': round(nuevo_iva, 2),
                        'total': round(nuevo_total, 2),
                        'estado': 'RECIBIDA',
                        'fecha_real_entrega': date.today().isoformat(),
                        'observaciones': observaciones,
                        'updated_at': datetime.now().isoformat()
                    }
                    self.model.update(orden_id, orden_update_data)

                if lotes_error_count > 0:
                    error_msg = f"Recepción procesada con {lotes_error_count} errores. Detalles: {'; '.join(errores_detalle)}"
                    return {'success': False, 'error': error_msg}

                # Lógica de reserva y transición de OP
                op_transition_message = ""
                if orden_data.get('orden_produccion_id'):
                    op_id = orden_data['orden_produccion_id']

                    op_result = orden_produccion_controller.obtener_orden_por_id(op_id)
                    if not op_result.get('success'):
                        op_error_msg = f"No se pudo encontrar la OP {op_id} asociada."
                        return {'success': False, 'error': op_error_msg}

                    orden_produccion = op_result['data']

                    logger.info(f"Intentando reservar insumos para la OP {op_id} tras recepción de OC.")
                    reserva_result = self.inventario_controller.reservar_stock_insumos_para_op(orden_produccion, usuario_id)

                    if not reserva_result.get('success'):
                        op_error_msg = f"Se recibieron los insumos pero falló la reserva automática para la OP {op_id}. Por favor, verifique manualmente. Error: {reserva_result.get('error')}"
                        op_transition_message = f"ADVERTENCIA: {op_error_msg}"
                    else:
                        logger.info(f"Reserva para OP {op_id} exitosa. Cambiando estado a 'LISTA PARA PRODUCIR'.")
                        op_update_result, op_status_code = orden_produccion_controller.cambiar_estado_orden(op_id, 'LISTA PARA PRODUCIR')

                        if op_status_code >= 400:
                            op_error_msg = op_update_result.get('error', 'Error desconocido.')
                            op_transition_message = f"ADVERTENCIA: Fallo al actualizar la OP {op_id}. Error: {op_error_msg}"
                        else:
                            op_transition_message = f"Insumos reservados. La Orden de Producción {op_id} asociada ha sido actualizada a 'LISTA PARA PRODUCIR'."
                            logger.info(f"OC {orden_id} recibida, OP {op_id} movida a 'LISTA PARA PRODUCIR'.")

                # Ahora 'lotes_creados_count' sí existe y se puede usar en el mensaje final
                final_message = f'Recepción completada. {lotes_creados_count} lotes creados.'
                if op_transition_message:
                    final_message += f" | {op_transition_message}"

                return {'success': True, 'message': final_message}

            elif accion == 'rechazar':
                return self.rechazar_orden(orden_id, f"Rechazada en recepción: {observaciones}")

            else:
                return {'success': False, 'error': 'Acción no válida.'}

        except Exception as e:
            logger.error(f"Error crítico procesando la recepción de la orden {orden_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}