from flask import Blueprint, flash, redirect, render_template, request, jsonify, session, url_for
from flask_jwt_extended import jwt_required, get_current_user
from datetime import datetime, timedelta
from app.controllers.pedido_controller import PedidoController
from app.controllers.cliente_controller import ClienteController
from app.controllers.consulta_controller import ConsultaController
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
@jwt_required()
def hacer_pedido():
    """
    Muestra el formulario para que un cliente haga un pedido desde la web pública.
    """
    current_user = get_current_user()
    if not current_user:
        flash('Por favor, inicia sesión para realizar un pedido.', 'info')
        return redirect(url_for('cliente.login'))

    # Asumiendo que el `user_lookup_loader` carga el estado de aprobación.
    # Si no es así, se necesitaría una consulta a la BD aquí.
    # Por ahora, se asume que un usuario logueado está aprobado.
    
    csrf_form = CSRFOnlyForm()
    pedido_controller = PedidoController()
    hoy = datetime.now()
    min_fecha_entrega = hoy + timedelta(days=7)
    response, _ = pedido_controller.obtener_datos_para_formulario()
    productos = response.get('data', {}).get('productos', [])
    cliente_controller = ClienteController()
    cliente_response, _ = cliente_controller.obtener_cliente(current_user.id)
    cliente = cliente_response.get('data', {})
    es_nuevo = not cliente_controller.cliente_tiene_pedidos_previos(current_user.id)


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
    usuario_id=0
    response, status_code = pedido_controller.crear_pedido_con_items(json_data,usuario_id)
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


@public_bp.route('/cliente/generar-proforma', methods=['POST'])
def generar_proforma_api():
    """
    API endpoint to generate a proforma invoice HTML from JSON data
    without creating a persistent order.
    """
    pedido_data = request.get_json()

    if not pedido_data or 'id_cliente' not in pedido_data:
        return jsonify({'success': False, 'error': 'Datos incompletos.'}), 400
    
    cliente_controller = ClienteController()
    controller = PedidoController()
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



@public_bp.route('/crear-reclamo/<int:pedido_id>')
def crear_reclamo_page(pedido_id):
    """
    Muestra el formulario para crear un reclamo para un pedido específico.
    """
    csrf_form = CSRFOnlyForm()

    hoy = datetime.now().strftime('%Y-%m-%d')
    # Aquí podrías añadir lógica para verificar que el pedido pertenece al cliente en sesión si fuera necesario.
    return render_template('public/crear_reclamo.html', pedido_id=pedido_id, today=hoy, csrf_form=csrf_form)

@public_bp.route('/consulta', methods=['GET', 'POST'])
def enviar_consulta():
    """
    Muestra el formulario para enviar una consulta y procesa el envío.
    """
    csrf_form = CSRFOnlyForm()
    if csrf_form.validate_on_submit():
        datos_consulta = {
            'nombre': request.form['nombre'],
            'email': request.form['email'],
            'mensaje': request.form['mensaje']
        }
        
        # Si el usuario está logueado, adjuntamos su ID
        if 'cliente_id' in session:
            datos_consulta['cliente_id'] = session['cliente_id']

        consulta_controller = ConsultaController()
        _, error = consulta_controller.crear_consulta(datos_consulta)

        if error:
            flash(error, 'danger')
            return redirect(url_for('public.enviar_consulta'))

        flash('Tu consulta ha sido enviada con éxito. Te responderemos a la brevedad.', 'success')
        return redirect(url_for('public.faq'))

    return render_template('public/formulario_consulta.html', csrf_form=csrf_form)