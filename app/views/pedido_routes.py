from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.controllers.pedido_controller import PedidoController
import re
from datetime import datetime

# The user is using 'orden_venta' and 'pedido' interchangeably.
# We'll use 'orden_venta' for the blueprint name and URL prefix for clarity.
orden_venta_bp = Blueprint('orden_venta', __name__, url_prefix='/orden-venta')

controller = PedidoController()

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
def nueva():
    """Gestiona la creación de un nuevo pedido de venta."""
    if request.method == 'POST':
        form_data = _parse_form_data(request.form.to_dict())
        response, status_code = controller.crear_pedido_con_items(form_data)
        
        if response.get('success'):
            flash(response.get('message', 'Pedido creado con éxito.'), 'success')
            return redirect(url_for('orden_venta.listar'))
        else:
            flash(response.get('error', 'Error al crear el pedido.'), 'error')
            # Volver a cargar los datos del formulario para no perderlos
            form_data_resp, _ = controller.obtener_datos_para_formulario()
            # Pasamos los datos parseados de vuelta para que el formulario se repoble correctamente
            return render_template('orden_venta/formulario.html', 
                                   productos=form_data_resp.get('data', {}).get('productos', []),
                                   pedido=form_data)

    # Método GET
    response, status_code = controller.obtener_datos_para_formulario()
    productos = []
    if response.get('success'):
        productos = response.get('data', {}).get('productos', [])
    else:
        flash(response.get('error', 'No se pudieron cargar los datos para el formulario.'), 'error')
        
    return render_template('orden_venta/formulario.html', productos=productos, pedido=None)

@orden_venta_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
def editar(id):
    """Gestiona la edición de un pedido de venta existente."""
    if request.method == 'POST':
        form_data = _parse_form_data(request.form.to_dict())
        response, status_code = controller.actualizar_pedido_con_items(id, form_data)
        
        if response.get('success'):
            flash(response.get('message', 'Pedido actualizado con éxito.'), 'success')
            return redirect(url_for('orden_venta.detalle', id=id))
        else:
            flash(response.get('error', 'Error al actualizar el pedido.'), 'error')
            # Si falla la actualización, volvemos a renderizar el formulario con los datos enviados
            form_data_resp, _ = controller.obtener_datos_para_formulario()
            # Añadimos el ID al diccionario para que el template sepa que estamos editando
            form_data['id'] = id
            return render_template('orden_venta/formulario.html',
                                   productos=form_data_resp.get('data', {}).get('productos', []),
                                   pedido=form_data)
    
    # Método GET
    pedido_resp, _ = controller.obtener_pedido_por_id(id)
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
                           pedido=pedido_resp.get('data'), 
                           productos=productos)

@orden_venta_bp.route('/<int:id>/detalle')
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
def cancelar(id):
    """Endpoint para cambiar el estado de un pedido a 'CANCELADO'."""
    response, status_code = controller.cancelar_pedido(id)
    
    if response.get('success'):
        flash(response.get('message', 'Pedido cancelado con éxito.'), 'success')
    else:
        flash(response.get('error', 'Error al cancelar el pedido.'), 'error')
        
    return redirect(url_for('orden_venta.detalle', id=id))