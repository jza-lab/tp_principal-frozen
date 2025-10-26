from flask import Blueprint, render_template, request, jsonify, url_for
from datetime import datetime
from app.controllers.pedido_controller import PedidoController
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
    csrf_form = CSRFOnlyForm()
    pedido_controller = PedidoController()
    hoy = datetime.now().strftime('%Y-%m-%d')
    response, _ = pedido_controller.obtener_datos_para_formulario()
    productos = response.get('data', {}).get('productos', [])

    return render_template(
        'orden_venta/formulario_cliente_pasos.html', 
        productos=productos, 
        pedido=None, 
        is_edit=False, 
        csrf_form=csrf_form,
        today=hoy,
        cliente={},
        es_cliente_nuevo=True 
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

    if status_code < 300:
        return jsonify({
            'success': True, 
            'message': '¡Pedido recibido con éxito! Nos pondremos en contacto a la brevedad.',
            'redirect_url': url_for('public.index') 
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
        return render_template('public/comprobante_pago.html', pedido=pedido_data)
    else:
        return "Pedido no encontrado o error al cargar los datos.", 404
