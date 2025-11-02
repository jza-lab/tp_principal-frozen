# app/views/op_tabla_routes.py
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.planificacion_controller import PlanificacionController
from app.utils.decorators import permission_required

op_tabla_bp = Blueprint("op_tabla", __name__, url_prefix="/tabla-produccion")

@op_tabla_bp.route('/')
@permission_required(accion='consultar_plan_de_produccion')
def tablero_produccion():
    """
    Muestra el tablero Kanban para operarios con las órdenes de producción
    planificadas para el día de hoy.
    """
    controller = PlanificacionController()
    
    # Obtener OPs planificadas para hoy
    response, _ = controller.obtener_ops_para_hoy()
    
    if not response.get('success'):
        flash(response.get('error', 'Error al cargar las órdenes de producción de hoy.'), 'error')
        ordenes_por_estado = {}
    else:
        ordenes_por_estado = response.get('data', {})

    # Definir las columnas que la plantilla espera
    columnas = {
        'LISTA PARA PRODUCIR': 'Lista para Producir',
        'EN PROCESO': 'En Proceso',
        'PAUSADA': 'Pausada',
        'CONTROL DE CALIDAD': 'Control de Calidad'
    }

    return render_template(
        'planificacion/produccion_hoy.html',
        ordenes_por_estado=ordenes_por_estado,
        columnas=columnas
    )

@op_tabla_bp.route('/foco/<int:op_id>')
@permission_required(accion='produccion_ejecucion')
def foco_produccion(op_id):
    """
    Muestra la vista de foco para una orden de producción activa.
    """
    orden_controller = OrdenProduccionController()
    response, status_code = orden_controller.obtener_datos_para_vista_foco(op_id)

    if status_code == 200:
        return render_template('planificacion/foco_produccion.html', **response['data'])
    else:
        flash(response.get('error', 'Error desconocido al cargar la orden.'), 'danger')
        return redirect(url_for('op_tabla.tablero_produccion'))

@op_tabla_bp.route('/api/mover-op/<int:op_id>', methods=['POST'])
@permission_required(accion='produccion_ejecucion') # Permiso más general
def mover_op_api(op_id):
    """
    API endpoint para cambiar el estado de una OP.
    Usado tanto por el drag-and-drop como por la asignación post-recomendación.
    """
    current_user = get_jwt()
    user_role = current_user.get('roles', {}).get('codigo')

    data = request.get_json()
    nuevo_estado = data.get('nuevo_estado')

    controller = PlanificacionController()
    response, status_code = controller.mover_orden(op_id, nuevo_estado, user_role)
    return jsonify(response), status_code

@op_tabla_bp.route('/api/op/<int:op_id>/reportar', methods=['POST'])
@jwt_required()
@permission_required(accion='produccion_ejecucion')
def api_reportar_avance(op_id):
    data = request.get_json()
    usuario_id = get_jwt_identity()
    controller = OrdenProduccionController()
    response, status_code = controller.reportar_avance(op_id, data, usuario_id)
    return jsonify(response), status_code

@op_tabla_bp.route('/api/op/<int:op_id>/pausar', methods=['POST'])
@jwt_required()
@permission_required(accion='produccion_ejecucion')
def api_pausar_produccion(op_id):
    data = request.get_json()
    motivo_id = data.get('motivo_id')
    if not motivo_id:
        return jsonify({'success': False, 'error': 'El motivo de la pausa es requerido.'}), 400
    
    usuario_id = get_jwt_identity()
    controller = OrdenProduccionController()
    response, status_code = controller.pausar_produccion(op_id, int(motivo_id), usuario_id)
    return jsonify(response), status_code

@op_tabla_bp.route('/api/op/<int:op_id>/reanudar', methods=['POST'])
@jwt_required()
@permission_required(accion='produccion_ejecucion')
def api_reanudar_produccion(op_id):
    usuario_id = get_jwt_identity()
    controller = OrdenProduccionController()
    response, status_code = controller.reanudar_produccion(op_id, usuario_id)
    return jsonify(response), status_code
