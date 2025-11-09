from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.controllers.vehiculo_controller import VehiculoController
# from app.utils.decorators import permission_required # TODO: Añadir permisos cuando esté definido

vehiculo_bp = Blueprint('vehiculo', __name__, url_prefix='/admin/vehiculos')
vehiculo_controller = VehiculoController()

@vehiculo_bp.route('/')
# @permission_required('gestionar_flota')
def listar_vehiculos():
    response = vehiculo_controller.obtener_todos_los_vehiculos()
    if not response['success']:
        flash(response['error'], 'danger')
        vehiculos = []
    else:
        vehiculos = response['data']
    return render_template('vehiculos/listar.html', vehiculos=vehiculos)

@vehiculo_bp.route('/nuevo', methods=['GET', 'POST'])
# @permission_required('gestionar_flota')
def crear_vehiculo():
    if request.method == 'POST':
        data = request.form.to_dict()
        response = vehiculo_controller.crear_vehiculo(data)
        if response['success']:
            flash('Vehículo creado exitosamente.', 'success')
            return redirect(url_for('envio.gestion_envios'))
        else:
            flash(f"Error al crear el vehículo: {response['error']}", 'danger')
    return render_template('vehiculos/formulario.html', vehiculo=None, is_new=True)

@vehiculo_bp.route('/<int:vehiculo_id>/editar', methods=['GET', 'POST'])
# @permission_required('gestionar_flota')
def editar_vehiculo(vehiculo_id):
    if request.method == 'POST':
        data = request.form.to_dict()
        response = vehiculo_controller.actualizar_vehiculo(vehiculo_id, data)
        if response['success']:
            flash('Vehículo actualizado exitosamente.', 'success')
            return redirect(url_for('envio.gestion_envios'))
        else:
            flash(f"Error al actualizar el vehículo: {response['error']}", 'danger')

    response = vehiculo_controller.obtener_vehiculo_por_id(vehiculo_id)
    if not response['success']:
        flash(response['error'], 'danger')
        return redirect(url_for('envio.gestion_envios'))
    
    vehiculo = response['data']
    return render_template('vehiculos/formulario.html', vehiculo=vehiculo, is_new=False)

@vehiculo_bp.route('/<int:vehiculo_id>/eliminar', methods=['POST'])
# @permission_required('gestionar_flota')
def eliminar_vehiculo(vehiculo_id):
    response = vehiculo_controller.eliminar_vehiculo(vehiculo_id)
    if response['success']:
        flash('Vehículo eliminado exitosamente.', 'success')
    else:
        flash(f"Error al eliminar el vehículo: {response['error']}", 'danger')
    return redirect(url_for('envio.gestion_envios'))

# --- API Endpoints ---
@vehiculo_bp.route('/api/buscar', methods=['GET'])
# @permission_required('crear_despachos') # O el permiso que corresponda
def api_buscar_vehiculo():
    patente = request.args.get('patente')
    if not patente:
        return {'success': False, 'error': 'La patente es requerida'}, 400
    
    response = vehiculo_controller.buscar_por_patente(patente)
    if response['success'] and response['data']:
        return {'success': True, 'data': response['data'][0]}
    elif response['success']:
        return {'success': False, 'error': 'Vehículo no encontrado'}, 404
    else:
        return {'success': False, 'error': response['error']}, 500
