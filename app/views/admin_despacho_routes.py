from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.controllers.despacho_controller import DespachoController
# from app.utils.decorators import permission_required

despacho_bp = Blueprint('despacho', __name__, url_prefix='/admin/despachos')
despacho_controller = DespachoController()

@despacho_bp.route('/crear')
# @permission_required('crear_despachos')
def crear_despacho_vista():
    """
    Muestra la página para crear un nuevo despacho, cargando los pedidos
    que están listos para ser enviados.
    """
    response = despacho_controller.obtener_pedidos_para_despacho()
    if not response['success']:
        flash(response['error'], 'danger')
        pedidos = []
    else:
        pedidos = response['data']
    
    # Agrupar pedidos por localidad para la vista
    pedidos_por_localidad = {}
    for pedido in pedidos:
        localidad = pedido.get('direccion', {}).get('localidad', 'Sin Localidad')
        if localidad not in pedidos_por_localidad:
            pedidos_por_localidad[localidad] = []
        pedidos_por_localidad[localidad].append(pedido)

    return render_template('despachos/crear.html', pedidos_por_localidad=pedidos_por_localidad)

@despacho_bp.route('/api/crear', methods=['POST'])
# @permission_required('crear_despachos')
def api_crear_despacho():
    """
    Endpoint API para crear un despacho y asociar los pedidos.
    """
    data = request.json
    vehiculo_id = data.get('vehiculo_id')
    pedido_ids = data.get('pedido_ids')
    observaciones = data.get('observaciones', '')

    if not vehiculo_id or not pedido_ids:
        return {'success': False, 'error': 'Faltan datos requeridos (vehiculo_id, pedido_ids)'}, 400

    response = despacho_controller.crear_despacho_y_actualizar_pedidos(
        vehiculo_id,
        pedido_ids,
        observaciones
    )

    if response['success']:
        flash('Despacho creado exitosamente.', 'success')
        return {'success': True, 'data': response['data'], 'redirect_url': url_for('orden_venta.listar')}, 201
    else:
        return {'success': False, 'error': response.get('error', 'Error interno al crear el despacho')}, 500
