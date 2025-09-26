from dataclasses import dataclass, asdict
from typing import Optional
from datetime import date, datetime

@dataclass
class Pedido:
    """Representa un pedido de un cliente para un producto específico.
    Esta clase modela la solicitud de un cliente, que luego puede ser
    agrupada con otros pedidos para generar una orden de producción consolidada."""

    id: Optional[int]
    producto_id: int
    cantidad: float
    nombre_cliente: str
    fecha_solicitud: date
    estado: str = 'PENDIENTE'
    orden_produccion_id: Optional[int] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convierte la instancia del modelo a un diccionario."""
        d = asdict(self)
        for key, value in d.items():
            if isinstance(value, (datetime, date)):
                d[key] = value.isoformat() if value else None
        return d