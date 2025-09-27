from flask import Blueprint, jsonify, session, request, redirect, url_for, flash, render_template
from app.controllers.usuario_controller import UsuarioController
from app.controllers.facial_controller import FacialController

# Blueprint para la autenticación de usuarios
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Instanciar controladores
usuario_controller = UsuarioController()
facial_controller = FacialController()

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Gestiona el inicio de sesión de los usuarios."""
    session.clear()
    if request.method == 'POST':
        legajo = request.form['legajo']
        password = request.form['password']

        # Validar con rostro si está pendiente
        pending_user = session.get("pending_face_user")

        if pending_user and legajo != pending_user:
            flash("El legajo no coincide con el rostro detectado.", "error")
            return redirect(url_for('auth.login'))

        usuario = usuario_controller.autenticar_usuario(legajo, password)

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
            return redirect(url_for('admin_usuario.index'))
        else:
            flash('Credenciales incorrectas o usuario inactivo.', 'error')
            return redirect(url_for('auth.login'))

    # Para peticiones GET, simplemente renderizar la plantilla
    return render_template('usuarios/login.html')

@auth_bp.route("/identificar_rostro", methods=["GET","POST"])
def identificar_rostro():
    data = request.get_json()
    image_data_url = data.get("image")
    
    resultado = facial_controller.identificar_rostro(image_data_url)
    estado=resultado['success']

    if(estado):
        usuario= resultado['usuario']
        if(usuario and usuario.get('id') and usuario.get('activo')):
            session['usuario_id'] = usuario['id']
            session['rol'] = usuario['rol']
            session['usuario_nombre'] = f"{usuario['nombre']} {usuario['apellido']}"
            session['user_data'] = usuario
            return jsonify({
                    'success': True, 
                    'message': 'Rostro identificado correctamente.',
                    'redirect': url_for('admin_usuario.index') # Redirigir a la página principal
                }), 200
    else:
         return jsonify({
            'success': False, 
            'message': 'Rostro no reconocido o usuario inactivo. Por favor, ingrese mediante sus credenciales.'
        }), 401

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