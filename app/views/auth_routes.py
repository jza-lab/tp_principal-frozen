from flask import Blueprint, jsonify, request, redirect, url_for, flash, render_template, make_response, g
from flask_jwt_extended import create_access_token, jwt_required, get_jwt, unset_jwt_cookies, set_access_cookies, get_jwt_identity, verify_jwt_in_request
from app.controllers.usuario_controller import UsuarioController
from app.controllers.registro_controller import RegistroController
from app.utils.roles import get_redirect_url_by_role
from app.models.totem_sesion import TotemSesionModel
from app.models.autorizacion_ingreso import AutorizacionIngresoModel
from app.utils.date_utils import get_now_in_argentina
from app.models.token_blacklist_model import TokenBlacklistModel
from app.models.rol import RoleModel  # <--- NUEVO (Importar RoleModel)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

totem_sesion_model = TotemSesionModel()
autorizacion_model = AutorizacionIngresoModel()

@auth_bp.route('/login', methods=['GET', 'POST'])
@jwt_required(optional=True)
def login():
    """Gestiona el inicio de sesión de los usuarios."""
    # ... (el código de verificación de 'try...except...pass' se mantiene igual)
    try:
        verify_jwt_in_request(optional=True)
        jwt_payload = get_jwt()
        if jwt_payload:
            rol_codigo = jwt_payload.get('rol')
            redirect_url = get_redirect_url_by_role(rol_codigo)
            return redirect(redirect_url)
    except Exception:
        pass

    if request.method == 'POST':
        usuario_controller = UsuarioController()
        legajo = request.form['legajo']
        password = request.form['password']

        respuesta = usuario_controller.autenticar_usuario_web(legajo, password)

        if respuesta.get('success'):
            usuario_data = respuesta['data']
            rol_codigo = usuario_data.get('roles', {}).get('codigo') # <--- NUEVO
            
            # Obtenemos la lista de permisos para este rol
            lista_permisos = RoleModel.get_permissions_for_role(rol_codigo) # <--- NUEVO

            # Creamos el token.
            access_token = create_access_token(
                identity=str(usuario_data['id']),
                additional_claims={
                    'nombre': usuario_data.get('nombre'),
                    'apellido': usuario_data.get('apellido'),
                    'rol': rol_codigo, # <--- MODIFICADO
                    'rol_nombre': usuario_data.get('roles', {}).get('nombre'),
                    'user_level': usuario_data.get('roles', {}).get('nivel', 0),
                    'permisos': lista_permisos  # <--- NUEVO (¡Aquí está la lista!)
                }
            )

            # rol_codigo = usuario_data.get('roles', {}).get('codigo') # (Línea movida arriba)
            redirect_url = get_redirect_url_by_role(rol_codigo)

            # ... (el resto de la función 'login' se mantiene igual)
            response = redirect(redirect_url)
            unset_jwt_cookies(response)
            set_access_cookies(response, access_token)

            from types import SimpleNamespace
            usuario_log = SimpleNamespace(nombre=usuario_data['nombre'], apellido=usuario_data['apellido'], roles=[rol_codigo])
            detalle = f"El usuario '{usuario_data['nombre']} {usuario_data['apellido']}' inició sesión con credenciales."
            registro_controller = RegistroController()
            registro_controller.crear_registro(usuario_log, 'Accesos', 'Ingreso', detalle)

            return response
        else:
            # ... (la lógica de 'else' se mantiene igual)
            error_message = respuesta.get('error', 'Credenciales incorrectas o usuario inactivo.')
            flash(error_message, 'error')
            response = redirect(url_for('auth.login'))
            unset_jwt_cookies(response)
            return response

    # ... (el 'return' final del GET se mantiene igual)
    response = make_response(render_template('usuarios/login.html'))
    unset_jwt_cookies(response)
    return response

@auth_bp.route("/identificar_rostro", methods=["POST"])
def identificar_rostro():
    """Gestiona el inicio de sesión web mediante reconocimiento facial."""
    totem_sesion_model.cerrar_sesiones_expiradas()

    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"success": False, "message": "No se proporcionó imagen."}), 400

    usuario_controller = UsuarioController()
    image_data_url = data.get("image")
    respuesta = usuario_controller.autenticar_usuario_facial_web(image_data_url)

    if respuesta.get('success'):
        usuario_data = respuesta['data']
        rol_codigo = usuario_data.get('roles', {}).get('codigo') # <--- NUEVO
        
        # Obtenemos la lista de permisos para este rol
        lista_permisos = RoleModel.get_permissions_for_role(rol_codigo) # <--- NUEVO
        
        access_token = create_access_token(
            identity=str(usuario_data['id']),
            additional_claims={
                'nombre': usuario_data.get('nombre'),
                'apellido': usuario_data.get('apellido'),
                'rol': rol_codigo, # <--- MODIFICADO
                'rol_nombre': usuario_data.get('roles', {}).get('nombre'),
                'user_level': usuario_data.get('roles', {}).get('nivel', 0),
                'permisos': lista_permisos  # <--- NUEVO (¡Aquí también!)
            }
        )

        # rol_codigo = usuario_data.get('roles', {}).get('codigo') # (Línea movida arriba)
        redirect_url = get_redirect_url_by_role(rol_codigo)

        response = jsonify({
            'success': True,
            'message': 'Rostro identificado correctamente.',
            'redirect': redirect_url
        })

        unset_jwt_cookies(response)
        set_access_cookies(response, access_token)

        from types import SimpleNamespace
        usuario_log = SimpleNamespace(nombre=usuario_data['nombre'], apellido=usuario_data['apellido'], roles=[rol_codigo])
        detalle = f"El usuario '{usuario_data['nombre']} {usuario_data['apellido']}' inició sesión con reconocimiento facial."
        registro_controller = RegistroController()
        registro_controller.crear_registro(usuario_log, 'Accesos', 'Ingreso', detalle)

        return response, 200
    else:
        error_message = respuesta.get('error', 'Rostro no reconocido o usuario inactivo.')
        return jsonify({'success': False, 'message': error_message}), 401

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    # ... (la función 'logout' se mantiene igual)
    try:
        jwt_payload = get_jwt()
        jti = jwt_payload['jti']
        exp = jwt_payload['exp']

        from types import SimpleNamespace
        usuario_log = SimpleNamespace(nombre=jwt_payload['nombre'], apellido=jwt_payload['apellido'], roles=[jwt_payload['rol']])
        detalle = f"El usuario '{jwt_payload['nombre']} {jwt_payload['apellido']}' cerró sesión."
        registro_controller = RegistroController()
        registro_controller.crear_registro(usuario_log, 'Accesos', 'Egreso', detalle)

        TokenBlacklistModel.add_to_blacklist(jti, exp)
        response = redirect(url_for('auth.login'))
        unset_jwt_cookies(response)
        flash("Sesión cerrada correctamente.", "info")
        return response
    except Exception as e:
        flash("Ocurrió un error al cerrar la sesión.", "error")
        response = redirect(url_for('auth.login'))
        unset_jwt_cookies(response)
        return response

@auth_bp.route('/perfil')
@jwt_required()
def perfil():
    # ... (la función 'perfil' se mantiene igual)
    usuario_controller = UsuarioController()
    usuario_id = get_jwt_identity()
    usuario = usuario_controller.obtener_usuario_por_id(usuario_id)
    if not usuario:
        flash('Usuario no encontrado.', 'error')
        response = redirect(url_for('auth.login'))
        unset_jwt_cookies(response)
        return response
    return render_template('usuarios/perfil.html', usuario=usuario)