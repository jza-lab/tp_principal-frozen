import os
import random
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.controllers.pedido_controller import PedidoController
from app.controllers.cliente_controller import ClienteController
from app.utils.decorators import permission_required
import re
from datetime import datetime
import base64
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
@permission_required(accion='consultar_ordenes_de_venta')
def listar():
    """Muestra la lista de todos los pedidos de venta con ordenamiento por estado."""
    estado = request.args.get('estado')
    filtros = {'estado': estado} if estado else {}

    response, _ = controller.obtener_pedidos(filtros)
    pedidos = []

    if response.get('success'):
        todos_los_pedidos = response.get('data', [])
        # --- LÓGICA DE ORDENAMIENTO POR ESTADO ---
        estado_orden = {
            'PENDIENTE': 1,
            'PLANIFICACION': 2,
            'EN_PROCESO': 3,
            'LISTO_PARA_ARMAR': 4,
            'LISTO_PARA_ENTREGAR': 5,
            'COMPLETADO': 6,
            'CANCELADO': 7
        }
        pedidos = sorted(todos_los_pedidos, key=lambda p: estado_orden.get(p.get('estado'), 99))
    else:
        flash(response.get('error', 'Error al cargar los pedidos.'), 'error')

    return render_template('orden_venta/listar.html', pedidos=pedidos, titulo="Pedidos de Venta")

@orden_venta_bp.route('/nueva', methods=['GET', 'POST'])
@jwt_required()
@permission_required(accion='crear_orden_de_venta')
def nueva():
    """Gestiona la creación de un nuevo pedido de venta."""
    hoy = datetime.now().strftime('%Y-%m-%d')

    if request.method == 'POST':
        json_data = request.get_json()
        if not json_data:
            return jsonify({"success": False, "error": "Datos no válidos"}), 400

        usuario_id = get_jwt_identity()
        response, status_code = controller.crear_pedido_con_items(json_data, usuario_id)

        if status_code < 300:
            nuevo_pedido = response.get('data', {})
            redirect_url = url_for('orden_venta.detalle', id=nuevo_pedido.get('id'))
            return jsonify({'success': True, 'message': response.get('message'), 'redirect_url': redirect_url}), 201
        else:
            return jsonify({'success': False, 'message': response.get('message', 'Error al crear el pedido.')}), status_code

    # Método GET
    response, _ = controller.obtener_datos_para_formulario()
    productos = response.get('data', {}).get('productos', [])
    return render_template('orden_venta/formulario.html', productos=productos, pedido=None, is_edit=False, today=hoy)

@orden_venta_bp.route('/<int:id>/editar', methods=['GET', 'POST', 'PUT'])
@permission_required(accion='modificar_orden_de_venta')
def editar(id):
    """Gestiona la edición de un pedido. Solo permitido en PENDIENTE y PLANIFICACION."""
    pedido_resp, _ = controller.obtener_pedido_por_id(id)
    if not pedido_resp.get('success'):
        flash('Pedido no encontrado.', 'error')
        return redirect(url_for('orden_venta.listar'))

    pedido = pedido_resp.get('data')
    estados_permitidos = ['PENDIENTE', 'PLANIFICACION']


    cliente_resp, _ = cliente_controller.obtener_cliente(pedido.get('id_cliente'))
    cliente= cliente_resp.get('data')
    cuit = cliente['cuit']
    cliente['cuit']= cuit.replace('-', '')

    if pedido.get('estado') not in estados_permitidos:
        flash(f"No se puede editar un pedido en estado '{pedido.get('estado')}'.", 'warning')
        return redirect(url_for('orden_venta.detalle', id=id))

    if request.method == 'PUT':
        json_data = request.get_json()
        if not json_data:
            return jsonify({"success": False, "error": "Datos no válidos"}), 400

        response_data, status_code = controller.actualizar_pedido_con_items(id, json_data, pedido.get('estado'))
        if status_code < 300:
            return jsonify({'success': True, 'message': 'Pedido actualizado.', 'redirect_url': url_for('orden_venta.detalle', id=id)}), 200
        else:
            return jsonify({'success': False, 'message': response_data.get('message')}), status_code

    # Método GET
    hoy = datetime.now().strftime('%Y-%m-%d')
    form_data_resp, _ = controller.obtener_datos_para_formulario()
    productos = form_data_resp.get('data', {}).get('productos', [])
    return render_template('orden_venta/formulario.html', pedido=pedido, productos=productos, is_edit=True, today=hoy, cliente = cliente)

