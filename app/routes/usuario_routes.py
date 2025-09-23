import logging
from flask import Blueprint, session, request, redirect, url_for, flash, render_template
from services.usuario_service import UsuarioService

usuario_bp = Blueprint('usuario', __name__, url_prefix='/usuarios')
usuario_service = UsuarioService()

@usuario_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login de usuario"""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        logging.warning(f"Login attempt for email: {email}")

        usuario = usuario_service.autenticar(email, password)
        if usuario:
            session['usuario_id'] = usuario.id
            session['usuario_rol'] = usuario.rol
            session['usuario_nombre'] = f"{usuario.nombre} {usuario.apellido}"
            
            flash(f'Bienvenido {usuario.nombre}', 'success')
            return redirect(url_for('dashboard.index')) #CAMBIAR HTML QUE PASE EL FRONT.
        else:
            # Logging mejorado para depuración
            user_exists = usuario_service.repository.obtener_por_email(email)
            if user_exists is None:
                logging.warning(f"DEBUG: Fallo de login para '{email}'. Razón: Usuario no encontrado o inactivo.")
            else:
                logging.warning(f"DEBUG: Fallo de login para '{email}'. Razón: Contraseña incorrecta.")

            flash('Credenciales incorrectas', 'error')
    
    return render_template('usuarios/login.html') #CAMBIAR HTML QUE PASE EL FRONT

@usuario_bp.route('/logout')
def logout():
    """Cerrar sesión"""
    session.clear()
    flash('Sesión cerrada', 'info')
    return redirect(url_for('usuario.login'))