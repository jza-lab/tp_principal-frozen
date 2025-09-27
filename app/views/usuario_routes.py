from flask import Blueprint, session, request, redirect, url_for, flash, render_template
from controllers.usuario_controller import UsuarioController
from utils.decorators import roles_required

usuario_bp = Blueprint('usuario', __name__, url_prefix='/')
usuario_controller = UsuarioController()

# --- Rutas de Autenticación ---

@usuario_bp.route('/auth/login', methods=['GET', 'POST'])
def login():
    """Gestiona el inicio de sesión de los usuarios."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        usuario = usuario_controller.autenticar_usuario(email, password)
        if usuario and usuario.get('activo'):
            session['usuario_id'] = usuario['id']
            session['rol'] = usuario['rol']
            session['usuario_nombre'] = f"{usuario['nombre']} {usuario['apellido']}"
            flash(f"Bienvenido {usuario['nombre']}", 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('Credenciales incorrectas o usuario inactivo.', 'error')
    return render_template('usuarios/login.html')

@usuario_bp.route('/auth/logout')
def logout():
    """Cierra la sesión del usuario actual."""
    session.clear()
    flash('Sesión cerrada exitosamente.', 'info')
    return redirect(url_for('usuario.login'))

@usuario_bp.route('/auth/perfil')
def perfil():
    """Muestra la página de perfil del usuario que ha iniciado sesión."""
    if 'usuario_id' not in session:
        return redirect(url_for('usuario.login'))
    usuario = usuario_controller.obtener_usuario_por_id(session['usuario_id'])
    if not usuario:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('usuario.logout'))
    return render_template('usuarios/perfil.html', usuario=usuario)

# --- Panel de Administración ---

@usuario_bp.route('/admin')
@roles_required('ADMIN')
def admin_index():
    """Página principal del panel de administración."""
    return render_template('admin/index.html')

# --- Administración de Usuarios ---

@usuario_bp.route('/admin/usuarios')
@roles_required('ADMIN')
def admin_listar_usuarios():
    """Muestra la lista de todos los usuarios del sistema."""
    usuarios = usuario_controller.obtener_todos_los_usuarios()
    return render_template('admin/usuarios/listar.html', usuarios=usuarios)

@usuario_bp.route('/admin/usuarios/nuevo', methods=['GET', 'POST'])
@roles_required('ADMIN')
def admin_nuevo_usuario():
    """Gestiona la creación de un nuevo usuario."""
    if request.method == 'POST':
        datos_usuario = request.form.to_dict()
        resultado = usuario_controller.crear_usuario(datos_usuario)
        if resultado.get('success'):
            flash('Usuario creado exitosamente.', 'success')
            return redirect(url_for('usuario.admin_listar_usuarios'))
        else:
            flash(f"Error al crear el usuario: {resultado.get('error')}", 'error')
            return render_template('admin/usuarios/formulario.html', usuario=datos_usuario, is_new=True)
    return render_template('admin/usuarios/formulario.html', usuario={}, is_new=True)

@usuario_bp.route('/admin/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@roles_required('ADMIN')
def admin_editar_usuario(id):
    """Gestiona la edición de un usuario existente."""
    if request.method == 'POST':
        datos_actualizados = request.form.to_dict()
        resultado = usuario_controller.actualizar_usuario(id, datos_actualizados)
        if resultado.get('success'):
            flash('Usuario actualizado exitosamente.', 'success')
            return redirect(url_for('usuario.admin_listar_usuarios'))
        else:
            flash(f"Error al actualizar el usuario: {resultado.get('error')}", 'error')
            usuario = request.form.to_dict()
            usuario['id'] = id
            return render_template('admin/usuarios/formulario.html', usuario=usuario, is_new=False)
    usuario = usuario_controller.obtener_usuario_por_id(id)
    if not usuario:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('usuario.admin_listar_usuarios'))
    return render_template('admin/usuarios/formulario.html', usuario=usuario, is_new=False)

@usuario_bp.route('/admin/usuarios/<int:id>/eliminar', methods=['POST'])
@roles_required('ADMIN')
def admin_eliminar_usuario(id):
    """Desactiva un usuario (eliminación lógica)."""
    if session.get('usuario_id') == id:
        flash('No puedes desactivar tu propia cuenta.', 'error')
        return redirect(url_for('usuario.admin_listar_usuarios'))
    resultado = usuario_controller.eliminar_usuario(id)
    if resultado.get('success'):
        flash('Usuario desactivado exitosamente.', 'success')
    else:
        flash(f"Error al desactivar el usuario: {resultado.get('error')}", 'error')
    return redirect(url_for('usuario.admin_listar_usuarios'))