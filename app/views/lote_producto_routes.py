# app/routes/lote_producto_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.controllers.lote_producto_controller import LoteProductoController
from app.controllers.producto_controller import ProductoController # Para el formulario
from app.utils.decorators import permission_required
import logging
from datetime import date
from flask import jsonify


logger = logging.getLogger(__name__)

lote_producto_bp = Blueprint("lote_producto", __name__)

controller = LoteProductoController()
producto_controller = ProductoController() # Para obtener la lista de productos

@lote_producto_bp.route('/')
@permission_required(accion='realizar_control_calidad')
def listar_lotes():
    response, _ = controller.obtener_lotes_para_vista()
    lotes = response.get('data', [])
    return render_template('lotes_productos/listar.html', lotes=lotes)

@lote_producto_bp.route('/<int:id_lote>/detalle')
@permission_required(accion='realizar_control_calidad')
def detalle_lote(id_lote):
    response, _ = controller.obtener_lote_por_id_para_vista(id_lote)
    if not response.get('success'):
        flash(response.get('error'), 'error')
        return redirect(url_for('lote_producto.listar_lotes'))

    return render_template('lotes_productos/detalle.html', lote=response.get('data'))


@lote_producto_bp.route('/nuevo', methods=['GET', 'POST'])
@permission_required(accion='control_calidad_lote')
def nuevo_lote():
    if request.method == 'POST':
        usuario_id = session.get('usuario_id')
        response, status_code = controller.crear_lote_desde_formulario(request.form, usuario_id)
        if response.get('success'):
            flash(response.get('message'), 'success')
            return redirect(url_for('lote_producto.listar_lotes'))
        else:
            flash(response.get('error'), 'error')

    productos_resp_dict, _ = producto_controller.obtener_todos_los_productos()
    productos = productos_resp_dict.get('data', [])

    return render_template('lotes_productos/formulario.html',
                           productos=productos,
                           today=date.today().isoformat())

@lote_producto_bp.route("/lotes", methods=["GET"])
@permission_required(accion='ver_historial_controles')
def obtener_lotes():
    """Obtiene todos los lotes."""
    try:
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
@permission_required(accion='ver_historial_controles')
def obtener_lote_por_id(lote_id):
    """Obtiene un lote por su ID."""
    try:
        response, status = controller.obtener_lote_por_id(lote_id)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en obtener_lote_por_id: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@lote_producto_bp.route("/lotes/<int:lote_id>", methods=["PUT"])
@permission_required(accion='control_calidad_lote')
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
@permission_required(accion='rechazar_lotes')
def eliminar_lote(lote_id):
    """Eliminación lógica de un lote."""
    try:
        response, status = controller.eliminar_lote_logico(lote_id)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en eliminar_lote: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@lote_producto_bp.route("/lotes/disponibles", methods=["GET"])
@permission_required(accion='aprobar_lotes')
def obtener_lotes_disponibles():
    """Obtiene lotes disponibles."""
    try:
        response, status = controller.obtener_lotes({'estado': 'DISPONIBLE'})
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en obtener_lotes_disponibles: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500
