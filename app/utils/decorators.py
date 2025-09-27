from functools import wraps
from flask import session, flash, redirect, url_for

def roles_required(*roles):
    """
    Decorator que verifica si el rol del usuario actual está entre los permitidos.
    Uso: @roles_required('ADMIN', 'GERENTE')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Asumimos que el rol se guarda en la sesión al iniciar sesión
            if 'rol' not in session:
                flash('Acceso no autorizado. Por favor, inicie sesión.', 'error')
                return redirect(url_for('usuario.login'))

            user_role = session['rol']
            if user_role not in roles:
                flash('No tiene permiso para acceder a esta página.', 'error')
                # Redirigir al dashboard o a una página de 'acceso denegado'
                return redirect(url_for('dashboard.index'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator