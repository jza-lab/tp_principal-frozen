from typing import Dict
from flask import request, jsonify
from app.models.orden_compra_model import OrdenCompraItemModel, OrdenCompraModel
from app.models.orden_compra_model import OrdenCompra
from app.controllers.inventario_controller import InventarioController
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

class OrdenCompraController:
    def __init__(self):
        self.model = OrdenCompraModel()
        self.inventario_controller = InventarioController()


    def _parse_form_data(self, form_data):
        """
        Parsea los datos del formulario web, incluyendo los items anidados.
        """
        orden_data = {
            'proveedor_id': form_data.get('proveedor_id'),
            'fecha_emision': form_data.get('fecha_emision'),
            'fecha_estimada_entrega': form_data.get('fecha_estimada_entrega'),
            'prioridad': form_data.get('prioridad'),
            'observaciones': form_data.get('observaciones'),
            'subtotal': form_data.get('subtotal'),
            'iva': form_data.get('iva'),
            'total': form_data.get('total'),
        }

        items_data = []
        insumo_ids = form_data.getlist('insumo_id[]')
        cantidades = form_data.getlist('cantidad_solicitada[]')
        precios = form_data.getlist('precio_unitario[]')

        for i in range(len(insumo_ids)):
            if insumo_ids[i]:
                try:
                    cantidad = float(cantidades[i] or 0)
                    precio = float(precios[i] or 0)
                    items_data.append({
                        'insumo_id': insumo_ids[i],
                        'cantidad_solicitada': cantidad,
                        'precio_unitario': precio
                    })
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parseando item de orden de compra: {e}")
                    continue
        
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

    def procesar_recepcion(self, orden_id, form_data, usuario_id):
        """
        Procesa la recepción de una orden de compra, actualiza cantidades,
        cambia el estado y crea los lotes correspondientes en el inventario.
        """
        try:
            accion = form_data.get('accion')
            observaciones = form_data.get('observaciones', '')

            if accion == 'aceptar':
                # Obtener datos de la orden para usarlos en la creación de lotes
                orden_result = self.model.find_by_id(orden_id)
                if not orden_result.get('success'):
                    return {'success': False, 'error': 'No se pudo encontrar la orden de compra.'}
                orden_data = orden_result['data']

                item_ids = form_data.getlist('item_id[]')
                cantidades_recibidas = form_data.getlist('cantidad_recibida[]')

                if len(item_ids) != len(cantidades_recibidas):
                    return {'success': False, 'error': 'Los datos de los ítems no coinciden.'}

                items_para_lote = []

                # 1. Actualizar cada ítem de la orden
                for i in range(len(item_ids)):
                    item_id = int(item_ids[i])
                    cantidad = float(cantidades_recibidas[i])
                    
                    self.model.item_model.update(item_id, {'cantidad_recibida': cantidad})
                    
                    if cantidad > 0:
                        item_info_result = self.model.item_model.find_by_id(item_id, 'id')
                        if item_info_result.get('success'):
                            items_para_lote.append({
                                'data': item_info_result['data'],
                                'cantidad_recibida': cantidad
                            })

                # 2. Actualizar el estado de la orden principal
                orden_update_data = {
                    'estado': 'RECIBIDA',
                    'fecha_real_entrega': date.today().isoformat(),
                    'observaciones': observaciones,
                    'updated_at': datetime.now().isoformat()
                }
                update_result = self.model.update(orden_id, orden_update_data)
                
                if not update_result.get('success'):
                    return update_result

                # 3. Crear lotes en inventario
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
                        lote_result, status_code = self.inventario_controller.crear_lote(lote_data, usuario_id)
                        if lote_result.get('success'):
                            lotes_creados_count += 1
                        else:
                            lotes_error_count += 1
                            logger.error(f"Error creando lote para insumo {lote_data['id_insumo']}: {lote_result.get('error')}")
                    except Exception as e:
                        lotes_error_count += 1
                        logger.error(f"Excepción creando lote para insumo {lote_data['id_insumo']}: {e}")

                if lotes_error_count > 0:
                    logger.warning(f"Recepción de OC {orden_id} completada, pero {lotes_error_count} lotes no se pudieron crear.")

                return {'success': True, 'message': f'Recepción completada. {lotes_creados_count} lotes creados.'}

            elif accion == 'rechazar':
                return self.rechazar_orden(orden_id, f"Rechazada en recepción: {observaciones}")
            
            else:
                return {'success': False, 'error': 'Acción no válida.'}

        except Exception as e:
            logger.error(f"Error crítico procesando la recepción de la orden {orden_id}: {e}")
            return {'success': False, 'error': str(e)}