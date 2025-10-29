from datetime import date, timedelta
from venv import logger
from flask import Blueprint, jsonify, session, request, redirect, url_for, flash, render_template

from app.controllers.usuario_controller import UsuarioController
from app.controllers.pedido_controller  import PedidoController
from app.controllers.proveedor_controller import ProveedorController
from app.controllers.insumo_controller import InsumoController
from app.controllers.cliente_controller import ClienteController
from app.utils.decorators import permission_required, permission_any_of

# Blueprint para la administración de usuarios
cliente_proveedor = Blueprint('clientes_proveedores', __name__, url_prefix='/administrar')

# Instanciar controladores
proveedor_controller = ProveedorController()
pedido_controller = PedidoController()
insumo_controller = InsumoController()
usuario_controller = UsuarioController()
cliente_controller = ClienteController()

@cliente_proveedor.route('/solicitudes/clientes/')
@permission_required(accion='gestionar_clientes')
def listar_solicitudes_clientes():
    clientes_result, status = cliente_controller.obtener_clientes(filtros={'estado_aprobacion': 'pendiente'})
    
    clientes = clientes_result.get('data', []) if clientes_result.get('success') else []
    
    return render_template('clientes/solicitudes.html', clientes=clientes)

@cliente_proveedor.route('/clientes/')
@permission_required(accion='gestionar_clientes')
def listar_clientes():
    # Extraer todos los filtros de la solicitud (incluye 'busqueda')
    filtros = {k: v for k, v in request.args.items() if v is not None and v != ""}
    clientes_result, status = cliente_controller.obtener_clientes(filtros=filtros)
    
    clientes= clientes_result.get('data', []) if clientes_result.get('success') else []
    
    # Pasar el término de búsqueda actual al template
    busqueda_actual = request.args.get('busqueda', '')

    return render_template('clientes/listar.html', clientes=clientes, busqueda_actual=busqueda_actual)

@cliente_proveedor.route('/clientes/<int:id>')
@permission_required(accion='gestionar_clientes')
def ver_perfil_cliente(id):
    """Muestra el perfil de un cliente específico."""
    cliente_result, status = cliente_controller.obtener_cliente(id)
    cliente= cliente_result.get('data') if cliente_result.get('success') else None
    pedidos_resp, status = pedido_controller.get_ordenes_by_cliente(id)
    if pedidos_resp.get('data'):
        pedidos = pedidos_resp['data']
    else:
        pedidos={}
    return render_template('clientes/perfil.html', cliente=cliente, pedidos=pedidos)

@cliente_proveedor.route('/clientes/nuevo', methods=['GET', 'PUT', 'POST'])
@permission_required(accion='gestionar_clientes')
def nuevo_cliente():
    """
    Gestiona la creación de un nuevo cliente
    """
    try:
        if request.method == 'PUT' or request.method == 'POST':

            datos_json = request.get_json()
            if not datos_json:
                return jsonify(
                    {"success": False, "error": "No se recibieron datos JSON válidos"}
                ), 400
            
            resultado, status = cliente_controller.crear_cliente(datos_json)
            
            return jsonify(resultado), status
    except Exception as e:
        flash(f"Error al crear cliente: {str(e)}", 'error')
    cliente=None
    return render_template('clientes/formulario.html', cliente=cliente)

@cliente_proveedor.route('/buscar_por_cuil/<cliente_cuil>', methods=['GET'])
@permission_required(accion='gestionar_clientes')
def buscar_por_cuil(cliente_cuil):
    """
    Endpoint HTTP que llama a la función obtener_cliente_cuil
    """
    cliente_respuesta, estado = cliente_controller.obtener_cliente_cuil(cliente_cuil) 
    if(cliente_respuesta['success']):
        cliente=cliente_respuesta['data'][0]
        return jsonify(cliente), 200
    if estado == 404:
        # Devolvemos 404 con un mensaje simple. El frontend IGNORARÁ esta respuesta.
        return jsonify({'mensaje': 'Cliente no encontrado'}), 404
    return jsonify(cliente_respuesta), estado

