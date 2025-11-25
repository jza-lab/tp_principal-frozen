from typing import Dict, TYPE_CHECKING
from flask import request, jsonify
from flask_jwt_extended import get_jwt, get_current_user
from marshmallow import ValidationError
from app.controllers.registro_controller import RegistroController
from app.models.orden_compra_model import OrdenCompraItemModel, OrdenCompraModel
from app.models.orden_compra_model import OrdenCompra
from app.controllers.inventario_controller import InventarioController
from app.controllers.usuario_controller import UsuarioController
from app.controllers.reclamo_proveedor_controller import ReclamoProveedorController
from datetime import datetime, date, timedelta
import logging
import time
import math
import requests  # <-- AÑADIR
import threading # <-- AÑADIR
from app.models.control_calidad_insumo import ControlCalidadInsumoModel

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.controllers.orden_produccion_controller import OrdenProduccionController

def enviar_webhook_async(url: str, data: dict):
    """
    Envía un webhook en un hilo separado (Thread) para no bloquear
    la respuesta de la aplicación web principal.
    """
    def thread_target():
        try:
            requests.post(url, json=data, timeout=3)
            logger.info(f"Webhook de n8n enviado exitosamente (OC Alerta): {data.get('oc_codigo')}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al enviar webhook de n8n (OC Alerta): {e}")

    thread = threading.Thread(target=thread_target)
    thread.start()

