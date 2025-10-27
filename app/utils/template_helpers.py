from datetime import datetime
from app.utils.permission_map import CANONICAL_PERMISSION_MAP
from flask import Flask
from flask_jwt_extended import get_jwt, current_user

def _format_datetime_filter(value, format='%d/%m/%Y %H:%M'):
    """
    Filtro de Jinja2 para formatear un string ISO 8601 a un formato de fecha legible.
    """
    if value is None:
        return ""
    try:
        dt_object = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt_object.strftime(format)
    except (ValueError, TypeError):
        return value

def _inject_permission_map():
    """
    Procesador de contexto para inyectar el mapa de permisos en las plantillas.
    """
    return {'CANONICAL_PERMISSION_MAP': CANONICAL_PERMISSION_MAP}

def _formato_moneda_filter(value):
    """
    Filtro de Jinja2 para formatear un número como moneda (ej: 1.234,50).
    """
    if value is None:
        return "0,00"  # Aseguramos formato ARS/Latam para cero
    try:
        num = float(value)
        formatted_us = f"{num:,.2f}"
        formatted_ars = formatted_us.replace(",", "X") 
        formatted_ars = formatted_ars.replace(".", ",")
        formatted_ars = formatted_ars.replace("X", ".")
        return formatted_ars
            
    except (ValueError, TypeError):
        return value

def _has_permission_filter(action: str) -> bool:
    """
    Filtro de Jinja2 que verifica si el usuario actual tiene permiso para una acción.
    Utiliza el objeto `current_user` cargado en cada petición.
    """
    try:
        # `current_user` es un proxy gestionado por Flask-JWT-Extended.
        # Si no hay un usuario autenticado, será None.
        if not current_user:
            return False

        # El rol del usuario ahora se obtiene del objeto `current_user`.
        # Se accede de forma segura al objeto de rol anidado y a su código.
        user_role_obj = getattr(current_user, 'roles', None)
        user_role_code = None
        if isinstance(user_role_obj, dict):
            user_role_code = user_role_obj.get('codigo')
        elif hasattr(user_role_obj, 'codigo'):
            user_role_code = user_role_obj.codigo

        if not user_role_code:
            return False
        if user_role_code == 'DEV':
            return True

        allowed_roles = CANONICAL_PERMISSION_MAP.get(action, [])
        return user_role_code in allowed_roles
    except Exception as e:
        # Capturamos cualquier error inesperado y evitamos que la aplicación falle.
        print(f"Error en _has_permission_filter: {e}") # Log para depuración
        return False

def _inject_user_from_jwt():
    """
    Procesador de contexto para inyectar el objeto `current_user` completo,
    cargado por Flask-JWT-Extended, en todas las plantillas.
    """
    try:
        # Si hay un usuario cargado en el contexto de la solicitud, lo inyectamos.
        # current_user es un proxy que será None si no hay un usuario autenticado.
        if current_user:
            return {'current_user': current_user}
        return {}
    except Exception:
        # En caso de cualquier error (ej. fuera de un contexto de solicitud),
        # devolvemos un diccionario vacío para no romper la aplicación.
        return {}


def register_template_extensions(app: Flask):
    """
    Registra todos los helpers de plantillas (filtros, procesadores de contexto)
    en la aplicación Flask.
    """
    app.jinja_env.filters['format_datetime'] = _format_datetime_filter
    app.jinja_env.filters['formato_moneda'] = _formato_moneda_filter
    app.jinja_env.globals['has_permission'] = _has_permission_filter
    app.jinja_env.tests['has_permission'] = _has_permission_filter
    app.context_processor(_inject_permission_map)
    app.context_processor(_inject_user_from_jwt)