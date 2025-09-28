from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime
from app.models.base_model import BaseModel


@dataclass
class Receta:
    """Representa la receta para fabricar un producto terminado.

    Esta clase define los parámetros, tiempos y rendimiento de una versión
    específica de la receta para un producto. Se asocia con una lista de
    ingredientes a través de la clase `RecetaIngrediente`."""
    
    id: Optional[int]
    nombre: str
    version: str
    producto_id: Optional[int] = None
    descripcion: Optional[str] = None
    rendimiento: float = 0.0
    activa: bool = True
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.created_at:
            d['created_at'] = self.created_at.isoformat()
        return d

@dataclass
class RecetaIngrediente:
    """Representa un ingrediente específico dentro de una receta.

    Esta clase asocia una `MateriaPrima` con una `Receta`, especificando
    la cantidad necesaria de ese ingrediente."""
    id: Optional[int]
    receta_id: int
    materia_prima_id: int
    cantidad: float
    unidad: str

    def to_dict(self) -> dict:
        """Convierte la instancia del modelo a un diccionario."""
        return asdict(self)

class RecetaModel(BaseModel):
    """
    Modelo para interactuar con la tabla de recetas en la base de datos.
    """
    def get_table_name(self) -> str:
        return 'recetas'