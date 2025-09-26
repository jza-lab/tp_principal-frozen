from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime
from models.base_model import BaseModel

@dataclass
class AsistenciaRegistro:
    """Representa un registro de entrada o salida de un empleado.

    Esta clase modela un evento de fichaje, que puede ser tanto el inicio
    como el fin de la jornada laboral de un usuario."""
    id: Optional[int]
    usuario_id: int
    tipo: str  # 'ENTRADA' o 'SALIDA'
    fecha_hora: Optional[datetime] = None
    observaciones: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.fecha_hora:
            d['fecha_hora'] = self.fecha_hora.isoformat()
        return d


class AsistenciaModel(BaseModel):
    """
    Modelo para interactuar con la tabla 'asistencias'.
    """
    def get_table_name(self) -> str:
        return 'asistencias'
