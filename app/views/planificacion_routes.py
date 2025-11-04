import logging
from flask import Blueprint, render_template, flash, url_for, request, jsonify, session, redirect 
from flask_jwt_extended import get_jwt_identity, jwt_required, get_jwt
from app.controllers.planificacion_controller import PlanificacionController
from app.controllers.usuario_controller import UsuarioController
from datetime import date, timedelta, datetime
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
    Muestra la vista principal de planificación, incluyendo MPS y CRP.
    """
    controller = PlanificacionController()
    usuario_controller = UsuarioController()
    
    # Obtener rol del usuario
    jwt_data = get_jwt()
    user_role = jwt_data.get('rol', '')
    is_operario = user_role == 'OPERARIO'
    is_supervisor_calidad = user_role == 'SUPERVISOR_CALIDAD'

    week_str = request.args.get('semana')
    horizonte_dias = request.args.get('horizonte', default=7, type=int)

    # Datos para el Plan Maestro (MPS)
    ctx_mps = {}
    response_mps, _ = controller.obtener_ops_pendientes_planificacion(horizonte_dias)
    if response_mps.get('success'):
        ctx_mps = response_mps.get('data', {})
    else:
        flash(response_mps.get('error', 'Error cargando el Plan Maestro.'), 'danger')

    # Datos para el Calendario Semanal
    ctx_semanal = {}
    response_semanal, _ = controller.obtener_planificacion_semanal(week_str)
    if response_semanal.get('success'):
        ctx_semanal = response_semanal.get('data', {})
    else:
        flash(response_semanal.get('error', 'Error cargando la planificación semanal.'), 'danger')

    # Datos para los formularios
    supervisores_resp = usuario_controller.obtener_usuarios_por_rol(['SUPERVISOR'])
    operarios_resp = usuario_controller.obtener_usuarios_por_rol(['OPERARIO'])
    
    # Lógica de CRP (Carga vs Capacidad)
    carga_crp = {}
    capacidad_crp = {}
    inicio_semana_crp = ctx_semanal.get('inicio_semana')
    fin_semana_crp = ctx_semanal.get('fin_semana')

    if inicio_semana_crp and fin_semana_crp:
        fecha_inicio_obj = date.fromisoformat(inicio_semana_crp)
        fecha_fin_obj = date.fromisoformat(fin_semana_crp)
        
        ops_visibles = ctx_semanal.get('ops_visibles_por_dia', {})
        ordenes_para_crp = [op for lista_ops in ops_visibles.values() for op in lista_ops]

        if ordenes_para_crp:
            carga_crp = controller.calcular_carga_capacidad(ordenes_para_crp)
        
        capacidad_crp = controller.obtener_capacidad_disponible([1, 2], fecha_inicio_obj, fecha_fin_obj)

    # Navegación de semana
    try:
        current_year, week_num_int = map(int, (ctx_semanal.get('semana_actual_str') or f"{date.today().year}-W{date.today().isocalendar().week}").split('-W'))
        current_week_start = date.fromisocalendar(current_year, week_num_int, 1)
        prev_week_start = current_week_start - timedelta(days=7)
        next_week_start = current_week_start + timedelta(days=7)
        semana_anterior_str = prev_week_start.strftime("%Y-W%V")
        semana_siguiente_str = next_week_start.strftime("%Y-W%V")
    except (ValueError, TypeError):
        semana_anterior_str, semana_siguiente_str = None, None

    return render_template(
        'planificacion/tablero.html',
        mps_data=ctx_mps,
        ordenes_por_dia=ctx_semanal.get('ops_visibles_por_dia', {}),
        semana_actual_str=ctx_semanal.get('semana_actual_str'),
        supervisores=supervisores_resp.get('data', []),
        operarios=operarios_resp.get('data', []),
        semana_anterior_str=semana_anterior_str,
        semana_siguiente_str=semana_siguiente_str,
        carga_crp=carga_crp,
        capacidad_crp=capacidad_crp,
        inicio_semana_crp=inicio_semana_crp,
        fin_semana_crp=fin_semana_crp,
        is_operario=is_operario,
        is_supervisor_calidad=is_supervisor_calidad,
        now=datetime.now(),
        date=date,
        timedelta=timedelta
    )

# --- Rutas de API (sin cambios) ---

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

@planificacion_bp.route('/api/validar-fecha-requerida', methods=['POST'])
@jwt_required()
def validar_fecha_requerida_api():
    data = request.json
    items_data = data.get('items', [])
    fecha_requerida = data.get('fecha_requerida')

    if not items_data or not fecha_requerida:
        return jsonify({'success': False, 'error': 'Faltan items o fecha_requerida.'}), 400

    controller = PlanificacionController()
    # Asumo que el método `api_validar_fecha_requerida` existe en el controlador
    response, status_code = controller.api_validar_fecha_requerida(items_data, fecha_requerida)
    return jsonify(response), status_code

@planificacion_bp.route('/configuracion', methods=['GET'])
##@jwt_required()
# @permission_required(accion='configurar_planificacion') # <-- Asegura esto
def configuracion_lineas():
    """Muestra la página de configuración de líneas y bloqueos."""
    controller = PlanificacionController()
    response, status_code = controller.obtener_datos_configuracion()
    if status_code != 200:
        flash(response.get('error', 'No se pudieron cargar los datos de configuración.'), 'error')
        return redirect(url_for('planificacion.index'))

    return render_template(
        'planificacion/configuracion.html',
        lineas=response.get('data', {}).get('lineas', []),
        bloqueos=response.get('data', {}).get('bloqueos', []),
        now=datetime.utcnow()  # <-- ¡AÑADIR ESTA LÍNEA!
    )

@planificacion_bp.route('/configuracion/guardar-linea', methods=['POST'])
##@jwt_required()
# @permission_required(accion='configurar_planificacion')
def guardar_configuracion_linea():
    """Guarda los cambios de eficiencia/utilización de una línea."""
    data = request.form
    controller = PlanificacionController()
    response, status_code = controller.actualizar_configuracion_linea(data)

    if status_code == 200:
        flash(response.get('message', 'Línea actualizada.'), 'success')
    else:
        flash(response.get('error', 'Error al actualizar.'), 'error')

    return redirect(url_for('planificacion.configuracion_lineas'))


@planificacion_bp.route('/configuracion/agregar-bloqueo', methods=['POST'])
##@jwt_required()
# @permission_required(accion='configurar_planificacion')
def agregar_bloqueo_capacidad():
    """Agrega un nuevo bloqueo de mantenimiento."""
    data = request.form
    controller = PlanificacionController()
    response, status_code = controller.agregar_bloqueo(data)

    if status_code == 201:
        flash(response.get('message', 'Bloqueo agregado.'), 'success')
    else:
        flash(response.get('error', 'Error al agregar bloqueo.'), 'error')

    return redirect(url_for('planificacion.configuracion_lineas'))

@planificacion_bp.route('/configuracion/eliminar-bloqueo/<int:bloqueo_id>', methods=['POST'])
##@jwt_required()
# @permission_required(accion='configurar_planificacion')
def eliminar_bloqueo_capacidad(bloqueo_id):
    """Elimina un bloqueo de mantenimiento."""
    controller = PlanificacionController()
    response, status_code = controller.eliminar_bloqueo(bloqueo_id)

    if status_code == 200:
        flash(response.get('message', 'Bloqueo eliminado.'), 'success')
    else:
        flash(response.get('error', 'Error al eliminar.'), 'error')

    return redirect(url_for('planificacion.configuracion_lineas'))
