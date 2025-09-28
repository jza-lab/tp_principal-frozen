from flask import Blueprint, session, request, redirect, url_for, flash, render_template
from app.controllers.usuario_controller import UsuarioController
from app.controllers.facial_controller import FacialController
from app.utils.decorators import roles_required

# Blueprint para la administración de usuarios
admin_usuario_bp = Blueprint('admin_usuario', __name__, url_prefix='/admin')

# Instanciar controladores
usuario_controller = UsuarioController()
facial_controller = FacialController()

@admin_usuario_bp.route('/')
@roles_required('ADMIN')
def index():
    """Página principal del panel de administración."""
    return render_template('dashboard/index.html')

@admin_usuario_bp.route('/usuarios')
@roles_required('ADMIN')
def listar_usuarios():
    """Muestra la lista de todos los usuarios del sistema."""
    usuarios = usuario_controller.obtener_todos_los_usuarios()
    return render_template('usuarios/listar.html', usuarios=usuarios)

@admin_usuario_bp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@roles_required('ADMIN')
def nuevo_usuario():
    """Gestiona la creación de un nuevo usuario, incluyendo el registro facial."""
    if request.method == 'POST':
        datos_usuario = request.form.to_dict()
        face_data = datos_usuario.pop('face_data', None)

        resultado = usuario_controller.crear_usuario(datos_usuario)
        
        if resultado.get('success'):
            usuario_creado = resultado.get('data')
            user_id = usuario_creado.get('id')
            
            if user_id and face_data:
                # Si hay datos faciales, intentar registrarlos
                resultado_facial = facial_controller.registrar_rostro(user_id, face_data)
                if resultado_facial.get('success'):
                    flash('Usuario creado y rostro registrado exitosamente.', 'success')
                else:
                    flash(f"Usuario creado, pero falló el registro facial: {resultado_facial.get('message')}", 'warning')
            else:
                # Si no hay datos faciales, solo informar de la creación del usuario
                flash('Usuario creado exitosamente (sin registro facial).', 'success')

            return redirect(url_for('admin_usuario.listar_usuarios'))
        else:
            # Si la creación del usuario falla, mostrar el error
            flash(f"Error al crear el usuario: {resultado.get('error')}", 'error')
            return render_template('usuarios/formulario.html', usuario=datos_usuario, is_new=True)
            
    return render_template('usuarios/formulario.html', usuario={}, is_new=True)

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
            return render_template('usuarios/formulario.html', usuario=usuario, is_new=False)

    usuario = usuario_controller.obtener_usuario_por_id(id)
    if not usuario:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('admin_usuario.listar_usuarios'))
    return render_template('usuarios/formulario.html', usuario=usuario, is_new=False)

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

@admin_usuario_bp.route('/usuarios/<int:id>/habilitar', methods=['POST'])
@roles_required('ADMIN')
def habilitar_usuario(id):
    """Reactiva un usuario."""
    resultado = usuario_controller.habilitar_usuario(id)
    if resultado.get('success'):
        flash('Usuario activado exitosamente.', 'success')
    else:
        flash(f"Error al activar el usuario: {resultado.get('error')}", 'error')
    return redirect(url_for('admin_usuario.listar_usuarios'))