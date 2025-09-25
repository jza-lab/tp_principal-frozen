import json
from decimal import Decimal
from datetime import date, datetime
from flask.json.provider import DefaultJSONProvider  # ✅ Importación correcta para Flask 2.3+

class CustomJSONEncoder(DefaultJSONProvider):
    """Encoder personalizado para manejar Decimal y otros tipos no serializables"""

    def default(self, obj):
        # Convertir Decimal a float
        if isinstance(obj, Decimal):
            return float(obj)

        # Convertir date y datetime a string ISO
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()

        # Para otros tipos, usar el encoder por defecto
        return super().default(obj)
