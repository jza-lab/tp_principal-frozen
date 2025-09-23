# Crea un archivo utils/serializers.py
from decimal import Decimal
from datetime import date, datetime

def serialize_data(data):
    """Convierte objetos Decimal y DateTime a tipos serializables por JSON"""
    if isinstance(data, dict):
        return {key: serialize_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [serialize_data(item) for item in data]
    elif isinstance(data, Decimal):
        return float(data)
    elif isinstance(data, (date, datetime)):
        return data.isoformat()
    else:
        return data