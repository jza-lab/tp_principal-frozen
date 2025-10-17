import json
from flask import Blueprint, jsonify, session, request, redirect, url_for, flash, render_template
from app.controllers.usuario_controller import UsuarioController
from app.controllers.facial_controller import FacialController
from app.utils.decorators import permission_required, permission_any_of

# Blueprint para la administración de usuarios
admin_usuario_bp = Blueprint('admin_usuario', __name__, url_prefix='/admin/usuarios')

# Instanciar controladores
usuario_controller = UsuarioController()
facial_controller = FacialController()


@admin_usuario_bp.route('/')
@permission_any_of('ver_info_empleados', 'modificar_usuarios', 'crear_usuarios')
def listar_usuarios():
    """Muestra la lista de todos los usuarios del sistema."""
    usuarios = usuario_controller.obtener_todos_los_usuarios()
    # Datos para modales o filtros en la vista
    turnos = usuario_controller.obtener_todos_los_turnos()
    sectores = usuario_controller.obtener_todos_los_sectores()
    return render_template('usuarios/gestionEmpleados.html', usuarios=usuarios, turnos=turnos, sectores=sectores)

@admin_usuario_bp.route('/<int:id>')
@permission_any_of('ver_info_empleados', 'modificar_usuarios')
def ver_perfil(id):
    """Muestra el perfil de un usuario específico, delegando la carga de datos al controlador."""
    resultado = usuario_controller.obtener_datos_para_vista_perfil(id)

    if not resultado.get('success'):
        flash(resultado.get('error', 'Ocurrió un error'), 'error')
        return redirect(url_for('admin_usuario.listar_usuarios'))

    return render_template('usuarios/perfil.html', **resultado.get('data', {}))

@admin_usuario_bp.route('/nuevo', methods=['GET', 'POST'])
@permission_required(accion='crear_usuarios')
def nuevo_usuario():
    """Gestiona la creación de un nuevo usuario."""
    if request.method == 'POST':
        resultado = usuario_controller.gestionar_creacion_usuario_form(request.form, facial_controller)

        if resultado.get('success'):
            flash('Usuario creado exitosamente.', 'success')
            if resultado.get('warning'):
                flash(resultado.get('warning'), 'warning')
            return redirect(url_for('admin_usuario.listar_usuarios'))
        else:
            flash(f"Error al crear el usuario: {resultado.get('error')}", 'error')
            form_data = usuario_controller.obtener_datos_para_formulario_usuario()
            datos_formulario = request.form.to_dict()
            sectores_seleccionados = [int(s) for s in request.form.getlist('sectores') if s.isdigit()]

            return render_template('usuarios/formulario.html', 
                                 usuario=datos_formulario, 
                                 is_new=True,
                                 roles=form_data.get('roles'),
                                 sectores=form_data.get('sectores'),
                                 turnos=form_data.get('turnos'),
                                 usuario_sectores_ids=sectores_seleccionados)

    # Método GET
    form_data = usuario_controller.obtener_datos_para_formulario_usuario()
    return render_template('usuarios/formulario.html', 
                         usuario={}, 
                         is_new=True,
                         roles=form_data.get('roles'),
                         sectores=form_data.get('sectores'),
                         turnos=form_data.get('turnos'),
                         usuario_sectores_ids=[])

@admin_usuario_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@permission_any_of('modificar_usuarios', 'modificar_info_empleados')
def editar_usuario(id):
    """Gestiona la edición de un usuario."""
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        resultado = usuario_controller.gestionar_actualizacion_usuario_form(id, request.form)

        if resultado.get('success'):
            if is_ajax:
                return jsonify({'success': True, 'message': 'Usuario actualizado exitosamente.'})
            flash('Usuario actualizado exitosamente.', 'success')
            return redirect(url_for('admin_usuario.listar_usuarios'))
        else:
            error_message = resultado.get('error', 'Ocurrió un error desconocido.')
            if is_ajax:
                return jsonify({'success': False, 'message': error_message}), 400
            
            flash(f"Error al actualizar: {error_message}", 'error')
            usuario_existente = usuario_controller.obtener_usuario_por_id(id, include_direccion=True)
            if not usuario_existente:
                return redirect(url_for('admin_usuario.listar_usuarios'))
            
            usuario_existente.update(request.form.to_dict())
            form_data = usuario_controller.obtener_datos_para_formulario_usuario()
            
            return render_template('usuarios/formulario.html', 
                                 usuario=usuario_existente, 
                                 is_new=False,
                                 roles=form_data.get('roles'),
                                 sectores=form_data.get('sectores'),
                                 turnos=form_data.get('turnos'),
                                 usuario_sectores_ids=[int(s) for s in request.form.getlist('sectores') if s.isdigit()])

    # Método GET
    usuario = usuario_controller.obtener_usuario_por_id(id, include_direccion=True)
    if not usuario:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('admin_usuario.listar_usuarios'))
        
    form_data = usuario_controller.obtener_datos_para_formulario_usuario()
    usuario_sectores_ids = usuario_controller.obtener_sectores_ids_usuario(id)

    return render_template('usuarios/formulario.html', 
                         usuario=usuario, 
                         is_new=False,
                         roles=form_data.get('roles'),
                         sectores=form_data.get('sectores'),
                         turnos=form_data.get('turnos'),
                         usuario_sectores_ids=usuario_sectores_ids)

@admin_usuario_bp.route('/<int:id>/eliminar', methods=['POST'])
@permission_required(accion='inactivar_usuarios')
def eliminar_usuario(id):
    """Realiza una desactivación lógica de un usuario."""
    if session.get('usuario_id') == id:
        msg = 'No puedes desactivar tu propia cuenta.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, error=msg), 400
        flash(msg, 'error')
        return redirect(url_for('admin_usuario.listar_usuarios'))

    resultado = usuario_controller.eliminar_usuario(id)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(resultado)
    
    if resultado.get('success'):
        flash('Usuario desactivado exitosamente.', 'success')
    else:
        flash(f"Error al desactivar el usuario: {resultado.get('error')}", 'error')
    return redirect(url_for('admin_usuario.listar_usuarios'))

@admin_usuario_bp.route('/<int:id>/habilitar', methods=['POST'])
@permission_any_of('modificar_usuarios', 'inactivar_usuarios')
def habilitar_usuario(id):
    """Reactiva un usuario lógicamente eliminado."""
    resultado = usuario_controller.habilitar_usuario(id)
    if resultado.get('success'):
        flash('Usuario activado exitosamente.', 'success')
    else:
        flash(f"Error al activar el usuario: {resultado.get('error')}", 'error')
    return redirect(url_for('admin_usuario.listar_usuarios'))
