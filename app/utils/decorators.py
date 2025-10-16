from functools import wraps
from flask import session, flash, redirect, url_for
from app.utils.roles import get_redirect_url_by_role

def roles_required(min_level: int = 0, allowed_roles: list = None):
    """
    Decorador para restringir el acceso a rutas basado en el nivel jerárquico
    o en una lista de roles permitidos.

    Un usuario obtiene acceso si su rol es 'GERENTE', o si cumple al menos
    una de las siguientes condiciones:
    - Su nivel jerárquico es igual o superior a `min_level`.
    - El código de su rol está en la lista `allowed_roles`.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'rol' not in session or 'user_level' not in session:
                flash('Acceso no autorizado. Por favor, inicie sesión.', 'error')
                return redirect(url_for('auth.login'))

            user_role_code = session.get('rol')
            user_level = session.get('user_level', 0)

            # El rol 'GERENTE' tiene acceso universal
            if user_role_code == 'GERENTE':
                return f(*args, **kwargs)

            is_authorized = False
            # Si no se especifica ninguna regla, se deniega el acceso por defecto
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
