from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.controllers.costo_fijo_controller import CostoFijoController
from app.utils.decorators import permission_required

costos_fijos_bp = Blueprint('costos_fijos', __name__, url_prefix='/admin/costos-fijos')

@costos_fijos_bp.route('/')
@permission_required('admin_configuracion_sistema') # Proteger la ruta con un permiso adecuado
def listar():
    controller = CostoFijoController()
    response, _ = controller.get_all_costos_fijos()
    costos = response.get('data', [])
    return render_template('costos_fijos/listar.html', costos=costos)

@costos_fijos_bp.route('/nuevo', methods=['GET', 'POST'])
@permission_required('admin_configuracion_sistema')
def nuevo():
    if request.method == 'POST':
        data = request.form.to_dict()
        data.pop('csrf_token', None)
        controller = CostoFijoController()
        _, status_code = controller.create_costo_fijo(data)
        if status_code == 201:
            flash('Costo fijo creado exitosamente.', 'success')
            return redirect(url_for('costos_fijos.listar'))
        else:
            flash('Error al crear el costo fijo.', 'error')
    
    return render_template('costos_fijos/formulario.html', costo=None, is_edit=False)

@costos_fijos_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@permission_required('admin_configuracion_sistema')
def editar(id):
    controller = CostoFijoController()
    if request.method == 'POST':
        data = request.form.to_dict()
        data.pop('csrf_token', None)
        _, status_code = controller.update_costo_fijo(id, data)
        if status_code == 200:
            flash('Costo fijo actualizado exitosamente.', 'success')
            return redirect(url_for('costos_fijos.listar'))
        else:
            flash('Error al actualizar el costo fijo.', 'error')

    response, _ = controller.get_costo_fijo_by_id(id)
    costo = response.get('data')
    if not costo:
        flash('Costo fijo no encontrado.', 'error')
        return redirect(url_for('costos_fijos.listar'))
        
    return render_template('costos_fijos/formulario.html', costo=costo, is_edit=True)

@costos_fijos_bp.route('/<int:id>/eliminar', methods=['POST'])
@permission_required('admin_configuracion_sistema')
def eliminar(id):
    controller = CostoFijoController()
    _, status_code = controller.delete_costo_fijo(id)
    if status_code == 200:
        flash('Costo fijo desactivado exitosamente.', 'success')
    else:
        flash('Error al desactivar el costo fijo.', 'error')
    return redirect(url_for('costos_fijos.listar'))

@costos_fijos_bp.route('/<int:id>/reactivar', methods=['POST'])
@permission_required('admin_configuracion_sistema')
def reactivar(id):
    controller = CostoFijoController()
    _, status_code = controller.reactivate_costo_fijo(id)
    
    if status_code == 200:
        flash('Costo fijo reactivado exitosamente.', 'success')
    else:
        flash('Error al reactivar el costo fijo.', 'error')
        
    return redirect(url_for('costos_fijos.listar'))

@costos_fijos_bp.route('/<int:id>/historial', methods=['GET'])
@permission_required('admin_configuracion_sistema')
def historial(id):
    controller = CostoFijoController()
    
    costo_res, _ = controller.get_costo_fijo_by_id(id)
    costo = costo_res.get('data')
    if not costo:
        flash('Costo fijo no encontrado.', 'error')
        return redirect(url_for('costos_fijos.listar'))

    historial_res, _ = controller.get_historial(id)
    historial = historial_res.get('data', [])
    
    return render_template('costos_fijos/historial.html', costo=costo, historial=historial)

@costos_fijos_bp.route('/<int:id>/historial/nuevo', methods=['POST'])
@permission_required('admin_configuracion_sistema')
def historial_nuevo(id):
    """
    Ruta para agregar un registro histórico manualmente.
    """
    controller = CostoFijoController()
    data = request.form.to_dict()
    
    _, status_code = controller.agregar_registro_historial(id, data)
    
    if status_code == 200:
        flash('Registro histórico agregado exitosamente.', 'success')
    else:
        flash('Error al agregar el registro histórico.', 'error')
        
    return redirect(url_for('costos_fijos.historial', id=id))
