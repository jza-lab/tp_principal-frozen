# app/views/op_tabla_routes.py
from flask import Blueprint, render_template, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.planificacion_controller import PlanificacionController
from app.utils.decorators import permission_required

op_tabla_bp = Blueprint("op_tabla", __name__, url_prefix="/tabla-produccion")

@op_tabla_bp.route('/')
@permission_required(accion='consultar_plan_de_produccion')
def tablero_produccion():
    """
    Muestra el tablero Kanban de producción.
    """
    ordenp = OrdenProduccionController()
    
    # Obtener roles del usuario actual desde el token JWT para pasarlos a la plantilla.
    claims = get_jwt()
    user_role_code = claims.get('roles', {}).get('codigo', '')
    is_operario = user_role_code == 'OPERARIO'
    is_supervisor_calidad = user_role_code == 'SUPERVISOR_CALIDAD'

    datos = ordenp.obtener_datos_para_tablero()
    # Añadir las nuevas variables al contexto del template
    return render_template('planificacion/produccion_hoy.html', **datos, is_operario=is_operario, is_supervisor_calidad=is_supervisor_calidad)

@op_tabla_bp.route('/api/<int:op_id>/iniciar-trabajo', methods=['POST'])
@jwt_required()
@permission_required(accion='produccion_ejecucion')
def api_iniciar_trabajo(op_id):
    """
    API endpoint para mover una OP de 'LISTA PARA PRODUCIR' a 'EN_LINEA_X'.
    """
    data = request.get_json()
    linea = data.get('linea')
    if not linea or linea not in [1, 2]:
        return jsonify({'success': False, 'error': 'Línea de producción inválida.'}), 400

    nuevo_estado = f'EN_LINEA_{linea}'
    
    controller = OrdenProduccionController()
    response = controller.cambiar_estado_orden_simple(op_id, nuevo_estado)
    
    status_code = 200 if response.get('success') else 500
    return jsonify(response), status_code

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
