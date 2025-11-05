import logging
from flask import Blueprint, render_template, flash, url_for, request, jsonify, redirect 
from flask_jwt_extended import get_jwt_identity, jwt_required, get_jwt
from app.controllers.planificacion_controller import PlanificacionController
from app.controllers.usuario_controller import UsuarioController
from datetime import date, timedelta, datetime
from app.utils.decorators import permission_required
from app import csrf

planificacion_bp = Blueprint('planificacion', __name__, url_prefix='/planificacion')
logger = logging.getLogger(__name__)
csrf.exempt(planificacion_bp)

@planificacion_bp.route('/') # La ruta principal ahora manejará todo
@jwt_required()
@permission_required(accion='consultar_plan_de_produccion')
def index():
    controller = PlanificacionController()
    current_user = get_jwt()
    user_roles = current_user.get('roles', [])
    is_operario = 'OPERARIO' in user_roles
    is_supervisor_calidad = 'SUPERVISOR_CALIDAD' in user_roles
    # ... (obtener semana, horizonte, mps_data - sin cambios) ...
    week_str = request.args.get('semana')
    if not week_str:
        today = date.today()
        start_of_week_iso = today - timedelta(days=today.isoweekday() - 1)
        week_str = start_of_week_iso.strftime("%Y-W%V")
    try:
        horizonte_dias = request.args.get('horizonte', default=7, type=int)
        if horizonte_dias <= 0: horizonte_dias = 7
    except ValueError: horizonte_dias = 7
    response_pendientes, _ = controller.obtener_ops_pendientes_planificacion(dias_horizonte=horizonte_dias)
    # ... (manejo de mps_data - sin cambios) ...
    mps_data_para_template = { 'mps_agrupado': [], 'inicio_horizonte': 'N/A', 'fin_horizonte': 'N/A', 'dias_horizonte': horizonte_dias }
    if response_pendientes.get('success'): mps_data_para_template = response_pendientes.get('data', mps_data_para_template)
    else: flash(response_pendientes.get('error', 'Error cargando MPS.'), 'error'); mps_data_para_template['dias_horizonte'] = horizonte_dias


    # --- INICIALIZACIÓN DE VARIABLES ---
    ordenes_por_dia = {}
    inicio_semana = None # Inicializar aquí
    fin_semana = None # Inicializar aquí
    ordenes_para_crp = [] # <--- INICIALIZAR AQUÍ
    carga_calculada = {}
    capacidad_disponible = {}
    ordenes_combinadas = []
    # ----------------------------------

    # 3. Obtener OPs para el CALENDARIO SEMANAL
    response_semanal, _ = controller.obtener_planificacion_semanal(week_str)
    ops_visibles_por_dia_formato = {} # <--- Usar nuevo nombre
    if response_semanal.get('success'):
        data_semanal = response_semanal.get('data', {})
        ordenes_por_dia = data_semanal.get('ops_visibles_por_dia', {}) # <--- Usar nuevo nombre
        ops_visibles_por_dia_formato = ordenes_por_dia
        inicio_semana_str = data_semanal.get('inicio_semana')
        fin_semana_str = data_semanal.get('fin_semana')
        if inicio_semana_str: inicio_semana = date.fromisoformat(inicio_semana_str) # Asignar si existe
        if fin_semana_str: fin_semana = date.fromisoformat(fin_semana_str) # Asignar si existe
    else:
        flash(response_semanal.get('error', 'Error cargando planificación semanal.'), 'error')

    # --- OBTENER OPS RELEVANTES PARA CRP ---
    # 1. OPs del Kanban
    from app.controllers.produccion_kanban_controller import ProduccionKanbanController
    kanban_controller = ProduccionKanbanController()
    response_kanban, _ = kanban_controller.obtener_datos_para_tablero(current_user.get('id'), current_user.get('rol'))
    ordenes_kanban_dict = response_kanban.get('data', {}).get('ordenes_por_estado', {}) if response_kanban.get('success') else {}
    ops_kanban = [op for estado, lista_ops in ordenes_kanban_dict.items() if estado not in ['COMPLETADA', 'CANCELADA'] for op in lista_ops]

    # 2. OPs de la semana
    ops_semana = [op for dia, lista_ops in ordenes_por_dia.items() for op in lista_ops if op.get('estado') not in ['COMPLETADA', 'CANCELADA']]

    # 3. Combinar y eliminar duplicados
    ops_combinadas_dict = {op['id']: op for op in ops_kanban + ops_semana if op.get('id')}
    ordenes_para_crp = list(ops_combinadas_dict.values()) # Ahora sí, se asigna valor
    # Ahora 'ordenes_combinadas' siempre será una lista (posiblemente vacía)
    ordenes_combinadas = list(ops_combinadas_dict.values())
    logger.info(f"Total OPs consideradas para CRP: {len(ordenes_para_crp)}")


    # --- CALCULAR CARGA Y CAPACIDAD (Usando la lista combinada) ---
    carga_calculada = {}
    capacidad_disponible = {}
    # Esta condición ahora usa la lista combinada (ordenes_para_crp)
    if ordenes_para_crp and inicio_semana and fin_semana: # <-- CAMBIO AQUÍ
        carga_calculada = controller.calcular_carga_capacidad(ordenes_para_crp) # <--- CAMBIO AQUÍ
        capacidad_disponible = controller.obtener_capacidad_disponible([1, 2], inicio_semana, fin_semana)

    # ... (lógica para obtener supervisores, operarios, columnas, navegación - sin cambios) ...
    usuario_controller = UsuarioController()
    supervisores_resp = usuario_controller.obtener_usuarios_por_rol(['SUPERVISOR']); operarios_resp = usuario_controller.obtener_usuarios_por_rol(['OPERARIO'])
    supervisores = supervisores_resp.get('data', []) if supervisores_resp.get('success') else []; operarios = operarios_resp.get('data', []) if supervisores_resp.get('success') else []
    columnas_kanban = { 'EN ESPERA': 'En Espera', 'LISTA PARA PRODUCIR':'Listas', 'EN_LINEA_1': 'L1', 'EN_LINEA_2': 'L2', 'EN_EMPAQUETADO': 'Emp.', 'CONTROL_DE_CALIDAD': 'CC', 'COMPLETADA': 'OK' }
    ordenes_por_estado = ordenes_kanban_dict # Usar el dict obtenido antes
    try:
        year, week_num_str = week_str.split('-W'); week_num = int(week_num_str); current_week_start = date.fromisocalendar(int(year), week_num, 1)
        prev_week_start = current_week_start - timedelta(days=7); next_week_start = current_week_start + timedelta(days=7)
        prev_week_str = prev_week_start.strftime("%Y-W%V"); next_week_str = next_week_start.strftime("%Y-W%V")
    except ValueError: prev_week_str = None; next_week_str = None; logger.warning(f"Error parseando week_str {week_str}")

    columnas_kanban = {
    'EN ESPERA': 'En Espera',
    'LISTA PARA PRODUCIR':'Lista para producir', # <-- Cambiado
    'EN_LINEA_1': 'Linea 1', # <-- Cambiado
    'EN_LINEA_2': 'Linea 2', # <-- Cambiado
    'EN_EMPAQUETADO': 'Empaquetado', # <-- Cambiado
    'CONTROL_DE_CALIDAD': 'Control de Calidad', # <-- Cambiado
    'COMPLETADA': 'Completada' # <-- Cambiado
    }

    return render_template(
        'planificacion/tablero.html',
        mps_data=mps_data_para_template,
        inicio_semana=inicio_semana.isoformat() if inicio_semana else None, # Pasar ISO o None
        fin_semana=fin_semana.isoformat() if fin_semana else None, # Pasar ISO o None
        semana_actual_str=week_str,
        semana_anterior_str=prev_week_str,
        semana_siguiente_str=next_week_str,
        ordenes_por_estado=ordenes_por_estado,
        columnas=columnas_kanban,
        supervisores=supervisores,
        operarios=operarios,
        carga_crp=carga_calculada,
        capacidad_crp=capacidad_disponible,
        ordenes_por_dia=ordenes_por_dia,
        inicio_semana_crp=inicio_semana.isoformat() if inicio_semana else None, # Usar las mismas fechas
        fin_semana_crp=fin_semana.isoformat() if fin_semana else None,
        now=datetime.utcnow(),
        timedelta=timedelta,
        date=date,
        is_operario=is_operario,
        is_supervisor_calidad=is_supervisor_calidad
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
