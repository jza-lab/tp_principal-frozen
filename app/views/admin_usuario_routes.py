from flask import Blueprint, jsonify, session, request, redirect, url_for, flash, render_template
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

@admin_usuario_bp.route('/usuarios/<int:id>')
@roles_required('ADMIN')
def ver_perfil(id):
    """Muestra el perfil de un usuario específico."""
    usuario = usuario_controller.obtener_usuario_por_id(id)
    if not usuario:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('admin_usuario.listar_usuarios'))
    return render_template('usuarios/perfil.html', usuario=usuario)

@admin_usuario_bp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@roles_required('ADMIN')
def nuevo_usuario():
    """
    Gestiona la creación de un nuevo usuario con una lógica de validación facial robusta.
    El rostro se valida ANTES de crear el usuario para asegurar la atomicidad.
    """
    if request.method == 'POST':
        datos_usuario = request.form.to_dict()
        face_data = datos_usuario.pop('face_data', None)

        # 1. Si se adjuntó una foto, validarla primero.
        if face_data:
            validacion_facial = facial_controller.validar_y_codificar_rostro(face_data)
            if not validacion_facial.get('success'):
                flash(f"Error en el registro facial: {validacion_facial.get('message')}", 'error')
                return render_template('usuarios/formulario.html', usuario=datos_usuario, is_new=True)

        # 2. Si no hubo foto o la validación facial fue exitosa, proceder a crear el usuario.
        resultado_creacion = usuario_controller.crear_usuario(datos_usuario)
        
        if not resultado_creacion.get('success'):
            # Si la creación del usuario falla (p. ej. email/legajo duplicado), mostrar error.
            flash(f"Error al crear el usuario: {resultado_creacion.get('error')}", 'error')
            return render_template('usuarios/formulario.html', usuario=datos_usuario, is_new=True)

        # 3. Si el usuario se creó correctamente, registrar el rostro (si aplica).
        usuario_creado = resultado_creacion.get('data')
        user_id = usuario_creado.get('id')

        if user_id and face_data:
            # Llamamos a registrar_rostro, que ahora solo actualiza el encoding.
            # La validación costosa ya se hizo.
            resultado_facial = facial_controller.registrar_rostro(user_id, face_data)
            if resultado_facial.get('success'):
                flash('Usuario creado y rostro registrado exitosamente.', 'success')
            else:
                # Este es un caso raro donde la validación inicial pasó pero el guardado final falló.
                # Se informa al admin que el usuario se creó pero sin rostro.
                flash(f"Usuario creado, pero falló el registro facial final: {resultado_facial.get('message')}", 'warning')
        else:
            flash('Usuario creado exitosamente (sin registro facial).', 'success')

        return redirect(url_for('admin_usuario.listar_usuarios'))

    # Para el método GET, simplemente mostrar el formulario vacío.
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
    if session.get('usuario_id') == id:
        msg = 'No puedes desactivar tu propia cuenta.'
        if request.is_json:  # viene desde fetch
            return jsonify(success=False, error=msg)
        flash(msg, 'error')
        return redirect(url_for('admin_usuario.listar_usuarios'))

    resultado = usuario_controller.eliminar_usuario(id)
    if request.is_json:
        return jsonify(resultado)
    
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

@admin_usuario_bp.route('/usuarios/validar', methods=['POST'])
@roles_required('ADMIN')
def validar_campo():
    """
    Valida de forma asíncrona si un campo (legajo o email) ya existe.
    """
    data = request.get_json()
    field = data.get('field')
    value = data.get('value')
    
    if not field or not value:
        return jsonify({'valid': False, 'error': 'Campo o valor no proporcionado.'}), 400

    resultado = usuario_controller.validar_campo_unico(field, value)
    return jsonify(resultado)