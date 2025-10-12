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
from app.controllers.inventario_controller import InventarioController
from app.controllers.proveedor_controller import ProveedorController
from app.controllers.orden_compra_controller import OrdenCompraController
from app.controllers.usuario_controller import UsuarioController
from app.permisos import permission_required
from app.utils.validators import validate_uuid
from marshmallow import ValidationError
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

insumos_bp = Blueprint("insumos_api", __name__, url_prefix="/api/insumos")

insumo_controller = InsumoController()
proveedor_controller = ProveedorController()
ordenes_compra_controller = OrdenCompraController()
inventario_controller = InventarioController()
usuario_controller = UsuarioController()


@insumos_bp.route("/catalogo/nuevo", methods=["GET", "POST"])
@permission_required(sector_codigo='ALMACEN', accion='crear')
def crear_insumo():
    try:
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
##@permission_required(sector_codigo='ALMACEN', accion='leer')
def obtener_insumos():
    try:
        filtros = {k: v for k, v in request.args.items() if v is not None and v != ""}
        response, status = insumo_controller.obtener_insumos(filtros)
        insumos = response.get("data", [])
        categorias_response, _ = insumo_controller.obtener_categorias_distintas()
        categorias = categorias_response.get("data", [])

        return render_template(
            "insumos/listar.html", insumos=insumos, categorias=categorias
        )

    except Exception as e:
        logger.error(f"Error inesperado en obtener_insumos: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@insumos_bp.route("/catalogo/<string:id_insumo>", methods=["GET"])
@permission_required(sector_codigo='ALMACEN', accion='leer')
def obtener_insumo_por_id(id_insumo):
    try:
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
@permission_required(sector_codigo='ALMACEN', accion='actualizar')
def actualizar_insumo(id_insumo):
    try:
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
@permission_required(sector_codigo='ALMACEN', accion='eliminar')
def eliminar_insumo(id_insumo):
    try:
        if not validate_uuid(id_insumo):
            return jsonify({"success": False, "error": "ID de insumo inválido"}), 400
        response, status = insumo_controller.eliminar_insumo_logico(id_insumo)
        return jsonify(response), status
    except Exception as e:
        logger.error(f"Error inesperado en eliminar_insumo: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@insumos_bp.route("/catalogo/habilitar/<string:id_insumo>", methods=["POST"])
@permission_required(sector_codigo='ALMACEN', accion='actualizar')
def habilitar_insumo(id_insumo):
    try:
        if not validate_uuid(id_insumo):
            return jsonify({"success": False, "error": "ID de insumo inválido"}), 400
        response, status = insumo_controller.habilitar_insumo(id_insumo)
        return jsonify(response), status
    except Exception as e:
        logger.error(f"Error inesperado en habilitar_insumo: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@insumos_bp.route("/catalogo/lote/nuevo/<string:id_insumo>", methods=["GET", "POST"])
@permission_required(sector_codigo='ALMACEN', accion='crear')
def agregar_lote(id_insumo):
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
@permission_required(sector_codigo='ALMACEN', accion='crear')
def crear_lote(id_insumo):
    try:
        datos_json = request.get_json()
        if not datos_json:
            return jsonify(
                {"success": False, "error": "No se recibieron datos JSON válidos"}
            ), 400
        id = session["usuario_id"]
        response, status = inventario_controller.crear_lote(datos_json, id)
        return jsonify(response), status
    except Exception as e:
        logger.error(f"Error inesperado en crear_lote: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@insumos_bp.route(
    "/catalogo/lote/editar/<string:id_insumo>/<string:id_lote>", methods=["GET"]
)
@permission_required(sector_codigo='ALMACEN', accion='actualizar')
def editar_lote(id_insumo, id_lote):
    def parse_date(date_str):
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        except:
            return date_str

    try:
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
@permission_required(sector_codigo='ALMACEN', accion='actualizar')
def actualizar_lote_api(id_insumo, id_lote):
    try:
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
@permission_required(sector_codigo='ALMACEN', accion='eliminar')
def eliminar_lote(id_insumo, id_lote):
    try:
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


@insumos_bp.route("/stock", methods=["GET"])
@permission_required(sector_codigo='ALMACEN', accion='leer')
def obtener_stock_consolidado():
    try:
        filtros = {k: v for k, v in request.args.items() if v is not None and v != ""}
        response, status = insumo_controller.obtener_con_stock(filtros)
        return jsonify(response), status
    except Exception as e:
        logger.error(f"Error inesperado en obtener_stock_consolidado: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@insumos_bp.route("/catalogo/actualizar-stock/<string:id_insumo>", methods=["POST"])
@permission_required(sector_codigo='ALMACEN', accion='actualizar')
def actualizar_stock_insumo(id_insumo):
    """
    Endpoint para calcular y actualizar el stock de un insumo.
    """
    try:
        if not validate_uuid(id_insumo):
            return jsonify({"success": False, "error": "ID de insumo inválido"}), 400

        response, status = insumo_controller.actualizar_stock_insumo(id_insumo)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en actualizar_stock_insumo: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500
