from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    jsonify,
    url_for,
    flash,
)
from flask_jwt_extended import get_current_user
from app.controllers.insumo_controller import InsumoController
from app.controllers.inventario_controller import InventarioController
from app.controllers.proveedor_controller import ProveedorController
from app.controllers.orden_compra_controller import OrdenCompraController
from app.controllers.usuario_controller import UsuarioController
from app.utils.decorators import permission_required
from app.utils.validators import validate_uuid
from marshmallow import ValidationError
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

insumos_bp = Blueprint("insumos_api", __name__, url_prefix="/api/insumos")


@insumos_bp.route("/catalogo/nuevo", methods=["GET", "POST"])
@permission_required(accion='gestionar_catalogo_insumos')
def crear_insumo():
    try:
        insumo_controller = InsumoController()
        proveedor_controller = ProveedorController()
        if request.method == "POST":
            datos_json = request.get_json()
            if not datos_json:
                return jsonify(
                    {"success": False, "error": "No se recibieron datos JSON válidos"}
                ), 400
            response, status = insumo_controller.crear_insumo(datos_json)
            return jsonify(response), status
        insumo = None
        proveedores_resp, estado = proveedor_controller.obtener_proveedores_activos()
        proveedores = proveedores_resp.get("data", [])
        return render_template("insumos/formulario.html", insumo=insumo, proveedores=proveedores)
    except Exception as e:
        logger.error(f"Error inesperado en crear_insumo: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@insumos_bp.route("/catalogo", methods=["GET"])
@permission_required(accion='almacen_ver_insumos')
def obtener_insumos():
    try:
        insumo_controller = InsumoController()
        proveedor_controller = ProveedorController()

        filtros = {k: v for k, v in request.args.items() if v is not None and v != ""}
        response, status = insumo_controller.obtener_insumos(filtros)
        insumos = response.get("data", [])
        
        categorias_response, _ = insumo_controller.obtener_categorias_distintas()
        categorias = categorias_response.get("data", [])
        
        proveedores_resp, _ = proveedor_controller.obtener_proveedores_activos()
        proveedores = proveedores_resp.get("data", [])

        return render_template(
            "insumos/listar.html", 
            insumos=insumos, 
            categorias=categorias,
            proveedores=proveedores
        )

    except Exception as e:
        logger.error(f"Error inesperado en obtener_insumos: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@insumos_bp.route("/catalogo/<string:id_insumo>", methods=["GET"])
@permission_required(accion='almacen_ver_insumos')
def obtener_insumo_por_id(id_insumo):
    try:
        insumo_controller = InsumoController()
        inventario_controller = InventarioController()
        if not validate_uuid(id_insumo):
            return jsonify({"success": False, "error": "ID de insumo inválido"}), 400
        response, status = insumo_controller.obtener_insumo_por_id(id_insumo)
        insumo = response["data"]
        lotes_response, lotes_status = inventario_controller.obtener_lotes_por_insumo(
            id_insumo, solo_disponibles=False
        )
        lotes = lotes_response.get("data", []) if lotes_status == 200 else []
        return render_template("insumos/perfil_insumo.html", insumo=insumo, lotes=lotes)
    except Exception as e:
        logger.error(f"Error inesperado en obtener_insumo_por_id: {str(e)}")
        return redirect(url_for("insumos_api.obtener_insumos"))


@insumos_bp.route(
    "/catalogo/actualizar/<string:id_insumo>", methods=["GET", "POST", "PUT"]
)
@permission_required(accion='gestionar_catalogo_insumos')
def actualizar_insumo(id_insumo):
    try:
        insumo_controller = InsumoController()
        proveedor_controller = ProveedorController()
        if not validate_uuid(id_insumo):
            return jsonify({"success": False, "error": "ID de insumo inválido"}), 400
        if request.method in ["POST", "PUT"]:
            datos_json = request.get_json()
            if not datos_json:
                return jsonify(
                    {"success": False, "error": "No se recibieron datos JSON válidos"}
                ), 400
            response, status = insumo_controller.actualizar_insumo(
                id_insumo, datos_json
            )

            return jsonify(response), status
        response, status = insumo_controller.obtener_insumo_por_id(id_insumo)
        insumo = response["data"]
        proveedores_resp, estado = proveedor_controller.obtener_proveedores_activos()
        proveedores = proveedores_resp.get("data", [])

        return render_template("insumos/formulario.html", insumo=insumo, proveedores=proveedores)
    except Exception as e:
        logger.error(f"Error inesperado en actualizar_insumo: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@insumos_bp.route("/catalogo/eliminar/<string:id_insumo>", methods=["DELETE"])
@permission_required(accion='gestionar_catalogo_insumos')
def eliminar_insumo(id_insumo):
    try:
        insumo_controller = InsumoController()
        if not validate_uuid(id_insumo):
            return jsonify({"success": False, "error": "ID de insumo inválido"}), 400
        response, status = insumo_controller.eliminar_insumo_logico(id_insumo)
        return jsonify(response), status
    except Exception as e:
        logger.error(f"Error inesperado en eliminar_insumo: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@insumos_bp.route("/catalogo/habilitar/<string:id_insumo>", methods=["POST"])
@permission_required(accion='gestionar_catalogo_insumos')
def habilitar_insumo(id_insumo):
    try:
        insumo_controller = InsumoController()
        if not validate_uuid(id_insumo):
            return jsonify({"success": False, "error": "ID de insumo inválido"}), 400
        response, status = insumo_controller.habilitar_insumo(id_insumo)
        return jsonify(response), status
    except Exception as e:
        logger.error(f"Error inesperado en habilitar_insumo: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@insumos_bp.route("/catalogo/lote/nuevo/<string:id_insumo>", methods=["GET", "POST"])
@permission_required(accion='almacen_consulta_stock')
def agregar_lote(id_insumo):
    proveedor_controller = ProveedorController()
    insumo_controller = InsumoController()
    ordenes_compra_controller = OrdenCompraController()
    proveedores_resp, _ = proveedor_controller.obtener_proveedores_activos()
    proveedores = proveedores_resp.get("data", [])
    response, _ = insumo_controller.obtener_insumo_por_id(id_insumo)
    insumo = response["data"]
    ordenes_compra_resp, _ = ordenes_compra_controller.obtener_codigos_por_insumo(
        id_insumo
    )
    ordenes_compra_data = ordenes_compra_resp.get("data", [])
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template(
        "insumos/registrar_lote.html",
        insumo=insumo,
        proveedores=proveedores,
        ordenes=ordenes_compra_data,
        is_edit=False,
        lote={},
        today=today,
    )


@insumos_bp.route(
    "/catalogo/lote/nuevo/<string:id_insumo>/crear", methods=["GET", "POST"]
)
@permission_required(accion='consultar_stock_de_lotes')
def crear_lote(id_insumo):
    try:
        inventario_controller = InventarioController()
        datos_json = request.get_json()
        if not datos_json:
            return jsonify(
                {"success": False, "error": "No se recibieron datos JSON válidos"}
            ), 400
        current_user = get_current_user()
        usuario_id = current_user.id
        response, status = inventario_controller.crear_lote(datos_json, usuario_id)
        return jsonify(response), status
    except Exception as e:
        logger.error(f"Error inesperado en crear_lote: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@insumos_bp.route(
    "/catalogo/lote/editar/<string:id_insumo>/<string:id_lote>", methods=["GET"]
)
@permission_required(accion='consultar_stock_de_lotes')
def editar_lote(id_insumo, id_lote):
    def parse_date(date_str):
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        except:
            return date_str

    try:
        proveedor_controller = ProveedorController()
        ordenes_compra_controller = OrdenCompraController()
        insumo_controller = InsumoController()
        inventario_controller = InventarioController()
        if not validate_uuid(id_insumo) or not validate_uuid(id_lote):
            return "ID inválido", 400
        proveedores = proveedor_controller.obtener_proveedores_activos()[0].get(
            "data", []
        )
        ordenes = ordenes_compra_controller.obtener_codigos_por_insumo(id_insumo)[
            0
        ].get("data", [])
        insumo = insumo_controller.obtener_insumo_por_id(id_insumo)[0].get("data")
        lote = inventario_controller.obtener_lote_por_id(id_lote)[0].get("data")
        if lote:
            lote["f_ingreso"] = parse_date(lote.get("f_ingreso"))
            lote["f_vencimiento"] = parse_date(lote.get("f_vencimiento"))
        return render_template(
            "insumos/registrar_lote.html",
            insumo=insumo,
            lote=lote,
            proveedores=proveedores,
            ordenes=ordenes,
            is_edit=True,
        )
    except Exception as e:
        logger.exception(
            f"Error en editar_lote (GET) para insumo={id_insumo}, lote={id_lote}."
        )
        return "Error interno del servidor", 500


@insumos_bp.route(
    "/catalogo/lote/editar/<string:id_insumo>/<string:id_lote>", methods=["PUT"]
)
@permission_required(accion='consultar_stock_de_lotes')
def actualizar_lote_api(id_insumo, id_lote):
    try:
        inventario_controller = InventarioController()
        if not validate_uuid(id_lote):
            return jsonify({"success": False, "error": "ID de lote inválido"}), 400
        datos_json = request.get_json()
        if not datos_json:
            return jsonify({"success": False, "error": "Cuerpo JSON requerido"}), 400
        response, status = inventario_controller.actualizar_lote_parcial(
            id_lote, datos_json
        )
        return jsonify(response), status
    except Exception as e:
        logger.error(f"Error inesperado en actualizar_lote_api: {e}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@insumos_bp.route(
    "/catalogo/lote/eliminar/<string:id_insumo>/<string:id_lote>", methods=["POST"]
)
@permission_required(accion='consultar_stock_de_lotes')
def eliminar_lote(id_insumo, id_lote):
    try:
        inventario_controller = InventarioController()
        if not validate_uuid(id_lote) or not validate_uuid(id_insumo):
            flash("ID de lote o insumo inválido.", "error")
            return redirect(url_for("insumos_api.obtener_insumos"))
        response, status = inventario_controller.eliminar_lote(id_lote)
        if status == 200:
            flash("Lote eliminado correctamente.", "success")
        else:
            flash(
                response.get("error", "Ocurrió un error al eliminar el lote."), "error"
            )
        return redirect(
            url_for("insumos_api.obtener_insumo_por_id", id_insumo=id_insumo)
        )
    except Exception as e:
        logger.error(f"Error inesperado en eliminar_lote: {e}")
        return redirect(
            url_for("insumos_api.obtener_insumo_por_id", id_insumo=id_insumo)
        )


@insumos_bp.route("/filter", methods=["GET"])
@permission_required(accion='almacen_ver_insumos')
def api_filter_insumos():
    """
    Endpoint de API para el filtrado dinámico de insumos.
    """
    try:
        insumo_controller = InsumoController()
        
        # Recolectar filtros desde los query parameters
        filtros = {
            'busqueda': request.args.get('busqueda', None),
            'stock_status': request.args.get('stock_status', None),
            'categoria': request.args.getlist('categoria'),
            'id_proveedor': request.args.getlist('id_proveedor')
        }
        
        # Limpiar filtros nulos o vacíos
        filtros = {k: v for k, v in filtros.items() if v}
        
        response, status = insumo_controller.obtener_insumos(filtros)
        
        return jsonify(response), status
            
    except Exception as e:
        logger.error(f"Error en api_filter_insumos: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@insumos_bp.route("/", methods=["GET"])
def api_get_insumos():
    """
    Endpoint de API para obtener insumos en formato JSON, con búsqueda y filtro por proveedor.
    """
    try:
        insumo_controller = InsumoController()
        search_query = request.args.get('search', None)
        proveedor_id = request.args.get('proveedor_id', None)
        
        filtros = {}
        if search_query:
            filtros['busqueda'] = search_query
        if proveedor_id:
            filtros['id_proveedor'] = proveedor_id
        
        response, status = insumo_controller.obtener_insumos(filtros)
        
        if status == 200:
            return jsonify(response.get("data", []))
        else:
            return jsonify(response), status
            
    except Exception as e:
        logger.error(f"Error en api_get_insumos: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@insumos_bp.route("/suggestions", methods=["GET"])
@permission_required(accion='almacen_ver_insumos')
def api_get_insumo_suggestions():
    """
    Endpoint de API para obtener sugerencias de insumos para autocompletar.
    """
    try:
        insumo_controller = InsumoController()
        query = request.args.get('q', '')
        
        response, status = insumo_controller.obtener_sugerencias_insumos(query)
        
        return jsonify(response), status
            
    except Exception as e:
        logger.error(f"Error en api_get_insumo_suggestions: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@insumos_bp.route("/stock", methods=["GET"])
@permission_required(accion='almacen_consulta_stock')
def obtener_stock_consolidado():
    try:
        insumo_controller = InsumoController()
        filtros = {k: v for k, v in request.args.items() if v is not None and v != ""}
        response, status = insumo_controller.obtener_con_stock(filtros)
        return jsonify(response), status
    except Exception as e:
        logger.error(f"Error inesperado en obtener_stock_consolidado: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@insumos_bp.route("/catalogo/actualizar-stock/<string:id_insumo>", methods=["POST"])
@permission_required(accion='registrar_ingreso_de_materia_prima')
def actualizar_stock_insumo(id_insumo):
    """
    Endpoint para calcular y actualizar el stock de un insumo.
    """
    try:
        insumo_controller = InsumoController()
        if not validate_uuid(id_insumo):
            return jsonify({"success": False, "error": "ID de insumo inválido"}), 400

        response, status = insumo_controller.actualizar_stock_insumo(id_insumo)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en actualizar_stock_insumo: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500
