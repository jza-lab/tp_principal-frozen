from flask import Blueprint, jsonify, session, request, redirect, url_for, flash, render_template
from app.controllers.usuario_controller import UsuarioController
from app.utils.roles import get_redirect_url_by_role
from app.models.totem_sesion import TotemSesionModel
from app.models.autorizacion_ingreso import AutorizacionIngresoModel
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

usuario_controller = UsuarioController()
totem_sesion_model = TotemSesionModel()
autorizacion_model = AutorizacionIngresoModel()

@auth_bp.before_app_request
def before_request_auth():
    """
    Se ejecuta antes de cada solicitud para:
    1. Cerrar la sesión web del usuario si su turno ha expirado.
    2. Limpiar las sesiones de tótem expiradas de todos los usuarios.
    """
    if 'usuario_id' not in session or request.endpoint in ['auth.login', 'auth.logout', 'static']:
        return

    usuario = session.get('user_data')
    if not usuario:
        return

    rol = usuario.get('roles', {})
    if rol.get('codigo') == 'GERENTE':
        return

    turno_info = usuario.get('turno')
    if not turno_info or 'hora_inicio' not in turno_info or 'hora_fin' not in turno_info:
        return

    try:
        hora_inicio = datetime.strptime(turno_info['hora_inicio'], '%H:%M:%S').time()
        hora_fin = datetime.strptime(turno_info['hora_fin'], '%H:%M:%S').time()
        
        # Asumimos que la sesión web se inició el día de hoy
        fecha_sesion = datetime.today().date()
        
        limite_dt = datetime.combine(fecha_sesion, hora_fin) + timedelta(minutes=15)

        # Si es un turno nocturno, el límite es al día siguiente
        if hora_fin < hora_inicio:
            limite_dt += timedelta(days=1)
        
        if datetime.now() > limite_dt:
            # Antes de cerrar sesión, verificar si hay autorización de horas extras
            auth_result = autorizacion_model.find_by_usuario_and_fecha(
                usuario_id=usuario['id'],
                fecha=fecha_sesion,
                tipo='HORAS_EXTRAS',
                estado='APROBADA'
            )
            if auth_result.get('success'):
                # Iterar sobre todas las autorizaciones de HE para ver si alguna justifica la sesión activa
                for autorizacion in auth_result['data']:
                    auth_turno_info = autorizacion.get('turno')
                    if auth_turno_info:
                        auth_hora_inicio = datetime.strptime(auth_turno_info['hora_inicio'], '%H:%M:%S').time()
                        auth_hora_fin = datetime.strptime(auth_turno_info['hora_fin'], '%H:%M:%S').time()
                        
                        limite_he_dt = datetime.combine(fecha_sesion, auth_hora_fin) + timedelta(minutes=15)
                        
                        if auth_hora_fin < auth_hora_inicio: # Turno nocturno
                            limite_he_dt += timedelta(days=1)

                        if datetime.now() < limite_he_dt:
                            return  # La sesión está justificada por al menos una autorización, no hacer nada.
                
            flash('Tu turno ha finalizado. La sesión se ha cerrado automáticamente.', 'info')
            session.clear()
            return redirect(url_for('auth.login'))

    except (ValueError, TypeError):
        return

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Gestiona el inicio de sesión de los usuarios."""
    # Optimización: limpiar sesiones de tótem solo en el login
    totem_sesion_model.cerrar_sesiones_expiradas()
    
    if request.method == 'POST':
        legajo = request.form['legajo']
        password = request.form['password']        
        respuesta = usuario_controller.autenticar_usuario_web(legajo, password)

        if respuesta.get('success'):
            rol_codigo = respuesta.get('rol_codigo')
            usuario_nombre = session.get('usuario_nombre', 'Usuario') 
            flash(f"Bienvenido {usuario_nombre}", 'success')
            return redirect(get_redirect_url_by_role(rol_codigo))
        else:
            # Mostrar el error específico devuelto por el controlador
            error_message = respuesta.get('error', 'Credenciales incorrectas o usuario inactivo.')
            flash(error_message, 'error')
            return redirect(url_for('auth.login'))

    return render_template('usuarios/login.html')

@auth_bp.route("/identificar_rostro", methods=["POST"])
def identificar_rostro():
    """Gestiona el inicio de sesión web mediante reconocimiento facial."""
    # Optimización: limpiar sesiones de tótem solo en el login
    totem_sesion_model.cerrar_sesiones_expiradas()

    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"success": False, "message": "No se proporcionó imagen."}), 400

    image_data_url = data.get("image")
    respuesta = usuario_controller.autenticar_usuario_facial_web(image_data_url)

    if respuesta.get('success'):
        rol_codigo = respuesta.get('rol_codigo')
        return jsonify({
            'success': True, 
            'message': 'Rostro identificado correctamente.',
            'redirect': get_redirect_url_by_role(rol_codigo)
        }), 200
    else:
        error_message = respuesta.get('error', 'Rostro no reconocido o usuario inactivo.')
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