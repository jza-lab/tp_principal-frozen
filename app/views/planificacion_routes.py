# En app/routes/planificacion_routes.py
from flask import Blueprint, render_template, flash, url_for, request, jsonify # Añade request y jsonify
from app.controllers.planificacion_controller import PlanificacionController


planificacion_bp = Blueprint('planificacion', __name__, url_prefix='/planificacion')
controller = PlanificacionController()

@planificacion_bp.route('/')
##@permission_required(sector_codigo='PRODUCCION', accion='leer')
def index():
    """
    Muestra el tablero de planificación de producción (Kanban).
    """
    response, _ = controller.obtener_ops_para_tablero()

    ordenes_por_estado = {}
    if response.get('success'):
        ordenes_por_estado = response.get('data', {})
    else:
        flash(response.get('error', 'No se pudieron cargar los datos del tablero.'), 'error')

    # Definimos las columnas y sus títulos para la plantilla
    columnas = {
        'LISTA PARA PRODUCIR': 'Por Asignar',
        'EN_LINEA_1': 'Línea 1 (Moderna)',
        'EN_LINEA_2': 'Línea 2 (Clásica)',
        'EN_EMPAQUETADO': 'Empaquetado',
        'CONTROL_DE_CALIDAD': 'Control de Calidad',
        'COMPLETADA': 'Completadas'
    }

    return render_template(
        'planificacion/tablero.html',
        ordenes_por_estado=ordenes_por_estado,
        columnas=columnas
    )

# Endpoint para la API de consolidación
@planificacion_bp.route('/api/consolidar', methods=['POST'])
def consolidar_api():
    """
    API endpoint para consolidar múltiples OPs en una Super OP.
    """
    data = request.get_json()
    op_ids = data.get('op_ids', [])

    # Asumimos que el usuario logueado tiene ID 1, debes reemplazarlo con el real
    usuario_id = 1

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