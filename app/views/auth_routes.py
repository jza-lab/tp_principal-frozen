from flask import Blueprint, jsonify, request, redirect, url_for, flash, render_template
from flask_jwt_extended import create_access_token, jwt_required, get_jwt, unset_jwt_cookies, set_access_cookies, get_jwt_identity
from app.controllers.usuario_controller import UsuarioController
from app.utils.roles import get_redirect_url_by_role
from app.models.totem_sesion import TotemSesionModel
from app.models.autorizacion_ingreso import AutorizacionIngresoModel
from app.utils.date_utils import get_now_in_argentina
from app.models.token_blacklist_model import TokenBlacklistModel

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

usuario_controller = UsuarioController()
totem_sesion_model = TotemSesionModel()
autorizacion_model = AutorizacionIngresoModel()

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Gestiona el inicio de sesión de los usuarios."""
    totem_sesion_model.cerrar_sesiones_expiradas()
    
    if request.method == 'POST':
        legajo = request.form['legajo']
        password = request.form['password']
        
        respuesta = usuario_controller.autenticar_usuario_web(legajo, password)

        if respuesta.get('success'):
            usuario_data = respuesta['data']
            # Creamos el token. La 'identity' es el ID del usuario, y pasamos el resto
            # de los datos (rol, permisos) como 'additional_claims'.
            access_token = create_access_token(
                identity=usuario_data['id'],
                additional_claims={
                    'rol': usuario_data.get('roles', {}).get('codigo'),
                    'permisos': usuario_data.get('permisos', {}),
                    'user_level': usuario_data.get('roles', {}).get('nivel', 0)
                }
            )
            
            rol_codigo = usuario_data.get('roles', {}).get('codigo')
            redirect_url = get_redirect_url_by_role(rol_codigo)
            
            # Creamos la respuesta de redirección
            response = redirect(redirect_url)
            
            # Establecemos el token JWT en una cookie HttpOnly
            set_access_cookies(response, access_token)
            
            flash(f"Bienvenido {usuario_data['nombre']}", 'success')
            return response
        else:
            error_message = respuesta.get('error', 'Credenciales incorrectas o usuario inactivo.')
            flash(error_message, 'error')
            return redirect(url_for('auth.login'))

    return render_template('usuarios/login.html')

@auth_bp.route("/identificar_rostro", methods=["POST"])
def identificar_rostro():
    """Gestiona el inicio de sesión web mediante reconocimiento facial."""
    totem_sesion_model.cerrar_sesiones_expiradas()

    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"success": False, "message": "No se proporcionó imagen."}), 400

    image_data_url = data.get("image")
    respuesta = usuario_controller.autenticar_usuario_facial_web(image_data_url)

    if respuesta.get('success'):
        usuario_data = respuesta['data']
        access_token = create_access_token(
            identity=usuario_data['id'],
            additional_claims={
                'rol': usuario_data.get('roles', {}).get('codigo'),
                'permisos': usuario_data.get('permisos', {}),
                'user_level': usuario_data.get('roles', {}).get('nivel', 0)
            }
        )
        
        rol_codigo = usuario_data.get('roles', {}).get('codigo')
        redirect_url = get_redirect_url_by_role(rol_codigo)
        
        response = jsonify({
            'success': True,
            'message': 'Rostro identificado correctamente.',
            'redirect': redirect_url
        })
        
        # Establecemos la cookie en la respuesta JSON
        set_access_cookies(response, access_token)
        
        return response, 200
    else:
        error_message = respuesta.get('error', 'Rostro no reconocido o usuario inactivo.')
        return jsonify({'success': False, 'message': error_message}), 401

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    Cierra la sesión del usuario actual invalidando el token JWT.
    Se cambia a método POST por seguridad (evita CSRF en logout).
    """
    try:
        jwt_payload = get_jwt()
        jti = jwt_payload['jti']
        exp = jwt_payload['exp']
        
        TokenBlacklistModel.add_to_blacklist(jti, exp)
        
        response = redirect(url_for('auth.login'))
        unset_jwt_cookies(response)
        
        flash("Sesión cerrada correctamente.", "info")
        return response
        
    except Exception as e:
        # Loggear el error sería ideal en producción
        flash("Ocurrió un error al cerrar la sesión.", "error")
        response = redirect(url_for('auth.login'))
        unset_jwt_cookies(response)
        return response

@auth_bp.route('/perfil')
@jwt_required()
def perfil():
    """Muestra la página de perfil del usuario que ha iniciado sesión."""
    usuario_id = get_jwt_identity()
    usuario = usuario_controller.obtener_usuario_por_id(usuario_id)
    if not usuario:
        flash('Usuario no encontrado.', 'error')
        
        # Preparamos una respuesta de logout para limpiar la cookie en caso de inconsistencia
        response = redirect(url_for('auth.login'))
        unset_jwt_cookies(response)
        return response
        
    return render_template('usuarios/perfil.html', usuario=usuario)