@orden_venta_bp.route('/<int:id>/detalle')
@permission_required(accion='consultar_ordenes_de_venta')
def detalle(id):
    """Muestra la página de detalle de un pedido de venta."""
    response, _ = controller.obtener_pedido_por_id(id)
    if response.get('success'):
        pedido_data = response.get('data')
        # --- FIX: Convertir strings de fecha a objetos datetime ---
        if pedido_data and pedido_data.get('created_at') and isinstance(pedido_data['created_at'], str):
            pedido_data['created_at'] = datetime.fromisoformat(pedido_data['created_at'])
        if pedido_data and pedido_data.get('updated_at') and isinstance(pedido_data['updated_at'], str):
            pedido_data['updated_at'] = datetime.fromisoformat(pedido_data['updated_at'])
        return render_template('orden_venta/detalle.html', pedido=pedido_data)
    else:
        flash(response.get('error', 'Pedido no encontrado.'), 'error')
        return redirect(url_for('orden_venta.listar'))

@orden_venta_bp.route('/<int:id>/cancelar', methods=['POST'])
@permission_required(accion='modificar_orden_de_venta')
def cancelar(id):
    """Endpoint para cambiar el estado de un pedido a 'CANCELADO'."""
    response, _ = controller.cancelar_pedido(id)
    if response.get('success'):
        flash(response.get('message'), 'success')
    else:
        flash(response.get('error'), 'error')
    return redirect(url_for('orden_venta.detalle', id=id))

@orden_venta_bp.route('/<int:id>/planificar', methods=['POST'])
@permission_required(accion='aprobar_orden_de_venta')
def planificar(id):
    """Pasa el pedido a estado de PLANIFICACION, guardando la fecha estimada."""
    fecha_estimativa = request.form.get('fecha_estimativa_proceso')
    if not fecha_estimativa:
        flash("Debe seleccionar una fecha estimada de proceso.", "error")
        return redirect(url_for('orden_venta.detalle', id=id))

    response, _ = controller.planificar_pedido(id, fecha_estimativa)
    if response.get('success'):
        flash(response.get('message'), 'success')
    else:
        flash(response.get('error'), 'error')
    return redirect(url_for('orden_venta.detalle', id=id))

@orden_venta_bp.route('/<int:id>/iniciar_proceso', methods=['POST'])
@jwt_required()
@permission_required(accion='aprobar_orden_de_venta')
def iniciar_proceso(id):
    """Pasa el pedido a EN PROCESO y crea las OPs."""
    usuario_id = get_jwt_identity()
    response, _ = controller.iniciar_proceso_pedido(id, usuario_id)
    if response.get('success'):
        flash(response.get('message'), 'success')
    else:
        flash(response.get('error'), 'error')
    return redirect(url_for('orden_venta.detalle', id=id))

@orden_venta_bp.route('/<int:id>/preparar_entrega', methods=['POST'])
@jwt_required()
@permission_required(accion='modificar_orden_de_venta')
def preparar_entrega(id):
    """Pasa el pedido a LISTO PARA ENTREGAR y descuenta stock."""
    usuario_id = get_jwt_identity()
    response, _ = controller.preparar_para_entrega(id, usuario_id)
    if response.get('success'):
        flash(response.get('message'), 'success')
    else:
        flash(response.get('error'), 'error')
    return redirect(url_for('orden_venta.detalle', id=id))

@orden_venta_bp.route('/<int:id>/completar', methods=['POST'])
@jwt_required()
@permission_required(accion='modificar_orden_de_venta')
def completar(id):
    """Endpoint para marcar un pedido como COMPLETADO."""
    usuario_id = get_jwt_identity()
    # Llama al NUEVO y correcto método del controlador
    response, _ = controller.marcar_como_completado(id, usuario_id)

    if response.get('success'):
        flash(response.get('message'), 'success')
    else:
        flash(response.get('error'), 'error')

    return redirect(url_for('orden_venta.detalle', id=id))

