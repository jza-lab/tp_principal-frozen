from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from matplotlib.dates import relativedelta
from app.controllers.pedido_controller import PedidoController
from app.controllers.cliente_controller import ClienteController
from app.utils.decorators import permission_required
import re
from datetime import datetime

orden_venta_bp = Blueprint('orden_venta', __name__, url_prefix='/orden-venta')

controller = PedidoController()
cliente_controller = ClienteController()
def _parse_form_data(form_dict):
    """
    Convierte los datos planos del formulario en una estructura anidada para el schema.
    Ej: de 'items-0-producto_id' a {'items': [{'producto_id': ...}]}
    """
    parsed_data = {}
    items_dict = {}

    for key, value in form_dict.items():
        match = re.match(r'items-(\d+)-(\w+)', key)
        if match:
            index = int(match.group(1))
            field = match.group(2)
            if index not in items_dict:
                items_dict[index] = {}
            # Ignorar valores vacíos para no enviar items incompletos
            if value:
                items_dict[index][field] = value
        else:
            # Ignorar valores vacíos para campos principales
            if value:
                parsed_data[key] = value

    # Convertir el diccionario de items a una lista, ignorando items vacíos
    if items_dict:
        parsed_data['items'] = [v for k, v in sorted(items_dict.items()) if v]
    else:
        parsed_data['items'] = []

    return parsed_data

@orden_venta_bp.route('/')
@permission_required(accion='ver_ordenes_venta')
def listar():
    """Muestra la lista de todos los pedidos de venta."""
    estado = request.args.get('estado')
    filtros = {'estado': estado} if estado else {}

    response, status_code = controller.obtener_pedidos(filtros)

    pedidos = []
    if response.get('success'):
        # Ordenar para que los pedidos CANCELADOS aparezcan al final
        todos_los_pedidos = response.get('data', [])
        pedidos = sorted(todos_los_pedidos, key=lambda p: p.get('estado') == 'CANCELADO')
    else:
        flash(response.get('error', 'Error al cargar los pedidos.'), 'error')

    return render_template('orden_venta/listar.html', pedidos=pedidos, titulo="Pedidos de Venta")

@orden_venta_bp.route('/nueva', methods=['GET', 'POST'])
@permission_required(accion='crear_ordenes_venta')
def nueva():
    """Gestiona la creación de un nuevo pedido de venta."""

    # Calculamos la fecha de hoy en formato AAAA-MM-DD
    hoy = datetime.now().strftime('%Y-%m-%d')
    fecha_limite= (datetime.now() + relativedelta(months=3)).strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        json_data = request.get_json()
        if not json_data:
            return jsonify({"success": False, "error": "No se recibieron datos JSON válidos"}), 400

        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return jsonify({"success": False, "error": "Su sesión ha expirado o no está autenticado."}), 401
        
        # Se pasa el usuario_id al controlador.
        response, status_code = controller.crear_pedido_con_items(json_data, usuario_id)

        if status_code < 300: # Éxito (e.g., 201 Created)
                nuevo_pedido_id = response.get('data', {}).get('id')
                
                is_completed_immediately = response.get('data', {}).get('estado_completado_inmediato', False)
                
                if is_completed_immediately:
                    success_message = "STOCK EXISTENTE Y RESERVADO, OV LISTA Y COMPLETADA."
                    redirect_url = url_for('orden_venta.listar') 
                else:
                    success_message = response.get('message', 'Pedido creado con éxito.')
                    redirect_url = url_for('orden_venta.detalle', id=nuevo_pedido_id)

                return jsonify({
                    'success': True,
                    'message': success_message,
                    'redirect_url': redirect_url
                }), 201
        
        else: # Error de validación
                return jsonify({
                    'success': False,
                    'message': response.get('message', 'Error al crear el pedido.'),
                    'errors': response.get('errors', {})
                }), status_code

    # Método GET
    response, status_code = controller.obtener_datos_para_formulario()
    productos = []
    if response.get('success'):
        productos = response.get('data', {}).get('productos', [])
    else:
        flash(response.get('error', 'No se pudieron cargar los datos para el formulario.'), 'error')

    return render_template('orden_venta/formulario.html',
                           productos=productos,
                           pedido=None, cliente=None,
                           is_edit=False,
                           today=hoy,
                           fecha_limite=fecha_limite)

