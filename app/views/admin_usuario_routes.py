from flask import Blueprint, session, request, redirect, url_for, flash, render_template
from app.controllers.usuario_controller import UsuarioController
from app.utils.decorators import roles_required

# Blueprint para la administración de usuarios
admin_usuario_bp = Blueprint('admin_usuario', __name__, url_prefix='/admin')

# Instanciar controlador
usuario_controller = UsuarioController()

@admin_usuario_bp.route('/')
@roles_required('ADMIN')
def index():
    """Página principal del panel de administración."""
    return render_template('admin/index.html')

@admin_usuario_bp.route('/usuarios')
@roles_required('ADMIN')
def listar_usuarios():
    """Muestra la lista de todos los usuarios del sistema."""
    usuarios = usuario_controller.obtener_todos_los_usuarios()
    return render_template('admin/usuarios/listar.html', usuarios=usuarios)

@admin_usuario_bp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@roles_required('ADMIN')
def nuevo_usuario():
    """Gestiona la creación de un nuevo usuario."""
    if request.method == 'POST':
        datos_usuario = request.form.to_dict()
        resultado = usuario_controller.crear_usuario(datos_usuario)
        if resultado.get('success'):
            usuario_creado = resultado.get('usuario')
            # Guardar el ID del nuevo usuario y una bandera para el flujo de registro facial
            session['pending_register_user_id'] = usuario_creado['id']
            session['admin_creation_flow'] = True  # Bandera para redirigir de vuelta al admin
            
            flash('Usuario creado. Ahora proceda con el registro facial.', 'info')
            return redirect(url_for('auth.register_face_page'))
        else:
            flash(f"Error al crear el usuario: {resultado.get('error')}", 'error')
            return render_template('admin/usuarios/formulario.html', usuario=datos_usuario, is_new=True)
    return render_template('admin/usuarios/formulario.html', usuario={}, is_new=True)

@admin_usuario_bp.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@roles_required('ADMIN')
def editar_usuario(id):
    """Gestiona la edición de un usuario existente."""
    if request.method == 'POST':
        datos_actualizados = request.form.to_dict()
        resultado = usuario_controller.actualizar_usuario(id, datos_actualizados)
        if resultado.get('success'):
            flash('Usuario actualizado exitosamente.', 'success')
            return redirect(url_for('admin_usuario.listar_usuarios'))
        else:
            flash(f"Error al actualizar el usuario: {resultado.get('error')}", 'error')
            usuario = request.form.to_dict()
            usuario['id'] = id
            return render_template('admin/usuarios/formulario.html', usuario=usuario, is_new=False)

    usuario = usuario_controller.obtener_usuario_por_id(id)
    if not usuario:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('admin_usuario.listar_usuarios'))
    return render_template('admin/usuarios/formulario.html', usuario=usuario, is_new=False)

@admin_usuario_bp.route('/usuarios/<int:id>/eliminar', methods=['POST'])
@roles_required('ADMIN')
def eliminar_usuario(id):
    """Desactiva un usuario (eliminación lógica)."""
    if session.get('usuario_id') == id:
        flash('No puedes desactivar tu propia cuenta.', 'error')
        return redirect(url_for('admin_usuario.listar_usuarios'))

    resultado = usuario_controller.eliminar_usuario(id)
    if resultado.get('success'):
        flash('Usuario desactivado exitosamente.', 'success')
    else:
        flash(f"Error al desactivar el usuario: {resultado.get('error')}", 'error')
    return redirect(url_for('admin_usuario.listar_usuarios'))