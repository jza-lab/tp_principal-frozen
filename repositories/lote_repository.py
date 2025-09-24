from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from models.lote import Lote
from .base_repository import BaseRepository

class LoteRepository(BaseRepository[Lote]):

    @property
    def table_name(self) -> str:
        return 'lotes'

    def _dict_to_model(self, data: Dict[str, Any]) -> Lote:
        """Convierte un diccionario en una instancia del modelo Lote."""
        materia_prima_data = data.pop('materia_prima', None)

        lote = Lote(
            id=data['id'],
            codigo=data['codigo'],
            materia_prima_id=data['materia_prima_id'],
            proveedor_id=data['proveedor_id'],
            cantidad_inicial=data['cantidad_inicial'],
            cantidad_actual=data['cantidad_actual'],
            fecha_ingreso=datetime.fromisoformat(data['fecha_ingreso']) if data.get('fecha_ingreso') else None,
            fecha_vencimiento=datetime.fromisoformat(data['fecha_vencimiento']) if data.get('fecha_vencimiento') else None,
            numero_factura=data.get('numero_factura'),
            costo_por_unidad=data.get('costo_por_unidad'),
            activo=data['activo']
        )

        if materia_prima_data:
            lote.materia_prima = materia_prima_data

        return lote

    def obtener_por_materia_prima(self, materia_prima_id: int, solo_activos: bool = True) -> List[Lote]:
        """
        Recupera los lotes de una materia prima determinada, ordenados por fecha de ingreso (FIFO).
        """
        query = self.client.table(self.table_name).select("*").eq(
            'materia_prima_id', materia_prima_id
        )
        if solo_activos:
            query = query.gt('cantidad_actual', 0).eq('activo', True)

        response = query.order('fecha_ingreso').execute()
        
        return [self._dict_to_model(item) for item in response.data]
    
    def obtener_proximos_a_vencer(self, dias: int = 30) -> List[Lote]:
        """
        Recupera los lotes que están a punto de vencer, incluyendo información de la materia prima.
        """
        fecha_limite = datetime.now() + timedelta(days=dias)
        
        response = self.client.table(self.table_name).select(
            "*, materia_prima:materias_primas(nombre, codigo)"
        ).lte(
            'fecha_vencimiento', fecha_limite.date().isoformat()
        ).gt('cantidad_actual', 0).eq('activo', True).order('fecha_vencimiento').execute()
        
        return [self._dict_to_model(item) for item in response.data]

    def obtener_por_codigo(self, codigo: str) -> Optional[Lote]:
        """Recupera un lote por su código único."""
        return self.get_by('codigo', codigo)
