from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt, get_current_user
from app.controllers.orden_compra_controller import OrdenCompraController
from app.controllers.usuario_controller import UsuarioController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.proveedor_controller import ProveedorController
from app.controllers.insumo_controller import InsumoController
from app.controllers.reclamo_proveedor_controller import ReclamoProveedorController
from app.utils.decorators import permission_required, permission_any_of
from datetime import datetime
# --- MODIFICACIÓN: Se re-importa ESTADOS_INSPECCION ---
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
        filtros['estado_in'] = ['EN_TRANSITO', 'EN_RECEPCION', 'RECEPCION_INCOMPLETA', 'RECEPCION_COMPLETA', 'RECHAZADA']

    response, status_code = controller.get_all_ordenes(filtros)
    ordenes = []
    if response.get("success"):
        ordenes_data = response.get("data", [])
        
        # Lógica de ordenación especial
        filtro_activo = bool(estado)
        if not filtro_activo:
            # Si no hay filtro, mover las cerradas/rechazadas/canceladas al final
            estados_finales = {'CERRADA', 'RECHAZADA', 'CANCELADA'}
            ordenes = sorted(
                ordenes_data,
                key=lambda x: (
                    1 if x.get("estado") in estados_finales else 0,
                    OC_MAP_STRING_TO_INT.get(x.get("estado"), 999)
                )
            )
        else:
            # Con un filtro activo, usar la ordenación normal
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
    user = get_current_user()
    if hasattr(user, 'rol') and user.rol == 'ADMIN':
        flash('No tiene permisos para crear una orden de compra.', 'error')
        return redirect(url_for('orden_compra.listar'))
    
    controller = OrdenCompraController()
    insumo_controller = InsumoController()
    proveedor_controller = ProveedorController()

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
    insumos_resp, _ = insumo_controller.obtener_insumos()
    insumos = insumos_resp.get("data", [])

    # Obtener proveedores con su rating
    proveedores_resp, _ = proveedor_controller.get_proveedores_con_rating()
    proveedores = proveedores_resp.get("data", [])

    return render_template(
        "ordenes_compra/formulario.html",
        insumos=insumos,
        proveedores=proveedores, # Pasar proveedores con rating a la plantilla
        today=today,
    )


from flask_wtf import FlaskForm

@orden_compra_bp.route("/detalle/<int:id>")
@permission_required(accion='consultar_ordenes_de_compra')
def detalle(id):
    orden_controller = OrdenCompraController()
    reclamo_controller = ReclamoProveedorController()
    csrf_form = FlaskForm()

    response_data, status_code = orden_controller.get_orden(id)
    if not response_data.get("success"):
        flash(response_data.get("error", "Orden de compra no encontrada."), "error")
        return redirect(url_for("orden_compra.listar"))

    orden = response_data.get("data")
    
    # Verificar si ya existe un reclamo para esta orden
    reclamo_existente = None
    reclamo_resp, _ = reclamo_controller.get_reclamo_por_orden(id)
    if reclamo_resp.get("success") and reclamo_resp.get("data"):
        reclamo_existente = reclamo_resp.get("data")

    return render_template(
        "ordenes_compra/detalle.html", 
        orden=orden,
        reclamo_existente=reclamo_existente,
        estados_inspeccion=ESTADOS_INSPECCION,
        csrf_form=csrf_form
    )


@orden_compra_bp.route("/<int:id>/aprobar", methods=["POST"])
@jwt_required()
@permission_required(accion='aprobar_orden_de_compra')
def aprobar(id):
    user = get_current_user()
    if hasattr(user, 'rol') and user.rol == 'ADMIN':
        flash('No tiene permisos para aprobar una orden de compra.', 'error')
        return redirect(url_for('orden_compra.listar'))
        
    controller = OrdenCompraController()
    usuario_id = get_jwt_identity()
    resultado = controller.aprobar_orden(id, usuario_id)
    if resultado.get("success"):
        flash("Orden de compra aprobada.", "success")
    else:
        flash(
            f"Error al aprobar: {resultado.get('error', 'Error desconocido')}", "error"
        )
    
    estado_actual = request.args.get('estado', '')
    
    if estado_actual:
        return redirect(url_for("orden_compra.listar", estado=estado_actual))
    return redirect(url_for("orden_compra.listar"))


@orden_compra_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@permission_required(accion='editar_orden_de_compra')
def editar(id):
    controller = OrdenCompraController()
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
    insumos_resp, _ = insumo_controller.obtener_insumos()
    insumos = insumos_resp.get("data", [])
    return render_template(
        "ordenes_compra/formulario.html",
        orden=orden,
        insumos=insumos,
    )


