import logging
from flask import Blueprint, render_template, flash, request, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from app.controllers.planificacion_controller import PlanificacionController
from app.controllers.usuario_controller import UsuarioController
from datetime import date, timedelta
from app.utils.decorators import permission_required
from app import csrf

planificacion_bp = Blueprint('planificacion', __name__, url_prefix='/planificacion')
logger = logging.getLogger(__name__)
csrf.exempt(planificacion_bp)

@planificacion_bp.route('/')
@jwt_required()
@permission_required(accion='consultar_plan_de_produccion')
def index():
    """
    Muestra la vista principal de planificación, que incluye el Plan Maestro de Producción (MPS)
    y el Calendario Semanal de capacidad (CRP).
    """
    controller = PlanificacionController()
    usuario_controller = UsuarioController()
    
    # 1. Obtener parámetros de la solicitud
    week_str = request.args.get('semana')
    horizonte_dias = request.args.get('horizonte', default=7, type=int)

    # 2. Obtener datos para el Plan Maestro (MPS)
    ctx_mps = {}
    response_mps, _ = controller.obtener_ops_pendientes_planificacion(horizonte_dias)
    if response_mps.get('success'):
        ctx_mps = response_mps.get('data', {})
    else:
        flash(response_mps.get('error', 'Error cargando el Plan Maestro de Producción.'), 'danger')

    # 3. Obtener datos para el Calendario Semanal (CRP)
    ctx_semanal = {}
    response_semanal, _ = controller.obtener_planificacion_semanal(week_str)
    if response_semanal.get('success'):
        ctx_semanal = response_semanal.get('data', {})
    else:
        flash(response_semanal.get('error', 'Error cargando la planificación semanal.'), 'danger')

    # 4. Obtener datos para los formularios (Supervisores y Operarios)
    supervisores_resp, _ = usuario_controller.obtener_usuarios_por_rol(['SUPERVISOR'])
    operarios_resp, _ = usuario_controller.obtener_usuarios_por_rol(['OPERARIO'])
    
    # 5. Navegación de semana para el calendario
    try:
        current_year, week_num_int = map(int, (ctx_semanal.get('semana_actual_str') or '2023-W01').split('-W'))
        current_week_start = date.fromisocalendar(current_year, week_num_int, 1)
        prev_week_start = current_week_start - timedelta(days=7)
        next_week_start = current_week_start + timedelta(days=7)
        prev_week_str = prev_week_start.strftime("%Y-W%V")
        next_week_str = next_week_start.strftime("%Y-W%V")
    except (ValueError, TypeError):
        prev_week_str, next_week_str = None, None
        logger.warning(f"Error al parsear week_str para la navegación: {week_str}")

    # 6. Renderizar la plantilla con todo el contexto
    return render_template(
        'planificacion/tablero.html',
        mps_agrupado=ctx_mps.get('mps_agrupado', []),
        inicio_horizonte=ctx_mps.get('inicio_horizonte'),
        fin_horizonte=ctx_mps.get('fin_horizonte'),
        ops_visibles_por_dia=ctx_semanal.get('ops_visibles_por_dia', {}),
        inicio_semana=ctx_semanal.get('inicio_semana'),
        fin_semana=ctx_semanal.get('fin_semana'),
        semana_actual_str=ctx_semanal.get('semana_actual_str'),
        supervisores=supervisores_resp.get('data', []),
        operarios=operarios_resp.get('data', []),
        prev_week_str=prev_week_str,
        next_week_str=next_week_str
    )

# --- Rutas de API para Planificación ---

@planificacion_bp.route('/api/consolidar', methods=['POST'])
@jwt_required()
@permission_required(accion='aprobar_plan_de_produccion')
def consolidar_api():
    data = request.get_json()
    op_ids = data.get('op_ids', [])
    usuario_id = get_jwt_identity()
    controller = PlanificacionController()
    response, status_code = controller.consolidar_ops(op_ids, usuario_id)
    return jsonify(response), status_code

@planificacion_bp.route('/api/consolidar-y-aprobar', methods=['POST'])
@jwt_required()
@permission_required(accion='aprobar_plan_de_produccion')
def consolidar_y_aprobar_api():
    data = request.get_json()
    usuario_id = get_jwt_identity()
    controller = PlanificacionController()
    response, status_code = controller.consolidar_y_aprobar_lote(
        op_ids=data.get('op_ids', []),
        asignaciones=data.get('asignaciones', {}),
        usuario_id=usuario_id
    )
    return jsonify(response), status_code

@planificacion_bp.route('/api/confirmar-aprobacion', methods=['POST'])
@jwt_required()
@permission_required(accion='aprobar_plan_de_produccion')
def confirmar_aprobacion_api():
    data = request.get_json()
    usuario_id = get_jwt_identity()
    op_id = data.get('op_id')
    asignaciones = data.get('asignaciones')
    if not op_id or not asignaciones:
        return jsonify({'success': False, 'error': 'Faltan datos (op_id o asignaciones).'}), 400
    controller = PlanificacionController()
    response, status_code = controller.confirmar_aprobacion_lote(op_id, asignaciones, usuario_id)
    return jsonify(response), status_code

@planificacion_bp.route('/forzar_auto_planificacion', methods=['POST'])
@jwt_required()
@permission_required(accion='ejecutar_planificacion_automatica')
def forzar_planificacion():
    usuario_id = get_jwt_identity()
    controller = PlanificacionController()
    response, status_code = controller.forzar_auto_planificacion(usuario_id)
    return jsonify(response), status_code
