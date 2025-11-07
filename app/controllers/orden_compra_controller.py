from typing import Dict, TYPE_CHECKING
from flask import request, jsonify
from flask_jwt_extended import get_jwt, get_current_user
from marshmallow import ValidationError
from app.controllers.registro_controller import RegistroController
from app.models.orden_compra_model import OrdenCompraItemModel, OrdenCompraModel
from app.models.orden_compra_model import OrdenCompra
from app.controllers.inventario_controller import InventarioController
from app.controllers.usuario_controller import UsuarioController
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


    def _marcar_cadena_como_en_control_calidad(self, orden_id):
        """
        Marca una orden y todas sus predecesoras como 'EN_CONTROL_CALIDAD'.
        La lógica de reinicio de la bandera de stock se ha movido a `_reiniciar_bandera_stock_recibido`.
        """
        try:
            current_id = orden_id
            while current_id:
                orden_res = self.model.get_one_with_details(current_id)
                if not orden_res.get('success'):
                    logger.warning(f"No se encontró la orden con ID {current_id} en la cadena de completado.")
                    break

                orden_actual = orden_res['data']

                # Actualizar el estado de la orden actual a 'EN_CONTROL_CALIDAD'
                self.model.update(current_id, {
                    'estado': 'EN_CONTROL_CALIDAD',
                    'fecha_real_entrega': date.today().isoformat()
                })

                logger.info(f"Orden {current_id} marcada como EN_CONTROL_CALIDAD.")

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
                    # --- INICIO DE LA CORRECCIÓN (Versión Robusta) ---
                    # 1. Crear un mapa con las cantidades recibidas directamente del formulario.
                    #    Esto evita condiciones de carrera al no depender de una re-lectura de la BD.
                    cantidades_recibidas_map = {int(item_ids[i]): float(cantidades_recibidas_str[i] or 0) for i in range(len(item_ids))}

                    # 2. Recalcular los totales de la orden padre usando el mapa de cantidades del formulario.
                    subtotal_padre = 0
                    for item in orden_data.get('items', []):
                        item_id = item.get('id')
                        # Se usa la cantidad del formulario, no se vuelve a leer de la BD
                        cantidad_recibida = cantidades_recibidas_map.get(item_id, 0.0) 
                        precio = float(item.get('precio_unitario', 0))
                        subtotal_padre += cantidad_recibida * precio
                    
                    iva_padre = subtotal_padre * 0.21 if orden_data.get('iva', 0) > 0 else 0
                    total_padre = subtotal_padre + iva_padre
                    
                    # 3. Crear la orden complementaria (esto ya funcionaba bien).
                    nueva_orden_result = self._crear_orden_complementaria(orden_data, items_faltantes, usuario_id)
                    if not nueva_orden_result.get('success'):
                        return {'success': False, 'error': f"Recepción parcial procesada, pero falló la creación de la orden complementaria: {nueva_orden_result.get('error')}"}

                    # 4. Actualizar la orden padre con el nuevo estado, observaciones Y los totales recalculados.
                    self.model.update(orden_id, {
                        'estado': 'RECEPCION_INCOMPLETA',
                        'observaciones': f"{observaciones}\nRecepción parcial. Pendiente completado en OC: {nueva_orden_result['data']['codigo_oc']}",
                        'subtotal': round(subtotal_padre, 2),
                        'iva': round(iva_padre, 2),
                        'total': round(total_padre, 2)
                    })
                    detalle = f"Se procesó una recepción parcial para la OC {orden_data.get('codigo_oc')}. Se generó la OC complementaria {nueva_orden_result['data']['codigo_oc']}."
                    self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Cambio de Estado', detalle)
                    # --- FIN DE LA CORRECCIÓN ---

                    return {'success': True, 'message': f'Recepción parcial registrada. Se creó la orden {nueva_orden_result["data"]["codigo_oc"]} para los insumos restantes.'}
                else:
                    # --- INICIO DE LA CORRECCIÓN ---
                    # 1. Establecer el estado correcto (RECEPCION COMPLETA)
                    # (OC_RECEPCION_COMPLETA se define en estados.py)
                    update_data = {
                        'estado': 'RECEPCION_COMPLETA',
                        'fecha_real_entrega': date.today().isoformat(),
                        'observaciones': f"{observaciones}\nRecepción completada. Pendiente de Control de Calidad."
                    }
                    result = self.model.update(orden_id, update_data)
                    if result.get('success'):
                        oc = result.get('data')
                        detalle = f"Se procesó la recepción completa de la OC {oc.get('codigo_oc')}."
                        self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Cambio de Estado', detalle)

                    # 2. Mensaje de éxito (ya NO se mueve a calidad)
                    final_message = f'Recepción completada. {lotes_creados} lotes creados.'
                    if lotes_error > 0: final_message += f' ({lotes_error} con error).'

                    # 3. Manejar OP asociada (esto se mantiene)
                    op_transition_message = self._manejar_transicion_op_asociada(orden_data, usuario_id, orden_produccion_controller)
                    if op_transition_message:
                        final_message += f" | {op_transition_message}"

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

    def marcar_como_cerrada(self, orden_id: int) -> Dict:
        """
        Marca una orden de compra como 'CERRADA' después de que el control de calidad ha finalizado.
        """
        try:
            # Verificar que la orden exista y esté en el estado correcto
            orden_actual_res = self.model.find_by_id(orden_id)
            if not orden_actual_res.get('success'):
                return {'success': False, 'error': 'Orden no encontrada.'}
            
            orden_actual = orden_actual_res['data']
            if orden_actual.get('estado') != 'EN_CONTROL_CALIDAD':
                logger.warning(f"Intento de cerrar la orden {orden_id} que no está en 'EN_CONTROL_CALIDAD'. Estado actual: {orden_actual.get('estado')}")
                # Podríamos devolver un error o simplemente no hacer nada. Por ahora, no hacemos nada.
                return {'success': True, 'message': 'La orden no requiere ser cerrada en este momento.'}

            update_data = {
                'estado': 'CERRADA',
                'updated_at': datetime.now().isoformat()
            }
            result = self.model.update(orden_id, update_data)

            if result.get('success'):
                logger.info(f"Orden de compra {orden_id} marcada como CERRADA.")

                # --- INICIO DE LA NUEVA LÓGICA DE RESERVA DE LOTES ---
                orden_produccion_id = orden_actual.get('orden_produccion_id')
                codigo_oc = orden_actual.get('codigo_oc')

                if orden_produccion_id and codigo_oc:
                    logger.info(f"OC {orden_id} está vinculada a la OP {orden_produccion_id}. Procediendo a reservar lotes.")
                    # El documento de ingreso puede tener o no el prefijo 'OC-'
                    documento_ingreso_con_prefijo = f"OC-{codigo_oc}" if not codigo_oc.startswith('OC-') else codigo_oc
                    documento_ingreso_sin_prefijo = codigo_oc.replace('OC-', '')

                    # Buscamos lotes que coincidan con cualquiera de los dos formatos del código de OC
                    lotes_a_reservar_res = self.inventario_controller.inventario_model.find_all(
                        filters={'documento_ingreso': ('in', [documento_ingreso_con_prefijo, documento_ingreso_sin_prefijo])}
                    )

                    if lotes_a_reservar_res.get('success'):
                        lotes_encontrados = lotes_a_reservar_res.get('data', [])
                        logger.info(f"Se encontraron {len(lotes_encontrados)} lotes para reservar para la OP {orden_produccion_id}.")
                        for lote in lotes_encontrados:
                            update_data_lote = {
                                'estado': 'reservado',
                                'orden_produccion_id': orden_produccion_id
                            }
                            # Actualizamos cada lote individualmente
                            self.inventario_controller.inventario_model.update(lote['id_lote'], update_data_lote, 'id_lote')
                            logger.info(f"Lote {lote['id_lote']} reservado para la OP {orden_produccion_id}.")
                    else:
                        logger.error(f"Error al buscar lotes para la OC {codigo_oc}: {lotes_a_reservar_res.get('error')}")
                # --- FIN DE LA NUEVA LÓGICA ---

                # >>> PASO CRÍTICO CORREGIDO <<<
                # Al cerrar la orden, después de que Control de Calidad ha finalizado,
                # se reinicia la bandera para permitir nuevas OC automáticas.
                self._reiniciar_bandera_stock_recibido(orden_id)

            if result.get('success'):
                oc = result.get('data')
                detalle = f"La orden de compra {oc.get('codigo_oc')} se marcó como CERRADA."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Cambio de Estado', detalle)
            
            return result

        except Exception as e:
            logger.error(f"Error marcando la orden {orden_id} como CERRADA: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
        
    def iniciar_control_de_calidad(self, orden_id, usuario_id):
            """
            Pasa una orden de 'RECEPCION_COMPLETA'
            a 'EN_CONTROL_CALIDAD'.
            Este método es llamado por la ruta POST /<id>/iniciar-calidad
        
            """
            try:
                # 1. Validar el estado actual de la orden
                orden_res, _ = self.get_orden(orden_id)
                if not orden_res.get('success'):
                    return orden_res
                
                orden_actual = orden_res['data']
                estado_actual = orden_actual.get('estado')

                # Estados desde los que Calidad puede tomar la orden
                # (Definidos en estados.py)
                estados_permitidos = ['RECEPCION_COMPLETA']
                
                if estado_actual not in estados_permitidos:
                    return {'success': False, 'error': f"Solo se puede iniciar Control de Calidad en órdenes recibidas. Estado actual: {estado_actual}."}

                # 2. Usar la función existente para actualizar el estado
                # Esta función ya actualiza el estado a 'EN_CONTROL_CALIDAD'
                #
                self._marcar_cadena_como_en_control_calidad(orden_id)
                
                detalle = f"La OC {orden_actual.get('codigo_oc')} pasó a EN CONTROL DE CALIDAD."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de compra', 'Cambio de Estado', detalle)

                logger.info(f"Usuario {usuario_id} movió la OC {orden_id} a EN_CONTROL_CALIDAD.")
                
                return {'success': True, 'message': 'La orden ha sido movida a Control de Calidad.'}
                
            except Exception as e:
                logger.error(f"Error al iniciar control de calidad para OC {orden_id}: {e}", exc_info=True)
                return {'success': False, 'error': str(e)}