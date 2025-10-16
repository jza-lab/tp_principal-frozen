from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from typing import Any

def safe_serialize(obj: Any) -> Any:
    """
    Serializa de forma recursiva un objeto a tipos de datos compatibles con JSON.

    Maneja tipos comunes como datetime, date, Decimal y UUID, convirtiéndolos
    a strings. Es útil para preparar datos complejos antes de enviarlos
    como respuesta JSON.
    """
    if isinstance(obj, (dict)):
        return {k: safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [safe_serialize(item) for item in obj]
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    
    # Devuelve el objeto sin cambios si ya es de un tipo compatible con JSON
    return obj
