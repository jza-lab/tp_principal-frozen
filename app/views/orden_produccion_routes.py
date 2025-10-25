from venv import logger
from flask import (
    Blueprint,
    jsonify,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.producto_controller import ProductoController
from app.controllers.etapa_produccion_controller import EtapaProduccionController
from app.controllers.usuario_controller import UsuarioController
from app.controllers.receta_controller import RecetaController
from app.controllers.pedido_controller import PedidoController
from app.utils.decorators import roles_required
from app.utils.decorators import permission_required
from datetime import date

orden_produccion_bp = Blueprint("orden_produccion", __name__, url_prefix="/ordenes")

controller = OrdenProduccionController()
producto_controller = ProductoController()
etapa_controller = EtapaProduccionController()
usuario_controller = UsuarioController()
receta_controller = RecetaController()
pedido_controller = PedidoController()


@orden_produccion_bp.route("/")
@permission_required(accion='consultar_ordenes_de_produccion')
def listar():
    """Muestra la lista de órdenes de producción."""
    estado = request.args.get("estado")
    if estado:
        # Normalizar el estado reemplazando espacios con guiones bajos
        estado = estado.replace(" ", "_")
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
    supervisores = []
    if isinstance(supervisores_response, dict) and supervisores_response.get("success"):
        supervisores = supervisores_response.get("data", [])
    elif isinstance(supervisores_response, list):
        supervisores = supervisores_response

    from app.utils.estados import OP_PENDIENTE, OP_EN_ESPERA, OP_APROBADA, OP_EN_PRODUCCION, OP_CONTROL_DE_CALIDAD, OP_COMPLETADA, OP_CANCELADA, OP_RECHAZADA, OP_CONSOLIDADA, OP_PLANIFICADA, OP_EN_LINEA_1, OP_EN_LINEA_2, OP_EN_EMPAQUETADO

    # Lista de estados de OP para los filtros
    estados_op = {
        'PENDIENTE': OP_PENDIENTE,
        'EN_ESPERA': OP_EN_ESPERA,
        'APROBADA': OP_APROBADA,
        'EN_PRODUCCION': OP_EN_PRODUCCION,
        'CONTROL_DE_CALIDAD': OP_CONTROL_DE_CALIDAD,
        'COMPLETADA': OP_COMPLETADA,
        'CANCELADA': OP_CANCELADA,
        'RECHAZADA': OP_RECHAZADA,
        'CONSOLIDADA': OP_CONSOLIDADA,
        'PLANIFICADA': OP_PLANIFICADA,
        'EN_LINEA_1': OP_EN_LINEA_1,
        'EN_LINEA_2': OP_EN_LINEA_2,
        'EN_EMPAQUETADO': OP_EN_EMPAQUETADO
    }

    titulo = f"Órdenes de Producción ({'Todas' if not estado else estado.replace('_', ' ').title()})"
    return render_template(
        "ordenes_produccion/listar.html", ordenes=ordenes, titulo=titulo, supervisores=supervisores, estados_op=estados_op
    )


@orden_produccion_bp.route("/nueva", methods=["GET", "POST", "PUT"])
@permission_required(accion='crear_orden_de_produccion')
def nueva():
    """Muestra la página para crear una nueva orden de producción."""
    productos_tupla = producto_controller.obtener_todos_los_productos()
    productos_resp = productos_tupla[0] if productos_tupla else {}
    productos = productos_resp.get('data', [])

    supervisores_tupla = usuario_controller.obtener_todos_los_usuarios(filtros={'role_id': 4})
    supervisores_resp = supervisores_tupla[0] if supervisores_tupla else {}
    supervisores = supervisores_resp.get("data", [])

    return render_template(
        "ordenes_produccion/formulario.html", productos=productos, supervisores=supervisores
    )


@orden_produccion_bp.route("/nueva/crear", methods=["POST"])
@jwt_required()
@permission_required(accion='crear_orden_de_produccion')
def crear():
    try:
        datos_json = request.get_json()
        if not datos_json:
            return jsonify({"success": False, "error": "No se recibieron datos JSON válidos."}), 400

        usuario_id_creador = get_jwt_identity()
        resultado = controller.crear_orden(datos_json, usuario_id_creador)

        if isinstance(resultado, tuple):
            resultado_dict, status_code = resultado
            return jsonify(resultado_dict), status_code
        else:
            return jsonify(resultado), 201 if resultado.get("success") else 400

    except Exception as e:
        logger.error(f"Error inesperado en la ruta crear: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@orden_produccion_bp.route("/modificar/<int:id>", methods=["GET", "POST", "PUT"])
@permission_required(accion='supervisar_avance_de_etapas')
def modificar(id):
    """Gestiona la modificación de una orden de producción."""
    try:
        if request.method in ["POST", "PUT"]:
            datos_json = request.get_json()
            if not datos_json:
                return jsonify(
                    {"success": False, "error": "No se recibieron datos JSON válidos"}
                ), 400
            response, status = controller.actualizar_orden(id, datos_json)
            return jsonify(response), status
        orden = controller.obtener_orden_por_id(id).get("data")
        productos = producto_controller.obtener_todos_los_productos()
        operarios = usuario_controller.obtener_todos_los_usuarios()


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
            operarios=operarios_list
        )
    except Exception as e:
        print(f"Error inesperado en modificar: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@orden_produccion_bp.route("/<int:id>/detalle")
@permission_required(accion='consultar_ordenes_de_produccion')
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
    pedidos_asociados_resp, status= pedido_controller.obtener_pedidos_por_orden_produccion(id)
    pedidos_asociados=[]
    if pedidos_asociados_resp.get('data') and len(pedidos_asociados_resp.get('data'))>0:
        pedidos_asociados=pedidos_asociados_resp.get('data')

    return render_template(
        "ordenes_produccion/detalle.html",
        orden=orden,
        ingredientes=ingredientes,
        desglose_origen=desglose_origen,
        pedidos_asociados=pedidos_asociados
    )


@orden_produccion_bp.route("/<int:id>/iniciar", methods=["POST"])
@permission_required(accion='supervisar_avance_de_etapas')
def iniciar(id):
    """Inicia una orden de producción, previa validación de stock."""
    try:
        resultado_dict, status_code = controller.cambiar_estado_orden(id, "EN_PROCESO")

        if resultado_dict.get("success"):
            flash(resultado_dict.get("message", "Orden de producción iniciada correctamente."), "success")
        else:
            flash(resultado_dict.get("error", "No se pudo iniciar la orden."), "error")

        return redirect(url_for("orden_produccion.listar"))

    except Exception as e:
        logger.error(f"Error inesperado en la ruta iniciar OP: {e}", exc_info=True)
        flash("Ocurrió un error interno al intentar iniciar la producción.", "danger")
        return redirect(url_for("orden_produccion.listar"))


@orden_produccion_bp.route("/<int:id>/completar", methods=["POST"])
@permission_required(accion='registrar_etapa_de_produccion')
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
@permission_required(accion='consultar_ordenes_de_produccion')
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
@jwt_required()
@permission_required(accion='crear_orden_de_produccion')
def aprobar(id):
    """Aprueba una orden de producción. Devuelve JSON si es una llamada AJAX."""
    try:
        usuario_id = get_jwt_identity()
        # El controller devuelve (response_dict, status_code)
        response = controller.aprobar_orden(id, usuario_id)

        # --- LÓGICA CLAVE: Manejo de Respuesta AJAX vs. Web ---
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Si es AJAX, devolvemos JSON (incluyendo el mensaje detallado o el error 409 con los faltantes)
            status_code = response[1] if isinstance(response, tuple) else (200 if response.get('success') else (409 if response.get('data', {}).get('insumos_faltantes') else 500))
            response_dict = response[0] if isinstance(response, tuple) else response
            return jsonify(response_dict), status_code
        # --- FIN LÓGICA CLAVE ---

        # Lógica para Petición Web Normal (Redirección con Flash)
        if response.get("success"):
            flash(response.get('message', 'Operación realizada con éxito.'), "success")
            if response.get('data', {}).get('oc_generada'):
                # Si se generó una OC, redirigir a la lista de OCs
                return redirect(url_for("orden_compra.listar"))
        else:
            flash(response.get('error', 'Ocurrió un error.'), "error")

        return redirect(url_for("orden_produccion.detalle", id=id))

    except Exception as e:
        logger.error(f"Error inesperado en la ruta aprobar OP: {e}", exc_info=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
             return jsonify({"success": False, "error": "Ocurrió un error interno al procesar la solicitud."}), 500
        flash("Ocurrió un error interno al procesar la solicitud.", "danger")
        return redirect(url_for("orden_produccion.listar"))


@orden_produccion_bp.route("/<int:orden_id>/crear_oc_op", methods=["POST"])
@jwt_required()
@permission_required(accion='crear_orden_de_produccion')
def crear_oc_op(orden_id):
    """
    Crea la OC y aprueba la OP después de la confirmación manual del usuario.
    """
    try:
        usuario_id = get_jwt_identity()
        datos_json = request.get_json()
        insumos_faltantes = datos_json.get('insumos_faltantes')

        if not insumos_faltantes:
            return jsonify({"success": False, "error": "No se recibieron datos de insumos faltantes."}), 400

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

        orden_result = controller.obtener_orden_por_id(orden_id)
        orden_produccion = orden_result['data']

        orden_produccion['orden_compra_id'] = oc_id

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
@permission_required(accion='crear_orden_de_produccion')
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
@permission_required(accion='reasignar_operarios_a_una_orden')
def asignar_supervisor(id):
    """Asigna un supervisor a una orden de producción."""
    supervisor_id = request.form.get("supervisor_id")
    if not supervisor_id:
        flash("Debe seleccionar un supervisor.", "error")
        return redirect(url_for("orden_produccion.listar"))

    response, status_code = controller.asignar_supervisor(id, int(supervisor_id))

    if status_code == 200:
        flash(response.get("message", "Supervisor asignado con éxito."), "success")
    else:
        flash(response.get("error", "Error al asignar supervisor."), "error")

    return redirect(url_for("orden_produccion.listar"))


@orden_produccion_bp.route('/<int:orden_id>/sugerir-inicio', methods=['GET'])
@jwt_required()
def api_sugerir_fecha_inicio(orden_id):
    """
    API para calcular y sugerir la fecha de inicio óptima para una OP.
    """
    usuario_id = get_jwt_identity()
    response, status_code = controller.sugerir_fecha_inicio(orden_id, usuario_id)
    return jsonify(response), status_code

# Ruta para guardar las asignaciones (SIN aprobar)
@orden_produccion_bp.route('/<int:orden_id>/pre-asignar', methods=['POST'])
@jwt_required()
def api_pre_asignar(orden_id):
    data = request.get_json()
    usuario_id = get_jwt_identity()
    response, status_code = controller.pre_asignar_recursos(orden_id, data, usuario_id)
    return jsonify(response), status_code

# NUEVA Ruta para confirmar fecha y aprobar
@orden_produccion_bp.route('/<int:orden_id>/confirmar-inicio', methods=['POST'])
@jwt_required()
def api_confirmar_inicio(orden_id):
    data = request.get_json()
    usuario_id = get_jwt_identity()
    response, status_code = controller.confirmar_inicio_y_aprobar(orden_id, data, usuario_id)
    return jsonify(response), status_code
