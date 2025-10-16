from datetime import datetime
from app.utils.permission_map import CANONICAL_PERMISSION_MAP
from flask import Flask

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

def register_template_extensions(app: Flask):
    """
    Registra todos los helpers de plantillas (filtros, procesadores de contexto)
    en la aplicación Flask.
    """
    app.jinja_env.filters['format_datetime'] = _format_datetime_filter
    app.context_processor(_inject_permission_map)
