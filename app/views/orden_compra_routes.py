from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.controllers.orden_compra_controller import OrdenCompraController
from app.controllers.usuario_controller import UsuarioController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.proveedor_controller import ProveedorController
from app.controllers.insumo_controller import InsumoController
from app.utils.decorators import permission_required, permission_any_of
from datetime import datetime
from app.utils.estados import OC_FILTROS_UI, OC_MAP_STRING_TO_INT, ESTADOS_INSPECCION

orden_compra_bp = Blueprint("orden_compra", __name__, url_prefix="/compras")


@orden_compra_bp.route("/")
@jwt_required()
@permission_required(accion='consultar_ordenes_de_compra')
def listar():
    """Muestra la lista de órdenes de compra."""
    controller = OrdenCompraController()
    estado = request.args.get("estado")
    filtros = {"estado": estado} if estado else {}
    
    # Obtener rol del usuario
    claims = get_jwt()
    rol_usuario = claims.get('roles', [])[0] if claims.get('roles') else None

    # Si es SUPERVISOR_CALIDAD y no hay un filtro de estado específico,
    # mostrar solo los estados relevantes para Calidad.
    if rol_usuario == 'SUPERVISOR_CALIDAD' and not estado:
        filtros['estado_in'] = ['EN TRANSITO', 'RECEPCION INCOMPLETA', 'RECEPCION COMPLETA', 'RECHAZADA']

    response, status_code = controller.get_all_ordenes(filtros)
    ordenes = []
    if response.get("success"):
        ordenes_data = response.get("data", [])
        ordenes = sorted(ordenes_data, key=lambda x: OC_MAP_STRING_TO_INT.get(x.get("estado"), 999))
    else:
        flash(response.get("error", "Error al cargar las órdenes de compra."), "error")
    
    titulo = f"Órdenes de Compra ({'Todas' if not estado else estado.replace('_', ' ').title()})"
    
    return render_template("ordenes_compra/listar.html", 
                           ordenes=ordenes, 
                           titulo=titulo, 
                           filtros_ui=OC_FILTROS_UI)


@orden_compra_bp.route("/nueva", methods=["GET", "POST"])
@jwt_required()
@permission_required(accion='crear_orden_de_compra')
def nueva():
    controller = OrdenCompraController()
    proveedor_controller = ProveedorController()
    insumo_controller = InsumoController()
    if request.method == "POST":
        usuario_id = get_jwt_identity()
        resultado = controller.crear_orden_desde_form(request.form, usuario_id)
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


from app.controllers.inventario_controller import InventarioController
from flask_wtf import FlaskForm

@orden_compra_bp.route("/detalle/<int:id>")
@permission_required(accion='consultar_ordenes_de_compra')
def detalle(id):
    orden_controller = OrdenCompraController()
    inventario_controller = InventarioController()
    csrf_form = FlaskForm()

    response_data, status_code = orden_controller.get_orden(id)
    if not response_data.get("success"):
        flash(response_data.get("error", "Orden de compra no encontrada."), "error")
        return redirect(url_for("orden_compra.listar"))

    orden = response_data.get("data")
    lotes = []

    # La lógica para calcular los totales originales ahora está centralizada en el OrdenCompraController.
    # La plantilla recibe directamente los campos `subtotal_original`, `iva_original` y `total_original`.
    
    # Si la orden está en control de calidad, buscamos sus lotes para inspección
    if orden and orden.get('estado') == 'EN_CONTROL_CALIDAD':
        codigo_oc = orden.get('codigo_oc')
        if not codigo_oc:
            flash('La orden no tiene un código válido para buscar sus lotes.', 'danger')
        else:
            # Usamos el método existente en el controlador de inventario
            documento_ingreso = codigo_oc if codigo_oc.startswith('OC-') else f"OC-{codigo_oc}"
            lotes_result, _ = inventario_controller.obtener_lotes_para_vista(
                filtros={'documento_ingreso': documento_ingreso}
            )
            if not lotes_result.get('success'):
                flash('Error al obtener los lotes de la orden para inspección.', 'danger')
            else:
                lotes = lotes_result.get('data', [])

    return render_template(
        "ordenes_compra/detalle.html", 
        orden=orden,
        lotes=lotes,
        estados_inspeccion=ESTADOS_INSPECCION,
        csrf_form=csrf_form
    )


@orden_compra_bp.route("/<int:id>/aprobar", methods=["POST"])
@jwt_required()
@permission_required(accion='aprobar_orden_de_compra')
def aprobar(id):
    controller = OrdenCompraController()
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
@permission_required(accion='editar_orden_de_compra')
def editar(id):
    controller = OrdenCompraController()
    proveedor_controller = ProveedorController()
    insumo_controller = InsumoController()
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
@permission_any_of('editar_orden_de_compra', 'gestionar_recepcion_orden_compra')
def rechazar(id):
    controller = OrdenCompraController()
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
@permission_required(accion='logistica_recepcion_oc')
def marcar_en_transito(id):
    controller = OrdenCompraController()
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
@permission_any_of('logistica_recepcion_oc', 'gestionar_recepcion_orden_compra')
def procesar_recepcion(orden_id):
    controller = OrdenCompraController()
    orden_produccion_controller = OrdenProduccionController()
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
    return redirect(url_for("orden_compra.listar"))


@orden_compra_bp.route("/<int:id>/iniciar-calidad", methods=["POST"])
@jwt_required()
@permission_required(accion='realizar_control_de_calidad_insumos')
def iniciar_calidad(id):
    """
    Endpoint para que el supervisor de calidad mueva una orden a 'EN CONTROL DE CALIDAD'.
    """
    controller = OrdenCompraController()
    usuario_id = get_jwt_identity()
    resultado = controller.iniciar_control_de_calidad(id, usuario_id)
    
    if resultado.get("success"):
        flash("La orden se ha movido a Control de Calidad.", "success")
    else:
        flash(f"Error: {resultado.get('error', 'No se pudo iniciar el control de calidad.')}", "danger")
        
    return redirect(url_for("orden_compra.detalle", id=id))

