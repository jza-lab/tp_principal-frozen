import os
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, session, jsonify
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
@permission_required(accion='ver_ordenes_venta')
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
@permission_required(accion='crear_ordenes_venta')
def nueva():
    """Gestiona la creación de un nuevo pedido de venta."""
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        json_data = request.get_json()
        if not json_data:
            return jsonify({"success": False, "error": "Datos no válidos"}), 400

        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return jsonify({"success": False, "error": "Sesión expirada"}), 401
        
        response, status_code = controller.crear_pedido_con_items(json_data)

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

@orden_venta_bp.route('/<int:id>/editar', methods=['GET', 'PUT'])
@permission_required(accion='modificar_ordenes_venta')
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
@permission_required(accion='ver_ordenes_venta')
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
@permission_required(accion='cancelar_ordenes_venta')
def cancelar(id):
    """Endpoint para cambiar el estado de un pedido a 'CANCELADO'."""
    response, _ = controller.cancelar_pedido(id)
    if response.get('success'):
        flash(response.get('message'), 'success')
    else:
        flash(response.get('error'), 'error')
    return redirect(url_for('orden_venta.detalle', id=id))

@orden_venta_bp.route('/<int:id>/planificar', methods=['POST'])
@permission_required(accion='aprobar_ordenes_venta')
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
@permission_required(accion='aprobar_ordenes_venta')
def iniciar_proceso(id):
    """Pasa el pedido a EN PROCESO y crea las OPs."""
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        flash("Faltan datos para iniciar el proceso.", "error")
        return redirect(url_for('orden_venta.detalle', id=id))

    response, _ = controller.iniciar_proceso_pedido(id, usuario_id)
    if response.get('success'):
        flash(response.get('message'), 'success')
    else:
        flash(response.get('error'), 'error')
    return redirect(url_for('orden_venta.detalle', id=id))

@orden_venta_bp.route('/<int:id>/preparar_entrega', methods=['POST'])
@permission_required(accion='modificar_ordenes_venta')
def preparar_entrega(id):
    """Pasa el pedido a LISTO PARA ENTREGAR y descuenta stock."""
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        flash("Sesión expirada.", "error")
        return redirect(url_for("auth.login"))
    
    response, _ = controller.preparar_para_entrega(id, usuario_id)
    if response.get('success'):
        flash(response.get('message'), 'success')
    else:
        flash(response.get('error'), 'error')
    return redirect(url_for('orden_venta.detalle', id=id))

@orden_venta_bp.route('/<int:id>/completar', methods=['POST'])
@permission_required(accion='modificar_ordenes_venta')
def completar(id):
    """Finaliza el pedido, pasándolo a COMPLETADO."""
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        flash("Sesión expirada.", "error")
        return redirect(url_for("auth.login"))

    response, _ = controller.completar_pedido(id, usuario_id)
    if response.get('success'):
        flash(response.get('message'), 'success')
    else:
        flash(response.get('error'), 'error')
    return redirect(url_for('orden_venta.listar'))


@orden_venta_bp.route('/api/<int:id>/generar_factura_html', methods=['GET'])
@permission_required(accion='ver_ordenes_venta')
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
            'cae': '00000000000000', # Valores de ejemplo o obtenidos de otra fuente
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