from flask import Blueprint, jsonify, request
from app.controllers.trazabilidad_controller import TrazabilidadController

api_trazabilidad_bp = Blueprint('api_trazabilidad', __name__, url_prefix='/api/trazabilidad')

@api_trazabilidad_bp.route('/<string:tipo_entidad>/<string:id>', methods=['GET'])
def get_trazabilidad_unificada(tipo_entidad, id):
    """
    Endpoint unificado para obtener los datos de trazabilidad para cualquier entidad.
    Acepta un parámetro 'nivel' en la URL (?nivel=simple o ?nivel=completo).
    Por defecto, el nivel es 'simple'.
    """
    nivel = request.args.get('nivel', 'simple')
    controller = TrazabilidadController()
    response, status_code = controller.obtener_trazabilidad(tipo_entidad, id, nivel)
    return jsonify(response), status_code