class OrdenCompraController:
    def __init__(self):
        from app.controllers.insumo_controller import InsumoController
        self.model = OrdenCompraModel()
        self.inventario_controller = InventarioController()
        self.insumo_controller = InsumoController()
        self.usuario_controller = UsuarioController()
        self.registro_controller = RegistroController()
        self.reclamo_proveedor_controller = ReclamoProveedorController()
        self.control_calidad_insumo_model = ControlCalidadInsumoModel()


    def _parse_form_data(self, form_data):
        from app.controllers.insumo_controller import InsumoController
        insumo_controller = InsumoController()
        if hasattr(form_data, 'getlist'):
            insumo_ids = form_data.getlist('insumo_id[]')
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

        primer_insumo_id = insumo_ids[0] if insumo_ids else None
        if not primer_insumo_id:
            raise ValueError("No se proporcionaron insumos para la orden.")

        primer_insumo_data, _ = insumo_controller.obtener_insumo_por_id(primer_insumo_id)
        proveedor_id = primer_insumo_data.get('data', {}).get('id_proveedor')
        if not proveedor_id:
            raise ValueError(f"El insumo {primer_insumo_id} no tiene un proveedor asociado.")

        orden_data = {
            'proveedor_id': proveedor_id,
            'fecha_emision': form_data.get('fecha_emision'),
            'fecha_estimada_entrega': form_data.get('fecha_estimada_entrega'),
            'prioridad': form_data.get('prioridad'),
            'observaciones': form_data.get('observaciones'),
            'orden_produccion_id': form_data.get('orden_produccion_id'),
        }

        items_data = []
        subtotal_calculado = 0.0

        for i in range(len(insumo_ids)):
            if insumo_ids[i]:
                try:
                    cantidad = float(cantidades[i] or 0)
                    precio_str = (precios[i] or "0").replace("$", "").strip()
                    precio = float(precio_str)
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

        incluir_iva = form_data.get('incluir_iva', 'true').lower() in ['true', 'on', '1']
        iva_calculado = subtotal_calculado * 0.21 if incluir_iva else 0.0
        total_calculado = subtotal_calculado + iva_calculado

        orden_data['subtotal'] = round(subtotal_calculado, 2)
        orden_data['iva'] = round(iva_calculado, 2)
        orden_data['total'] = round(total_calculado, 2)

        return orden_data, items_data

    def crear_orden(self, orden_data, items_data, usuario_id: int) -> Dict:
        try:
            if not orden_data.get('proveedor_id') or not orden_data.get('fecha_emision'):
                return {'success': False, 'error': 'El proveedor y la fecha de emisión son obligatorios.'}

            subtotal = sum(float(item.get('cantidad_solicitada', 0)) * float(item.get('precio_unitario', 0)) for item in items_data)
            iva = subtotal * 0.21
            total = subtotal + iva

            orden_data['subtotal'] = round(subtotal, 2)
            orden_data['iva'] = round(iva, 2)
            orden_data['total'] = round(total, 2)

            if 'codigo_oc' not in orden_data or not orden_data['codigo_oc']:
                orden_data['codigo_oc'] = f"OC-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

            orden_data['usuario_creador_id'] = usuario_id
            if not orden_data.get('estado'):
                orden_data['estado'] = 'PENDIENTE'

            result = self.model.create_with_items(orden_data, items_data)
            if result.get('success'):
                oc = result.get('data')
                detalle = f"Se creó la orden de compra {oc.get('codigo_oc')}."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Creación', detalle)
            return result
        except Exception as e:
            logger.error(f"Error en el controlador al crear la orden: {e}")
            return {'success': False, 'error': str(e)}

    def crear_orden_desde_form(self, form_data, usuario_id):
        from collections import defaultdict
        from app.controllers.insumo_controller import InsumoController
        insumo_controller = InsumoController()

        try:
            if hasattr(form_data, 'getlist'):
                insumo_ids = form_data.getlist('insumo_id[]')
                cantidades = form_data.getlist('cantidad_solicitada[]')
            else:
                insumo_ids = form_data.get('insumo_id[]', [])
                cantidades = form_data.get('cantidad_solicitada[]', [])

            if not insumo_ids:
                raise ValueError("No se proporcionaron insumos para la orden.")

            items_procesados = []
            for i in range(len(insumo_ids)):
                insumo_id = insumo_ids[i]
                cantidad = float(cantidades[i] or 0)

                if not insumo_id or cantidad <= 0:
                    continue

                insumo_data_res, _ = insumo_controller.obtener_insumo_por_id(insumo_id)
                if not insumo_data_res.get('success'):
                    raise ValueError(f"El insumo con ID {insumo_id} no fue encontrado.")

                insumo_data = insumo_data_res['data']
                proveedor_id = insumo_data.get('id_proveedor')
                precio_unitario = float(insumo_data.get('precio_unitario', 0))

                if not proveedor_id:
                    raise ValueError(f"El insumo '{insumo_data.get('nombre')}' no tiene un proveedor asociado.")

                items_procesados.append({
                    'insumo_id': insumo_id,
                    'cantidad_solicitada': cantidad,
                    'precio_unitario': precio_unitario,
                    'proveedor_id': proveedor_id
                })

            items_por_proveedor = defaultdict(list)
            for item in items_procesados:
                items_por_proveedor[item['proveedor_id']].append(item)

            if not items_procesados:
                return {'success': False, 'error': 'La orden de compra debe tener al menos un item.'}

            if not items_por_proveedor:
                 return {'success': False, 'error': 'No se procesaron items válidos para crear órdenes.'}

            resultados_creacion = []
            ordenes_creadas_count = 0

            for proveedor_id, items_del_proveedor in items_por_proveedor.items():
                codigo_oc = f"OC-{datetime.now().strftime('%Y%m%d-%H%M%S%f')}"
                time.sleep(0.01)

                subtotal = sum(item['cantidad_solicitada'] * item['precio_unitario'] for item in items_del_proveedor)
                incluir_iva = form_data.get('incluir_iva', 'true').lower() in ['true', 'on', '1']
                iva = subtotal * 0.21 if incluir_iva else 0.0
                total = subtotal + iva

                orden_data = {
                    'codigo_oc': codigo_oc,
                    'proveedor_id': proveedor_id,
                    'fecha_emision': form_data.get('fecha_emision'),
                    'fecha_estimada_entrega': form_data.get('fecha_estimada_entrega'),
                    'observaciones': form_data.get('observaciones'),
                    'subtotal': round(subtotal, 2),
                    'iva': round(iva, 2),
                    'total': round(total, 2)
                }

                items_para_crear = [{k: v for k, v in item.items() if k != 'proveedor_id'} for item in items_del_proveedor]

                resultado = self.crear_orden(orden_data, items_para_crear, usuario_id)
                resultados_creacion.append(resultado)
                if resultado.get('success'):
                    ordenes_creadas_count += 1

            if ordenes_creadas_count > 0:
                codigos_ocs = [res['data']['codigo_oc'] for res in resultados_creacion if res.get('success')]
                detalle = f"Se crearon {ordenes_creadas_count} órdenes de compra desde el formulario: {', '.join(codigos_ocs)}."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Creación Múltiple', detalle)

            if ordenes_creadas_count == len(items_por_proveedor):
                return {
                    'success': True,
                    'message': f'Se crearon {ordenes_creadas_count} órdenes de compra exitosamente.',
                    'data': [res['data'] for res in resultados_creacion if res.get('success')]
                }
            elif ordenes_creadas_count > 0:
                 return {
                    'success': True,
                    'message': f'Se crearon {ordenes_creadas_count} de {len(items_por_proveedor)} órdenes de compra. Algunas fallaron.',
                    'data': resultados_creacion
                }
            else:
                 return {
                    'success': False,
                    'error': 'No se pudo crear ninguna orden de compra.',
                    'data': [res.get('error', 'Error desconocido') for res in resultados_creacion]
                }

        except ValueError as ve:
            logger.error(f"Error de validación procesando formulario para crear órdenes: {ve}")
            return {'success': False, 'error': str(ve)}
        except Exception as e:
            logger.error(f"Error procesando formulario para crear órdenes: {e}", exc_info=True)
            return {'success': False, 'error': 'Ocurrió un error inesperado al procesar la solicitud.'}

    def actualizar_orden(self, orden_id, form_data):
        try:
            orden_data, items_data = self._parse_form_data(form_data)

            if not orden_data.get('proveedor_id') or not orden_data.get('fecha_emision'):
                return {'success': False, 'error': 'El proveedor y la fecha de emisión son obligatorios.'}

            result = self.model.update_with_items(orden_id, orden_data, items_data)

            if result.get('success'):
                oc = result.get('data')
                detalle = f"Se actualizó la orden de compra {oc.get('codigo_oc')}."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Actualización', detalle)

            return result

        except Exception as e:
            logger.error(f"Error en el controlador al actualizar la orden: {e}")
            return {'success': False, 'error': str(e)}

    def get_orden(self, orden_id):
        try:
            result = self.model.get_one_with_details(orden_id)
            if result.get('success'):
                orden_data = result['data']

                if orden_data.get('estado') == 'RECEPCION_INCOMPLETA':
                    resumen_items = self._get_resumen_recepcion(orden_data)
                    orden_data['resumen_recepcion'] = resumen_items

                # Verificar si existe un reclamo para esta orden
                reclamo_response, _ = self.reclamo_proveedor_controller.get_reclamo_por_orden(orden_id)
                orden_data['reclamo_existente'] = reclamo_response.get('success', False) and reclamo_response.get('data') is not None

                subtotal_original = 0.0
                if 'items' in orden_data and orden_data['items']:
                    for item in orden_data['items']:
                        try:
                            cantidad_solicitada = float(item.get('cantidad_solicitada', 0))
                            precio_unitario = float(item.get('precio_unitario', 0))
                            subtotal_original += cantidad_solicitada * precio_unitario
                        except (ValueError, TypeError):
                            continue

                iva_original = subtotal_original * 0.21
                total_original = subtotal_original + iva_original

                orden_data['subtotal_original'] = round(subtotal_original, 2)
                orden_data['iva_original'] = round(iva_original, 2)
                orden_data['total_original'] = round(total_original, 2)

                return result, 200
            else:
                return result, 404
        except Exception as e:
            logger.error(f"Error en el controlador al obtener la orden {orden_id}: {e}")
            return {'success': False, 'error': str(e)}, 500

    def _get_resumen_recepcion(self, orden_data):
        from app.models.control_calidad_insumo import ControlCalidadInsumoModel
        control_calidad_model = ControlCalidadInsumoModel()

        items_resumen = []
        documento_ingreso = f"{orden_data.get('codigo_oc')}"

        lotes_asociados_res = self.inventario_controller.inventario_model.find_all(
            filters={'documento_ingreso': ('ilike', documento_ingreso)}
        )
        lotes_asociados = lotes_asociados_res.get('data', []) if lotes_asociados_res.get('success') else []

        qc_asociados_res = control_calidad_model.find_all(
            filters={'orden_compra_id': orden_data.get('id')}
        )
        qc_asociados = qc_asociados_res.get('data', []) if qc_asociados_res.get('success') else []

        lotes_por_insumo = {}
        for lote in lotes_asociados:
            insumo_id = lote.get('id_insumo')
            if insumo_id not in lotes_por_insumo:
                lotes_por_insumo[insumo_id] = []
            lotes_por_insumo[insumo_id].append(lote)

        qc_por_lote = {qc.get('lote_insumo_id'): qc for qc in qc_asociados}

        for item in orden_data.get('items', []):
            insumo_id = item.get('insumo_id')
            lotes_del_item = lotes_por_insumo.get(insumo_id, [])

            cantidad_aprobada = sum(float(l.get('cantidad_actual', 0)) for l in lotes_del_item)
            cantidad_cuarentena = sum(float(l.get('cantidad_en_cuarentena', 0)) for l in lotes_del_item)

            total_recibido = float(item.get('cantidad_recibida', 0))
            cantidad_rechazada = total_recibido - (cantidad_aprobada + cantidad_cuarentena)

            detalles_qc = []
            for lote in lotes_del_item:
                qc = qc_por_lote.get(lote.get('id_lote'))
                if qc:
                    detalles_qc.append({
                        'motivo': qc.get('resultado_inspeccion'),
                        'comentarios': qc.get('comentarios')
                    })

            items_resumen.append({
                'insumo_nombre': item.get('insumo_nombre'),
                'cantidad_solicitada': item.get('cantidad_solicitada'),
                'cantidad_recibida': item.get('cantidad_recibida'),
                'cantidad_aprobada': round(cantidad_aprobada, 2),
                'cantidad_cuarentena': round(cantidad_cuarentena, 2),
                'cantidad_rechazada': round(max(0, cantidad_rechazada), 2),
                'detalles_qc': detalles_qc
            })

        return items_resumen

    def _get_detalles_problemas_por_item(self, orden_data):
        from app.models.control_calidad_insumo import ControlCalidadInsumoModel
        control_calidad_model = ControlCalidadInsumoModel()

        problemas_por_item = {}

        qc_asociados_res = control_calidad_model.find_all(filters={'orden_compra_id': orden_data.get('id')})
        qc_asociados = qc_asociados_res.get('data', []) if qc_asociados_res.get('success') else []

        lotes_asociados_res = self.inventario_controller.inventario_model.find_all(
            filters={'documento_ingreso': ('ilike', f"{orden_data.get('codigo_oc')}")}
        )
        lotes_asociados = lotes_asociados_res.get('data', []) if lotes_asociados_res.get('success') else []

        qc_por_lote_id = {qc.get('lote_insumo_id'): qc for qc in qc_asociados}
        lotes_por_insumo_id = {}
        for lote in lotes_asociados:
            insumo_id = lote.get('id_insumo')
            if insumo_id not in lotes_por_insumo_id:
                lotes_por_insumo_id[insumo_id] = []
            lotes_por_insumo_id[insumo_id].append(lote)

        for item in orden_data.get('items', []):
            insumo_id = item.get('insumo_id')
            problemas_por_item[insumo_id] = None

            # Prioridad 1: Fallo de Calidad
            lotes_del_item = lotes_por_insumo_id.get(insumo_id, [])
            for lote in lotes_del_item:
                qc = qc_por_lote_id.get(lote.get('id_lote'))
                if qc and qc.get('resultado_inspeccion'):
                    problemas_por_item[insumo_id] = qc.get('resultado_inspeccion')
                    break
            if problemas_por_item[insumo_id]:
                continue

            # Prioridad 2: Discrepancia de Cantidad
            solicitada = float(item.get('cantidad_solicitada', 0))
            recibida = float(item.get('cantidad_recibida', 0))
            if not math.isclose(solicitada, recibida):
                problemas_por_item[insumo_id] = "CANTIDAD_INCORRECTA"

        return problemas_por_item

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
        try:
            filters = filtros or {}
            if 'estado' not in filters and request.args.get('estado'):
                filters['estado'] = request.args.get('estado')
            if 'proveedor_id' not in filters and request.args.get('proveedor_id'):
                filters['proveedor_id'] = int(request.args.get('proveedor_id'))
            if 'prioridad' not in filters and request.args.get('prioridad'):
                filters['prioridad'] = request.args.get('prioridad')
            if 'rango_fecha' not in filters and request.args.get('rango_fecha'):
                filters['rango_fecha'] = request.args.get('rango_fecha')

            if 'filtro' not in filters and request.args.get('filtro') == 'mis_ordenes':
                current_user_id = get_current_user().id
                if current_user_id:
                    filters['usuario_id'] = current_user_id

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
                oc = result.get('data')
                detalle = f"Se actualizó la orden de compra {oc.get('codigo_oc')} (vía API)."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Actualización', detalle)
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
        try:
            data = request.get_json() or {}
            motivo = data.get('motivo', '')

            orden_actual_res = self.model.find_by_id(orden_id)
            if not orden_actual_res.get('success'):
                return {'success': False, 'error': 'Orden no encontrada'}, 404

            orden_data = orden_actual_res['data']
            estado_actual = orden_data.get('estado', 'PENDIENTE')

            estados_no_cancelables = ['COMPLETADA', 'CANCELADA', 'RECEPCION_COMPLETA', 'RECEPCION_INCOMPLETA']
            if estado_actual in estados_no_cancelables:
                return {'success': False, 'error': f'No se puede cancelar una orden en estado {estado_actual}'}, 400

            observaciones_actuales = orden_data.get('observaciones', '') or ''
            cancelacion_data = {
                'estado': 'CANCELADA',
                'updated_at': datetime.now().isoformat(),
                'observaciones': f"{observaciones_actuales}\n--- CANCELADA ---\nMotivo: {motivo}\nFecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            }

            result = self.model.update(orden_id, cancelacion_data)

            if result.get('success'):
                oc = result.get('data')
                detalle = f"Se canceló la orden de compra {oc.get('codigo_oc')}. Motivo: {motivo}"
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Cancelación', detalle)
                return {'success': True, 'data': result.get('data'), 'message': 'Orden de compra cancelada exitosamente'}, 200
            else:
                return {'success': False, 'error': result.get('error')}, 400

        except Exception as e:
            return {'success': False, 'error': str(e)}, 500

    def obtener_orden_por_id(self, orden_id):
        return self.get_orden(orden_id)

    def aprobar_orden(self, orden_id, usuario_id):
        try:
            update_data = {
                'estado': 'APROBADA',
                'usuario_aprobador_id': usuario_id,
                'updated_at': datetime.now().isoformat()
            }
            result = self.model.update(orden_id, update_data)
            if result.get('success'):
                oc = result.get('data')
                detalle = f"Se aprobó la orden de compra {oc.get('codigo_oc')}."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Cambio de Estado', detalle)
            return result
        except Exception as e:
            logger.error(f"Error aprobando orden {orden_id}: {e}")
            return {'success': False, 'error': str(e)}

    def marcar_en_transito(self, orden_id):
        try:
            update_data = {
                'estado': 'EN_TRANSITO',
                'updated_at': datetime.now().isoformat()
            }
            result = self.model.update(orden_id, update_data)
            if result.get('success'):
                oc = result.get('data')
                detalle = f"La orden de compra {oc.get('codigo_oc')} se marcó como EN TRANSITO."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Cambio de Estado', detalle)
            return result
        except Exception as e:
            logger.error(f"Error marcando la orden {orden_id} como EN TRANSITO: {e}")
            return {'success': False, 'error': str(e)}

    def cambiar_estado_oc(self, orden_id, nuevo_estado):
        try:
            if nuevo_estado == 'EN_RECEPCION':
                orden_actual_res, status_code = self.get_orden(orden_id)
                if not orden_actual_res.get('success'):
                    return orden_actual_res, status_code

                orden_data = orden_actual_res.get('data', {})
                if orden_data.get('estado') != 'EN_TRANSITO':
                    error_msg = f"La orden solo puede pasar a recepción desde 'EN TRANSITO'. Estado actual: {orden_data.get('estado')}"
                    return {'success': False, 'error': error_msg}, 400

            update_data = {
                'estado': nuevo_estado,
                'updated_at': datetime.now().isoformat()
            }
            result = self.model.update(orden_id, update_data)

            if result.get('success'):
                oc = result.get('data')
                detalle = f"La orden de compra {oc.get('codigo_oc')} cambió su estado a {nuevo_estado.replace('_', ' ')}."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Cambio de Estado', detalle)
                return result, 200
            else:
                return result, 400 if 'not found' not in result.get('error', '').lower() else 404

        except Exception as e:
            logger.error(f"Error cambiando estado de la orden {orden_id} a {nuevo_estado}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}, 500

    def marcar_en_recepcion(self, orden_id):
        try:
            orden_actual_res, _ = self.get_orden(orden_id)
            if not orden_actual_res.get('success'):
                return orden_actual_res

            orden_data = orden_actual_res['data']
            if orden_data.get('estado') != 'EN_TRANSITO':
                return {'success': False, 'error': f"La orden solo puede pasar a recepción desde el estado 'EN TRANSITO'. Estado actual: {orden_data.get('estado')}"}

            update_data = {
                'estado': 'EN_RECEPCION',
                'updated_at': datetime.now().isoformat()
            }
            result = self.model.update(orden_id, update_data)
            if result.get('success'):
                oc = result.get('data')
                detalle = f"La orden de compra {oc.get('codigo_oc')} cambió su estado a EN RECEPCIÓN."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Cambio de Estado', detalle)
            return result
        except Exception as e:
            logger.error(f"Error marcando la orden {orden_id} como EN RECEPCION: {e}")
            return {'success': False, 'error': str(e)}

    def rechazar_orden(self, orden_id, motivo):
        try:
            orden_actual_result, _ = self.get_orden(orden_id)
            if not orden_actual_result.get('success'):
                return orden_actual_result

            orden_data = orden_actual_result['data']
            observaciones_actuales = orden_data.get('observaciones', '')

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
            if result.get('success'):
                oc = result.get('data')
                detalle = f"Se rechazó la orden de compra {oc.get('codigo_oc')}. Motivo: {motivo}"
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Cambio de Estado', detalle)
            return result
        except Exception as e:
            logger.error(f"Error rechazando orden {orden_id}: {e}")
            return {'success': False, 'error': str(e)}

    def _crear_reclamo_automatico(self, orden_data, motivo, descripcion):
        try:
            reclamo_data = {
                'orden_compra_id': orden_data.get('id'),
                'proveedor_id': orden_data.get('proveedor_id'),
                'motivo': motivo,
                'descripcion_problema': descripcion,
                'usuario_creador_id': get_current_user().id
            }
            self.reclamo_proveedor_controller.crear_reclamo(reclamo_data)
            logger.info(f"Reclamo creado automáticamente para la OC {orden_data.get('codigo_oc')}.")
        except Exception as e_reclamo:
            logger.error(f"Error al crear el reclamo automático para la OC {orden_data.get('codigo_oc')}: {e_reclamo}")

    # --- MÉTODO CLAVE: MANEJO DE ESCENARIOS FALLIDOS (ACTUALIZADO) ---
    def _manejar_escenario_fallido(self, orden_data, motivo, descripcion, orden_produccion_controller: "OrdenProduccionController", modo_oc='auto', usuario_id=None):
        """
        Maneja los escenarios donde la recepción es incompleta.
        Aplica lógica diferenciada si hay OP vinculada o si es OC manual.
        """
        op_id = orden_data.get('orden_produccion_id')
        mensaje_extra = ""

        # 1. Actualizar estado de la OC actual
        self.model.update(orden_data['id'], {'estado': 'RECEPCION_INCOMPLETA'})

        # --- CASO A: OC VINCULADA A UNA OP ---
        if op_id:
            logger.info(f"[OC RECEPCION] Fallo/Discrepancia en OC {orden_data.get('codigo_oc')} vinculada a OP {op_id}. Modo: {modo_oc}")

            if modo_oc == 'manual':
                # Manual: OP vuelve a PENDIENTE, NO se crea OC hija automática.
                orden_produccion_controller.cambiar_estado_orden_simple(op_id, 'PENDIENTE')
                mensaje_extra = "La OP asociada volvió al estado PENDIENTE para gestión manual del faltante."
                logger.info(f"[OC RECEPCION] OP {op_id} movida a PENDIENTE (Gestión Manual).")
                return {
                    'success': True,
                    'partial': True,
                    'message': f"{motivo}. Se generó un reclamo. {mensaje_extra}"
                }

            else:
                # Automático: OP a EN ESPERA.
                orden_produccion_controller.cambiar_estado_orden_simple(op_id, 'EN ESPERA')
                mensaje_extra_op = "La OP asociada pasó a EN ESPERA."

        # --- CASO B: OC MANUAL (SIN OP) ---
        else:
            # Si es manual y el usuario eligió "gestionar manualmente", no hacemos nada extra.
            if modo_oc == 'manual':
                return {
                    'success': True,
                    'partial': True,
                    'message': f"{motivo}. Se generó un reclamo. No se generó OC hija (gestión manual)."
                }
            # Si es automático, seguimos al bloque de creación de hija.
            mensaje_extra_op = "OC Manual incompleta."

        # --- CREACIÓN DE OC HIJA (Común para Auto-OP y Auto-Manual) ---
        if usuario_id:
            resultado_hija = self.crear_oc_hija_desde_fallo(orden_data['id'], usuario_id)
            if resultado_hija.get('success'):
                nueva_oc = resultado_hija.get('data', {}).get('data', {}).get('codigo_oc', 'N/A')
                mensaje_extra = f"{mensaje_extra_op} Se generó automáticamente la OC complementaria {nueva_oc}."
                logger.info(f"[OC RECEPCION] OC Hija creada para OC {orden_data.get('id')}.")
            else:
                mensaje_extra = f"{mensaje_extra_op} Pero falló la creación automática de la OC hija: {resultado_hija.get('error')}"
                logger.error(f"[OC RECEPCION] Fallo creando OC hija automática: {resultado_hija.get('error')}")
        else:
             mensaje_extra = f"{mensaje_extra_op} (No se pudo crear OC hija por falta de ID de usuario)."

        return {
            'success': True,
            'partial': True,
            'message': f"{motivo}. Se generó un reclamo. {mensaje_extra}"
        }



    # --- INICIO DE LA MODIFICACIÓN: La función ahora guarda las cantidades correctas y el QC ---
    def _crear_lotes_para_items_recibidos(self, items_recibidos, orden_data, usuario_id):
        lotes_creados_count = 0
        errores = []

        from app.models.reserva_insumo import ReservaInsumoModel
        reserva_insumo_model = ReservaInsumoModel()

        for item_info in items_recibidos:
            item_data = item_info['data']
            cantidad_aprobada = float(item_info['cantidad_aprobada'])
            qc_data = item_info.get('qc_data')

            # --- CORRECCIÓN: FILTRO ESTRICTO ---
            # Solo creamos lote si hay cantidad APROBADA.
            # La cantidad en cuarentena o rechazada se ignora para el lote (va a reclamo).
            if cantidad_aprobada <= 0:
                continue

            # La cantidad real del lote es SOLO lo aprobado.
            cantidad_real_lote = cantidad_aprobada

            # Configuración de Reserva Dura
            op_id = orden_data.get('orden_produccion_id')
            es_reserva_automatica = bool(op_id and cantidad_aprobada > 0)

            if es_reserva_automatica:
                estado_lote = 'reservado'
                cantidad_inicial_disponible = 0 # Todo se reserva
                cantidad_a_reservar = cantidad_aprobada
            else:
                estado_lote = 'disponible'
                cantidad_inicial_disponible = cantidad_aprobada
                cantidad_a_reservar = 0

            lote_data = {
                'id_insumo': item_data['insumo_id'],
                'id_proveedor': orden_data.get('proveedor_id'),
                'cantidad_inicial': cantidad_real_lote,     # Solo lo aprobado
                'cantidad_actual': cantidad_inicial_disponible,
                'cantidad_en_cuarentena': 0, # Forzamos 0 porque "no cuenta para el lote"
                'precio_unitario': item_data.get('precio_unitario'),
                'documento_ingreso': f"{orden_data.get('codigo_oc')}",
                'f_ingreso': date.today().isoformat(),
                'estado': estado_lote,
                'orden_produccion_id': op_id
            }

            # Cálculo de vencimiento (Mantenemos tu lógica original)
            insumo_id_para_lote = item_data.get('insumo_id')
            if insumo_id_para_lote:
                insumo_res, _ = self.insumo_controller.obtener_insumo_por_id(insumo_id_para_lote)
                if insumo_res.get('success') and insumo_res.get('data'):
                    vida_util = int(insumo_res['data'].get('vida_util_dias') or 0)
                    if vida_util > 0:
                        fecha_vencimiento = datetime.now().date() + timedelta(days=vida_util)
                        lote_data['f_vencimiento'] = fecha_vencimiento.isoformat()

            try:
                # Crear el lote
                lote_result, status_code = self.inventario_controller.crear_lote(lote_data, usuario_id)

                if lote_result.get('success'):
                    lotes_creados_count += 1
                    nuevo_lote_id = lote_result.get('data', {}).get('id_lote')

                    # Crear Reserva (si aplica)
                    if es_reserva_automatica and nuevo_lote_id:
                        try:
                            datos_reserva = {
                                'orden_produccion_id': op_id,
                                'lote_inventario_id': nuevo_lote_id,
                                'insumo_id': item_data['insumo_id'],
                                'cantidad_reservada': cantidad_a_reservar,
                                'usuario_reserva_id': usuario_id,
                                'estado': 'RESERVADO'
                            }
                            reserva_insumo_model.create(datos_reserva)
                            logger.info(f"Reserva creada: Lote {nuevo_lote_id} -> OP {op_id}")
                        except Exception as e_reserva:
                            logger.error(f"Fallo reserva auto: {e_reserva}")

                    # Registrar Control de Calidad vinculado al lote
                    # (Opcional: si quieres guardar el registro de que este lote "pasó" la inspección)
                    if qc_data and nuevo_lote_id:
                        qc_data['lote_insumo_id'] = nuevo_lote_id
                        qc_data['orden_compra_id'] = orden_data.get('id')
                        # Ajustamos la decisión a APROBADO porque este lote solo tiene lo bueno
                        qc_data['decision_final'] = 'APROBADO'
                        self.control_calidad_insumo_model.create_registro(qc_data)

                else:
                    errores.append(f"Insumo {item_data['insumo_id']}: {lote_result.get('error')}")
            except Exception as e_lote:
                errores.append(f"Insumo {item_data['insumo_id']}: {str(e_lote)}")

        return lotes_creados_count, errores
    # --- FIN DE LA MODIFICACIÓN ---

    def procesar_recepcion(self, orden_id, form_data, files_data, usuario_id, orden_produccion_controller: "OrdenProduccionController"):
        try:
            orden_actual_res, status = self.get_orden(orden_id)
            if not orden_actual_res.get('success'):
                return {'success': False, 'error': 'Orden de compra no encontrada.'}
            orden_actual = orden_actual_res.get('data')

            if orden_actual.get('estado') != 'EN_RECEPCION':
                return {'success': False, 'error': f"Estado incorrecto: {orden_actual.get('estado')}"}

            paso = form_data.get('paso')

            # --- PASO 1: VERIFICACIÓN DE CANTIDAD ---
            if paso == '1':
                item_ids = form_data.getlist('item_id[]')
                cantidades_recibidas_form = form_data.getlist('cantidad_recibida[]')

                if len(item_ids) != len(cantidades_recibidas_form):
                    return {'success': False, 'error': 'Error en formulario: descalce de items.'}

                for i, item_id_str in enumerate(item_ids):
                    cantidad_recibida = float(cantidades_recibidas_form[i])
                    self.model.item_model.update(int(item_id_str), {'cantidad_recibida': cantidad_recibida})

                self.model.update(orden_id, {'paso_recepcion': 1})
                return {'success': True, 'message': 'Paso 1 completado. Proceda al control de calidad.'}

            # --- PASO 2: CONTROL DE CALIDAD Y CIERRE ---
            elif paso == '2':
                if orden_actual.get('paso_recepcion') != 1:
                    return {'success': False, 'error': 'Debe completar el Paso 1 primero.'}

                # 1. Capturar la decisión del usuario (Auto vs Manual)
                modo_oc = form_data.get('modo_oc', 'auto') # Default a auto si no viene

                item_ids = form_data.getlist('item_id[]')
                cantidades_aprobadas_form = form_data.getlist('cantidad_aprobada[]')
                cantidades_cuarentena_form = form_data.getlist('cantidad_cuarentena[]')
                cantidades_rechazadas_form = form_data.getlist('cantidad_rechazada[]')
                resultado_inspeccion_form = form_data.getlist('resultado_inspeccion[]')
                comentarios_form = form_data.getlist('comentarios[]')

                # Validaciones de formulario...
                if not (len(item_ids) == len(cantidades_aprobadas_form)):
                     return {'success': False, 'error': 'Error en formulario Paso 2.'}

                # Refrescamos items
                items_result, _ = self.get_orden(orden_id)
                items_actualizados = items_result.get('data', {}).get('items', [])
                items_originales_map = {str(item['id']): item for item in items_actualizados}

                # Flags de estado
                hay_discrepancia_cantidad = False
                hay_fallo_calidad = False
                descripcion_problemas = ""

                # 2. Detectar Discrepancia Global (Solicitado vs Recibido Físico en Paso 1)
                for item in items_actualizados:
                    solicitada = float(item.get('cantidad_solicitada', 0))
                    recibida = float(item.get('cantidad_recibida', 0))
                    if not math.isclose(recibida, solicitada) and recibida < solicitada:
                        hay_discrepancia_cantidad = True
                        descripcion_problemas += f"- Faltante Físico: {item['insumo_nombre']} (Ped: {solicitada}, Llegó: {recibida})\n"

                # 3. Procesar QC y preparar lotes
                items_para_crear_lote = []

                for i, item_id_str in enumerate(item_ids):
                    item_original = items_originales_map.get(item_id_str)
                    if not item_original: continue

                    cant_aprobada = float(cantidades_aprobadas_form[i])
                    cant_cuarentena = float(cantidades_cuarentena_form[i])
                    cant_rechazada = float(cantidades_rechazadas_form[i])
                    total_recibido = float(item_original.get('cantidad_recibida', 0))

                    # Detectar fallo de calidad
                    if cant_rechazada > 0 or cant_cuarentena > 0:
                        hay_fallo_calidad = True
                        motivo = resultado_inspeccion_form[i]
                        comentarios = comentarios_form[i]
                        tipo_fallo = "RECHAZADO" if cant_rechazada > 0 else "CUARENTENA"
                        cantidad_afectada = cant_rechazada if cant_rechazada > 0 else cant_cuarentena

                        descripcion_problemas += (f"- Calidad {tipo_fallo}: {item_original['insumo_nombre']} "
                                                  f"({cantidad_afectada} un.). Motivo: {motivo}. {comentarios}\n")

                        qc_data = {
                            'usuario_supervisor_id': usuario_id,
                            'decision_final': tipo_fallo,
                            'comentarios': comentarios,
                            'resultado_inspeccion': motivo,
                            'foto_url': None
                        }
                    else:
                        qc_data = None

                    if total_recibido > 0:
                        items_para_crear_lote.append({
                            'data': item_original,
                            'cantidad_total_recibida': total_recibido,
                            'cantidad_aprobada': cant_aprobada,
                            'cantidad_cuarentena': cant_cuarentena,
                            'qc_data': qc_data
                        })

                # 4. Crear Lotes (Esto consolida el stock real en el sistema)
                lotes_creados, errores_lote = self._crear_lotes_para_items_recibidos(
                    items_para_crear_lote, orden_actual, usuario_id
                )

                if errores_lote:
                    # Si falla la creación de lotes, es un error de sistema, no de flujo.
                    return {'success': False, 'error': f"Error creando inventario: {', '.join(errores_lote)}"}

                # 5. Decisión final basada en los flags
                if hay_discrepancia_cantidad or hay_fallo_calidad:

                    # A. Crear Reclamo
                    tipo_problema = "Fallo de Calidad" if hay_fallo_calidad else "Recepción Incompleta"
                    self._crear_reclamo_automatico(orden_actual, tipo_problema, descripcion_problemas)

                    # B. Enviar Webhook (Notificación)
                    try:
                        N8N_OC_ALERTA_URL = "https://n8n-kthy.onrender.com/webhook/alerta-oc-hija"
                        BASE_APP_URL = "https://tp-principal-frozen.onrender.com"
                        payload = {
                            "oc_id": orden_id,
                            "oc_codigo": orden_actual.get('codigo_oc'),
                            "proveedor_nombre": orden_actual.get('proveedor_nombre'),
                            "descripcion": descripcion_problemas.strip(),
                            "link_url": f"{BASE_APP_URL}/compras/detalle/{orden_id}"
                        }
                        enviar_webhook_async(N8N_OC_ALERTA_URL, payload)
                    except Exception as e_hook:
                        logger.error(f"Error webhook: {e_hook}")

                    # C. Manejar Estados de OP y OC Hija usando la función centralizada
                    return self._manejar_escenario_fallido(
                        orden_data=orden_actual,
                        motivo=tipo_problema,
                        descripcion=descripcion_problemas,
                        orden_produccion_controller=orden_produccion_controller,
                        modo_oc=modo_oc,  # <-- Pasamos la decisión del usuario
                        usuario_id=usuario_id
                    )

                # 6. Escenario Exitoso (Recepción Perfecta)
                else:
                    self.model.update(orden_id, {'estado': 'RECEPCION_COMPLETA'})

                    # Verificar OP vinculada
                    id_op_vinculada = orden_actual.get('orden_produccion_id')
                    if id_op_vinculada:
                        # Verificar si TODAS las OCs de esa OP están completas
                        todas_ocs_res = self.model.get_all({'orden_produccion_id': id_op_vinculada})
                        if todas_ocs_res.get('success'):
                            todas_ocs = todas_ocs_res.get('data', [])
                            # Actualizar estado en memoria de la actual
                            for oc in todas_ocs:
                                if oc['id'] == orden_id: oc['estado'] = 'RECEPCION_COMPLETA'

                            if all(oc.get('estado') == 'RECEPCION_COMPLETA' for oc in todas_ocs):
                                logger.info(f"Todas las OCs completas. Actualizando OP {id_op_vinculada}.")
                                orden_produccion_controller.verificar_y_actualizar_op_especifica(id_op_vinculada)
                    else:
                        # Es una OC manual sin OP, verificar stock general
                        orden_produccion_controller.verificar_y_actualizar_ordenes_en_espera()

                    # Cerrar OC padre si existe
                    id_padre = orden_actual.get('complementa_a_orden_id')
                    if id_padre:
                        self.model.update(id_padre, {'estado': 'RECEPCION_COMPLETA'})

                    return {'success': True, 'message': f'Recepción Completa. {lotes_creados} lotes ingresados.'}

            else:
                return {'success': False, 'error': 'Paso inválido.'}

        except Exception as e:
            logger.error(f"Error procesando recepción: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    # --- INICIO DE LA MODIFICACIÓN ---
    def crear_oc_hija_desde_fallo(self, orden_padre_id, usuario_id):
        try:
            orden_padre_res, _ = self.get_orden(orden_padre_id)
            if not orden_padre_res.get('success'):
                return {'success': False, 'error': 'No se encontró la orden de compra original.'}
            orden_padre = orden_padre_res.get('data')

            codigo_oc_padre = orden_padre.get('codigo_oc')
            if not codigo_oc_padre:
                return {'success': False, 'error': 'La orden padre no tiene un código de OC para trazar los lotes.'}

            # Usamos el código exacto del padre
            documento_ingreso = codigo_oc_padre

            items_faltantes = []

            # Delay para asegurar consistencia en DB
            time.sleep(1)

            lotes_creados_res = self.inventario_controller.inventario_model.find_all(
                filters={'documento_ingreso': documento_ingreso}
            )
            lotes_creados = lotes_creados_res.get('data', []) if lotes_creados_res.get('success') else []

            logger.info(f"[OC HIJA] Buscando lotes con doc '{documento_ingreso}'. Encontrados: {len(lotes_creados)}")

            lotes_por_insumo = {}
            for lote in lotes_creados:
                insumo_id = lote.get('id_insumo')
                if insumo_id not in lotes_por_insumo:
                    lotes_por_insumo[insumo_id] = []
                lotes_por_insumo[insumo_id].append(lote)

            for item in orden_padre.get('items', []):
                item_insumo_id = item.get('insumo_id')
                solicitado = float(item.get('cantidad_solicitada', 0))

                lotes_del_item = lotes_por_insumo.get(item_insumo_id, [])

                # --- CORRECCIÓN: Restar Cuarentena/Rechazo ---
                total_ingresado_neto = 0.0

                for lote in lotes_del_item:
                    inicial = float(lote.get('cantidad_inicial', 0))
                    cuarentena = float(lote.get('cantidad_en_cuarentena', 0))

                    # Si el lote está 'rechazado' o 'no_apto', no cuenta nada.
                    # Si está en 'cuarentena', tampoco cuenta como disponible para producción inmediata.
                    # Si está 'disponible' o 'reservado', cuenta lo que no sea cuarentena.

                    estado = lote.get('estado', '').lower()

                    if estado in ['rechazado', 'no_apto', 'retirado']:
                        continue # Este lote no sirve, no suma al ingresado

                    # Lo que sirve es lo que entró MENOS lo que se apartó por calidad
                    cantidad_util = max(0, inicial - cuarentena)
                    total_ingresado_neto += cantidad_util

                # Calculamos el faltante real (Lo que pedí - Lo que sirve)
                cantidad_a_reordenar = solicitado - total_ingresado_neto

                logger.info(f"[OC HIJA] Insumo {item_insumo_id}: Solicitado {solicitado} - Útil {total_ingresado_neto} = Faltante {cantidad_a_reordenar}")
                if cantidad_a_reordenar > 0.01:
                    items_faltantes.append({
                        'insumo_id': item_insumo_id,
                        'cantidad_faltante': cantidad_a_reordenar,
                        'precio_unitario': float(item.get('precio_unitario', 0))
                    })

            if not items_faltantes:
                return {'success': False, 'error': 'No se encontraron discrepancias (faltantes o rechazados) para crear una nueva orden.'}

            return self._crear_orden_complementaria(orden_padre, items_faltantes, usuario_id)

        except Exception as e:
            logger.error(f"Error creando OC hija para la OC {orden_padre_id}: {e}", exc_info=True)
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

    def establecer_gestion_manual(self, orden_id):
        """Establece la bandera de gestión manual a True para una orden."""
        try:
            update_data = {
                'gestion_manual': True,
                'updated_at': datetime.now().isoformat()
            }
            result = self.model.update(orden_id, update_data)
            if result.get('success'):
                oc = result.get('data')
                detalle = f"Se estableció gestión manual para la OC {oc.get('codigo_oc')}."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Actualización', detalle)
            return result
        except Exception as e:
            logger.error(f"Error estableciendo gestión manual para orden {orden_id}: {e}")
            return {'success': False, 'error': str(e)}

    def desvincular_de_orden_produccion(self, orden_produccion_id: int) -> dict:
        """
        Desvincula las OCs de una OP específica (setea orden_produccion_id = NULL).
        Útil cuando se cancela una OP pero se quiere mantener la compra de insumos para stock general.
        """
        try:
            # Buscamos OCs asociadas a esta OP que no estén ya canceladas/completas
            # (Aunque técnicamente desvinculamos todas para mantener limpieza histórica)
            update_result = self.model.db.table(self.model.get_table_name())\
                .update({'orden_produccion_id': None})\
                .eq('orden_produccion_id', orden_produccion_id)\
                .execute()

            if update_result.data:
                logger.info(f"Se desvincularon {len(update_result.data)} OCs de la OP {orden_produccion_id}.")

            return {'success': True}
        except Exception as e:
            logger.error(f"Error desvinculando OCs de la OP {orden_produccion_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
