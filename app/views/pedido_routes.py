from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from app.controllers.pedido_controller import PedidoController
from app.models.producto import ProductoModel
from datetime import date
from app.utils.decorators import roles_required
from werkzeug.datastructures import MultiDict

pedido_bp = Blueprint('pedido', __name__, url_prefix='/pedidos')

# --- Instanciación de Controladores y Modelos ---
pedido_controller = PedidoController()
producto_model = ProductoModel()

def _parse_form_data_for_items(form_data: MultiDict) -> dict:
    """
    Transforma los datos planos del formulario (MultiDict) en una estructura anidada
    para los ítems del pedido, que es lo que espera el PedidoSchema.
    Ejemplo de entrada: {'items-0-producto_id': '1', 'items-0-cantidad': '10.5'}
    Ejemplo de salida: {'items': [{'producto_id': 1, 'cantidad': 10.5}]}
    """
    parsed_data = {
        'nombre_cliente': form_data.get('nombre_cliente'),
        'fecha_solicitud': form_data.get('fecha_solicitud'),
        'items': []
    }
    items_map = {}
    # Iterar sobre las claves únicas que contienen 'producto_id' para identificar los ítems
    for key in form_data:
        if 'producto_id' in key:
            # Extraer el prefijo (ej. 'items-0-')
            prefix = key.rsplit('-', 1)[0]

            producto_id = form_data.get(f'{prefix}-producto_id')
            cantidad = form_data.get(f'{prefix}-cantidad')

            if producto_id and cantidad:
                try:
                    # Agregamos el item a la lista para validación
                    items_map[prefix] = {
                        'producto_id': int(producto_id),
                        'cantidad': float(cantidad)
                    }
                except (ValueError, TypeError) as e:
                    current_app.logger.warning(f"Dato de ítem inválido ignorado: {e}")
                    continue

    parsed_data['items'] = list(items_map.values())
    return parsed_data


@pedido_bp.route('/')
@roles_required('VENDEDOR', 'SUPERVISOR', 'ADMIN', 'GERENTE')
def listar():
    """Muestra una lista de todos los pedidos de clientes."""
    pedidos = pedido_controller.obtener_todos_los_pedidos()
    return render_template('pedidos/listar.html', pedidos=pedidos)

@pedido_bp.route('/nuevo', methods=['GET', 'POST'])
@roles_required('VENDEDOR', 'SUPERVISOR', 'ADMIN', 'GERENTE')
def nuevo():
    """Muestra el formulario para crear un nuevo pedido y maneja su creación."""
    if request.method == 'POST':
        # Los datos del formulario con ítems dinámicos requieren un parseo especial
        datos_pedido = _parse_form_data_for_items(request.form)

        resultado = pedido_controller.crear_pedido(datos_pedido)

        if resultado.get('success'):
            flash('Pedido de cliente creado exitosamente.', 'success')
            return redirect(url_for('pedido.listar'))
        else:
            flash(f"Error al crear el pedido: {resultado.get('error')}", 'error')
            # Si falla, volvemos a cargar el formulario con los datos introducidos
            productos = producto_model.find_all().get('data', [])
            # Pasamos los datos originales del formulario para que el usuario pueda corregirlos
            return render_template('pedidos/formulario.html', productos=productos, pedido=request.form, today=date.today().isoformat(), form=request.form)

    # Para la petición GET, simplemente mostramos el formulario vacío
    productos = producto_model.find_all().get('data', [])
    return render_template('pedidos/formulario.html', productos=productos, today=date.today().isoformat(), pedido=None, form={})

@pedido_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@roles_required('VENDEDOR', 'SUPERVISOR', 'ADMIN', 'GERENTE')
def editar(id):
    """Muestra el formulario para editar un pedido y maneja su actualización."""
    if request.method == 'POST':
        datos_actualizados = request.form.to_dict()
        resultado = pedido_controller.actualizar_pedido(id, datos_actualizados)

        if resultado.get('success'):
            flash('Pedido actualizado exitosamente.', 'success')
            return redirect(url_for('pedido.listar'))
        else:
            flash(f"Error al actualizar el pedido: {resultado.get('error')}", 'error')
            # Si falla la actualización, recargamos el formulario con los datos actuales
            pedido_actual = pedido_controller.obtener_pedido_por_id(id)
            productos = producto_model.find_all().get('data', [])
            return render_template('pedidos/formulario.html', productos=productos, pedido=pedido_actual, form=request.form)

    # Para la petición GET
    pedido = pedido_controller.obtener_pedido_por_id(id)
    if not pedido:
        flash('El pedido no fue encontrado.', 'error')
        return redirect(url_for('pedido.listar'))

    if pedido.get('estado') != 'PENDIENTE':
        flash('Este pedido ya no se encuentra en estado PENDIENTE y no puede ser editado.', 'warning')
        return redirect(url_for('pedido.listar'))

    productos = producto_model.find_all().get('data', [])
    return render_template('pedidos/formulario.html', productos=productos, pedido=pedido, today=date.today().isoformat(), form={})

@pedido_bp.route('/<int:id>/eliminar', methods=['POST'])
@roles_required('SUPERVISOR', 'ADMIN', 'GERENTE')
def eliminar(id):
    """Maneja la eliminación de un pedido."""
    resultado = pedido_controller.eliminar_pedido(id)
    if resultado.get('success'):
        flash('Pedido eliminado exitosamente.', 'success')
    else:
        flash(f"Error al eliminar el pedido: {resultado.get('error')}", 'error')

    return redirect(url_for('pedido.listar'))