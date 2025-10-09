from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    jsonify,
    session,
    url_for,
    flash,
)
from app.controllers.insumo_controller import InsumoController
from app.controllers.producto_controller import ProductoController
from app.controllers.inventario_controller import InventarioController
from app.controllers.orden_compra_controller import OrdenCompraController
from app.controllers.usuario_controller import UsuarioController
from app.controllers.receta_controller import RecetaController
from app.utils.decorators import roles_required
from app.utils.validators import validate_uuid
from marshmallow import ValidationError
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# The url_prefix will be handled in app/__init__.py
productos_bp = Blueprint("productos", __name__)

insumo_controller = InsumoController()
producto_controller = ProductoController()
receta_controller = RecetaController()
ordenes_compra_controller = OrdenCompraController()
inventario_controller = InventarioController()
usuario_controller = UsuarioController()


@productos_bp.route("/catalogo/nuevo", methods=["GET", "POST"])
@roles_required(
    allowed_roles=["GERENTE", "SUPERVISOR", "COMERCIAL"]
)
def crear_producto():
    try:
        if request.method == "POST":
            datos_json = request.get_json()
            if not datos_json:
                return jsonify(
                    {"success": False, "error": "No se recibieron datos JSON válidos"}
                ), 400
            # Correctly unpack the response from the controller
            response, status = producto_controller.crear_producto(datos_json)
            return jsonify(response), status
        
        # For GET request
        producto = None
        insumos_resp, _ = insumo_controller.obtener_insumos()
        insumos = insumos_resp.get("data", [])
        return render_template("productos/formulario.html", producto=producto, receta_items=[], insumos=insumos)
    except Exception as e:
        logger.error(f"Error inesperado en crear_producto: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@productos_bp.route("/catalogo", methods=["GET"])
@roles_required(min_level=2, allowed_roles=["EMPLEADO"])
def obtener_productos():
    try:
        filtros = {k: v for k, v in request.args.items() if v is not None and v != ""}
        response, status = producto_controller.obtener_todos_los_productos(filtros)
        productos = response.get("data", [])
        
        # 1. Obtener categorías distintas
        categorias_response, _ = producto_controller.obtener_categorias_distintas()
        categorias = categorias_response.get("data", [])
        
        return render_template(
            "productos/listar.html", 
            productos=productos, 
            categorias=categorias # <-- AÑADIDO: Pasa la lista de categorías
        )
    except Exception as e:
        logger.error(f"Error inesperado en obtener_todos_los_productos: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@productos_bp.route("/catalogo/<int:id_producto>", methods=["GET"])
@roles_required(min_level=2, allowed_roles=["EMPLEADO"])
def obtener_producto_por_id(id_producto):
    try:
        producto= producto_controller.obtener_producto_por_id(id_producto)
        
        response_insumos, status_insumo = insumo_controller.obtener_insumos()
        insumos = response_insumos.get("data", [])

        # Correctly fetch recipe and then its ingredients
        receta_items = []
        receta_response = receta_controller.model.db.table('recetas').select('id').eq('producto_id', id_producto).execute()
        if receta_response.data:
            receta_id = receta_response.data[0]['id']
            receta_items_response = receta_controller.obtener_ingredientes_para_receta(receta_id)
            receta_items = receta_items_response.get("data", [])

        insumos_dict = {str(insumo['id']): insumo for insumo in insumos}

        for item in receta_items:
            insumo = insumos_dict.get(str(item['id_insumo']))
            if insumo:
                item['nombre_insumo'] = insumo.get('nombre', 'Insumo no encontrado')
                item['precio_unitario'] = insumo.get('precio_unitario', 0)
                item['unidad_medida'] = insumo.get('unidad_medida', '')
            else:
                item['nombre_insumo'] = ''
                item['precio_unitario'] = 0
                item['unidad_medida'] = ''

        return render_template("productos/perfil_producto.html",  producto=producto, insumos=insumos, receta_items=receta_items)
    except Exception as e:
        logger.error(f"Error inesperado en obtener_producto_por_id: {str(e)}")
        return redirect(url_for("productos.obtener_productos"))

@productos_bp.route(
    "/catalogo/actualizar/<int:id_producto>", methods=["GET", "PUT"]
)
@roles_required(
    allowed_roles=["GERENTE", "SUPERVISOR", "COMERCIAL"]
)
def actualizar_producto(id_producto):
    try:
        if request.method == "PUT":
            datos_json = request.get_json()
            if not datos_json:
                return jsonify(
                    {"success": False, "error": "No se recibieron datos JSON válidos"}
                ), 400
            # Correctly unpack the response
            response, status = producto_controller.actualizar_producto(
                id_producto, datos_json
            )
            return jsonify(response), status

        # GET Request Logic
        producto = producto_controller.obtener_producto_por_id(id_producto)
        if not producto:
            flash("Producto no encontrado.", "error")
            return redirect(url_for('productos.obtener_productos'))

        response_insumos, status_insumo = insumo_controller.obtener_insumos()
        insumos = response_insumos.get("data", [])

        # Correctly fetch recipe and then its ingredients
        receta_items = []
        receta_response = receta_controller.model.db.table('recetas').select('id').eq('producto_id', id_producto).execute()
        if receta_response.data:
            receta_id = receta_response.data[0]['id']
            receta_items_response = receta_controller.obtener_ingredientes_para_receta(receta_id)
            receta_items = receta_items_response.get("data", [])
        
        insumos_dict = {str(insumo['id']): insumo for insumo in insumos}

        for item in receta_items:
            insumo = insumos_dict.get(str(item['id_insumo']))
            if insumo:
                item['precio_unitario'] = insumo.get('precio_unitario', 0)
                item['unidad_medida'] = insumo.get('unidad_medida', '')
            else:
                item['precio_unitario'] = 0
                item['unidad_medida'] = ''

        return render_template("productos/formulario.html", producto=producto, insumos=insumos, receta_items=receta_items)
    except Exception as e:
        logger.error(f"Error inesperado en actualizar_producto: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@productos_bp.route(
    "/catalogo/actualizar-precio/<string:id_producto>", methods=["GET","PUT"]
)
@roles_required(
    allowed_roles=["GERENTE", "SUPERVISOR", "COMERCIAL"]
)
def actualizar_precio(id_producto):
    try:
        respuesta, status = producto_controller.actualizar_costo_producto(id_producto)
        return jsonify(respuesta), status
    except Exception as e:
        logger.error(f"Error inesperado en actualizar_producto: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@productos_bp.route("/catalogo/eliminar/<string:id_producto>", methods=["DELETE"])
@roles_required(
    allowed_roles=["GERENTE", "SUPERVISOR", "COMERCIAL"]
)
def eliminar_producto(id_producto):
    try:
        response, status = producto_controller.eliminar_producto_logico(id_producto)
        return jsonify(response), status
    except Exception as e:
        logger.error(f"Error inesperado en eliminar_producto: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@productos_bp.route("/catalogo/habilitar/<string:id_producto>", methods=["POST"])
@roles_required(
    allowed_roles=["GERENTE", "SUPERVISOR", "COMERCIAL"]
)
def habilitar_producto(id_producto):
    try:
        response, status = producto_controller.habilitar_producto(id_producto)
        return jsonify(response), status
    except Exception as e:
        logger.error(f"Error inesperado en habilitar_producto: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500