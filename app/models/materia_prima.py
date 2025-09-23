from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class MateriaPrima:
    id: Optional[int]
    codigo: str
    nombre: str
    unidad_medida: str  # kg, g, litros, unidades
    categoria: str
    stock_actual: float
    stock_minimo: float
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    activo: bool = True
    
    def to_dict(self):
        return {
            'id': self.id,
            'codigo': self.codigo,
            'nombre': self.nombre,
            'unidad_medida': self.unidad_medida,
            'categoria': self.categoria,
            'stock_actual': self.stock_actual,
            'stock_minimo': self.stock_minimo,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'activo': self.activo
        }
    
    def esta_en_stock_minimo(self) -> bool:
        return self.stock_actual <= self.stock_minimo
