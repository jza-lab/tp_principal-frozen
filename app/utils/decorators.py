from functools import wraps
from flask import flash, redirect
from flask_jwt_extended import jwt_required, get_jwt
from app.utils.roles import get_redirect_url_by_role
from app.utils.permission_map import get_allowed_roles_for_action

def permission_required(accion: str, allowed_roles: list = None):
    """
    Decorador que verifica si el rol de un usuario tiene permiso para una acción específica.
    Obtiene el rol desde el token JWT.
    """
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            claims = get_jwt()
            user_role_code = claims.get('rol')

            if user_role_code == 'DEV':
                return f(*args, **kwargs)

            # Comprobación de roles adicionales permitidos
            if allowed_roles and user_role_code in allowed_roles:
                return f(*args, **kwargs)

            allowed_roles_for_action = get_allowed_roles_for_action(accion)
            if user_role_code not in allowed_roles_for_action:
                flash(f'No tiene los permisos necesarios ({accion}) para acceder a esta sección.', 'error')
                return redirect(get_redirect_url_by_role(user_role_code))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def permission_any_of(*actions):
    """
    Decorador que verifica si el rol del usuario tiene al menos UNO de los permisos especificados.
    Obtiene el rol desde el token JWT.
    """
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            claims = get_jwt()
            user_role_code = claims.get('rol')

            if user_role_code == 'DEV':
                return f(*args, **kwargs)

            has_any_permission = any(user_role_code in get_allowed_roles_for_action(action) for action in actions)
            if not has_any_permission:
                flash('No tiene ninguno de los permisos requeridos para acceder a esta sección.', 'error')
                return redirect(get_redirect_url_by_role(user_role_code))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def roles_required(min_level: int = 0, allowed_roles: list = None):
    """
    Decorador (posiblemente obsoleto) para restringir el acceso basado en nivel jerárquico o una lista de roles.
    Obtiene los datos del token JWT.
    """
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            claims = get_jwt()
            user_role_code = claims.get('rol')
            user_level = claims.get('user_level', 0)

            if user_role_code == 'DEV':
                return f(*args, **kwargs)

            is_authorized = False
            if min_level > 0 and user_level >= min_level:
                is_authorized = True
            if allowed_roles and user_role_code in allowed_roles:
                is_authorized = True

            if not is_authorized:
                flash('No tiene los permisos necesarios para acceder a esta página.', 'error')
                return redirect(get_redirect_url_by_role(user_role_code))

            return f(*args, **kwargs)
        return decorated_function
    return decorator
