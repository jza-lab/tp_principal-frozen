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
from app.utils.decorators import roles_required
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

    supervisores_response = usuario_controller.obtener_todos_los_usuarios(filtros={'role_id': 4})

    # --- CORRECCIÓN DEL ERROR 'list' object has no attribute 'get' ---
    supervisores = []
    if isinstance(supervisores_response, dict) and supervisores_response.get("success"):
        # Caso esperado: Si es un diccionario exitoso, extrae la lista de datos.
        supervisores = supervisores_response.get("data", [])
    elif isinstance(supervisores_response, list):
        # Caso problemático: Si es una lista directamente, asume que esa es la lista de supervisores.
        supervisores = supervisores_response
    # ------------------------------------------------------------------

    titulo = f"Órdenes de Producción ({'Todas' if not estado else estado.replace('_', ' ').title()})"
    return render_template(
        "ordenes_produccion/listar.html", ordenes=ordenes, titulo=titulo, supervisores=supervisores
    )


@orden_produccion_bp.route("/nueva", methods=["GET", "POST", "PUT"])
##@permission_required(sector_codigo='PRODUCCION', accion='crear')
def nueva():
    """Muestra la página para crear una nueva orden de producción."""
    productos = producto_controller.obtener_todos_los_productos()
    supervisores_response = usuario_controller.obtener_todos_los_usuarios(filtros={'role_id': 4})

    # --- CORRECCIÓN DEL ERROR 'list' object has no attribute 'get' ---
    supervisores = []
    if isinstance(supervisores_response, dict) and supervisores_response.get("success"):
        supervisores = supervisores_response.get("data", [])
    elif isinstance(supervisores_response, list):
        supervisores = supervisores_response
    # ------------------------------------------------------------------

    return render_template(
        "ordenes_produccion/formulario.html", productos=productos, supervisores=supervisores
    )


@orden_produccion_bp.route("/nueva/crear", methods=["POST"])
##@permission_required(sector_codigo='PRODUCCION', accion='crear')
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
        # Reemplazado venv.logger por print o logging estándar
        print(f"Error inesperado en crear_orden: {str(e)}")
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

        # FIX para operarios en modificar (ya que también llama a obtener_todos_los_usuarios)
        # Asumimos que aquí el problema no ocurrió, pero mejor prevenir
        if isinstance(operarios, list):
            operarios_list = operarios
        elif isinstance(operarios, dict):
             operarios_list = operarios.get("data", [])
        else:
             operarios_list = []

        return render_template(
            "ordenes_produccion/formulario.html",
            orden_m=orden,
            productos=productos,
            operarios=operarios_list,
        )
    except Exception as e:
        # Reemplazado venv.logger por print o logging estándar
        print(f"Error inesperado en modificar: {str(e)}")
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
        ingredientes_response.get("data", []) if ingredientes_response and isinstance(ingredientes_response, dict) else []
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


@orden_produccion_bp.route("/<int:id>/asignar_supervisor", methods=["POST"])
@roles_required(allowed_roles=["SUPERVISOR", "GERENTE"])
def asignar_supervisor(id):
    """Asigna un supervisor a una orden de producción."""
    supervisor_id = request.form.get("supervisor_id")
    if not supervisor_id:
        flash("Debe seleccionar un supervisor.", "error")
        return redirect(url_for("orden_produccion.listar"))

    # Nota: El error de la base de datos ('column... does not exist') que viste antes
    # no está en este archivo, sino dentro de controller.asignar_supervisor.
    # El error de tipo 'AttributeError' sí fue arreglado aquí.
    response, status_code = controller.asignar_supervisor(id, int(supervisor_id))

    if status_code == 200:
        flash(response.get("message", "Supervisor asignado con éxito."), "success")
    else:
        # Se muestra el mensaje de error de la respuesta, que puede ser el de PostgreSQL
        flash(response.get("error", "Error al asignar supervisor."), "error")

    return redirect(url_for("orden_produccion.listar"))
