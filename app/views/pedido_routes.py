from flask import Blueprint, render_template, request, redirect, url_for, flash
from controllers.pedido_controller import PedidoController
from models.producto import ProductoModel # Se usa el modelo directamente para obtener la lista
from datetime import date

pedido_bp = Blueprint('pedido', __name__, url_prefix='/pedidos')

# --- Instanciación de Controladores ---
pedido_controller = PedidoController()
producto_model = ProductoModel() # Para obtener la lista de productos

@pedido_bp.route('/')
def listar():
    """Muestra una lista de todos los pedidos de clientes."""
    pedidos = pedido_controller.obtener_todos_los_pedidos()
    return render_template('pedidos/listar.html', pedidos=pedidos)

@pedido_bp.route('/nuevo', methods=['GET', 'POST'])
def nuevo():
    """Muestra el formulario para crear un nuevo pedido y maneja su creación."""
    if request.method == 'POST':
        datos_pedido = request.form.to_dict()
        resultado = pedido_controller.crear_pedido(datos_pedido)

        if resultado.get('success'):
            flash('Pedido de cliente creado exitosamente.', 'success')
            return redirect(url_for('pedido.listar'))
        else:
            flash(f"Error al crear el pedido: {resultado.get('error')}", 'error')
            productos = producto_model.find_all().get('data', [])
            return render_template('pedidos/formulario.html', productos=productos, pedido=request.form, today=date.today().isoformat())

    # Para el formulario GET
    productos = producto_model.find_all().get('data', [])
    return render_template('pedidos/formulario.html', productos=productos, today=date.today().isoformat(), pedido=None)


@pedido_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
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
            pedido_actual = pedido_controller.obtener_pedido_por_id(id)
            productos = producto_model.find_all().get('data', [])
            return render_template('pedidos/formulario.html', productos=productos, pedido=pedido_actual)

    # Para la petición GET
    pedido = pedido_controller.obtener_pedido_por_id(id)
    if not pedido or pedido.get('estado') != 'PENDIENTE':
        flash('Este pedido no puede ser editado.', 'warning')
        return redirect(url_for('pedido.listar'))

    productos = producto_model.find_all().get('data', [])
    return render_template('pedidos/formulario.html', productos=productos, pedido=pedido, today=date.today().isoformat())


@pedido_bp.route('/<int:id>/eliminar', methods=['POST'])
def eliminar(id):
    """Maneja la eliminación de un pedido."""
    resultado = pedido_controller.eliminar_pedido(id)
    if resultado.get('success'):
        flash('Pedido eliminado exitosamente.', 'success')
    else:
        flash(f"Error al eliminar el pedido: {resultado.get('error')}", 'error')

    return redirect(url_for('pedido.listar'))