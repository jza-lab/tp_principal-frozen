from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

@dataclass
class Lote:
    id: Optional[int]
    codigo: str
    materia_prima_id: int
    proveedor_id: int
    cantidad_inicial: float
    cantidad_actual: float
    fecha_ingreso: datetime
    fecha_vencimiento: Optional[datetime]
    numero_factura: Optional[str]
    costo_por_unidad: Optional[float]
    activo: bool = True
    # Campo para almacenar datos de joins, no es una columna directa de la tabla
    materia_prima: Optional[Dict[str, Any]] = field(default=None, repr=False)

    def to_dict(self):
        return {
            'id': self.id,
            'codigo': self.codigo,
            'materia_prima_id': self.materia_prima_id,
            'proveedor_id': self.proveedor_id,
            'cantidad_inicial': self.cantidad_inicial,
            'cantidad_actual': self.cantidad_actual,
            'fecha_ingreso': self.fecha_ingreso.isoformat() if self.fecha_ingreso else None,
            'fecha_vencimiento': self.fecha_vencimiento.isoformat() if self.fecha_vencimiento else None,
            'numero_factura': self.numero_factura,
            'costo_por_unidad': self.costo_por_unidad,
            'activo': self.activo
        }
    
    def dias_hasta_vencimiento(self) -> Optional[int]:
        if self.fecha_vencimiento:
            return (self.fecha_vencimiento - datetime.now()).days
        return None