@orden_venta_bp.route('/api/generar-proforma', methods=['POST'])
def generar_proforma_api():
    """
    API endpoint to generate a proforma invoice HTML from JSON data
    without creating a persistent order.
    """
    pedido_data = request.get_json()

    if not pedido_data or 'id_cliente' not in pedido_data:
        return jsonify({'success': False, 'error': 'Datos incompletos.'}), 400
    # Get client data
    cliente_resp, _ = cliente_controller.obtener_cliente(pedido_data['id_cliente'])
    if not cliente_resp.get('success'):
        return jsonify({'success': False, 'error': 'Cliente no encontrado.'}), 404
    cliente = cliente_resp.get('data')

    # Get all products to embed their names in the items
    productos_resp, _ = controller.obtener_datos_para_formulario()
    todos_los_productos = {p['id']: p for p in productos_resp.get('data', {}).get('productos', [])}

    # Enrich items with product details
    subtotal_neto = 0
    for item in pedido_data.get('items', []):
        producto = todos_los_productos.get(item.get('producto_id'))
        
        if producto:
            nombre_producto=producto['nombre']
            item['producto_nombre'] = producto
    
    print("-------------------------")
    print(pedido_data)
    print("-------------------------")
    
    # Calculate IVA and Total
    iva = subtotal_neto * 0.21 if cliente.get('condicion_iva') == '1' else 0
    total = subtotal_neto + iva


    pedido_data['subtotal_neto'] = subtotal_neto
    pedido_data['iva'] = iva
    pedido_data['total'] = total
    pedido_data['cliente'] = cliente

    if(pedido_data.get('usar_direccion_alternativa')):
        direccion_a_usar = pedido_data.get('direccion_entrega')
    else:
        direccion_a_usar = cliente.get('direccion')
    
    pedido_data['direccion'] = direccion_a_usar
   
    # Add fake emitter data for proforma
    pedido_data['emisor'] = {
        'ingresos_brutos': '20-12345678-3',
        'inicio_actividades': '2020-01-01',}
    # Render the proforma template
    rendered_html = render_template(
        'orden_venta/factura_proforma_pedido.html',
        pedido=pedido_data,
        cliente=cliente
    )
    return jsonify({'success': True, 'html': rendered_html})

@orden_venta_bp.route('/api/<int:id>/generar_factura_html', methods=['GET'])
@permission_required(accion='consultar_ordenes_de_venta')
def generar_factura_html(id):

    """
    Ruta API para obtener el contenido HTML PÚRO de la factura.
    """
    response, status_code = controller.obtener_pedido_por_id(id)

    if status_code != 200:
        return jsonify({'success': False, 'error': 'Pedido no encontrado para generar factura.'}), 404

    pedido_data = response.get('data')
    if pedido_data:
        pedido_data['emisor'] = {
            'ingresos_brutos': '20-12345678-3',
            'inicio_actividades': '2020-01-01',
            'cae': ''.join([str(random.randint(0, 9)) for _ in range(14)]),
            'vencimiento_cae': '2025-10-31'
        }

    cliente_resp, _= cliente_controller.obtener_cliente(pedido_data['id_cliente'])
    cliente= cliente_resp['data']
    # Convertir las fechas a objetos datetime si son strings ISO (necesario para strftime en Jinja)
    if pedido_data and pedido_data.get('created_at') and isinstance(pedido_data['created_at'], str):
        try:
            pedido_data['created_at'] = datetime.fromisoformat(pedido_data['created_at'])
        except ValueError:
            pass
    if pedido_data['estado'] == 'PENDIENTE':
        rendered_html = render_template('orden_venta/factura_proforma_pedido.html', pedido=pedido_data, cliente=cliente)
    else:
        if cliente['condicion_iva'] == '1':
            # Renderiza la plantilla sin la maquetación base
            rendered_html = render_template('orden_venta/factura_a_pedido.html', pedido=pedido_data, cliente=cliente)
        else:
            rendered_html = render_template('orden_venta/factura_b_pedido.html', pedido=pedido_data, cliente=cliente)

    return jsonify({
        'success': True,
        'html': rendered_html
    }), 200

@orden_venta_bp.route('/nueva/cliente/pasos', methods=['GET'])
def nueva_cliente_pasos():
    """
    Ruta para el formulario de creación de pedidos en dos pasos (vista de cliente).
    """
    hoy = datetime.now().strftime('%Y-%m-%d')
    # Verificar si el cliente está logueado y si es nuevo
    cliente_id = session.get('cliente_id')
    es_cliente_nuevo = True
    if cliente_id:
        es_cliente_nuevo = not cliente_controller.cliente_tiene_pedidos_previos(cliente_id)

    
    response, _ = controller.obtener_datos_para_formulario()
    productos = response.get('data', {}).get('productos', [])
    
    # Usamos el nuevo template sin includes
    return render_template('orden_venta/formulario_cliente_pasos.html', 
                            productos=productos, 
                            pedido=None, 
                            is_edit=False, 
                            today=hoy,
                            cliente={},
                            es_cliente_nuevo=es_cliente_nuevo)