from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class MovimientoStock:
    id: Optional[int]
    materia_prima_id: int
    lote_id: Optional[int]
    tipo_movimiento: str  # ENTRADA, SALIDA
    cantidad: float
    fecha: datetime
    orden_produccion_id: Optional[int]
    usuario_id: int
    observaciones: Optional[str]
    
    def to_dict(self):
        return {
            'id': self.id,
            'materia_prima_id': self.materia_prima_id,
            'lote_id': self.lote_id,
            'tipo_movimiento': self.tipo_movimiento,
            'cantidad': self.cantidad,
            'fecha': self.fecha.isoformat() if self.fecha else None,
            'orden_produccion_id': self.orden_produccion_id,
            'usuario_id': self.usuario_id,
            'observaciones': self.observaciones
        }