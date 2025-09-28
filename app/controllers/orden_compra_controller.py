from flask import request, jsonify
from app.models.orden_compra_model import OrdenCompraModel, safe_serialize_simple
from datetime import datetime, date

class OrdenCompraController:
    def __init__(self):
        self.model = OrdenCompraModel()

    def create_orden(self):
        try:
            data = request.get_json()

            # Validación de campos requeridos según la tabla real
            campos_requeridos = ['proveedor_id', 'usuario_creador_id']
            for campo in campos_requeridos:
                if campo not in data:
                    return jsonify({
                        'success': False,
                        'error': f'Campo requerido faltante: {campo}'
                    }), 400

            # Generar código OC único (similar al número_orden anterior)
            data['codigo_oc'] = f"OC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            data['fecha_emision'] = date.today()
            data['estado'] = data.get('estado', 'PENDIENTE')
            data['prioridad'] = data.get('prioridad', 'NORMAL')

            # Calcular total si se proporciona subtotal e iva
            if 'subtotal' in data:
                subtotal = float(data['subtotal'])
                iva = float(data.get('iva', 0))
                data['total'] = subtotal + iva

            result = self.model.create(data)
            if result['success']:
                return jsonify({
                    'success': True,
                    'data': result['data'],
                    'message': 'Orden de compra creada exitosamente'
                }), 201
            else:
                return jsonify({'success': False, 'error': result['error']}), 400

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    def get_orden(self, orden_id):
        try:
            result = self.model.find_by_id(orden_id)
            if result['success']:
                return jsonify({
                    'success': True,
                    'data': result['data']
                })
            else:
                return jsonify({'success': False, 'error': result['error']}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

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
            # Si filtros no incluye ciertos campos, tomar de request.args
            if 'estado' not in filters and request.args.get('estado'):
                filters['estado'] = request.args.get('estado')
            if 'proveedor_id' not in filters and request.args.get('proveedor_id'):
                filters['proveedor_id'] = int(request.args.get('proveedor_id'))
            if 'prioridad' not in filters and request.args.get('prioridad'):
                filters['prioridad'] = request.args.get('prioridad')

            result = self.model.get_all(filters)
            if result['success']:
                return {'success': True, 'data': result['data'], 'count': len(result['data']) if result['data'] else 0}, 200
            else:
                return {'success': False, 'error': result['error']}, 400
        except Exception as e:
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
