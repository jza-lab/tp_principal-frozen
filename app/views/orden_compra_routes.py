from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.controllers.orden_compra_controller import OrdenCompraController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.proveedor_controller import ProveedorController
from app.controllers.insumo_controller import InsumoController
from app.utils.decorators import permission_required
from datetime import datetime

orden_compra_bp = Blueprint("orden_compra", __name__, url_prefix="/compras")

controller = OrdenCompraController()
orden_produccion_controller = OrdenProduccionController()
proveedor_controller = ProveedorController()
insumo_controller = InsumoController()


@orden_compra_bp.route("/")
@permission_required(accion='consultar_ordenes_de_compra')
def listar():
    """Muestra la lista de órdenes de compra."""
    estado = request.args.get("estado")
    filtros = {"estado": estado} if estado else {}
    response, status_code = controller.get_all_ordenes(filtros)
    ordenes = []
    if response.get("success"):
        ordenes_data = response.get("data", [])
        ordenes = sorted(ordenes_data, key=lambda x: x.get("estado") == "RECHAZADA")
    else:
        flash(response.get("error", "Error al cargar las órdenes de compra."), "error")
    titulo = f"Órdenes de Compra ({'Todas' if not estado else estado.replace('_', ' ').title()})"
    return render_template("ordenes_compra/listar.html", ordenes=ordenes, titulo=titulo)


@orden_compra_bp.route("/nueva", methods=["GET", "POST"])
@jwt_required()
@permission_required(accion='crear_orden_de_compra')
def nueva():
    if request.method == "POST":
        usuario_id = get_jwt_identity()
        resultado = controller.crear_orden(request.form, usuario_id)
        if resultado.get("success"):
            flash("Orden de compra creada exitosamente.", "success")
            return redirect(url_for("orden_compra.listar"))
        else:
            flash(
                f"Error al crear la orden: {resultado.get('error', 'Error desconocido')}",
                "error",
            )

    today = datetime.now().strftime("%Y-%m-%d")
    proveedores_resp, _ = proveedor_controller.obtener_proveedores_activos()
    insumos_resp, _ = insumo_controller.obtener_insumos()
    proveedores = proveedores_resp.get("data", [])
    insumos = insumos_resp.get("data", [])
    return render_template(
        "ordenes_compra/formulario.html",
        proveedores=proveedores,
        insumos=insumos,
        today=today,
    )


@orden_compra_bp.route("/detalle/<int:id>")
@permission_required(accion='consultar_ordenes_de_compra')
def detalle(id):
    response_data, status_code = controller.get_orden(id)
    if response_data.get("success"):
        orden = response_data.get("data")
        return render_template("ordenes_compra/detalle.html", orden=orden)
    else:
        flash(response_data.get("error", "Orden de compra no encontrada."), "error")
        return redirect(url_for("orden_compra.listar"))


@orden_compra_bp.route("/<int:id>/aprobar", methods=["POST"])
@jwt_required()
@permission_required(accion='aprobar_orden_de_compra')
def aprobar(id):
    usuario_id = get_jwt_identity()
    resultado = controller.aprobar_orden(id, usuario_id)
    if resultado.get("success"):
        flash("Orden de compra aprobada.", "success")
    else:
        flash(
            f"Error al aprobar: {resultado.get('error', 'Error desconocido')}", "error"
        )
    
    # Obtener el estado desde los query params de la URL
    estado_actual = request.args.get('estado', '')
    
    print(f"DEBUG: Estado a preservar: '{estado_actual}'")
    print(f"DEBUG: Redirigiendo a: {url_for('orden_compra.listar', estado=estado_actual) if estado_actual else url_for('orden_compra.listar')}")
    
    if estado_actual:
        return redirect(url_for("orden_compra.listar", estado=estado_actual))
    return redirect(url_for("orden_compra.listar"))


@orden_compra_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@permission_required(accion='crear_orden_de_compra')
def editar(id):
    if request.method == "POST":
        resultado = controller.actualizar_orden(id, request.form)
        if resultado.get("success"):
            flash("Orden de compra actualizada exitosamente.", "success")
            return redirect(url_for("orden_compra.detalle", id=id))
        else:
            flash(
                f"Error al actualizar la orden: {resultado.get('error', 'Error desconocido')}",
                "error",
            )
            return redirect(url_for("orden_compra.editar", id=id))

    response_data, status_code = controller.get_orden(id)
    if not response_data.get("success"):
        flash("Error al cargar la orden para editar.", "error")
        return redirect(url_for("orden_compra.listar"))
    orden = response_data.get("data")
    proveedores_resp, _ = proveedor_controller.obtener_proveedores_activos()
    insumos_resp, _ = insumo_controller.obtener_insumos()
    proveedores = proveedores_resp.get("data", [])
    insumos = insumos_resp.get("data", [])
    return render_template(
        "ordenes_compra/formulario.html",
        orden=orden,
        proveedores=proveedores,
        insumos=insumos,
    )


@orden_compra_bp.route("/<int:id>/rechazar", methods=["POST"])
@permission_required(accion='rechazar_orden_de_compra')
def rechazar(id):
    motivo = request.form.get("motivo", "No especificado")
    resultado = controller.rechazar_orden(id, motivo)
    if resultado.get("success"):
        flash("Orden de compra rechazada.", "warning")
    else:
        flash(
            f"Error al rechazar: {resultado.get('error', 'Error desconocido')}", "error"
        )
    
    # Obtener el estado desde los query params de la URL
    estado_actual = request.args.get('estado', '')
    if estado_actual:
        return redirect(url_for("orden_compra.listar", estado=estado_actual))
    return redirect(url_for("orden_compra.listar"))


@orden_compra_bp.route("/<int:id>/marcar-en-transito", methods=["POST"])
@permission_required(accion='solicitar_reposicion_de_insumos')
def marcar_en_transito(id):
    resultado = controller.marcar_en_transito(id)
    if resultado.get("success"):
        flash('La orden de compra ha sido marcada como "En Tránsito".', "info")
    else:
        flash(
            f"Error al actualizar el estado: {resultado.get('error', 'Error desconocido')}",
            "error",
        )
    
    # Obtener el estado desde los query params de la URL
    estado_actual = request.args.get('estado', '')
    if estado_actual:
        return redirect(url_for("orden_compra.listar", estado=estado_actual))
    return redirect(url_for("orden_compra.listar"))


@orden_compra_bp.route("/recepcion/<int:orden_id>", methods=["POST"])
@jwt_required()
@permission_required(accion='registrar_ingreso_de_materia_prima')
def procesar_recepcion(orden_id):
    usuario_id = get_jwt_identity()
    resultado = controller.procesar_recepcion(orden_id, request.form, usuario_id, orden_produccion_controller)
    if resultado.get("success"):
        flash(
            "Recepción de la orden procesada exitosamente. Se crearon los lotes en inventario.",
            "success",
        )
    else:
        flash(
            f"Error al procesar la recepción: {resultado.get('error', 'Error desconocido')}",
            "error",
        )
    return redirect(url_for("orden_compra.detalle", id=orden_id))