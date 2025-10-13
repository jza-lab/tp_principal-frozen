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

    # --- INICIO DE LA CORRECCIÓN ---

    # Para PRODUCTOS
    productos_tupla = producto_controller.obtener_todos_los_productos()
    productos_resp = productos_tupla[0] if productos_tupla else {}
    productos = productos_resp.get('data', [])

    # Para SUPERVISORES
    supervisores_tupla = usuario_controller.obtener_todos_los_usuarios(filtros={'role_id': 4})
    # Verificamos si la respuesta no es None antes de intentar acceder a ella
    supervisores_resp = supervisores_tupla[0] if supervisores_tupla else {}
    supervisores = supervisores_resp.get("data", [])

    # --- FIN DE LA CORRECCIÓN ---

    return render_template(
        "ordenes_produccion/formulario.html", productos=productos, supervisores=supervisores
    )


@orden_produccion_bp.route("/nueva/crear", methods=["POST"])
##@permission_required(sector_codigo='PRODUCCION', accion='crear')
def crear():
    try:
        datos_json = request.get_json()
        if not datos_json:
            return jsonify({"success": False, "error": "No se recibieron datos JSON válidos."}), 400

        usuario_id_creador = session.get("usuario_id")
        if not usuario_id_creador:
            return jsonify({"success": False, "error": "Usuario no autenticado."}), 401

        # --- INICIO DE LA CORRECCIÓN DE RUTA ---
        # El controlador puede devolver un dict (éxito) o una tupla (error).
        resultado = controller.crear_orden(datos_json, usuario_id_creador)

        # Verificamos si es una tupla (caso de error)
        if isinstance(resultado, tuple):
            resultado_dict, status_code = resultado
            return jsonify(resultado_dict), status_code
        else:
            # Si no, es un diccionario (caso de éxito)
            return jsonify(resultado), 201 if resultado.get("success") else 400
        # --- FIN DE LA CORRECCIÓN DE RUTA ---

    except Exception as e:
        logger.error(f"Error inesperado en la ruta crear: {e}", exc_info=True)
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
    """Inicia una orden de producción, previa validación de stock."""
    try:
        resultado_dict, status_code = controller.cambiar_estado_orden(id, "EN_PROCESO")

        if resultado_dict.get("success"):
            flash(resultado_dict.get("message", "Orden de producción iniciada correctamente."), "success")
        else:
            # Mostramos el error específico de falta de stock o cualquier otro.
            flash(resultado_dict.get("error", "No se pudo iniciar la orden."), "error")

        return redirect(url_for("orden_produccion.listar"))

    except Exception as e:
        logger.error(f"Error inesperado en la ruta iniciar OP: {e}", exc_info=True)
        flash("Ocurrió un error interno al intentar iniciar la producción.", "danger")
        return redirect(url_for("orden_produccion.listar"))


