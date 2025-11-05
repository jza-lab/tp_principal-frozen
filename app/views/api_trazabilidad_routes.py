from flask import Blueprint, jsonify
from app.controllers.trazabilidad_controller import TrazabilidadController

api_trazabilidad_bp = Blueprint('api_trazabilidad', __name__, url_prefix='/api/trazabilidad')

@api_trazabilidad_bp.route('/lote_insumo/<id>', methods=['GET'])
def get_trazabilidad_lote_insumo(id):
    """
    Endpoint para obtener los datos de trazabilidad para un lote de insumo.
    """
    controller = TrazabilidadController()
    response, status_code = controller.obtener_datos_trazabilidad('lote_insumo', id)
    return jsonify(response), status_code

@api_trazabilidad_bp.route('/lote_producto/<id>', methods=['GET'])
def get_trazabilidad_lote_producto(id):
    """
    Endpoint para obtener los datos de trazabilidad para un lote de producto.
    """
    controller = TrazabilidadController()
    response, status_code = controller.obtener_datos_trazabilidad('lote_producto', id)
    return jsonify(response), status_code


@api_trazabilidad_bp.route('/orden_produccion/<id>', methods=['GET'])
def get_trazabilidad_orden_produccion(id):
    """
    Endpoint para obtener los datos de trazabilidad para una Orden de Producción.
    """
    controller = TrazabilidadController()
    response, status_code = controller.obtener_datos_trazabilidad('orden_produccion', id)
    return jsonify(response), status_code
