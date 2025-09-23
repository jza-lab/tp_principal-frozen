from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime

@dataclass
class AsistenciaRegistro:
    id: Optional[int]
    usuario_id: int
    tipo: str  # 'ENTRADA' o 'SALIDA'
    fecha_hora: Optional[datetime] = None
    observaciones: Optional[str] = None

    def to_dict(self):
        """Convierte la instancia de dataclass a un diccionario."""
        d = asdict(self)
        if self.fecha_hora:
            d['fecha_hora'] = self.fecha_hora.isoformat()
        return d