@orden_compra_bp.route("/<int:id>/rechazar", methods=["POST"])
@permission_any_of('editar_orden_de_compra', 'gestionar_recepcion_orden_compra', 'aprobar_orden_de_compra')
def rechazar(id):
    user = get_current_user()
    if hasattr(user, 'rol') and user.rol == 'ADMIN':
        flash('No tiene permisos para rechazar una orden de compra.', 'error')
        return redirect(url_for('orden_compra.listar'))
        
    controller = OrdenCompraController()
    motivo = request.form.get("motivo", "No especificado")
    resultado = controller.rechazar_orden(id, motivo)
    if resultado.get("success"):
        flash("Orden de compra rechazada.", "warning")
    else:
        flash(
            f"Error al rechazar: {resultado.get('error', 'Error desconocido')}", "error"
        )
    
    estado_actual = request.args.get('estado', '')
    if estado_actual:
        return redirect(url_for("orden_compra.listar", estado=estado_actual))
    return redirect(url_for("orden_compra.listar"))


@orden_compra_bp.route("/<int:id>/marcar-en-recepcion", methods=["POST"])
@permission_required(accion='logistica_recepcion_oc')
def marcar_en_recepcion(id):
    controller = OrdenCompraController()
    resultado, status_code = controller.cambiar_estado_oc(id, 'EN_RECEPCION')
    if status_code == 200:
        flash('La orden de compra ha sido marcada como "En Recepción".', "info")
    else:
        flash(
            f"Error al actualizar el estado: {resultado.get('error', 'Error desconocido')}",
            "error",
        )
    
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
    
    resultado = controller.procesar_recepcion(
        orden_id, 
        request.form, 
        request.files,
        usuario_id, 
        orden_produccion_controller
    )
    
    if resultado.get("success"):
        if resultado.get("partial"):
            flash(
                resultado.get("message", "Recepción parcial completada. Items faltantes."),
                "warning", 
            )
        else:
            flash(
                resultado.get("message", "Recepción de la orden procesada exitosamente."),
                "success",
            )
    else:
        flash(
            resultado.get("error", "Ocurrió un error al procesar la recepción."),
            "error"
        )
    return redirect(url_for("orden_compra.detalle", id=orden_id))


@orden_compra_bp.route("/<int:id_padre>/crear-oc-hija", methods=["POST"])
@jwt_required()
@permission_required(accion='crear_orden_de_compra')
def crear_oc_hija(id_padre):
    controller = OrdenCompraController()
    usuario_id = get_jwt_identity()
    
    csrf_token = request.form.get('csrf_token')
    if not csrf_token:
         flash("Error de seguridad (Falta token CSRF).", "error")
         return redirect(url_for("orden_compra.detalle", id=id_padre))
         
    resultado = controller.crear_oc_hija_desde_fallo(id_padre, usuario_id)
    
    if resultado.get("success"):
        oc_hija = resultado.get('data')
        flash(f"Orden de Compra hija {oc_hija.get('codigo_oc')} creada exitosamente.", "success")
        return redirect(url_for("orden_compra.detalle", id=oc_hija.get('id')))
    else:
        flash(f"Error al crear OC hija: {resultado.get('error', 'Error desconocido')}", "error")
        return redirect(url_for("orden_compra.detalle", id=id_padre))

@orden_compra_bp.route("/<int:orden_id>/reclamo/nuevo", methods=["GET", "POST"])
@jwt_required()
@permission_required(accion='crear_reclamo_proveedor')
def crear_reclamo(orden_id):
    orden_controller = OrdenCompraController()
    reclamo_controller = ReclamoProveedorController()
    
    orden_response, _ = orden_controller.get_orden(orden_id)
    if not orden_response.get("success"):
        flash("Orden de compra no encontrada.", "error")
        return redirect(url_for("orden_compra.listar"))
    
    orden = orden_response.get("data")
    
    problemas_por_item = {}
    motivo_principal = None
    if request.method == "GET":
        problemas_por_item = orden_controller._get_detalles_problemas_por_item(orden)
        # Determinar el motivo principal (el primer problema encontrado que no sea de cantidad)
        for motivo in problemas_por_item.values():
            if motivo and motivo != "CANTIDAD_INCORRECTA":
                motivo_principal = motivo
                break
        # Si no se encontró un motivo de calidad, tomar el primero que exista
        if not motivo_principal:
             for motivo in problemas_por_item.values():
                if motivo:
                    motivo_principal = motivo
                    break

    if request.method == "POST":
        resultado, status_code = reclamo_controller.crear_reclamo_con_items(request.form)
        
        if status_code == 200 and resultado.get("success"):
            flash("Reclamo al proveedor creado exitosamente.", "success")
            return redirect(url_for("orden_compra.detalle", id=orden_id))
        else:
            error_msg = resultado.get('error', 'Error desconocido')
            if isinstance(error_msg, dict):
                formatted_errors = "; ".join([f"{key}: {', '.join(value)}" for key, value in error_msg.items()])
                flash(f"Error de validación: {formatted_errors}", "error")
            else:
                flash(f"Error al crear el reclamo: {error_msg}", "error")

    return render_template(
        "reclamos_proveedor/formulario.html",
        orden=orden,
        problemas_por_item=problemas_por_item,
        motivo_principal=motivo_principal
    )

