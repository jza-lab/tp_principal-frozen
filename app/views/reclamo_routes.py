from flask import Blueprint, request, jsonify, session
from app.controllers.reclamo_controller import ReclamoController


reclamo_bp = Blueprint('reclamo', __name__, url_prefix='/api/reclamos')
reclamo_controller = ReclamoController()

@reclamo_bp.route('/', methods=['POST'])
def crear_reclamo():
    """
    Endpoint para crear un nuevo reclamo.
    Espera un JSON con los datos del reclamo.
    """
    datos_json = request.get_json()
    if not datos_json:
        return jsonify({"success": False, "error": "No se recibieron datos JSON."}), 400
    
    # El ID del cliente se obtiene de la sesión para seguridad
    cliente_id = session['cliente_id']
    
    respuesta, status_code = reclamo_controller.crear_reclamo(datos_json, cliente_id)
    
    return jsonify(respuesta), status_code

@reclamo_bp.route('/', methods=['GET'])
def obtener_reclamos():
    """
    Endpoint para obtener todos los reclamos del cliente que ha iniciado sesión.
    """
    
    cliente_id = session['cliente_id']
    respuesta, status_code = reclamo_controller.obtener_reclamos_por_cliente(cliente_id)
    
    return jsonify(respuesta), status_code