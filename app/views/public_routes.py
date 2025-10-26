from flask import Blueprint, flash, redirect, render_template, request, jsonify, session, url_for
from datetime import datetime, timedelta
from app.controllers.pedido_controller import PedidoController
from app.controllers.cliente_controller import ClienteController
from flask_wtf import FlaskForm

public_bp = Blueprint('public', __name__, url_prefix='/public')

class CSRFOnlyForm(FlaskForm):
    pass

@public_bp.route('/')
def index():
    return render_template('public/index.html')

@public_bp.route('/about')
def about():
    return render_template('public/about.html')

@public_bp.route('/clients')
def clients():
    return render_template('public/clients.html')

@public_bp.route('/produccion')
def production():
    return render_template('public/produccion.html')

@public_bp.route('/faq')
def faq():
    """Muestra la página de preguntas frecuentes."""
    return render_template('public/faq.html')

@public_bp.route('/hace-tu-pedido')
def hacer_pedido():
    """
    Muestra el formulario para que un cliente haga un pedido desde la web pública.
    """
    # if 'cliente_id' not in session:
    #     flash('Por favor, inicia sesión para realizar un pedido.', 'info')
    #     return redirect(url_for('cliente.login'))

    # if not session.get('cliente_aprobado'):
    #     flash('Tu cuenta está pendiente de aprobación. No puedes realizar pedidos en este momento.', 'warning')
    #     return redirect(url_for('public.index'))
    
    csrf_form = CSRFOnlyForm()
    pedido_controller = PedidoController()
    hoy = datetime.now()
    min_fecha_entrega = hoy + timedelta(days=7)
    response, _ = pedido_controller.obtener_datos_para_formulario()
    productos = response.get('data', {}).get('productos', [])
    cliente_controller = ClienteController()
    cliente_response, _ = cliente_controller.obtener_cliente(session['cliente_id'])
    cliente = cliente_response.get('data', {})
    es_nuevo = not cliente_controller.cliente_tiene_pedidos_previos(session['cliente_id'])


    return render_template(
        'orden_venta/formulario_cliente_pasos.html', 
        productos=productos, 
        pedido=None, 
        is_edit=False, 
        csrf_form=csrf_form,
        today=hoy.strftime('%Y-%m-%d'),
        min_fecha_entrega=min_fecha_entrega.strftime('%Y-%m-%d'),
        cliente=cliente,
        es_cliente_nuevo=es_nuevo
    )

@public_bp.route('/api/crear-pedido', methods=['POST'])
def crear_pedido_api():
    """
    Endpoint público para recibir los datos del formulario y crear el pedido.
    No requiere autenticación. Reutiliza el controlador existente.
    """
    json_data = request.get_json()
    if not json_data:
        return jsonify({"success": False, "error": "Datos no válidos"}), 400
    pedido_controller = PedidoController()
    response, status_code = pedido_controller.crear_pedido_con_items(json_data)
    nuevo_pedido = response.get('data', {})
    if status_code < 300:
        return jsonify({
            'success': True, 
            'message': '¡Pedido recibido con éxito! Nos pondremos en contacto a la brevedad.',
            'data': {
            'id': nuevo_pedido.get('id')
            }
        }), 201
    else:
        return jsonify({
            'success': False, 
            'message': response.get('message', 'Error al procesar el pedido.')
        }), status_code

@public_bp.route('/comprobante-pago/<int:pedido_id>')
def ver_comprobante(pedido_id):
    """
    Muestra una página de confirmación y comprobante de pago para un pedido específico.
    """
    pedido_controller = PedidoController()
    response, status_code = pedido_controller.obtener_pedido_por_id(pedido_id)
    
    if response.get('success'):
        pedido_data = response.get('data')
        return render_template('orden_venta/comprobante_pago.html', pedido=pedido_data)
    else:
        return "Pedido no encontrado o error al cargar los datos.", 404

@public_bp.route('/api/cliente/<int:cliente_id>/condicion-pago', methods=['GET'])
def obtener_condicion_pago_cliente(cliente_id):
    """
    Determina si un cliente es nuevo o existente y devuelve las 
    condiciones de pago permitidas.
    """
    cliente_controller = ClienteController()
    es_cliente_nuevo = not cliente_controller.cliente_tiene_pedidos_previos(cliente_id)

    if es_cliente_nuevo:
        # Los clientes nuevos solo pueden pagar al contado
        condiciones_pago = [{'valor': 'contado', 'texto': 'Al Contado'}]
    else:
        response, _ = cliente_controller.obtener_cliente(cliente_id)
        if not response.get('success'):
            return jsonify({'success': False, 'error': 'Cliente no encontrado'}), 404

        cliente = response.get('data')
        condicion_venta = cliente.get('condicion_venta')

        condiciones_pago = [{'valor': 'contado', 'texto': 'Al Contado'}]
        if condicion_venta >= 2:
            condiciones_pago.append({'valor': 'credito_30', 'texto': 'Crédito a 30 días'})
        if condicion_venta >= 3:
            condiciones_pago.append({'valor': 'credito_90', 'texto': 'Crédito a 90 días'})

    return jsonify({
        'success': True,
        'es_cliente_nuevo': es_cliente_nuevo,
        'condiciones_pago': condiciones_pago
    })