@cliente_proveedor.route('/clientes/<int:id>/editar', methods=['GET', 'PUT', 'POST'])
@permission_required(accion='gestionar_clientes')
def editar_cliente(id):
    """Gestiona la edición de un cliente existente"""
    cliente_result, status = cliente_controller.obtener_cliente(id)
    cliente= cliente_result.get('data') if cliente_result.get('success') else None
    if not cliente:
        return redirect(url_for('clientes_proveedores.listar_clientes'))
    try:
        if request.method == 'PUT' or request.method == 'POST':
            datos_json = request.get_json()
            if not datos_json:
                return jsonify(
                    {"success": False, "error": "No se recibieron datos JSON válidos"}
                ), 400
            
            resultado, status = cliente_controller.actualizar_cliente(id, datos_json)
            
            return jsonify(resultado), status
    except Exception as e:
        flash(f"Error al actualizar el cliente: {str(e)}", 'error')
    return render_template('clientes/formulario.html', cliente=cliente)

@cliente_proveedor.route('/clientes/<int:id>/eliminar', methods=['POST'])
@permission_required(accion='inactivar_entidad')
def eliminar_cliente(id):
    """Desactiva un cliente."""
    try:
        resultado, status = cliente_controller.eliminar_cliente(id)
        return jsonify(resultado), status
    except Exception as e:
        logger.error(f"Error inesperado en eliminar_cliente: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


    
@cliente_proveedor.route('/clientes/<int:id>/habilitar', methods=['POST'])
@permission_required(accion='inactivar_entidad')
def habilitar_cliente(id):
    """Reactiva un cliente."""
    try:
        resultado, status = cliente_controller.habilitar_cliente(id)
        return jsonify(resultado), status
    except Exception as e:
        logger.error(f"Error inesperado en habilitar_proveedor: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@cliente_proveedor.route('/clientes/<int:id>/actualizar-estado', methods=['POST'])
@permission_required(accion='gestionar_clientes')
def actualizar_estado_cliente(id):
    """Actualiza el estado de aprobación de un cliente."""
    nuevo_estado = request.form.get('estado_aprobacion')
    next_page = request.args.get('next')

    if not nuevo_estado:
        flash('No se proporcionó un nuevo estado.', 'error')
        if next_page == 'solicitudes':
            return redirect(url_for('clientes_proveedores.listar_solicitudes_clientes'))
        return redirect(url_for('clientes_proveedores.ver_perfil_cliente', id=id))

    resultado, status = cliente_controller.actualizar_estado_cliente(id, nuevo_estado)
    
    if resultado.get('success'):
        flash(resultado.get('message', 'Estado del cliente actualizado con éxito.'), 'success')
    else:
        flash(resultado.get('error', 'Ocurrió un error al actualizar el estado.'), 'error')

    if next_page == 'solicitudes':
        return redirect(url_for('clientes_proveedores.listar_solicitudes_clientes'))
    return redirect(url_for('clientes_proveedores.ver_perfil_cliente', id=id))

#------------------- Proveedores ------------------#

@cliente_proveedor.route('/proveedores/')
@permission_required(accion='consultar_ordenes_de_compra')
def listar_proveedores():
    # Extraer todos los filtros de la solicitud (incluye 'busqueda')
    filtros = {k: v for k, v in request.args.items() if v is not None and v != ""}
    proveedores_result, status = proveedor_controller.obtener_proveedores(filtros=filtros)

    proveedores= proveedores_result.get('data', []) if proveedores_result.get('success') else []
    
    # Pasar el término de búsqueda actual al template
    busqueda_actual = request.args.get('busqueda', '')

    return render_template('proveedores/listar.html', proveedores=proveedores, busqueda_actual=busqueda_actual)

@cliente_proveedor.route('/proveedores/<int:id>')
@permission_required(accion='consultar_ordenes_de_compra')
def ver_perfil_proveedor(id):
    proveedor_result, status = proveedor_controller.obtener_proveedor(id)
    proveedor= proveedor_result.get('data') if proveedor_result.get('success') else None
    if not proveedor:
        return redirect(url_for('clientes_proveedores.listar_proveedores'))
    
    insumos_asociados_response, status = insumo_controller.obtener_insumos({"id_proveedor": id})
    insumos_asociados = insumos_asociados_response.get('data', []) if insumos_asociados_response.get('success') else []
    return render_template('proveedores/perfil.html', proveedor=proveedor, insumos_asociados=insumos_asociados)

@cliente_proveedor.route('/proveedores/nuevo', methods=['GET', 'POST', 'PUT'])
@permission_required(accion='gestionar_proveedores')
def nuevo_proveedor():
    """
    Gestiona la creación de un nuevo proveedor
    """
    try:
        if request.method == 'PUT' or request.method == 'POST':
            datos_json = request.get_json()
            if not datos_json:
                return jsonify(
                    {"success": False, "error": "No se recibieron datos JSON válidos"}
                ), 400
            
            resultado, status = proveedor_controller.crear_proveedor(datos_json)
            
            return jsonify(resultado), status
    except Exception as e:
        flash(f"Error al actualizar el proveedor: {str(e)}", 'error')

    proveedor = None
    return render_template('proveedores/formulario.html', proveedor=proveedor)

@cliente_proveedor.route('/proveedores/<int:id>/editar', methods=['GET', 'POST', 'PUT'])
@permission_required(accion='gestionar_proveedores')
def editar_proveedor(id):
    """Gestiona la edición de un proveedor existente"""
    proveedor_result, status = proveedor_controller.obtener_proveedor(id)
    proveedor= proveedor_result.get('data') if proveedor_result.get('success') else None

    if not proveedor:
        return redirect(url_for('clientes_proveedores.listar_proveedores'))
    try:
        if request.method == 'PUT' or request.method == 'POST':
            datos_json = request.get_json()
            if not datos_json:
                return jsonify(
                    {"success": False, "error": "No se recibieron datos JSON válidos"}
                ), 400
            
            resultado, status = proveedor_controller.actualizar_proveedor(id, datos_json)
            
            return jsonify(resultado), status
    except Exception as e:
        flash(f"Error al actualizar el proveedor: {str(e)}", 'error')
    return render_template('proveedores/formulario.html', proveedor=proveedor)

@cliente_proveedor.route('/proveedores/<int:id>/eliminar', methods=['POST'])
@permission_required(accion='inactivar_entidad')
def eliminar_proveedor(id):
    """Desactiva un proveedor."""
    try:
        resultado, status = proveedor_controller.eliminar_proveedor(id)
        return jsonify(resultado), status
    except Exception as e:
        logger.error(f"Error inesperado en eliminar_proveedor: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@cliente_proveedor.route('/proveedores/<int:id>/habilitar', methods=['POST'])
@permission_required(accion='inactivar_entidad')
def habilitar_proveedor(id):
    """Reactiva un proveedor."""
    try:
        resultado, status = proveedor_controller.habilitar_proveedor(id)
        return jsonify(resultado), status
    except Exception as e:
        logger.error(f"Error inesperado en habilitar_proveedor: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@cliente_proveedor.route('/clientes/api/buscar/cuil-email', methods=['POST'])
def buscar_cliente_por_cuil_y_email_api():
    """
    Busca un cliente por CUIL/CUIT y Email para precarga de datos.
    Se registra bajo el nombre de endpoint: clientes_proveedores.buscar_cliente_por_cuil_y_email_api
    """
    data = request.get_json()
    cuil = data.get('cuil')
    email = data.get('email')
    

    if not cuil or not email:
        return jsonify({"success": False, "error": "CUIL/CUIT y Email son requeridos."}), 400
    
    try:
        # Llama al nuevo método dentro de ClienteController
        resultado_busqueda, status_code = cliente_controller.buscar_cliente_por_cuit_y_email(cuil, email)
        print(resultado_busqueda)
    except Exception as e:
        logger.error(f"Error interno del servidor en búsqueda segura: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor al buscar datos."}), 500

    if resultado_busqueda.get('success'):
        # La respuesta ya viene serializada desde el controlador
        return jsonify({"success": True, "data": resultado_busqueda.get('data')}), 200
    else:
        return jsonify({"success": False, "error": resultado_busqueda.get('error', 'Credenciales no válidas.')}), status_code