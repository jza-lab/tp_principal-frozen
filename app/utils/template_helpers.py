from datetime import datetime
from app.utils.permission_map import CANONICAL_PERMISSION_MAP
from flask import Flask
from flask_jwt_extended import get_jwt

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
    """
    try:
        claims = get_jwt()
        user_role = claims.get('rol')

        if not user_role:
            return False
        
        if user_role == 'DEV':
            return True

        allowed_roles = CANONICAL_PERMISSION_MAP.get(action, [])
        return user_role in allowed_roles
    except Exception:
        # Si no hay un token JWT en el contexto (ej. página de login),
        # no hay permisos.
        return False

def _inject_user_from_jwt():
    """
    Procesador de contexto para inyectar datos del usuario desde el JWT.
    Esto hace que 'current_user' esté disponible en todas las plantillas
    siempre que haya un token JWT válido en la solicitud.
    """
    try:
        claims = get_jwt()
        nombre = claims.get('nombre')
        apellido = claims.get('apellido')
        
        # Crear un SimpleNamespace para permitir el acceso con notación de punto
        from types import SimpleNamespace
        current_user = SimpleNamespace(
            nombre=nombre,
            apellido=apellido,
            nombre_completo=f"{nombre or ''} {apellido or ''}".strip(),
            roles={'nombre': claims.get('rol')}
        )
        return {'current_user': current_user}
    except Exception:
        # Si no hay token JWT (p.ej. en la página de login),
        # get_jwt() lanza una excepción. En ese caso, no inyectamos nada.
        return {}


def register_template_extensions(app: Flask):
    """
    Registra todos los helpers de plantillas (filtros, procesadores de contexto)
    en la aplicación Flask.
    """
    app.jinja_env.filters['format_datetime'] = _format_datetime_filter
    app.jinja_env.filters['formato_moneda'] = _formato_moneda_filter
    app.jinja_env.tests['has_permission'] = _has_permission_filter
    app.context_processor(_inject_permission_map)
    app.context_processor(_inject_user_from_jwt)
