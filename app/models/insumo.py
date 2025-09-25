from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID

@dataclass
class Insumo:
    id_insumo: UUID
    nombre: str
    unidad_medida: str
    
    codigo_interno: Optional[str] = None
    codigo_ean: Optional[str] = None
    categoria: Optional[str] = None
    descripcion: Optional[str] = None
    tem_recomendada: Optional[float] = None
    stock_min: Optional[int] = 0
    stock_max: Optional[int] = None
    vida_util_dias: Optional[int] = None
    es_critico: Optional[bool] = False
    requiere_certificacion: Optional[bool] = False
    activo: Optional[bool] = True
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)

    # Campo no presente en la tabla, pero útil para la lógica de negocio
    stock_actual: float = 0.0

    def to_dict(self):
        return {
            "id_insumo": str(self.id_insumo),
            "nombre": self.nombre,
            "codigo_interno": self.codigo_interno,
            "codigo_ean": self.codigo_ean,
            "unidad_medida": self.unidad_medida,
            "categoria": self.categoria,
            "descripcion": self.descripcion,
            "tem_recomendada": self.tem_recomendada,
            "stock_min": self.stock_min,
            "stock_max": self.stock_max,
            "vida_util_dias": self.vida_util_dias,
            "es_critico": self.es_critico,
            "requiere_certificacion": self.requiere_certificacion,
            "activo": self.activo,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def esta_en_stock_minimo(self) -> bool:
        if self.stock_min is None:
            return False
        return self.stock_actual <= self.stock_min
