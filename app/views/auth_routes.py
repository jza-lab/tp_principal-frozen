from flask import Blueprint, jsonify, session, request, redirect, url_for, flash, render_template
from app.controllers.usuario_controller import UsuarioController
from app.controllers.facial_controller import FacialController
from app.utils.roles import get_redirect_url_by_role

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

usuario_controller = UsuarioController()
facial_controller = FacialController()

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Gestiona el inicio de sesión de los usuarios."""
    if request.method == 'POST':
        legajo = request.form['legajo']
        password = request.form['password']
        
        respuesta = usuario_controller.autenticar_usuario_web(legajo, password)
        usuario = respuesta.get('data')

        if respuesta.get('success') and usuario and usuario.get('activo'):
            rol = usuario.get('roles', {})
            rol_codigo = rol.get('codigo')
            rol_nivel = rol.get('nivel', 0)

            session['usuario_id'] = usuario['id']
            session['rol'] = rol_codigo
            session['user_level'] = rol_nivel
            session['usuario_nombre'] = f"{usuario['nombre']}"
            session['user_data'] = usuario

            flash(f"Bienvenido {usuario['nombre']}", 'success')
            return redirect(get_redirect_url_by_role(rol_codigo))
        else:
            error_message = respuesta.get('error', 'Credenciales incorrectas o usuario inactivo.')
            flash(error_message, 'error')
            return redirect(url_for('auth.login'))

    return render_template('usuarios/login.html')

@auth_bp.route("/identificar_rostro", methods=["POST"])
def identificar_rostro():
    """Gestiona el inicio de sesión web mediante reconocimiento facial."""
    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"success": False, "message": "No se proporcionó imagen."}), 400

    image_data_url = data.get("image")
    respuesta = usuario_controller.autenticar_usuario_facial_web(image_data_url)
    usuario = respuesta.get('data')

    if respuesta.get('success') and usuario:
        rol = usuario.get('roles', {})
        rol_codigo = rol.get('codigo')
        rol_nivel = rol.get('nivel', 0)
        
        session['usuario_id'] = usuario['id']
        session['rol'] = rol_codigo
        session['user_level'] = rol_nivel
        session['usuario_nombre'] = f"{usuario.get('nombre')} {usuario.get('apellido')}"
        session['user_data'] = usuario

        return jsonify({
            'success': True, 
            'message': 'Rostro identificado correctamente.',
            'redirect': get_redirect_url_by_role(rol_codigo)
        }), 200
    else:
        error_message = respuesta.get('message', 'Rostro no reconocido o usuario inactivo.')
        return jsonify({'success': False, 'message': error_message}), 401

@auth_bp.route('/logout')
def logout():
    """Cierra la sesión del usuario actual."""
    session.clear()
    flash("Sesión cerrada correctamente.", "info")
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