# app/routes/lote_producto_routes.py
from flask import Blueprint, request, jsonify
from app.controllers.lote_producto_controller import LoteProductoController
from app.utils.decorators import roles_required
import logging

logger = logging.getLogger(__name__)

lote_producto_bp = Blueprint("lote_producto", __name__)
controller = LoteProductoController()

@lote_producto_bp.route("/lotes", methods=["POST"])
##@roles_required(allowed_roles=["GERENTE", "SUPERVISOR", "ALMACEN"])
def crear_lote():
    """Crea un nuevo lote de producto."""
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Content-Type debe ser application/json"}), 400

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No se recibieron datos JSON"}), 400

        response, status = controller.crear_lote(data)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en crear_lote: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@lote_producto_bp.route("/lotes", methods=["GET"])
##@roles_required(min_level=2, allowed_roles=["EMPLEADO"])
def obtener_lotes():
    """Obtiene todos los lotes."""
    try:
        # Obtener filtros de query params
        filtros = {}
        for key, value in request.args.items():
            if value and value != "":
                filtros[key] = value

        response, status = controller.obtener_lotes(filtros)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en obtener_lotes: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@lote_producto_bp.route("/lotes/<int:lote_id>", methods=["GET"])
##@roles_required(min_level=2, allowed_roles=["EMPLEADO"])
def obtener_lote_por_id(lote_id):
    """Obtiene un lote por su ID."""
    try:
        response, status = controller.obtener_lote_por_id(lote_id)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en obtener_lote_por_id: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@lote_producto_bp.route("/lotes/<int:lote_id>", methods=["PUT"])
##@roles_required(allowed_roles=["GERENTE", "SUPERVISOR", "ALMACEN"])
def actualizar_lote(lote_id):
    """Actualiza un lote existente."""
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Content-Type debe ser application/json"}), 400

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No se recibieron datos JSON"}), 400

        response, status = controller.actualizar_lote(lote_id, data)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en actualizar_lote: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@lote_producto_bp.route("/lotes/<int:lote_id>", methods=["DELETE"])
##@roles_required(allowed_roles=["GERENTE", "SUPERVISOR", "ALMACEN"])
def eliminar_lote(lote_id):
    """Eliminación lógica de un lote."""
    try:
        response, status = controller.eliminar_lote_logico(lote_id)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en eliminar_lote: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@lote_producto_bp.route("/lotes/disponibles", methods=["GET"])
##@roles_required(min_level=2, allowed_roles=["EMPLEADO"])
def obtener_lotes_disponibles():
    """Obtiene lotes disponibles."""
    try:
        response, status = controller.obtener_lotes({'estado': 'DISPONIBLE'})
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en obtener_lotes_disponibles: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500