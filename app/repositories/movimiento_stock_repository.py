from typing import List
from models.movimiento_stock import MovimientoStock
from datetime import datetime
from .base_repository import BaseRepository

class MovimientoStockRepository(BaseRepository):
    
    def registrar_movimiento(self, materia_prima_id: int, tipo_movimiento: str, cantidad: float,
                           usuario_id: int, lote_id: int = None, orden_produccion_id: int = None,
                           observaciones: str = None) -> MovimientoStock:
        
        movimiento = MovimientoStock(
            id=None,
            materia_prima_id=materia_prima_id,
            lote_id=lote_id,
            tipo_movimiento=tipo_movimiento,
            cantidad=cantidad,
            fecha=datetime.now(),
            orden_produccion_id=orden_produccion_id,
            usuario_id=usuario_id,
            observaciones=observaciones
        )
        
        data = movimiento.to_dict()
        del data['id']
        
        response = self.client.table('movimientos_stock').insert(data).execute()
        
        if response.data:
            return self._dict_to_movimiento(response.data[0])
        
        raise Exception("Error al registrar movimiento de stock")
    
    def obtener_por_materia_prima(self, materia_prima_id: int, limite: int = 50) -> List[MovimientoStock]:
        response = self.client.table('movimientos_stock').select("*").eq(
            'materia_prima_id', materia_prima_id
        ).order('fecha', desc=True).limit(limite).execute()
        
        return [self._dict_to_movimiento(item) for item in response.data]
    
    def obtener_por_orden(self, orden_produccion_id: int) -> List[MovimientoStock]:
        response = self.client.table('movimientos_stock').select("*").eq(
            'orden_produccion_id', orden_produccion_id
        ).execute()
        
        return [self._dict_to_movimiento(item) for item in response.data]
    
    def obtener_por_periodo(self, fecha_inicio: datetime, fecha_fin: datetime) -> List[MovimientoStock]:
        response = self.client.table('movimientos_stock').select("*").gte(
            'fecha', fecha_inicio.isoformat()
        ).lte(
            'fecha', fecha_fin.isoformat()
        ).order('fecha', desc=True).execute()
        
        return [self._dict_to_movimiento(item) for item in response.data]
    
    def _dict_to_movimiento(self, data: dict) -> MovimientoStock:
        return MovimientoStock(
            id=data['id'],
            materia_prima_id=data['materia_prima_id'],
            lote_id=data.get('lote_id'),
            tipo_movimiento=data['tipo_movimiento'],
            cantidad=data['cantidad'],
            fecha=datetime.fromisoformat(data['fecha']) if data.get('fecha') else None,
            orden_produccion_id=data.get('orden_produccion_id'),
            usuario_id=data['usuario_id'],
            observaciones=data.get('observaciones')
        )