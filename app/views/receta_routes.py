from flask import Blueprint, render_template, request, redirect, url_for, flash
from controllers.receta_controller import RecetaController
from controllers.producto_controller import ProductoController
from controllers.insumo_controller import InsumoController
from utils.decorators import roles_required

receta_bp = Blueprint('receta', __name__, url_prefix='/recetas')
controller = RecetaController()

# Instanciar otros controladores para obtener datos para los formularios
producto_controller = ProductoController()
insumo_controller = InsumoController()

@receta_bp.route('/')
@roles_required('ADMIN', 'GERENTE', 'SUPERVISOR')
def listar():
    """Muestra una lista de todas las recetas."""
    recetas = controller.obtener_recetas()
    return render_template('recetas/listar.html', recetas=recetas)

@receta_bp.route('/<int:id>')
@roles_required('ADMIN', 'GERENTE', 'SUPERVISOR')
def detalle(id):
    """Muestra el detalle de una receta, incluyendo sus ingredientes."""
    receta = controller.obtener_receta_con_ingredientes(id)
    if not receta:
        flash('Receta no encontrada.', 'error')
        return redirect(url_for('receta.listar'))

    return render_template('recetas/detalle.html', receta=receta)

@receta_bp.route('/nueva', methods=['GET', 'POST'])
@roles_required('ADMIN', 'GERENTE')
def nueva():
    """Gestiona la creación de una nueva receta con sus ingredientes."""
    if request.method == 'POST':
        # Recolectar datos principales de la receta
        datos_receta = {
            'nombre': request.form.get('nombre'),
            'producto_id': request.form.get('producto_id'),
            'version': request.form.get('version'),
            'descripcion': request.form.get('descripcion'),
            'rendimiento': request.form.get('rendimiento')
        }

        # Recolectar datos de los ingredientes
        ingredientes = []
        i = 0
        while f'ingredientes-{i}-id_insumo' in request.form:
            id_insumo = request.form.get(f'ingredientes-{i}-id_insumo')
            cantidad = request.form.get(f'ingredientes-{i}-cantidad')
            unidad_medida = request.form.get(f'ingredientes-{i}-unidad_medida')
            if id_insumo and cantidad and unidad_medida:
                ingredientes.append({
                    'id_insumo': id_insumo,
                    'cantidad': float(cantidad),
                    'unidad_medida': unidad_medida
                })
            i += 1

        datos_receta['ingredientes'] = ingredientes

        resultado = controller.crear_receta_con_ingredientes(datos_receta)

        if resultado.get('success'):
            flash('Receta creada exitosamente.', 'success')
            return redirect(url_for('receta.listar'))
        else:
            flash(f"Error al crear la receta: {resultado.get('error')}", 'error')
            # Volver a cargar los datos para el formulario en caso de error
            productos = producto_controller.obtener_todos_los_productos()
            insumos = insumo_controller.obtener_insumos()
            return render_template('recetas/formulario.html', receta=datos_receta, productos=productos, insumos=insumos, is_new=True)

    # GET: Cargar datos para los desplegables del formulario
    productos = producto_controller.obtener_todos_los_productos()
    insumos = insumo_controller.obtener_insumos()
    return render_template('recetas/formulario.html', receta={}, productos=productos, insumos=insumos, is_new=True)


@receta_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@roles_required('ADMIN', 'GERENTE')
def editar(id):
    """Gestiona la edición de una receta existente (funcionalidad pendiente)."""
    flash('Funcionalidad de editar receta aún no implementada.', 'info')
    return redirect(url_for('receta.detalle', id=id))

@receta_bp.route('/<int:id>/eliminar', methods=['POST'])
@roles_required('ADMIN', 'GERENTE')
def eliminar(id):
    """Elimina una receta (funcionalidad pendiente)."""
    flash('Funcionalidad de eliminar receta aún no implementada.', 'info')
    return redirect(url_for('receta.listar'))