from flask import Blueprint, render_template, request, jsonify, url_for
from datetime import datetime
from app.controllers.pedido_controller import PedidoController

public_bp = Blueprint('public', __name__, url_prefix='/public')

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

@public_bp.route('/hace-tu-pedido')
def hacer_pedido():
    """
    Muestra el formulario para que un cliente haga un pedido desde la web pública.
    """
    pedido_controller = PedidoController()
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    # Reutilizamos la lógica del controlador para obtener los datos necesarios
    response, _ = pedido_controller.obtener_datos_para_formulario()
    productos = response.get('data', {}).get('productos', [])
    
    # Renderizamos el mismo formulario, que luego adaptaremos para el look&feel público
    return render_template(
        'orden_venta/formulario_cliente_pasos.html', 
        productos=productos, 
        pedido=None, 
        is_edit=False, 
        today=hoy,
        # Pasamos un cliente vacío y marcamos como nuevo por defecto para la lógica del template
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

    # Instanciamos el controlador para usar su lógica de negocio
    pedido_controller = PedidoController()
    
    # Llamamos al método del controlador que sabe cómo crear el pedido
    response, status_code = pedido_controller.crear_pedido_con_items(json_data)

    if status_code < 300:
        # Podríamos redirigir a una página de "gracias" o simplemente dar una respuesta exitosa
        return jsonify({
            'success': True, 
            'message': '¡Pedido recibido con éxito! Nos pondremos en contacto a la brevedad.',
            'redirect_url': url_for('public.index') # O una página de agradecimiento
        }), 201
    else:
        # Devolvemos el error que nos da el controlador
        return jsonify({
            'success': False, 
            'message': response.get('message', 'Error al procesar el pedido.')
        }), status_code