@orden_compra_bp.route("/proveedores/ratings")
@jwt_required()
@permission_required(accion='consultar_ordenes_de_compra')
def ver_ratings_proveedores():
    """
    Muestra el dashboard de ratings de proveedores.
    """
    proveedor_controller = ProveedorController()
    response, _ = proveedor_controller.get_proveedores_con_rating()
    
    proveedores = []
    if response and response.get("success"):
        proveedores = response.get("data", [])
    else:
        flash("Error al cargar los ratings de los proveedores.", "error")
        
    return render_template("reclamos_proveedor/ratings.html", proveedores=proveedores)

@orden_compra_bp.route("/reclamos")
@jwt_required()
@permission_required(accion='consultar_ordenes_de_compra')
def listar_reclamos():
    reclamo_controller = ReclamoProveedorController()
    proveedor_controller = ProveedorController()

    # Obtener filtro de proveedor de la URL
    proveedor_id = request.args.get('proveedor_id', type=int)
    filtros = {'proveedor_id': proveedor_id} if proveedor_id else {}

    # Obtener reclamos con filtros
    response, _ = reclamo_controller.get_all_reclamos(filtros=filtros)
    reclamos = []
    if response and response.get("success"):
        reclamos_data = response.get("data", [])
        for reclamo in reclamos_data:
            if reclamo.get('created_at'):
                try:
                    reclamo['created_at'] = datetime.fromisoformat(reclamo['created_at'])
                except (ValueError, TypeError):
                    pass
        reclamos = reclamos_data
    else:
        flash(response.get("error", "Error al cargar los reclamos."), "error")

    # Obtener todos los proveedores para el dropdown
    proveedores_resp, _ = proveedor_controller.obtener_proveedores()
    proveedores = proveedores_resp.get('data', [])
        
    return render_template(
        "reclamos_proveedor/listar.html", 
        reclamos=reclamos,
        proveedores=proveedores,
        selected_proveedor=proveedor_id
    )

@orden_compra_bp.route("/reclamos/<int:reclamo_id>")
@jwt_required()
@permission_required(accion='consultar_ordenes_de_compra')
def detalle_reclamo(reclamo_id):
    controller = ReclamoProveedorController()
    response, _ = controller.get_reclamo_with_details(reclamo_id)

    if not response.get("success"):
        flash(response.get("error", "Reclamo no encontrado."), "error")
        return redirect(url_for("orden_compra.listar_reclamos"))

    reclamo = response.get("data")
    # Convertir fechas a objetos datetime para la plantilla
    if reclamo.get('created_at'):
        reclamo['created_at'] = datetime.fromisoformat(reclamo['created_at'])
    if reclamo.get('fecha_cierre'):
        reclamo['fecha_cierre'] = datetime.fromisoformat(reclamo['fecha_cierre'])

    return render_template("reclamos_proveedor/detalle.html", reclamo=reclamo)

@orden_compra_bp.route("/reclamos/<int:reclamo_id>/cerrar", methods=["POST"])
@jwt_required()
@permission_required(accion='crear_reclamo_proveedor') # O un permiso más específico si existe
def cerrar_reclamo(reclamo_id):
    controller = ReclamoProveedorController()
    comentario = request.form.get('comentario_cierre')

    if not comentario:
        flash("El comentario de cierre es obligatorio.", "error")
        return redirect(url_for("orden_compra.detalle_reclamo", reclamo_id=reclamo_id))

    response, _ = controller.cerrar_reclamo(reclamo_id, comentario)

    if response.get("success"):
        flash("El reclamo ha sido cerrado exitosamente.", "success")
    else:
        flash(response.get("error", "Error al cerrar el reclamo."), "error")
    
    return redirect(url_for("orden_compra.detalle_reclamo", reclamo_id=reclamo_id))

from app.utils.estados import ESTADOS_INSPECCION

@orden_compra_bp.route("/reclamos/nuevo", methods=['GET', 'POST'])
@jwt_required()
@permission_required(accion='crear_reclamo_proveedor')
def nuevo_reclamo():
    proveedor_controller = ProveedorController()
    reclamo_controller = ReclamoProveedorController()

    if request.method == 'POST':
        resultado, status_code = reclamo_controller.crear_reclamo_flexible(request.form)
        if status_code == 200 and resultado.get("success"):
            flash("Reclamo creado exitosamente.", "success")
            return redirect(url_for("orden_compra.listar_reclamos"))
        else:
            error_msg = resultado.get('error', 'Error desconocido')
            flash(f"Error al crear el reclamo: {error_msg}", "error")
            # Volver a renderizar el formulario con los datos y el error
            proveedores_resp, _ = proveedor_controller.obtener_proveedores()
            proveedores = proveedores_resp.get('data', [])
            return render_template(
                "reclamos_proveedor/nuevo_reclamo.html",
                proveedores=proveedores,
                motivos_cuarentena=ESTADOS_INSPECCION,
                form_data=request.form
            ), 400

    proveedores_resp, _ = proveedor_controller.obtener_proveedores()
    proveedores = proveedores_resp.get('data', [])
    
    return render_template(
        "reclamos_proveedor/nuevo_reclamo.html",
        proveedores=proveedores,
        motivos_cuarentena=ESTADOS_INSPECCION
    )