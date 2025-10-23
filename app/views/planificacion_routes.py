# En app/routes/planificacion_routes.py
import logging
from flask import Blueprint, render_template, flash, url_for, request, jsonify, session # Añade request y jsonify
from app.controllers.planificacion_controller import PlanificacionController
from app.controllers.usuario_controller import UsuarioController
from datetime import date, timedelta, datetime # <--- SE AÑADIÓ DATETIME

planificacion_bp = Blueprint('planificacion', __name__, url_prefix='/planificacion')

controller = PlanificacionController()

@planificacion_bp.route('/') # La ruta principal ahora manejará todo
def index():
    """
    Muestra la BANDEJA, el CALENDARIO SEMANAL y el KANBAN.
    """
    # 1. Obtener semana de la URL o usar la actual
    week_str = request.args.get('semana')
    print(f"DEBUG: 'semana' recibida de URL: {week_str}")
    if not week_str:
        today = date.today()
        # --- CORRECCIÓN: Usar %V para semana ISO ---
        start_of_week_iso = today - timedelta(days=today.isoweekday() - 1) # Lunes
        week_str = start_of_week_iso.strftime("%Y-W%V") # Formato YYYY-WNN (ISO)
        print(f"DEBUG: No se recibió semana, usando actual: {week_str}")
        # ------------------------------------------

    # --- LEER HORIZONTE DE LA URL ---
    try:
        horizonte_dias = request.args.get('horizonte', default=7, type=int)
        if horizonte_dias <= 0: horizonte_dias = 7
    except ValueError:
        horizonte_dias = 7
    # ---------------------------------

    response_pendientes, _ = controller.obtener_ops_pendientes_planificacion(dias_horizonte=horizonte_dias)
    mps_data_para_template = {
        'mps_agrupado': [], 'inicio_horizonte': 'N/A', 'fin_horizonte': 'N/A', 'dias_horizonte': horizonte_dias
    }
    if response_pendientes.get('success'):
        mps_data_para_template = response_pendientes.get('data', mps_data_para_template)
    else:
        flash(response_pendientes.get('error', 'Error cargando MPS.'), 'error')
        mps_data_para_template['dias_horizonte'] = horizonte_dias

    # 3. Obtener OPs para el CALENDARIO SEMANAL
    response_semanal, _ = controller.obtener_planificacion_semanal(week_str)
    ordenes_por_dia = {}
    inicio_semana = None
    fin_semana = None
    if response_semanal.get('success'):
        data_semanal = response_semanal.get('data', {})
        ordenes_por_dia = data_semanal.get('ordenes_por_dia', {})
        inicio_semana = data_semanal.get('inicio_semana')
        fin_semana = data_semanal.get('fin_semana')
    else:
        flash(response_semanal.get('error', 'Error cargando planificación semanal.'), 'error')

    # 4. Obtener OPs para el KANBAN
    response_kanban, _ = controller.obtener_ops_para_tablero()
    ordenes_por_estado = response_kanban.get('data', {}) if response_kanban.get('success') else {}

    # 5. Obtener Operarios y Supervisores
    usuario_controller = UsuarioController()
    supervisores_resp = usuario_controller.obtener_usuarios_por_rol(['SUPERVISOR'])
    operarios_resp = usuario_controller.obtener_usuarios_por_rol(['OPERARIO'])
    supervisores = supervisores_resp.get('data', []) if supervisores_resp.get('success') else []
    operarios = operarios_resp.get('data', []) if operarios_resp.get('success') else []

    # 6. Definir columnas Kanban
    columnas_kanban = {
        'EN ESPERA': 'En Espera (Sin Insumos)',
        'LISTA PARA PRODUCIR':'Listas para Iniciar',
        'EN_LINEA_1': 'Línea 1', 'EN_LINEA_2': 'Línea 2', 'EN_EMPAQUETADO': 'Empaquetado',
        'CONTROL_DE_CALIDAD': 'Control Calidad', 'COMPLETADA': 'Completadas'
    }

    # 7. Calcular navegación semanal
    try:
        # --- CORRECCIÓN: Usar %V para semana ISO ---
        year, week_num_str = week_str.split('-W')
        week_num = int(week_num_str)
        current_week_start = date.fromisocalendar(int(year), week_num, 1) # Lunes
        prev_week_start = current_week_start - timedelta(days=7)
        next_week_start = current_week_start + timedelta(days=7)
        prev_week_str = prev_week_start.strftime("%Y-W%V")
        next_week_str = next_week_start.strftime("%Y-W%V")
        # -----------------------------------------------
    except ValueError:
        prev_week_str = None
        next_week_str = None
        print(f"DEBUG: Error parseando week_str {week_str}")

    # 8. Renderizar el tablero.html con TODOS los datos
    return render_template(
        'planificacion/tablero.html',
        mps_data=mps_data_para_template,
        ordenes_por_dia=ordenes_por_dia,
        inicio_semana=inicio_semana,
        fin_semana=fin_semana,
        semana_actual_str=week_str,
        semana_anterior_str=prev_week_str,
        semana_siguiente_str=next_week_str,
        ordenes_por_estado=ordenes_por_estado,
        columnas=columnas_kanban,
        supervisores=supervisores,
        operarios=operarios,
        # --- 2. VARIABLE AÑADIDA ---
        now=datetime.utcnow(), # <--- PASAMOS LA FECHA/HORA ACTUAL A LA PLANTILLA
        timedelta=timedelta
    )

