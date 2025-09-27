from flask import Blueprint, session, request, redirect, url_for, flash, render_template
from app.controllers.usuario_controller import UsuarioController
from app.views.facial_routes import FacialController

# Blueprint para la autenticación de usuarios
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Instanciar controladores
usuario_controller = UsuarioController()
facial_controller = FacialController()

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Gestiona el inicio de sesión de los usuarios."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Validar con rostro si está pendiente
        pending_user = session.get("pending_face_user")
        if pending_user and email != pending_user:
            flash("El email no coincide con el rostro detectado.", "error")
            return redirect(url_for('auth.login'))

        usuario = usuario_controller.autenticar_usuario(email, password)
        if usuario and usuario.get('activo'):
            session['usuario_id'] = usuario['id']
            session['rol'] = usuario['rol']
            session['usuario_nombre'] = f"{usuario['nombre']} {usuario['apellido']}"
            session['user_data'] = usuario # Guardar para el registro de egreso

            # Registrar ingreso en CSV
            facial_controller.registrar_ingreso_csv(usuario)

            # Limpiar sesión de rostro pendiente
            session.pop("pending_face_user", None)

            flash(f"Bienvenido {usuario['nombre']}", 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('Credenciales incorrectas o usuario inactivo.', 'error')
            return redirect(url_for('auth.login'))

    # Para peticiones GET, simplemente renderizar la plantilla
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    """Cierra la sesión del usuario actual."""
    if 'user_data' in session:
        facial_controller.registrar_egreso_csv(session['user_data'])
        flash("Egreso registrado correctamente. Sesión cerrada.", "info")
    else:
        flash("Sesión cerrada.", "info")

    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/perfil')
def perfil():
    """Muestra la página de perfil del usuario que ha iniciado sesión."""
    if 'usuario_id' not in session:
        return redirect(url_for('auth.login'))

    usuario = usuario_controller.obtener_usuario_por_id(session['usuario_id'])
    if not usuario:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('auth.logout'))

    return render_template('usuarios/perfil.html', usuario=usuario)