@orden_venta_bp.route('/<int:id>/editar', methods=['GET', 'POST', 'PUT'])
@permission_required(accion='modificar_ordenes_venta')
def editar(id):
    """Gestiona la edición de un pedido de venta existente."""
    
    # --- Verificación de Estado ---
    pedido_resp, _ = controller.obtener_pedido_por_id(id)
    if not pedido_resp.get('success'):
        flash(pedido_resp.get('error', 'Pedido no encontrado.'), 'error')
        return redirect(url_for('orden_venta.listar'))
    
    pedido = pedido_resp.get('data')
    
    # Estados permitidos para la edición
    estados_permitidos = ['PENDIENTE', 'EN_PROCESO']
    
    if pedido.get('estado') not in estados_permitidos:
        mensaje_error = f"No se puede editar el pedido porque su estado es '{pedido.get('estado')}'. Solo se permiten los estados: {', '.join(estados_permitidos)}."
        if request.method == 'PUT':
            return jsonify({"success": False, "error": mensaje_error}), 403
        else:
            flash(mensaje_error, 'error')
            return redirect(url_for('orden_venta.detalle', id=id))
    # -----------------------------

    hoy = datetime.now().strftime('%Y-%m-%d')
    
    if request.method == 'PUT':
        try:
            json_data = request.get_json()
            if not json_data:
                return jsonify({"success": False, "error": "No se recibieron datos JSON válidos"}), 400

            # Se pasa el estado original al controlador para la nueva lógica
            response_data, status_code = controller.actualizar_pedido_con_items(id, json_data, pedido.get('estado'))

            if status_code < 300:  # Éxito
                return jsonify({
                    'success': True,
                    'message': response_data.get('message', 'Pedido actualizado con éxito.'),
                    'redirect_url': url_for('orden_venta.detalle', id=id)
                }), 200
            else:  # Error de validación o de lógica de negocio
                return jsonify({
                    'success': False,
                    'message': response_data.get('message', 'Error al actualizar el pedido.'),
                    'errors': response_data.get('errors', {})
                }), status_code
            
        except Exception as e:
            print(f"Error inesperado en PUT /editar: {e}")
            return jsonify({"success": False, "error": "Ocurrió un error interno en el servidor."}), 500

    # Método GET
    cliente_resp, _ = cliente_controller.obtener_cliente(pedido.get('id_cliente'))
    cliente=cliente_resp.get('data')

    if(cliente and cliente['cuit']):
        cliente['cuit'] = cliente['cuit'].replace('-', '')

    form_data_resp, _ = controller.obtener_datos_para_formulario()


    productos = []
    if form_data_resp.get('success'):
        productos = form_data_resp.get('data', {}).get('productos', [])
    else:
        flash(form_data_resp.get('error', 'Error cargando datos del formulario.'), 'warning')
    
    return render_template('orden_venta/formulario.html',
                           pedido=pedido,
                           productos=productos,is_edit=True, cliente=cliente,
                           today=hoy)

@orden_venta_bp.route('/<int:id>/detalle')
@permission_required(accion='ver_ordenes_venta')
def detalle(id):
    """Muestra la página de detalle de un pedido de venta."""
    response, status_code = controller.obtener_pedido_por_id(id)

    if response.get('success'):
        pedido_data = response.get('data')
        if pedido_data and pedido_data.get('created_at') and isinstance(pedido_data['created_at'], str):
            pedido_data['created_at'] = datetime.fromisoformat(pedido_data['created_at'])
        if pedido_data and pedido_data.get('updated_at') and isinstance(pedido_data['updated_at'], str):
            pedido_data['updated_at'] = datetime.fromisoformat(pedido_data['updated_at'])

        return render_template('orden_venta/detalle.html', pedido=pedido_data)
    else:
        flash(response.get('error', 'Pedido no encontrado.'), 'error')
        return redirect(url_for('orden_venta.listar'))

@orden_venta_bp.route('/<int:id>/cancelar', methods=['POST'])
@permission_required(accion='cancelar_ordenes_venta')
def cancelar(id):
    """Endpoint para cambiar el estado de un pedido a 'CANCELADO'."""
    response, status_code = controller.cancelar_pedido(id)

    if response.get('success'):
        flash(response.get('message', 'Pedido cancelado con éxito.'), 'success')
    else:
        flash(response.get('error', 'Error al cancelar el pedido.'), 'error')

    return redirect(url_for('orden_venta.detalle', id=id))


@orden_venta_bp.route('/<int:id>/completar', methods=['POST'])
@permission_required(accion='modificar_ordenes_venta')
def completar(id):
        """Endpoint para completar el pedido (despacho de stock)."""
        try:
            usuario_id = session.get("usuario_id")
            if not usuario_id:
                flash("Su sesión ha expirado.", "error")
                return redirect(url_for("auth.login"))

            response, status_code = controller.completar_pedido(id, usuario_id)

            if response.get('success'):
                flash(response.get('message', 'Pedido completado con éxito.'), 'success')
            else:
                flash(response.get('error', 'Error al completar el pedido.'), 'error')

            return redirect(url_for('orden_venta.listar'))

        except Exception as e:
            flash(f"Ocurrió un error inesperado al completar el pedido: {str(e)}", 'error')
            return redirect(url_for('orden_venta.detalle', id=id))

@orden_venta_bp.route('/<int:id>/aprobar', methods=['POST'])
@permission_required(accion='aprobar_ordenes_venta')
def aprobar(id):
    """
    Endpoint de API para aprobar un pedido. Devuelve una respuesta JSON.
    """
    try:
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return jsonify({"success": False, "error": "Usuario no autenticado."}), 401

        response, status_code = controller.aprobar_pedido(id, usuario_id)

        if status_code == 202 and response.get('oc_generada'):
            oc_codigo = response['orden_compra_creada']['codigo_oc']
            
            return jsonify({
                "success": True,
                "message": response.get('message'),
                "redirect_url": url_for('orden_compra.listar'),
                "oc_generada": True,
                "oc_codigo": oc_codigo,
                "data": response.get('data')
            }), 202

        return jsonify(response), status_code

    except Exception as e:
        print(f"Error inesperado en la ruta aprobar pedido: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500
