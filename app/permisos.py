from functools import wraps
from flask import session, flash, redirect, url_for
from app.utils.roles import get_redirect_url_by_role
from app.utils.permission_map import get_allowed_roles_for_action

def permission_required(accion: str):
    """
    Decorator que verifica si un usuario tiene permiso para una acción.
    Utiliza el mapa canónico de permisos para determinar qué ROLES pueden realizar la acción,
    y luego comprueba el ROL del usuario en sesión contra esa lista.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'usuario_id' not in session or 'rol' not in session:
                flash('Acceso no autorizado. Por favor, inicie sesión.', 'error')
                return redirect(url_for('auth.login'))

            user_role_code = session.get('rol')
            if user_role_code == 'GERENTE': # El Gerente General tiene acceso a todo
                return f(*args, **kwargs)

            allowed_roles = get_allowed_roles_for_action(accion)

            if not allowed_roles:
                # Si la acción no está en el mapa, denegar por seguridad.
                flash(f'Acceso denegado. La acción "{accion}" no está configurada en el mapa de permisos.', 'error')
                return redirect(get_redirect_url_by_role(user_role_code))

            if user_role_code not in allowed_roles:
                flash(f'Su rol ({user_role_code}) no tiene los permisos necesarios ({accion}) para acceder a esta sección.', 'error')
                return redirect(get_redirect_url_by_role(user_role_code))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def permission_any_of(*actions):
    """
    Decorator que verifica si el rol tiene al menos UNO de varios permisos.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'rol' not in session:
                flash('Acceso no autorizado. Por favor, inicie sesión.', 'error')
                return redirect(url_for('auth.login'))

            user_role_code = session.get('rol')
            if user_role_code == 'GERENTE':
                return f(*args, **kwargs)

            has_any_permission = any(user_role_code in get_allowed_roles_for_action(action) for action in actions)

            if not has_any_permission:
                action_str = " o ".join(f'"{a}"' for a in actions)
                flash(f'Su rol ({user_role_code}) no tiene los permisos necesarios ({action_str}).', 'error')
                return redirect(get_redirect_url_by_role(user_role_code))

            return f(*args, **kwargs)
        return decorated_function
    return decorator