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
from datetime import datetime, date
import logging
import time

logger = logging.getLogger(__name__)

# --- AÑADIR ESTE BLOQUE ---
# Esto permite usar el nombre para type hints sin causar importación circular
if TYPE_CHECKING:
    from app.controllers.orden_produccion_controller import OrdenProduccionController
# -------------------------

class OrdenCompraController:
    def __init__(self):
        from app.controllers.insumo_controller import InsumoController
        self.model = OrdenCompraModel()
        self.inventario_controller = InventarioController()
        self.insumo_controller = InsumoController()
        self.usuario_controller = UsuarioController()
        self.registro_controller = RegistroController()
        self.reclamo_proveedor_controller = ReclamoProveedorController()


    def _parse_form_data(self, form_data):
        """
        Parsea los datos del formulario web o de un diccionario, calcula los totales
        y prepara los datos para la creación/actualización de la orden.
        """
        from app.controllers.insumo_controller import InsumoController
        insumo_controller = InsumoController()
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

        primer_insumo_id = insumo_ids[0] if insumo_ids else None
        if not primer_insumo_id:
            raise ValueError("No se proporcionaron insumos para la orden.")

        # Obtener el proveedor del primer insumo
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
            # >>> AÑADE ESTA LÍNEA CRÍTICA <<<
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

        # Calcular IVA y Total, condicionado por un campo en el formulario
        incluir_iva = form_data.get('incluir_iva', 'true').lower() in ['true', 'on', '1']
        iva_calculado = subtotal_calculado * 0.21 if incluir_iva else 0.0
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

            # --- CORRECCIÓN: Generar código único si no se provee ---
            if 'codigo_oc' not in orden_data or not orden_data['codigo_oc']:
                orden_data['codigo_oc'] = f"OC-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            # ----------------------------------------------------

            # Asignar datos clave
            orden_data['usuario_creador_id'] = usuario_id
            if not orden_data.get('estado'):
                orden_data['estado'] = 'PENDIENTE'

            # Crear la orden
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
        """
        Wrapper para crear una o más órdenes desde un formulario web.
        Agrupa los insumos por proveedor y genera una OC para cada uno.
        """
        from collections import defaultdict
        from app.controllers.insumo_controller import InsumoController
        insumo_controller = InsumoController()
        
        try:
            # 1. Pre-procesar todos los items del formulario para obtener datos fiables de la BD
            if hasattr(form_data, 'getlist'):
                insumo_ids = form_data.getlist('insumo_id[]')
                cantidades = form_data.getlist('cantidad_solicitada[]')
            else: # Soporte para datos tipo JSON/dict
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
                    
                # Obtener datos completos del insumo para asegurar proveedor y precio correctos
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
            
            # 2. Agrupar items por proveedor
            items_por_proveedor = defaultdict(list)
            for item in items_procesados:
                items_por_proveedor[item['proveedor_id']].append(item)
            
            if not items_procesados:
                return {'success': False, 'error': 'La orden de compra debe tener al menos un item.'}
                
            if not items_por_proveedor:
                 return {'success': False, 'error': 'No se procesaron items válidos para crear órdenes.'}

            # 3. Iterar sobre cada grupo de proveedor y crear una orden de compra
            resultados_creacion = []
            ordenes_creadas_count = 0
            
            for proveedor_id, items_del_proveedor in items_por_proveedor.items():
                # Generar código único para cada orden
                codigo_oc = f"OC-{datetime.now().strftime('%Y%m%d-%H%M%S%f')}"
                time.sleep(0.01) # Pausa mínima para asegurar timestamps diferentes

                # a. Calcular totales para esta orden específica
                subtotal = sum(item['cantidad_solicitada'] * item['precio_unitario'] for item in items_del_proveedor)
                incluir_iva = form_data.get('incluir_iva', 'true').lower() in ['true', 'on', '1']
                iva = subtotal * 0.21 if incluir_iva else 0.0
                total = subtotal + iva
                
                # b. Construir los datos de la orden
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
                
                # c. Limpiar el proveedor_id de los items antes de pasarlos a la creación
                items_para_crear = [{k: v for k, v in item.items() if k != 'proveedor_id'} for item in items_del_proveedor]

                # d. Crear la orden usando el método existente
                resultado = self.crear_orden(orden_data, items_para_crear, usuario_id)
                resultados_creacion.append(resultado)
                if resultado.get('success'):
                    ordenes_creadas_count += 1
            
            # 4. Formatear la respuesta final para el usuario
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
                    'success': True, # Éxito parcial
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
        """
        Actualiza una orden de compra existente a partir de datos de un formulario web.
        """
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
        """
        Obtiene una orden de compra específica con todos los detalles,
        y calcula los valores originales para la vista.
        """
        try:
            result = self.model.get_one_with_details(orden_id)
            if result.get('success'):
                orden_data = result['data']
                
                # Calcular totales basados en la cantidad SOLICITADA (valores originales)
                subtotal_original = 0.0
                if 'items' in orden_data and orden_data['items']:
                    for item in orden_data['items']:
                        try:
                            cantidad_solicitada = float(item.get('cantidad_solicitada', 0))
                            precio_unitario = float(item.get('precio_unitario', 0))
                            subtotal_original += cantidad_solicitada * precio_unitario
                        except (ValueError, TypeError):
                            continue
                
                # Basado en la lógica de creación, se asume que el IVA del 21% siempre aplica.
                iva_original = subtotal_original * 0.21
                total_original = subtotal_original + iva_original
                
                # Añadir los valores originales al diccionario de datos para ser usados en la plantilla
                orden_data['subtotal_original'] = round(subtotal_original, 2)
                orden_data['iva_original'] = round(iva_original, 2)
                orden_data['total_original'] = round(total_original, 2)

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
                oc = result.get('data')
                detalle = f"Se canceló la orden de compra {oc.get('codigo_oc')}. Motivo: {motivo}"
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Cancelación', detalle)
                return jsonify({
                    'success': True,
                    'data': result['data'],
                    'message': 'Orden de compra cancelada exitosamente'
                })
            else:
                return jsonify({'success': False, 'error': result['error']}), 400

        except Exception as e:
            return {'success': False, 'error': str(e)}, 500
            
    def cancelar_orden(self, orden_id):
        """Endpoint específico para cancelar órdenes de compra"""
        try:
            data = request.get_json() or {}
            motivo = data.get('motivo', '')

            # 1. Primero verificar que la orden existe y puede cancelarse
            orden_actual_res = self.model.find_by_id(orden_id)
            if not orden_actual_res.get('success'):
                return {'success': False, 'error': 'Orden no encontrada'}, 404

            orden_data = orden_actual_res['data']
            estado_actual = orden_data.get('estado', 'PENDIENTE')

            # 2. Validar que se puede cancelar
            estados_no_cancelables = ['COMPLETADA', 'CANCELADA', 'CERRADA', 'RECEPCION_COMPLETA', 'RECEPCION_INCOMPLETA']
            if estado_actual in estados_no_cancelables:
                return {'success': False, 'error': f'No se puede cancelar una orden en estado {estado_actual}'}, 400

            # 3. Preparar datos para cancelación
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
            if result.get('success'):
                oc = result.get('data')
                detalle = f"Se aprobó la orden de compra {oc.get('codigo_oc')}."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Cambio de Estado', detalle)
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
            if result.get('success'):
                oc = result.get('data')
                detalle = f"La orden de compra {oc.get('codigo_oc')} se marcó como EN TRANSITO."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Cambio de Estado', detalle)
            return result
        except Exception as e:
            logger.error(f"Error marcando la orden {orden_id} como EN TRANSITO: {e}")
            return {'success': False, 'error': str(e)}

    def cambiar_estado_oc(self, orden_id, nuevo_estado):
        """
        Cambia el estado de una orden de compra a un nuevo estado, con validaciones.
        """
        try:
            # Validación específica para la transición a EN_RECEPCION
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
                # Asumimos que un fallo en el modelo es un error del cliente o no encontrado
                return result, 400 if 'not found' not in result.get('error', '').lower() else 404

        except Exception as e:
            logger.error(f"Error cambiando estado de la orden {orden_id} a {nuevo_estado}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}, 500

    def marcar_en_recepcion(self, orden_id):
        """
        Marca una orden de compra como 'EN_RECEPCION'.
        """
        try:
            # Validar que la orden esté en 'EN_TRANSITO'
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
            if result.get('success'):
                oc = result.get('data')
                detalle = f"Se rechazó la orden de compra {oc.get('codigo_oc')}. Motivo: {motivo}"
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Cambio de Estado', detalle)
            return result
        except Exception as e:
            logger.error(f"Error rechazando orden {orden_id}: {e}")
            return {'success': False, 'error': str(e)}

    def _reiniciar_bandera_stock_recibido(self, orden_id: int):
        """
        Recorre la cadena de órdenes de compra hacia atrás (a través de 'complementa_a_orden_id')
        y para cada orden, quita la bandera 'en_espera_de_reestock' de todos sus insumos.
        Esto es crucial para permitir que se generen nuevas OCs automáticas para esos insumos.
        """
        logger.info(f"Iniciando reinicio de bandera 'en_espera_de_reestock' desde la OC ID: {orden_id}.")
        current_id = orden_id
        processed_ids = set()

        try:
            while current_id and current_id not in processed_ids:
                processed_ids.add(current_id)
                orden_res = self.model.get_one_with_details(current_id)

                if not orden_res.get('success'):
                    logger.warning(f"No se encontró la orden con ID {current_id} en la cadena de reinicio de bandera.")
                    break

                orden_actual = orden_res['data']
                logger.info(f"Procesando OC {orden_actual.get('codigo_oc')} (ID: {current_id}) para quitar banderas.")

                # Quitar estado 'en espera' de los insumos de esta orden
                if 'items' in orden_actual and orden_actual['items']:
                    for item in orden_actual['items']:
                        if item.get('insumo_id'):
                            self.insumo_controller.insumo_model.quitar_en_espera(item['insumo_id'])
                            logger.info(f"Bandera 'en_espera_de_reestock' reiniciada para insumo ID: {item['insumo_id']}.")
                else:
                    logger.info(f"La OC {current_id} no tiene items para procesar.")

                # Moverse a la orden que esta complementa
                current_id = orden_actual.get('complementa_a_orden_id')

            logger.info(f"Finalizado el reinicio de banderas para la cadena de la OC ID: {orden_id}.")

        except Exception as e:
            logger.error(f"Error crítico durante el reinicio de banderas para la cadena de la OC {orden_id}: {e}", exc_info=True)

    def _crear_reclamo_automatico(self, orden_id, orden_data, items_faltantes):
        try:
            descripcion_reclamo = "Insumos faltantes:\n" + "\n".join([f"- {item['insumo_id']}: {item['cantidad_faltante']}" for item in items_faltantes])
            reclamo_data = {
                'orden_compra_id': orden_id,
                'proveedor_id': orden_data.get('proveedor_id'),
                'motivo': 'Recepción Incompleta',
                'descripcion_problema': descripcion_reclamo
            }
            self.reclamo_proveedor_controller.crear_reclamo(reclamo_data)
            logger.info(f"Reclamo creado automáticamente para la OC {orden_id}.")
        except Exception as e_reclamo:
            logger.error(f"Error al crear el reclamo automático para la OC {orden_id}: {e_reclamo}")

    def _crear_lotes_para_items_recibidos(self, items_para_lote, orden_data, usuario_id):
        """
        Helper para crear lotes de inventario para los items recibidos.
        """
        lotes_creados_count = 0
        lotes_error_count = 0
        for item_lote in items_para_lote:
            item_data = item_lote['data']
            codigo_oc = orden_data.get('codigo_oc', 'N/A')
            if not codigo_oc.startswith('OC-'):
                codigo_oc = f"OC-{codigo_oc}"

            lote_data = {
                'id_insumo': item_data['insumo_id'],
                'id_proveedor': orden_data.get('proveedor_id'),
                'cantidad_inicial': item_lote['cantidad_recibida'],
                'precio_unitario': item_data.get('precio_unitario'),
                'documento_ingreso': codigo_oc,
                'f_ingreso': date.today().isoformat(),
                'estado': 'EN REVISION'
            }
            try:
                lote_result, status_code = self.inventario_controller.crear_lote(lote_data, usuario_id)
                if lote_result.get('success'):
                    lotes_creados_count += 1
                else:
                    logger.error(f"Fallo al crear el lote para el insumo {lote_data.get('id_insumo')}: {lote_result.get('error')}")
                    lotes_error_count += 1
            except ValidationError as e:
                 logger.error(f"Error de validación creando lote para insumo {lote_data.get('id_insumo')}: {e.messages}")
                 lotes_error_count += 1
            except Exception as e_lote:
                logger.error(f"Excepción creando lote para el insumo {lote_data.get('id_insumo')}: {e_lote}", exc_info=True)
                lotes_error_count += 1
        return lotes_creados_count, lotes_error_count

    def procesar_recepcion(self, orden_id, form_data, usuario_id, orden_produccion_controller: "OrdenProduccionController"):
        try:
            # Verificar que la orden de compra esté en estado 'EN_RECEPCION'
            orden_actual_res, status = self.get_orden(orden_id)
            if not orden_actual_res.get('success'):
                return {'success': False, 'error': 'Orden de compra no encontrada.'}

            orden_actual = orden_actual_res.get('data')
            if not orden_actual or orden_actual.get('estado') != 'EN_RECEPCION':
                estado = orden_actual.get('estado') if orden_actual else 'desconocido'
                return {'success': False, 'error': f"La recepción solo se puede procesar si la orden está en estado 'EN RECEPCION'. Estado actual: {estado}"}
                
            accion = form_data.get('accion')
            observaciones = form_data.get('observaciones', '')

            if accion == 'aceptar':
                # Reutilizamos la variable `orden_actual` que ya contiene los datos de la orden
                orden_data = orden_actual
                
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

                # Si se crearon lotes, verificamos si alguna OP 'EN ESPERA' puede pasar a 'LISTA'.
                if lotes_creados > 0:
                    try:
                        logger.info("Recepción de OC completada, iniciando verificación proactiva de Órdenes de Producción en espera.")
                        orden_produccion_controller.verificar_y_actualizar_ordenes_en_espera()
                    except Exception as e_op:
                        logger.error(f"Error al ejecutar la verificación proactiva de OPs tras recibir la OC {orden_id}: {e_op}", exc_info=True)

                # Ya no se cambia el estado de la OC aquí. Simplemente se crean los lotes.
                final_message = f'Recepción registrada. {lotes_creados} lotes creados y enviados a Control de Calidad.'
                if lotes_error > 0:
                    final_message += f' ({lotes_error} con error).'
                
                if items_faltantes:
                    # Si faltan items, se crea la OC hija, el reclamo, y la OC original se marca como incompleta.
                    nueva_orden_result = self._crear_orden_complementaria(orden_data, items_faltantes, usuario_id)
                    if not nueva_orden_result.get('success'):
                        return {'success': False, 'error': f"Lotes creados, pero falló la creación de la orden complementaria: {nueva_orden_result.get('error')}"}

                    self._crear_reclamo_automatico(orden_id, orden_data, items_faltantes)
                    
                    self.model.update(orden_id, {'estado': 'RECEPCION_INCOMPLETA'})
                    
                    final_message += f' Se generó la OC {nueva_orden_result["data"]["codigo_oc"]} para los items faltantes y la orden actual se marcó como Recepción Incompleta.'
                else:
                    # Si no hay items faltantes, la orden pasa a Control de Calidad
                    self.model.update(orden_id, {'estado': 'EN_CONTROL_CALIDAD'})

                return {'success': True, 'message': final_message}
                    # --- FIN DE LA CORRECCIÓN ---

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

    def _verificar_y_actualizar_op_si_corresponde(self, orden_produccion_id: int, usuario_id: int):
        """
        Verifica si todas las OCs asociadas a una OP están cerradas.
        Si es así, intenta actualizar el estado de la OP a 'LISTA PARA PRODUCIR'.
        """
        from app.controllers.orden_produccion_controller import OrdenProduccionController

        if not orden_produccion_id:
            return

        logger.info(f"Verificando estado de OCs para la OP ID: {orden_produccion_id}.")

        # 1. Obtener todas las OCs vinculadas a la OP
        ocs_asociadas_res = self.model.get_all(filters={'orden_produccion_id': orden_produccion_id})

        if not ocs_asociadas_res.get('success'):
            logger.error(f"No se pudieron obtener las OCs para la OP {orden_produccion_id}. No se tomarán acciones.")
            return

        ocs_asociadas = ocs_asociadas_res.get('data', [])
        if not ocs_asociadas:
            logger.warning(f"No se encontraron OCs asociadas a la OP {orden_produccion_id}.")
            return

        # 2. Verificar si TODAS están cerradas
        todas_cerradas = all(oc.get('estado') == 'CERRADA' for oc in ocs_asociadas)

        if not todas_cerradas:
            logger.info(f"Aún no todas las OCs para la OP {orden_produccion_id} están cerradas. No se tomarán acciones.")
            return

        # 3. Si todas están cerradas, proceder a actualizar la OP
        logger.info(f"Todas las OCs para la OP {orden_produccion_id} están cerradas. Intentando actualizar estado de la OP.")
        
        op_controller = OrdenProduccionController()
        op_result = op_controller.obtener_orden_por_id(orden_produccion_id)
        if not op_result.get('success'):
            logger.error(f"No se pudo encontrar la OP {orden_produccion_id} para actualizarla.")
            return

        orden_produccion = op_result['data']
        if orden_produccion.get('estado') == 'EN ESPERA':
            logger.info(f"OP {orden_produccion_id} está EN ESPERA. Intentando reservar insumos.")
            reserva_result = self.inventario_controller.reservar_stock_insumos_para_op(orden_produccion, usuario_id)

            if not reserva_result.get('success'):
                logger.error(f"Reserva automática para OP {orden_produccion_id} falló. Error: {reserva_result.get('error')}")
            else:
                nuevo_estado_op = 'LISTA PARA PRODUCIR'
                op_update_result = op_controller.cambiar_estado_orden_simple(orden_produccion_id, nuevo_estado_op)

                if not op_update_result.get('success'):
                    logger.error(f"Falló al actualizar la OP {orden_produccion_id} a {nuevo_estado_op}. Error: {op_update_result.get('error', 'Error desconocido.')}")
                else:
                    logger.info(f"OP {orden_produccion_id} ha sido actualizada a '{nuevo_estado_op}'.")
        else:
            logger.info(f"La OP {orden_produccion_id} ya no estaba en 'EN ESPERA' (estado actual: '{orden_produccion.get('estado')}'). No se realizaron cambios.")

    def marcar_como_cerrada(self, orden_id: int, usuario_id: int) -> Dict:
        """
        Marca una orden de compra como 'CERRADA' después de que el control de calidad ha finalizado.
        Si es la última OC de una OP, actualiza el estado de la OP.
        """
        try:
            # Verificar que la orden exista y esté en el estado correcto
            orden_actual_res = self.model.find_by_id(orden_id)
            if not orden_actual_res.get('success'):
                return {'success': False, 'error': 'Orden no encontrada.'}
            
            orden_actual = orden_actual_res['data']
            if orden_actual.get('estado') != 'EN_CONTROL_CALIDAD':
                logger.warning(f"Intento de cerrar la orden {orden_id} que no está en 'EN_CONTROL_CALIDAD'. Estado actual: {orden_actual.get('estado')}")
                return {'success': True, 'message': 'La orden no requiere ser cerrada en este momento.'}

            update_data = {
                'estado': 'CERRADA',
                'updated_at': datetime.now().isoformat()
            }
            result = self.model.update(orden_id, update_data)

            if result.get('success'):
                logger.info(f"Orden de compra {orden_id} marcada como CERRADA.")

                orden_produccion_id = orden_actual.get('orden_produccion_id')
                codigo_oc = orden_actual.get('codigo_oc')

                if orden_produccion_id and codigo_oc:
                    logger.info(f"OC {orden_id} está vinculada a la OP {orden_produccion_id}. Procediendo a reservar lotes de esta OC.")
                    documento_ingreso_con_prefijo = f"OC-{codigo_oc}" if not codigo_oc.startswith('OC-') else codigo_oc
                    documento_ingreso_sin_prefijo = codigo_oc.replace('OC-', '')

                    lotes_a_reservar_res = self.inventario_controller.inventario_model.find_all(
                        filters={'documento_ingreso': ('in', [documento_ingreso_con_prefijo, documento_ingreso_sin_prefijo])}
                    )

                    if lotes_a_reservar_res.get('success'):
                        lotes_encontrados = lotes_a_reservar_res.get('data', [])
                        logger.info(f"Se encontraron {len(lotes_encontrados)} lotes para reservar para la OP {orden_produccion_id}.")
                        for lote in lotes_encontrados:
                            self.inventario_controller.inventario_model.update(lote['id_lote'], {'estado': 'reservado', 'orden_produccion_id': orden_produccion_id}, 'id_lote')
                            logger.info(f"Lote {lote['id_lote']} reservado para la OP {orden_produccion_id}.")
                    else:
                        logger.error(f"Error al buscar lotes para la OC {codigo_oc}: {lotes_a_reservar_res.get('error')}")

                if orden_produccion_id:
                    self._verificar_y_actualizar_op_si_corresponde(orden_produccion_id, usuario_id)

                self._reiniciar_bandera_stock_recibido(orden_id)

                oc = result.get('data')
                detalle = f"La orden de compra {oc.get('codigo_oc')} se marcó como CERRADA."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Cambio de Estado', detalle)
                
                try:
                    from app.controllers.orden_produccion_controller import OrdenProduccionController
                    orden_produccion_controller = OrdenProduccionController()
                    orden_produccion_controller.verificar_y_actualizar_ordenes_en_espera()
                except Exception as e_op:
                    logger.error(f"Error al ejecutar la verificación proactiva de OPs tras cerrar la OC {orden_id}: {e_op}", exc_info=True)

            return result

        except Exception as e:
            logger.error(f"Error marcando la orden {orden_id} como CERRADA: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}