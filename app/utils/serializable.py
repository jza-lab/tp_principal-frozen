from decimal import Decimal
from datetime import date, datetime
from uuid import UUID

def safe_serialize(obj):
    """Serializa de forma segura cualquier objeto a tipos JSON-compatibles"""
    if obj is None:
        return None
    elif isinstance(obj, (dict)):
        return {k: safe_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [safe_serialize(item) for item in obj]
    elif isinstance(obj, (Decimal, float, int)):
        return float(obj) if isinstance(obj, Decimal) else obj
    elif isinstance(obj, (date, datetime)):
        return obj.isoformat()
    elif isinstance(obj, UUID):
        return str(obj)
    elif hasattr(obj, 'isoformat'):  # Para otros objetos con isoformat
        return obj.isoformat()
    else:
        return str(obj)  # Fallback seguro