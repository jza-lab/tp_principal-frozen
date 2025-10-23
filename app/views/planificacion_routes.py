# En app/routes/planificacion_routes.py
import logging
from flask import Blueprint, render_template, flash, url_for, request, jsonify, session # Añade request y jsonify
from app.controllers.planificacion_controller import PlanificacionController
from app.controllers.usuario_controller import UsuarioController
from app.utils.decorators import permission_required
from datetime import date, timedelta

planificacion_bp = Blueprint('planificacion', __name__, url_prefix='/planificacion')

controller = PlanificacionController()

@planificacion_bp.route('/') # La ruta principal ahora manejará todo
@permission_required(accion='consultar_plan_de_produccion')
def index():
    """
    Muestra la BANDEJA, el CALENDARIO SEMANAL y el KANBAN.
    """
    # 1. Obtener semana de la URL o usar la actual
    week_str = request.args.get('semana')
    print(f"DEBUG: 'semana' recibida de URL: {week_str}") # <-- TRAZA 1
    if not week_str:
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        week_str = start_of_week.strftime("%Y-W%W") # Formato YYYY-WNN
        print(f"DEBUG: No se recibió semana, usando actual: {week_str}")

    # 2. Obtener OPs Pendientes (Bandeja) - Sin cambios
    response_pendientes, _ = controller.obtener_ops_pendientes_planificacion()
    ops_pendientes = response_pendientes.get('data', []) if response_pendientes.get('success') else []
    # ... (manejo de flash si falla) ...

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

    # 4. Obtener OPs para el KANBAN - Sin cambios
    response_kanban, _ = controller.obtener_ops_para_tablero()
    ordenes_por_estado = response_kanban.get('data', {}) if response_kanban.get('success') else {}
    # ... (manejo de flash si falla) ...


    # 5. Obtener Operarios y Supervisores (para la bandeja) - Sin cambios
    usuario_controller = UsuarioController()
    supervisores_resp = usuario_controller.obtener_usuarios_por_rol(['SUPERVISOR'])
    operarios_resp = usuario_controller.obtener_usuarios_por_rol(['OPERARIO'])
    supervisores = supervisores_resp.get('data', []) if supervisores_resp.get('success') else []
    operarios = operarios_resp.get('data', []) if operarios_resp.get('success') else []

    # 6. Definir columnas Kanban - Sin cambios
    columnas_kanban = {
        'EN ESPERA': 'En Espera (Sin Insumos)',
        'LISTA PARA PRODUCIR':'Listas para Iniciar',
        'EN_LINEA_1': 'Línea 1', 'EN_LINEA_2': 'Línea 2', 'EN_EMPAQUETADO': 'Empaquetado',
        'CONTROL_DE_CALIDAD': 'Control Calidad', 'COMPLETADA': 'Completadas'
    }

    # 7. Calcular navegación semanal (como en semanal.html)
    try:
        year = int(week_str[:4])
        week_num = int(week_str[-2:])
        # Use isocalendar which returns (year, week, weekday)
        current_week_start = date.fromisocalendar(year, week_num, 1) # Monday
        prev_week_start = current_week_start - timedelta(days=7)
        next_week_start = current_week_start + timedelta(days=7)

        # --- CORRECTION: Use %V for ISO week number ---
        prev_week_str = prev_week_start.strftime("%Y-W%V")
        next_week_str = next_week_start.strftime("%Y-W%V")
        # Ensure week_str itself uses %V if generated initially
        if request.args.get('semana') is None: # If it was the default calculation
             week_str = current_week_start.strftime("%Y-W%V")
        # -----------------------------------------------

        print(f"DEBUG: current_week_start: {current_week_start}")
        print(f"DEBUG: next_week_start: {next_week_start}")
        print(f"DEBUG: next_week_str (calculado con %V): {next_week_str}") # Updated log
    except ValueError:
        prev_week_str = None
        next_week_str = None
        print("DEBUG: Error parseando week_str")

    # 8. Renderizar el tablero.html con TODOS los datos
    return render_template(
        'planificacion/tablero.html',
        ops_pendientes=ops_pendientes,               # Para Bandeja
        ordenes_por_dia=ordenes_por_dia,             # Para Calendario Semanal
        inicio_semana=inicio_semana,
        fin_semana=fin_semana,
        semana_actual_str=week_str,
        semana_anterior_str=prev_week_str,
        semana_siguiente_str=next_week_str,
        ordenes_por_estado=ordenes_por_estado,       # Para Kanban
        columnas=columnas_kanban,                  # Para Kanban
        supervisores=supervisores,                   # Para Bandeja
        operarios=operarios                          # Para Bandeja
    )

# Endpoint para la API de consolidación
@planificacion_bp.route('/api/consolidar', methods=['POST'])
@permission_required(accion='aprobar_plan_de_produccion')
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
@permission_required(accion='consultar_plan_de_produccion')
def recomendar_linea_api(op_id):
    """
    API endpoint para analizar una OP y recomendar una línea de producción.
    """
    response, status_code = controller.recomendar_linea_produccion(op_id)
    return jsonify(response), status_code


# Endpoint para la API de mover OPs (Drag-and-Drop y asignación)
@planificacion_bp.route('/api/mover-op/<int:op_id>', methods=['POST'])
@permission_required(accion='aprobar_plan_de_produccion')
def mover_op_api(op_id):
    """
    API endpoint para cambiar el estado de una OP.
    Usado tanto por el drag-and-drop como por la asignación post-recomendación.
    """
    data = request.get_json()
    nuevo_estado = data.get('nuevo_estado')

    response, status_code = controller.mover_orden(op_id, nuevo_estado)
    return jsonify(response), status_code
