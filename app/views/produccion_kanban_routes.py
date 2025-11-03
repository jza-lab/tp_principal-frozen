# app/views/produccion_kanban_routes.py
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.produccion_kanban_controller import ProduccionKanbanController # <-- Cambiado
from app.utils.decorators import permission_required

# Renombrado para mayor claridad
produccion_kanban_bp = Blueprint("produccion_kanban", __name__, url_prefix="/produccion/kanban")

@produccion_kanban_bp.route('/')
@jwt_required()
@permission_required(accion='consultar_kanban_produccion') # Permiso más específico
def tablero_produccion():
    """
    Muestra el tablero Kanban de Producción. La lógica de presentación
    y obtención de datos está centralizada en el controlador.
    """
    jwt_data = get_jwt()
    usuario_rol = jwt_data.get('rol', '')
    usuario_id = get_jwt_identity()
    
    # Usar el nuevo controlador dedicado
    controller = ProduccionKanbanController()
    
    # El controlador ahora prepara todos los datos necesarios para la vista
    response, _ = controller.obtener_datos_para_tablero(
        usuario_id=usuario_id, 
        usuario_rol=usuario_rol
    )
    
    if not response.get('success'):
        flash(response.get('error', 'Error al cargar los datos del tablero.'), 'danger')
        contexto = {
            'ordenes_por_estado': {},
            'columnas': {},
            'usuario_rol': usuario_rol
        }
    else:
        contexto = response.get('data', {})

    return render_template('planificacion/kanban.html', **contexto) # Plantilla renombrada

@produccion_kanban_bp.route('/foco/<int:op_id>')
@jwt_required()
@permission_required(accion='produccion_ejecucion')
def foco_produccion(op_id):
    """
    Muestra la vista de foco para una OP. Si la OP está 'LISTA PARA PRODUCIR',
    intenta iniciar el trabajo. Si ya está 'EN PROCESO', simplemente muestra el foco.
    """
    usuario_id = get_jwt_identity()
    orden_controller = OrdenProduccionController()

    # 1. Obtener la orden primero para saber su estado
    orden_result = orden_controller.obtener_orden_por_id(op_id)
    if not orden_result.get('success'):
        flash('Orden de producción no encontrada.', 'danger')
        return redirect(url_for('produccion_kanban.tablero_produccion'))
    
    orden_actual = orden_result.get('data', {})
    estado_actual = orden_actual.get('estado')

    # 2. Solo intentar iniciar el trabajo si está en el estado correcto
    # Se aceptan ambos formatos por posible inconsistencia en la BD
    if estado_actual in ['LISTA PARA PRODUCIR', 'LISTA_PARA_PRODUCIR']:
        response_inicio, status_inicio = orden_controller.iniciar_trabajo_op(op_id, usuario_id)
        if status_inicio >= 400:
            flash(response_inicio.get('error', 'No se pudo iniciar el trabajo.'), 'danger')
            return redirect(url_for('produccion_kanban.tablero_produccion'))

    # 3. Cargar los datos para la vista de foco (se ejecuta siempre, después del posible inicio)
    response_vista, status_vista = orden_controller.obtener_datos_para_vista_foco(op_id)
    if status_vista >= 400:
        flash(response_vista.get('error', 'Error al cargar datos de la orden.'), 'danger')
        return redirect(url_for('produccion_kanban.tablero_produccion'))
        
    return render_template('planificacion/foco_produccion.html', **response_vista.get('data', {}))

@produccion_kanban_bp.route('/api/mover-op/<int:op_id>', methods=['POST'])
@jwt_required()
@permission_required(accion='modificar_kanban_produccion') # Permiso más específico
def mover_op_api(op_id):
    """
    API endpoint para cambiar el estado de una OP en el Kanban.
    """
    jwt_data = get_jwt()
    user_role = jwt_data.get('rol', '')
    data = request.get_json()
    nuevo_estado = data.get('nuevo_estado')

    # Usar el nuevo controlador dedicado
    controller = ProduccionKanbanController()
    response, status_code = controller.mover_orden(op_id, nuevo_estado, user_role)
    return jsonify(response), status_code

# --- Las siguientes rutas son de "ejecución" y podrían moverse a su propio blueprint en el futuro ---

@produccion_kanban_bp.route('/api/op/<int:op_id>/reportar', methods=['POST'])
@jwt_required()
@permission_required(accion='produccion_ejecucion')
def api_reportar_avance(op_id):
    data = request.get_json()
    usuario_id = get_jwt_identity()
    controller = OrdenProduccionController()
    response, status_code = controller.reportar_avance(op_id, data, usuario_id)
    return jsonify(response), status_code

@produccion_kanban_bp.route('/api/op/<int:op_id>/pausar', methods=['POST'])
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

@produccion_kanban_bp.route('/api/op/<int:op_id>/reanudar', methods=['POST'])
@jwt_required()
@permission_required(accion='produccion_ejecucion')
def api_reanudar_produccion(op_id):
    usuario_id = get_jwt_identity()
    controller = OrdenProduccionController()
    response, status_code = controller.reanudar_produccion(op_id, usuario_id)
    return jsonify(response), status_code

@produccion_kanban_bp.route('/api/op/<int:op_id>/estado', methods=['GET'])
@jwt_required()
@permission_required(accion='produccion_ejecucion')
def api_get_estado_produccion(op_id):
    """
    API endpoint para obtener el estado actual de producción de una OP.
    Devuelve el tiempo trabajado, la cantidad producida y si está en pausa.
    """
    controller = ProduccionKanbanController()
    response, status_code = controller.obtener_estado_produccion(op_id)
    return jsonify(response), status_code

@produccion_kanban_bp.route('/api/op/<int:op_id>/aprobar-calidad', methods=['POST'])
@jwt_required()
@permission_required(accion='aprobar_control_calidad')
def api_aprobar_calidad(op_id):
    """
    API endpoint para que un supervisor de calidad apruebe una orden y la mueva a 'COMPLETADA'.
    """
    # En una implementación futura, se podría pasar un usuario_id si es relevante.
    # usuario_id = get_jwt_identity()
    controller = OrdenProduccionController()
    # Usamos el método robusto que ya maneja la creación de lotes.
    response, status_code = controller.cambiar_estado_orden(op_id, 'COMPLETADA')
    return jsonify(response), status_code