# Endpoint para la API de consolidación
@planificacion_bp.route('/api/consolidar', methods=['POST'])
def consolidar_api():
    """
    API endpoint para consolidar múltiples OPs en una Super OP.
    """
    logging.warning(f"Contenido de la sesión al consolidar: {dict(session)}")
    data = request.get_json()
    op_ids = data.get('op_ids', [])

    usuario_id = session.get('usuario_id')
    if not usuario_id:
        return jsonify({'success': False, 'error': 'Usuario no autenticado.'}), 401

    response, status_code = controller.consolidar_ops(op_ids, usuario_id)
    return jsonify(response), status_code

# Endpoint para la API de recomendación
@planificacion_bp.route('/api/recomendar-linea/<int:op_id>', methods=['GET'])
def recomendar_linea_api(op_id):
    """
    API endpoint para analizar una OP y recomendar una línea de producción.
    """
    response, status_code = controller.recomendar_linea_produccion(op_id)
    return jsonify(response), status_code


# Endpoint para la API de mover OPs (Drag-and-Drop y asignación)
@planificacion_bp.route('/api/mover-op/<int:op_id>', methods=['POST'])
def mover_op_api(op_id):
    """
    API endpoint para cambiar el estado de una OP.
    Usado tanto por el drag-and-drop como por la asignación post-recomendación.
    """
    data = request.get_json()
    nuevo_estado = data.get('nuevo_estado')

    response, status_code = controller.mover_orden(op_id, nuevo_estado)
    return jsonify(response), status_code

@planificacion_bp.route('/api/consolidar-y-aprobar', methods=['POST'])
def consolidar_y_aprobar_api():
    """
    API endpoint para el flujo completo de la modal de Plan Maestro:
    1. Consolida OPs.
    2. Asigna Línea, Supervisor, Operario.
    3. Confirma Fecha y ejecuta la aprobación (stock check, etc).
    """
    data = request.get_json()
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        return jsonify({'success': False, 'error': 'Usuario no autenticado.'}), 401

    # Pasamos todos los datos al nuevo método del controlador
    response, status_code = controller.consolidar_y_aprobar_lote(
        op_ids=data.get('op_ids', []),
        asignaciones=data.get('asignaciones', {}),
        usuario_id=usuario_id
    )
    return jsonify(response), status_code
