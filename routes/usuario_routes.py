import logging
from flask import Blueprint, session, request, redirect, url_for, flash, render_template, jsonify
from services.usuario_service import UsuarioService

usuario_bp = Blueprint('usuario', __name__, url_prefix='/usuarios')
usuario_service = UsuarioService()

@usuario_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login de usuario"""
    if request.method == 'POST':
        legajo = request.form['legajo']
        password = request.form['password']
        logging.warning(f"Login attempt for legajo: {legajo}")

        usuario = usuario_service.autenticar(legajo, password)
        if usuario:
            session['usuario_id'] = usuario.id
            session['usuario_rol'] = usuario.rol
            session['usuario_nombre'] = f"{usuario.nombre} {usuario.apellido}"
            
            flash(f'Bienvenido {usuario.nombre}', 'success')
            return redirect(url_for('dashboard.index')) #CAMBIAR HTML QUE PASE EL FRONT.
        else:
            # Logging mejorado para depuración
            user_exists = usuario_service.repository.obtener_por_legajo(legajo)
            if user_exists is None:
                logging.warning(f"DEBUG: Fallo de login para '{legajo}'. Razón: Usuario no encontrado o inactivo.")
            else:
                logging.warning(f"DEBUG: Fallo de login para '{legajo}'. Razón: Contraseña incorrecta.")

            flash('Credenciales incorrectas', 'error')
    
    return render_template('usuarios/login.html') #CAMBIAR HTML QUE PASE EL FRONT

@usuario_bp.route('/logout')
def logout():
    """Cerrar sesión"""
    session.clear()
    flash('Sesión cerrada', 'info')
    return redirect(url_for('usuario.login'))

@usuario_bp.route('/perfil')
def perfil():
    """Muestra el perfil del usuario."""
    if 'usuario_id' not in session:
        return redirect(url_for('usuario.login'))

    usuario = usuario_service.obtener_por_id(session['usuario_id'])
    if not usuario:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('usuario.logout'))

    return render_template('usuarios/perfil.html', usuario=usuario)

@usuario_bp.route('/registrar-rostro', methods=['POST'])
def registrar_rostro():
    """Endpoint para registrar el rostro de un usuario."""
    if 'usuario_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401

    # Aquí iría la lógica para recibir la imagen, procesarla y guardar el encoding.

    flash('Funcionalidad de registro facial no implementada.', 'info')
    return redirect(url_for('usuario.perfil'))

@usuario_bp.route('/login-facial', methods=['POST'])
def login_facial():
    """Endpoint para iniciar sesión con reconocimiento facial."""
    # Aquí iría la lógica para recibir la imagen, compararla y autenticar.
    
    flash('Funcionalidad de login facial no implementada.', 'info')
    return redirect(url_for('usuario.login'))