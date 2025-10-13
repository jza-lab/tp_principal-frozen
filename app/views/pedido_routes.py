from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from matplotlib.dates import relativedelta
from app.controllers.pedido_controller import PedidoController
from app.controllers.cliente_controller import ClienteController
from app.permisos import permission_required
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
@permission_required(sector_codigo='LOGISTICA', accion='leer')
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
@permission_required(sector_codigo='LOGISTICA', accion='crear')
def nueva():
    """Gestiona la creación de un nuevo pedido de venta."""

    # Calculamos la fecha de hoy en formato AAAA-MM-DD
    hoy = datetime.now().strftime('%Y-%m-%d')
    fecha_limite= (datetime.now() + relativedelta(months=3)).strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        json_data = request.get_json()
        if not json_data:
            return jsonify({"success": False, "error": "No se recibieron datos JSON válidos"}), 400

        response, status_code = controller.crear_pedido_con_items(json_data)

        if status_code < 300: # Éxito (e.g., 201 Created)
                nuevo_pedido_id = response.get('data', {}).get('id')
                return jsonify({
                    'success': True,
                    'message': response.get('message', 'Pedido creado con éxito.'),
                    # Envía la URL para que JS redirija
                    'redirect_url': url_for('orden_venta.detalle', id=nuevo_pedido_id)
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

@orden_venta_bp.route('/<int:id>/editar', methods=['GET', 'POST','PUT'])
@permission_required(sector_codigo='LOGISTICA', accion='actualizar')
def editar(id):
    
    """Gestiona la edición de un pedido de venta existente."""

    hoy = datetime.now().strftime('%Y-%m-%d')
    if request.method == 'PUT':
        try:
            # 1. Lee los datos JSON
            json_data = request.get_json()
            if not json_data:
                return jsonify({"success": False, "error": "No se recibieron datos JSON válidos"}), 400

            # 2. Llama a tu controlador para crear el pedido
            # Este controlador ahora debe saber cómo manejar el diccionario json_data
            response_data, status_code = controller.crear_pedido_con_items(json_data)

            # 3. Responde con JSON, no con redirect/flash
            if status_code < 300: # Éxito (e.g., 201 Created)
                    nuevo_pedido_id = response_data.get('data', {}).get('id')
                    return jsonify({
                        'success': True,
                        'message': response_data.get('message', 'Pedido actualizado con éxito.'),
                        # Envía la URL para que JS redirija
                        'redirect_url': url_for('orden_venta.detalle', id=nuevo_pedido_id)
                    }), 201
            else: # Error de validación
                    return jsonify({
                        'success': False,
                        'message': response_data.get('message', 'Error al actualizar el pedido.'),
                        'errors': response_data.get('errors', {})
                    }), status_code
            
        except Exception as e:
                print(f"Error inesperado en POST /nueva: {e}") # Esto aparecerá en tu terminal de Flask
                return jsonify({"success": False, "error": "Ocurrió un error interno en el servidor."}), 500
       

    # Método GET
    pedido_resp, _ = controller.obtener_pedido_por_id(id)
    pedido= pedido_resp.get('data')

    cliente_resp, _ = cliente_controller.obtener_cliente(pedido['id_cliente'])
    cliente=cliente_resp.get('data')

    if(cliente and cliente['cuit']):
        cliente['cuit'] = cliente['cuit'].replace('-', '')

    form_data_resp, _ = controller.obtener_datos_para_formulario()

    if not pedido_resp.get('success'):
        flash(pedido_resp.get('error', 'Pedido no encontrado.'), 'error')
        return redirect(url_for('orden_venta.listar'))

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
@permission_required(sector_codigo='LOGISTICA', accion='leer')
def detalle(id):
    """Muestra la página de detalle de un pedido de venta."""
    response, status_code = controller.obtener_pedido_por_id(id)

    if response.get('success'):
        pedido_data = response.get('data')
        # Convertir cadenas de fecha a objetos datetime para formatear en la plantilla
        if pedido_data and pedido_data.get('created_at') and isinstance(pedido_data['created_at'], str):
            pedido_data['created_at'] = datetime.fromisoformat(pedido_data['created_at'])
        if pedido_data and pedido_data.get('updated_at') and isinstance(pedido_data['updated_at'], str):
            pedido_data['updated_at'] = datetime.fromisoformat(pedido_data['updated_at'])

        return render_template('orden_venta/detalle.html', pedido=pedido_data)
    else:
        flash(response.get('error', 'Pedido no encontrado.'), 'error')
        return redirect(url_for('orden_venta.listar'))

@orden_venta_bp.route('/<int:id>/cancelar', methods=['POST'])
@permission_required(sector_codigo='LOGISTICA', accion='eliminar')
def cancelar(id):
    """Endpoint para cambiar el estado de un pedido a 'CANCELADO'."""
    response, status_code = controller.cancelar_pedido(id)

    if response.get('success'):
        flash(response.get('message', 'Pedido cancelado con éxito.'), 'success')
    else:
        flash(response.get('error', 'Error al cancelar el pedido.'), 'error')

    return redirect(url_for('orden_venta.detalle', id=id))


# --- RUTA DE APROBACIÓN REHECHA AL ESTILO API ---
@orden_venta_bp.route('/<int:id>/aprobar', methods=['POST'])
##@permission_required(sector_codigo='LOGISTICA', accion='actualizar')
def aprobar(id):
    """
    Endpoint de API para aprobar un pedido. Devuelve una respuesta JSON.
    """
    try:
        # Obtenemos el usuario de la sesión, igual que en tu ruta crear()
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return jsonify({"success": False, "error": "Usuario no autenticado."}), 401

        # Llamamos al controlador pasándole el id del pedido y del usuario
        response, status_code = controller.aprobar_pedido(id, usuario_id)

        # Devolvemos la respuesta del controlador en formato JSON
        return jsonify(response), status_code

    except Exception as e:
        print(f"Error inesperado en la ruta aprobar pedido: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500