from datetime import date, datetime
import uuid
from typing import Dict, Any

def validate_uuid(uuid_string: str) -> bool:
    """Validar formato UUID"""
    try:
        uuid.UUID(uuid_string)
        return True
    except (ValueError, TypeError):
        return False

def validate_pagination(page: int, page_size: int, max_page_size: int = 100) -> Dict[str, Any]:
    """Validar parámetros de paginación"""
    errors = {}

    if page < 1:
        errors['page'] = 'La página debe ser mayor a 0'

    if page_size < 1:
        errors['page_size'] = 'El tamaño de página debe ser mayor a 0'

    if page_size > max_page_size:
        errors['page_size'] = f'El tamaño máximo de página es {max_page_size}'

    return errors

def normalize_date(date_value):
    """Normalizar fecha a string ISO format"""
    if date_value is None:
        return None

    if isinstance(date_value, str):
        return date_value  # Ya es string, devolverlo tal como está

    if isinstance(date_value, (datetime, date)):
        if isinstance(date_value, datetime):
            return date_value.date().isoformat()  # Convertir datetime a string
        return date_value.isoformat()  # Convertir date a string

    return str(date_value)