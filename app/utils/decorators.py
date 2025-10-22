from functools import wraps
from flask import session, flash, redirect, url_for
from app.utils.roles import get_redirect_url_by_role
from app.utils.permission_map import get_allowed_roles_for_action

def permission_required(accion: str):
    """
    Decorador que verifica si el rol de un usuario tiene permiso para una acción específica.
    Utiliza el mapa canónico de permisos para la validación.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'rol' not in session:
                flash('Acceso no autorizado. Por favor, inicie sesión.', 'error')
                return redirect(url_for('auth.login'))

            user_role_code = session.get('rol')
            if user_role_code == 'DEV':
                return f(*args, **kwargs)

            allowed_roles = get_allowed_roles_for_action(accion)
            if user_role_code not in allowed_roles:
                flash(f'No tiene los permisos necesarios ({accion}) para acceder a esta sección.', 'error')
                return redirect(get_redirect_url_by_role(user_role_code))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def permission_any_of(*actions):
    """
    Decorador que verifica si el rol del usuario tiene al menos UNO de los permisos especificados.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'rol' not in session:
                flash('Acceso no autorizado. Por favor, inicie sesión.', 'error')
                return redirect(url_for('auth.login'))

            user_role_code = session.get('rol')
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
    Se mantiene por compatibilidad, pero se recomienda usar permission_required o permission_any_of.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'rol' not in session or 'user_level' not in session:
                flash('Acceso no autorizado. Por favor, inicie sesión.', 'error')
                return redirect(url_for('auth.login'))

            user_role_code = session.get('rol')
            user_level = session.get('user_level', 0)

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
