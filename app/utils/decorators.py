from functools import wraps
from flask import session, flash, redirect, url_for
from app.utils.roles import get_redirect_url_by_role

def roles_required(min_level=0, allowed_roles=None):
    """
    Decorator mejorado que verifica permisos por nivel jerárquico o por roles específicos.
    Un usuario debe cumplir AL MENOS UNA de las condiciones si se especifican ambas.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'rol' not in session or 'user_level' not in session:
                flash('Acceso no autorizado. Por favor, inicie sesión.', 'error')
                return redirect(url_for('auth.login'))

            user_role_code = session.get('rol')
            user_level = session.get('user_level', 0)

            is_authorized = False
            if not min_level and not allowed_roles:
                is_authorized = False
            else:
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