@orden_produccion_bp.route("/<int:id>/completar", methods=["POST"])
@permission_required(sector_codigo='PRODUCCION', accion='actualizar')
def completar(id):
    """Completa una orden de producción."""
    try:
        resultado_dict, status_code = controller.cambiar_estado_orden(id, "COMPLETADA")

        if resultado_dict.get("success"):
            flash(resultado_dict.get("message", "Orden de producción completada."), "success")
        else:
            flash(resultado_dict.get("error", "No se pudo completar la orden."), "error")

        return redirect(url_for("orden_produccion.detalle", id=id))
    except Exception as e:
        logger.error(f"Error inesperado en la ruta completar OP: {e}", exc_info=True)
        flash("Ocurrió un error interno al intentar completar la producción.", "danger")
        return redirect(url_for("orden_produccion.listar"))


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
##@permission_required(sector_codigo='PRODUCCION', accion='aprobar')
def aprobar(id):
    """Aprueba una orden de producción."""
    try:
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            flash("Error de autenticación. Por favor, inicie sesión.", "danger")
            return redirect(url_for("auth.login"))

        resultado_dict, status_code = controller.aprobar_orden(id, usuario_id)

        # Si el código de estado es 409, devolvemos el JSON al frontend para mostrar el modal.
        if status_code == 409 and not resultado_dict.get("success"):
            return jsonify(resultado_dict), 409

        # FIX: Lógica Robusta para Manejar la Respuesta con Posible None (siempre necesario)
        if isinstance(resultado_dict, dict) and resultado_dict.get("success"):
            message = resultado_dict.get("message", "Orden aprobada exitosamente.")
            
            data = resultado_dict.get("data")
            orden_compra_generada = data.get("orden_compra_generada") if isinstance(data, dict) else None

            if orden_compra_generada and isinstance(orden_compra_generada, dict):
                codigo_oc = orden_compra_generada.get('codigo_oc', 'N/A')
                message = f"Orden de Producción aprobada. Se generó la Orden de Compra {codigo_oc} para cubrir insumos faltantes."
                flash(message, "warning") 
            else:
                flash(message, "success")
        else:
            error_message = resultado_dict.get("error", "Ocurrió un error al aprobar la orden.") if isinstance(resultado_dict, dict) else "Error al procesar la aprobación."
            flash(error_message, "error")

        return redirect(url_for("orden_produccion.listar"))

    except Exception as e:
        logger.error(f"Error inesperado en la ruta aprobar OP: {e}", exc_info=True)
        flash("Ocurrió un error interno al procesar la solicitud.", "danger")
        return redirect(url_for("orden_produccion.listar"))

    except Exception as e:
        logger.error(f"Error inesperado en la ruta aprobar OP: {e}", exc_info=True)
        flash("Ocurrió un error interno al procesar la solicitud.", "danger")
        return redirect(url_for("orden_produccion.listar"))

@orden_produccion_bp.route("/<int:orden_id>/crear_oc_op", methods=["POST"])
@permission_required(sector_codigo='PRODUCCION', accion='aprobar')
def crear_oc_op(orden_id):
    """
    Crea la OC y aprueba la OP después de la confirmación manual del usuario.
    """
    try:
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return jsonify({"success": False, "error": "Usuario no autenticado."}), 401

        datos_json = request.get_json()
        insumos_faltantes = datos_json.get('insumos_faltantes')
        
        if not insumos_faltantes:
            return jsonify({"success": False, "error": "No se recibieron datos de insumos faltantes."}), 400

        # 1. Crear la Orden de Compra (OC)
        resultado_oc = controller.generar_orden_de_compra_automatica(insumos_faltantes, usuario_id)
        resultado_oc_dict = resultado_oc[0] if isinstance(resultado_oc, tuple) else resultado_oc

        if not resultado_oc_dict.get('success'):
            return jsonify({
                "success": False,
                "error": resultado_oc_dict.get('error', 'Fallo al crear la Orden de Compra.')
            }), 500

        orden_compra_creada = resultado_oc_dict.get('data')
        oc_codigo = orden_compra_creada.get('codigo_oc', 'N/A')
        oc_id = orden_compra_creada.get('id')

        # 2. Aprobar y reservar stock (Ahora la reserva no fallará, solo se asocia la OC)
        # Re-obtenemos la OP para trabajar con datos frescos
        orden_result = controller.obtener_orden_por_id(orden_id)
        orden_produccion = orden_result['data']
        
        # Asocia el ID de la OC a la OP
        orden_produccion['orden_compra_id'] = oc_id
        
        # Actualizamos el estado y forzamos la reserva (que no consumirá stock, solo registrará la reserva)
        resultado_aprobacion, status_code = controller.aprobar_orden_con_oc(orden_id, usuario_id, oc_id)


        if resultado_aprobacion.get('success'):
            return jsonify({
                "success": True,
                "message": f"OP aprobada. Se creó la OC {oc_codigo} para insumos. Se recomienda ir a Compras.",
                "oc_codigo": oc_codigo,
                "redirect_url": url_for('orden_compra.listar')
            }), 200
        else:
            return jsonify(resultado_aprobacion), status_code

    except Exception as e:
        logger.error(f"Error inesperado en crear_oc_op: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Error interno del servidor."}), 500


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