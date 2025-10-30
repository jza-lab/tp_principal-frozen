from flask import Blueprint, jsonify, request, redirect, url_for, flash, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.controllers.usuario_controller import UsuarioController
from app.controllers.autorizacion_controller import AutorizacionController
from app.utils.decorators import permission_required

# Blueprint para la administración de autorizaciones
admin_autorizacion_bp = Blueprint('admin_autorizacion', __name__, url_prefix='/admin/autorizaciones')

@admin_autorizacion_bp.route('/nueva', methods=['GET', 'POST'])
@jwt_required()
@permission_required(accion='gestionar_autorizaciones')
def nueva_autorizacion():
    """
    Muestra el formulario para crear una nueva autorización de ingreso y la procesa.
    """
    autorizacion_controller = AutorizacionController()
    usuario_controller = UsuarioController()
    if request.method == 'POST':
        data = request.form.to_dict()
        data['supervisor_id'] = get_jwt_identity()
        
        resultado = autorizacion_controller.crear_autorizacion(data)

        if resultado.get('success'):
            flash('Autorización creada exitosamente.', 'success')
            return redirect(url_for('admin_usuario.listar_usuarios')) # TODO: Redirigir a una vista de autorizaciones
        else:
            flash(f"Error al crear la autorización: {resultado.get('error')}", 'error')
            usuarios = usuario_controller.obtener_todos_los_usuarios({'activo': True})
            turnos = usuario_controller.obtener_todos_los_turnos()
            return render_template('usuarios/autorizacion.html',
                                 usuarios=usuarios,
                                 turnos=turnos,
                                 autorizacion=data)

    # Método GET
    usuarios = usuario_controller.obtener_todos_los_usuarios({'activo': True})
    turnos = usuario_controller.obtener_todos_los_turnos()
    return render_template('usuarios/autorizacion.html',
                         usuarios=usuarios,
                         turnos=turnos,
                         autorizacion={})

@admin_autorizacion_bp.route('/', methods=['GET'])
@permission_required(accion='gestionar_autorizaciones')
def listar_autorizaciones():
    """
    Obtiene todas las autorizaciones de ingreso en formato JSON.
    """
    autorizacion_controller = AutorizacionController()
    resultado = autorizacion_controller.obtener_todas_las_autorizaciones()
    if resultado.get('success'):
        grouped_data = resultado.get('data', {})
        pendientes = grouped_data.get('PENDIENTE', [])
        historial = grouped_data.get('APROBADO', []) + grouped_data.get('RECHAZADO', [])
        
        return jsonify(success=True, data={'pendientes': pendientes, 'historial': historial})
    
    return jsonify(success=False, error=resultado.get('error', 'Error al obtener las autorizaciones.')), 500

@admin_autorizacion_bp.route('/<int:id>/estado', methods=['POST'])
@permission_required(accion='gestionar_autorizaciones')
def actualizar_estado_autorizacion(id):
    """
    Actualiza el estado de una autorización (APROBADO o RECHAZADO).
    """
    data = request.get_json()
    nuevo_estado = data.get('estado')
    comentario = data.get('comentario')

    if not nuevo_estado or nuevo_estado not in ['APROBADO', 'RECHAZADO']:
        return jsonify(success=False, error='Estado no válido.'), 400

    autorizacion_controller = AutorizacionController()
    resultado = autorizacion_controller.actualizar_estado_autorizacion(id, nuevo_estado, comentario)

    if resultado.get('success'):
        return jsonify(success=True, message='Autorización actualizada exitosamente.')
    else:
        return jsonify(success=False, error=resultado.get('error', 'Error al actualizar la autorización.')), 500
