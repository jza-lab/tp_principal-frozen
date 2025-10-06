from venv import logger
from flask import (
    Blueprint,
    jsonify,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)
from marshmallow import ValidationError
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.producto_controller import ProductoController
from app.controllers.etapa_produccion_controller import EtapaProduccionController
from app.controllers.usuario_controller import UsuarioController
from app.controllers.receta_controller import RecetaController
from app.permisos import permission_required
from datetime import date

orden_produccion_bp = Blueprint("orden_produccion", __name__, url_prefix="/ordenes")

controller = OrdenProduccionController()
producto_controller = ProductoController()
etapa_controller = EtapaProduccionController()
usuario_controller = UsuarioController()
receta_controller = RecetaController()


@orden_produccion_bp.route("/")
@permission_required(sector_codigo='PRODUCCION', accion='leer')
def listar():
    """Muestra la lista de órdenes de producción."""
    estado = request.args.get("estado")
    filtros = {"estado": estado} if estado else {}
    response, status_code = controller.obtener_ordenes(filtros)
    ordenes = []
    if response.get("success"):
        ordenes_data = response.get("data", [])
        ordenes = sorted(ordenes_data, key=lambda x: x.get("estado") == "CANCELADA")
    else:
        flash(
            response.get("error", "Error al cargar las órdenes de producción."), "error"
        )
    titulo = f"Órdenes de Producción ({'Todas' if not estado else estado.replace('_', ' ').title()})"
    return render_template(
        "ordenes_produccion/listar.html", ordenes=ordenes, titulo=titulo
    )


@orden_produccion_bp.route("/nueva", methods=["GET", "POST", "PUT"])
@permission_required(sector_codigo='PRODUCCION', accion='crear')
def nueva():
    """Muestra la página para crear una nueva orden de producción."""
    productos = producto_controller.obtener_todos_los_productos()
    operarios = usuario_controller.obtener_todos_los_usuarios()
    return render_template(
        "ordenes_produccion/formulario.html", productos=productos, operarios=operarios
    )


@orden_produccion_bp.route("/nueva/crear", methods=["POST"])
@permission_required(sector_codigo='PRODUCCION', accion='crear')
def crear():
    try:
        datos_json = request.get_json()
        if not datos_json:
            return jsonify(
                {"success": False, "error": "No se recibieron datos JSON válidos."}
            ), 400
        usuario_id_creador = session.get("usuario_id")
        if not usuario_id_creador:
            return jsonify({"success": False, "error": "Usuario no autenticado."}), 401
        resultado = controller.crear_orden(datos_json, usuario_id_creador)
        return jsonify(resultado), 201 if resultado.get("success") else 400
    except ValidationError as e:
        return jsonify(
            {"success": False, "error": "Datos inválidos", "details": e.messages}
        ), 400
    except Exception as e:
        logger.error(f"Error inesperado en crear_orden: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@orden_produccion_bp.route("/modificar/<int:id>", methods=["GET", "POST", "PUT"])
@permission_required(sector_codigo='PRODUCCION', accion='actualizar')
def modificar(id):
    """Gestiona la modificación de una orden de producción."""
    try:
        if request.method in ["POST", "PUT"]:
            datos_json = request.get_json()
            if not datos_json:
                return jsonify(
                    {"success": False, "error": "No se recibieron datos JSON válidos"}
                ), 400
            response, status = controller.actualizar_orden(
                id, datos_json
            )  # Suponiendo que existe este método
            return jsonify(response), status
        orden = controller.obtener_orden_por_id(id).get("data")
        productos = producto_controller.obtener_todos_los_productos()
        operarios = usuario_controller.obtener_todos_los_usuarios()
        return render_template(
            "ordenes_produccion/formulario.html",
            orden_m=orden,
            productos=productos,
            operarios=operarios,
        )
    except Exception as e:
        logger.error(f"Error inesperado en modificar: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@orden_produccion_bp.route("/<int:id>/detalle")
@permission_required(sector_codigo='PRODUCCION', accion='leer')
def detalle(id):
    """Muestra el detalle de una orden de producción."""
    respuesta = controller.obtener_orden_por_id(id)
    if not respuesta.get("success"):
        flash("Orden no encontrada.", "error")
        return redirect(url_for("orden_produccion.listar"))
    orden = respuesta.get("data")
    desglose_response = controller.obtener_desglose_origen(id)
    desglose_origen = desglose_response.get("data", [])
    ingredientes_response = (
        receta_controller.obtener_ingredientes_para_receta(orden.get("receta_id"))
        if orden
        else None
    )
    ingredientes = (
        ingredientes_response.get("data", []) if ingredientes_response else []
    )
    return render_template(
        "ordenes_produccion/detalle.html",
        orden=orden,
        ingredientes=ingredientes,
        desglose_origen=desglose_origen,
    )


@orden_produccion_bp.route("/<int:id>/iniciar", methods=["POST"])
@permission_required(sector_codigo='PRODUCCION', accion='actualizar')
def iniciar(id):
    """Inicia una orden de producción."""
    resultado = controller.cambiar_estado_orden(id, "EN_PROCESO")
    flash(
        resultado.get("message", "Orden iniciada."),
        "success" if resultado.get("success") else "error",
    )
    return redirect(url_for("orden_produccion.listar"))


@orden_produccion_bp.route("/<int:id>/completar", methods=["POST"])
@permission_required(sector_codigo='PRODUCCION', accion='actualizar')
def completar(id):
    """Completa una orden de producción."""
    resultado = controller.cambiar_estado_orden(id, "COMPLETADA")
    flash(
        resultado.get("message", "Orden completada."),
        "success" if resultado.get("success") else "error",
    )
    return redirect(url_for("orden_produccion.detalle", id=id))


@orden_produccion_bp.route("/pendientes")
@permission_required(sector_codigo='PRODUCCION', accion='leer')
def listar_pendientes():
    """Muestra las órdenes pendientes de aprobación."""
    response, _ = controller.obtener_ordenes({"estado": "PENDIENTE"})
    ordenes = response.get("data", [])
    return render_template(
        "ordenes_produccion/listar.html",
        ordenes=ordenes,
        titulo="Órdenes Pendientes de Aprobación",
    )


@orden_produccion_bp.route("/<int:id>/aprobar", methods=["POST"])
@permission_required(sector_codigo='PRODUCCION', accion='aprobar')
def aprobar(id):
    """Aprueba una orden de producción."""
    usuario_id = session.get("usuario_id")
    resultado = controller.aprobar_orden(id, usuario_id)
    flash(
        resultado.get("message", "Orden aprobada."),
        "success" if resultado.get("success") else "error",
    )
    return redirect(url_for("orden_produccion.listar"))


@orden_produccion_bp.route("/<int:id>/rechazar", methods=["POST"])
@permission_required(sector_codigo='PRODUCCION', accion='aprobar')
def rechazar(id):
    """Rechaza una orden de producción."""
    motivo = request.form.get("motivo", "No especificado")
    resultado = controller.rechazar_orden(id, motivo)
    flash(
        resultado.get("message", "Orden rechazada."),
        "warning" if resultado.get("success") else "error",
    )
    return redirect(url_for("orden_produccion.listar"))
