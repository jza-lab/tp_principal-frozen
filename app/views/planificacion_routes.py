# En app/routes/planificacion_routes.py
import logging
from flask import Blueprint, render_template, flash, url_for, request, jsonify, session # Añade request y jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required, get_jwt
from app.controllers.planificacion_controller import PlanificacionController
from app.controllers.usuario_controller import UsuarioController
from datetime import date, timedelta, datetime # <--- SE AÑADIÓ DATETIME
from app.utils.decorators import permission_required
from datetime import date, timedelta

planificacion_bp = Blueprint('planificacion', __name__, url_prefix='/planificacion')

logger = logging.getLogger(__name__)


@planificacion_bp.route('/')
@permission_required(accion='consultar_plan_de_produccion')
def index():
    controller = PlanificacionController()
    
    # 1. Recolectar parámetros de la solicitud
    week_str = request.args.get('semana')
    try:
        horizonte_dias = request.args.get('horizonte', default=7, type=int)
        if horizonte_dias <= 0:
            horizonte_dias = 7
    except ValueError:
        horizonte_dias = 7
        
    user_roles = get_jwt().get('roles', [])

    # 2. Delegar toda la lógica de obtención de datos al controlador
    response, status_code = controller.obtener_datos_para_tablero_planificacion(
        week_str=week_str,
        horizonte_dias=horizonte_dias,
        user_roles=user_roles
    )

    # 3. Manejar la respuesta del controlador
    if status_code >= 400 or not response.get('success'):
        flash(response.get('error', 'Ocurrió un error al cargar los datos del tablero.'), 'danger')
        # Renderizar la plantilla con un contexto vacío o de error
        return render_template('planificacion/tablero.html', error=True)

    context = response.get('data', {})
    
    # Si el controlador devuelve un error específico de MPS, lo mostramos
    if 'error' in context.get('mps_data', {}):
        flash(context['mps_data']['error'], 'warning')

    # 4. Renderizar la plantilla con el contexto preparado por el controlador
    return render_template(
        'planificacion/tablero.html',
        **context,
        now=datetime.utcnow(),
        timedelta=timedelta,
        date=date
    )

# --- NUEVA RUTA PARA CONFIRMACIÓN MULTI-DÍA ---
@planificacion_bp.route('/api/confirmar-aprobacion', methods=['POST'])
@jwt_required()
def confirmar_aprobacion_api():
    """
    API endpoint que ejecuta la aprobación final DESPUÉS de que el usuario
    confirma una planificación multi-día o resuelve una sobrecarga (si se implementa).
    """
    data = request.get_json()

    # --- OBTENER USUARIO DESDE JWT ---
    usuario_id = get_jwt_identity()
    # ---------------------------------

    if not usuario_id:
        return jsonify({'success': False, 'error': 'Usuario no autenticado.'}), 401

    op_id = data.get('op_id')
    asignaciones = data.get('asignaciones')

    if not op_id or not asignaciones:
         return jsonify({'success': False, 'error': 'Faltan datos (op_id o asignaciones).'}), 400

    controller = PlanificacionController()
    # Llama al helper que solo ejecuta la aprobación
    response, status_code = controller._ejecutar_aprobacion_final(
        op_id,
        asignaciones,
        usuario_id
    )
    return jsonify(response), status_code
# --- FIN NUEVA RUTA ---

# Endpoint para la API de consolidación
@planificacion_bp.route('/api/consolidar', methods=['POST'])
@jwt_required()
@permission_required(accion='aprobar_plan_de_produccion')
def consolidar_api():
    """
    API endpoint para consolidar múltiples OPs en una Super OP.
    """
    data = request.get_json()
    op_ids = data.get('op_ids', [])
    usuario_id = get_jwt_identity()

    controller = PlanificacionController()
    response, status_code = controller.consolidar_ops(op_ids, usuario_id)
    return jsonify(response), status_code

# Endpoint para la API de recomendación
@planificacion_bp.route('/api/recomendar-linea/<int:op_id>', methods=['GET'])
@permission_required(accion='consultar_plan_de_produccion')
def recomendar_linea_api(op_id):
    """
    API endpoint para analizar una OP y recomendar una línea de producción.
    """
    controller = PlanificacionController()
    response, status_code = controller.recomendar_linea_produccion(op_id)
    return jsonify(response), status_code


@planificacion_bp.route('/api/consolidar-y-aprobar', methods=['POST'])
@jwt_required()
def consolidar_y_aprobar_api():
    """
    API endpoint para el flujo completo de la modal de Plan Maestro:
    1. Consolida OPs.
    2. Asigna Línea, Supervisor, Operario.
    3. Confirma Fecha y ejecuta la aprobación (stock check, etc).
    """
    data = request.get_json()
    usuario_id = get_jwt_identity()

    controller = PlanificacionController()
    # Pasamos todos los datos al nuevo método del controlador
    response, status_code = controller.consolidar_y_aprobar_lote(
        op_ids=data.get('op_ids', []),
        asignaciones=data.get('asignaciones', {}),
        usuario_id=usuario_id
    )
    return jsonify(response), status_code
