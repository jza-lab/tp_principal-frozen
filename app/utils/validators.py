from datetime import date, datetime
import uuid
from typing import Dict, Any, Optional

def validate_uuid(uuid_string: str) -> bool:
    """
    Valida si un string tiene el formato de un UUID válido.
    """
    try:
        uuid.UUID(uuid_string)
        return True
    except (ValueError, TypeError):
        return False

def validate_pagination(page: int, page_size: int, max_page_size: int = 100) -> Dict[str, str]:
    """
    Valida los parámetros de paginación para asegurar que estén dentro de rangos lógicos.
    """
    errors = {}
    if page < 1:
        errors['page'] = 'El número de página debe ser mayor a 0.'
    if page_size < 1:
        errors['page_size'] = 'El tamaño de página debe ser mayor a 0.'
    if page_size > max_page_size:
        errors['page_size'] = f'El tamaño máximo de página permitido es {max_page_size}.'
    return errors

def normalize_date(date_value: Any) -> Optional[str]:
    """
    Normaliza un valor de fecha (string, date, o datetime) a un string en formato ISO (YYYY-MM-DD).
    """
    if date_value is None:
        return None
    if isinstance(date_value, str):
        try:
            # Intenta parsear para normalizar formatos como "dd-mm-yyyy"
            return datetime.fromisoformat(date_value).date().isoformat()
        except ValueError:
            return date_value # Devuelve el string original si no es ISO
    if isinstance(date_value, datetime):
        return date_value.date().isoformat()
    if isinstance(date_value, date):
        return date_value.isoformat()
    
    return str(date_value)
