from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.controllers.producto_controller import ProductoController
from app.utils.decorators import roles_required

producto_bp = Blueprint('producto', __name__, url_prefix='/admin/productos')
producto_controller = ProductoController()

@producto_bp.route('/')
@roles_required(min_level=2, allowed_roles=['EMPLEADO'])
def listar():
    """Muestra la lista de todos los productos del catálogo."""
    productos = producto_controller.obtener_todos_los_productos()
    return render_template('productos/listar.html', productos=productos)

@producto_bp.route('/nuevo', methods=['GET', 'POST'])
@roles_required(allowed_roles=['GERENTE_GENERAL', 'RESPONSABLE_COMERCIAL'])
def nuevo():
    """Gestiona la creación de un nuevo producto."""
    if request.method == 'POST':
        datos_producto = request.form.to_dict()
        resultado = producto_controller.crear_producto(datos_producto)
        if resultado.get('success'):
            flash('Producto creado exitosamente.', 'success')
            return redirect(url_for('producto.listar'))
        else:
            flash(f"Error al crear el producto: {resultado.get('error')}", 'error')
            return render_template('productos/formulario.html', producto=datos_producto, is_new=True)
    return render_template('productos/formulario.html', producto={}, is_new=True)

@producto_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@roles_required(allowed_roles=['GERENTE_GENERAL', 'RESPONSABLE_COMERCIAL'])
def editar(id):
    """Gestiona la edición de un producto existente."""
    if request.method == 'POST':
        datos_actualizados = request.form.to_dict()
        resultado = producto_controller.actualizar_producto(id, datos_actualizados)
        if resultado.get('success'):
            flash('Producto actualizado exitosamente.', 'success')
            return redirect(url_for('producto.listar'))
        else:
            flash(f"Error al actualizar el producto: {resultado.get('error')}", 'error')
            producto_actual = request.form.to_dict()
            producto_actual['id'] = id
            return render_template('productos/formulario.html', producto=producto_actual, is_new=False)
    
    producto = producto_controller.obtener_producto_por_id(id)
    if not producto:
        flash('Producto no encontrado.', 'error')
        return redirect(url_for('producto.listar'))
    return render_template('productos/formulario.html', producto=producto, is_new=False)

@producto_bp.route('/<int:id>/eliminar', methods=['POST'])
@roles_required(allowed_roles=['GERENTE_GENERAL', 'RESPONSABLE_COMERCIAL'])
def eliminar(id):
    """Desactiva un producto (eliminación lógica)."""
    resultado = producto_controller.eliminar_producto(id)
    if resultado.get('success'):
        flash('Producto desactivado exitosamente.', 'success')
    else:
        flash(f"Error al desactivar el producto: {resultado.get('error')}", 'error')
    return redirect(url_for('producto.listar'))