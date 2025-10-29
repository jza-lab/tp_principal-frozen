from typing import Dict, TYPE_CHECKING
from flask import request, jsonify
from flask_jwt_extended import get_jwt
from app.models.orden_compra_model import OrdenCompraItemModel, OrdenCompraModel
from app.models.orden_compra_model import OrdenCompra
from app.controllers.inventario_controller import InventarioController
from app.controllers.insumo_controller import InsumoController
from app.controllers.usuario_controller import UsuarioController
from datetime import datetime, date
import logging

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
        self.usuario_controller = UsuarioController()


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

    def crear_orden(self, orden_data, items_data, usuario_id: int) -> Dict:
        """
        Crea una nueva orden de compra a partir de diccionarios de datos.
        """
        try:
            if not orden_data.get('proveedor_id') or not orden_data.get('fecha_emision'):
                return {'success': False, 'error': 'El proveedor y la fecha de emisión son obligatorios.'}

            # Asignar datos clave
            orden_data['usuario_creador_id'] = usuario_id
            if not orden_data.get('codigo_oc'):
                orden_data['codigo_oc'] = f"OC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            if not orden_data.get('estado'):
                orden_data['estado'] = 'PENDIENTE'

            # Crear la orden
            result = self.model.create_with_items(orden_data, items_data)
            return result
        except Exception as e:
            logger.error(f"Error en el controlador al crear la orden: {e}")
            return {'success': False, 'error': str(e)}

    def crear_orden_desde_form(self, form_data, usuario_id):
        """
        Wrapper para crear una orden desde un formulario web.
        Parsea los datos y luego llama al método principal de creación.
        """
        try:
            orden_data, items_data = self._parse_form_data(form_data)
            return self.crear_orden(orden_data, items_data, usuario_id)
        except Exception as e:
            logger.error(f"Error procesando formulario para crear orden: {e}")
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

            orden_data = orden_actual_result['data']
            observaciones_actuales = orden_data.get('observaciones', '')
            
            # Validacion de transicion de estado para SUPERVISOR_CALIDAD
            claims = get_jwt()
            rol_usuario = claims.get('roles', [])[0] if claims.get('roles') else None
            if rol_usuario == 'SUPERVISOR_CALIDAD':
                if orden_data.get('estado') != 'EN_TRANSITO':
                    return {'success': False, 'error': 'Solo puede rechazar órdenes que estén EN TRANSITO.'}

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

    def _marcar_cadena_como_completa(self, orden_id):
        """
        Marca una orden y todas sus predecesoras en la cadena de complemento
        como 'RECEPCION_COMPLETA' de forma recursiva.
        """
        try:
            current_id = orden_id
            while current_id:
                orden_res = self.model.find_by_id(current_id)
                if not orden_res.get('success'):
                    logger.warning(f"No se encontró la orden con ID {current_id} en la cadena de completado.")
                    break

                orden_actual = orden_res['data']

                # Actualizar el estado de la orden actual a 'RECEPCION_COMPLETA'
                self.model.update(current_id, {
                    'estado': 'RECEPCION_COMPLETA',
                    'fecha_real_entrega': date.today().isoformat()
                })

                logger.info(f"Orden {current_id} marcada como RECEPCION_COMPLETA.")
                
                # Moverse a la orden que esta complementa
                current_id = orden_actual.get('complementa_a_orden_id')

        except Exception as e:
            logger.error(f"Error en la cadena de completado para la orden {orden_id}: {e}", exc_info=True)

    def _manejar_transicion_op_asociada(self, orden_data, usuario_id, orden_produccion_controller: "OrdenProduccionController"):
        """
        Gestiona la transición de estado de una Orden de Producción asociada
        cuando se reciben todos los insumos necesarios de una Orden de Compra.
        """
        op_transition_message = ""
        if not orden_data.get('orden_produccion_id'):
            return op_transition_message

        op_id = orden_data['orden_produccion_id']
        op_result = orden_produccion_controller.obtener_orden_por_id(op_id)
        if not op_result.get('success'):
            op_error_msg = f"No se pudo encontrar la OP {op_id} asociada."
            logger.error(op_error_msg)
            return f"ADVERTENCIA: {op_error_msg}"

        orden_produccion = op_result['data']
        if orden_produccion.get('estado') == 'EN ESPERA':
            logger.info(f"OP {op_id} está EN ESPERA. Intentando reservar insumos tras recepción de OC.")
            reserva_result = self.inventario_controller.reservar_stock_insumos_para_op(orden_produccion, usuario_id)

            if not reserva_result.get('success'):
                op_error_msg = f"Insumos recibidos pero la reserva automática para OP {op_id} falló. Error: {reserva_result.get('error')}"
                op_transition_message = f"ADVERTENCIA: {op_error_msg}"
                logger.error(op_error_msg)
            else:
                nuevo_estado_op = 'LISTA PARA PRODUCIR'
                op_update_result = orden_produccion_controller.cambiar_estado_orden_simple(op_id, nuevo_estado_op)

                if not op_update_result.get('success'):
                    op_error_msg = op_update_result.get('error', 'Error desconocido.')
                    op_transition_message = f"ADVERTENCIA: Falló al actualizar la OP {op_id} a {nuevo_estado_op}. Error: {op_error_msg}"
                    logger.error(op_transition_message)
                else:
                    op_transition_message = f"Insumos reservados. La OP {op_id} ha sido actualizada a '{nuevo_estado_op}'."
                    logger.info(f"OC {orden_data['id']} recibida, OP {op_id} movida a '{nuevo_estado_op}'.")
        else:
            logger.info(f"OC {orden_data['id']} recibida, pero la OP {op_id} asociada ya estaba en estado '{orden_produccion.get('estado')}'. No se realizaron cambios.")
            op_transition_message = f"La OP {op_id} no estaba 'EN ESPERA', por lo que no fue modificada."

        return op_transition_message

    def _crear_lotes_para_items_recibidos(self, items_para_lote, orden_data, usuario_id):
        """
        Helper para crear lotes de inventario para los items recibidos.
        """
        lotes_creados_count = 0
        lotes_error_count = 0
        for item_lote in items_para_lote:
            item_data = item_lote['data']
            lote_data = {
                'id_insumo': item_data['insumo_id'],
                'id_proveedor': orden_data.get('proveedor_id'),
                'cantidad_inicial': item_lote['cantidad_recibida'],
                'precio_unitario': item_data.get('precio_unitario'),
                'documento_ingreso': f"OC-{orden_data.get('codigo_oc', 'N/A')}",
                'f_ingreso': date.today().isoformat()
            }
            try:
                lote_result = self.inventario_controller.crear_lote(lote_data, usuario_id)
                if lote_result.get('success'):
                    lotes_creados_count += 1
                else:
                    logger.error(f"Fallo al crear el lote para el insumo {lote_data.get('id_insumo')}: {lote_result.get('error')}")
                    lotes_error_count += 1
            except Exception as e_lote:
                logger.error(f"Excepción creando lote para el insumo {lote_data.get('id_insumo')}: {e_lote}", exc_info=True)
                lotes_error_count += 1
        return lotes_creados_count, lotes_error_count

    def procesar_recepcion(self, orden_id, form_data, usuario_id, orden_produccion_controller: "OrdenProduccionController"):
        try:
            accion = form_data.get('accion')
            observaciones = form_data.get('observaciones', '')

            if accion == 'aceptar':
                orden_result = self.model.get_one_with_details(orden_id)
                if not orden_result.get('success'):
                    return {'success': False, 'error': 'No se pudo encontrar la orden de compra.'}
                orden_data = orden_result['data']
                
                # Validacion de transicion de estado para SUPERVISOR_CALIDAD
                usuario = self.usuario_controller.obtener_usuario_por_id(usuario_id)
                if usuario and usuario.get('roles', {}).get('codigo') == 'SUPERVISOR_CALIDAD':
                    if orden_data.get('estado') != 'EN_TRANSITO':
                        return {'success': False, 'error': 'Solo puede recibir órdenes que estén EN TRANSITO.'}

                item_ids = form_data.getlist('item_id[]')
                cantidades_recibidas_str = form_data.getlist('cantidad_recibida[]')

                items_faltantes = []
                items_para_lote = []

                # Mapear item_id a su cantidad solicitada original
                items_originales = {str(item['id']): item for item in orden_data.get('items', [])}

                for i in range(len(item_ids)):
                    item_id_str = item_ids[i]
                    item_original = items_originales.get(item_id_str)

                    if not item_original:
                        logger.warning(f"Se recibió el item ID {item_id_str} que no pertenece a la orden {orden_id}.")
                        continue

                    try:
                        cantidad_recibida = float(cantidades_recibidas_str[i] or 0)
                        cantidad_solicitada = float(item_original.get('cantidad_solicitada', 0))

                        self.model.item_model.update(int(item_id_str), {'cantidad_recibida': cantidad_recibida})

                        if cantidad_recibida > 0:
                            items_para_lote.append({
                                'data': item_original,
                                'cantidad_recibida': cantidad_recibida
                            })

                        if cantidad_recibida < cantidad_solicitada:
                            items_faltantes.append({
                                'insumo_id': item_original['insumo_id'],
                                'cantidad_faltante': cantidad_solicitada - cantidad_recibida,
                                'precio_unitario': float(item_original.get('precio_unitario', 0)),
                            })
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Error procesando item {item_id_str}: {e}")
                        continue

                lotes_creados, lotes_error = self._crear_lotes_para_items_recibidos(items_para_lote, orden_data, usuario_id)

                if items_faltantes:
                    nueva_orden_result = self._crear_orden_complementaria(orden_data, items_faltantes, usuario_id)
                    if not nueva_orden_result.get('success'):
                        return {'success': False, 'error': f"Recepción parcial procesada, pero falló la creación de la orden complementaria: {nueva_orden_result.get('error')}"}

                    self.model.update(orden_id, {
                        'estado': 'RECEPCION_INCOMPLETA',
                        'observaciones': f"{observaciones}\nRecepción parcial. Pendiente completado en OC: {nueva_orden_result['data']['codigo_oc']}"
                    })

                    return {'success': True, 'message': f'Recepción parcial registrada. Se creó la orden {nueva_orden_result["data"]["codigo_oc"]} para los insumos restantes.'}
                else:
                    self._marcar_cadena_como_completa(orden_id)

                    final_message = f'Recepción completada. {lotes_creados} lotes creados.'
                    if lotes_error > 0: final_message += f' ({lotes_error} con error).'

                    op_transition_message = self._manejar_transicion_op_asociada(orden_data, usuario_id, orden_produccion_controller)
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

    def _crear_orden_complementaria(self, orden_original_data, items_faltantes, usuario_id):

        nueva_orden_data = {
            'proveedor_id': orden_original_data.get('proveedor_id'),
            'fecha_emision': date.today().isoformat(),
            'fecha_estimada_entrega': orden_original_data.get('fecha_estimada_entrega'),
            'prioridad': orden_original_data.get('prioridad', 'NORMAL'),
            'observaciones': f"Esta orden complementa a la OC: {orden_original_data.get('codigo_oc')}",
            'orden_produccion_id': orden_original_data.get('orden_produccion_id'),
            'complementa_a_orden_id': orden_original_data.get('id')
        }


        items_para_nueva_orden = []
        for item in items_faltantes:
            items_para_nueva_orden.append({
                'insumo_id': item['insumo_id'],
                'cantidad_solicitada': item['cantidad_faltante'],
                'precio_unitario': item['precio_unitario'],
                'cantidad_recibida': 0.0
            })


        subtotal = sum(item['cantidad_faltante'] * item['precio_unitario'] for item in items_faltantes)
        iva = subtotal * 0.21 if orden_original_data.get('iva', 0) > 0 else 0
        total = subtotal + iva

        nueva_orden_data.update({
            'subtotal': round(subtotal, 2),
            'iva': round(iva, 2),
            'total': round(total, 2)
        })


        return self.crear_orden(nueva_orden_data, items_para_nueva_orden, usuario_id)
