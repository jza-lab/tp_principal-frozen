from typing import List, Optional, Dict, Any
from datetime import datetime
from app.models.insumo import Insumo
from .base_repository import BaseRepository

class InsumoRepository(BaseRepository[Insumo]):
    
    @property
    def table_name(self) -> str:
        return 'insumos_catalogo'

    @property
    def primary_key_column(self) -> str:
        return 'id_insumo'

    def _dict_to_model(self, data: Dict[str, Any]) -> Insumo:
        """Convierte un diccionario en una instancia del modelo Insumo."""
        return Insumo(
            id_insumo=data.get('id_insumo'),
            nombre=data.get('nombre'),
            unidad_medida=data.get('unidad_medida'),
            codigo_interno=data.get('codigo_interno'),
            codigo_ean=data.get('codigo_ean'),
            categoria=data.get('categoria'),
            descripcion=data.get('descripcion'),
            tem_recomendada=data.get('tem_recomendada'),
            stock_min=data.get('stock_min'),
            stock_max=data.get('stock_max'),
            vida_util_dias=data.get('vida_util_dias'),
            es_critico=data.get('es_critico'),
            requiere_certificacion=data.get('requiere_certificacion'),
            activo=data.get('activo'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None,
            # El stock actual se calcula por separado, no viene de esta tabla
            stock_actual=data.get('stock_actual', 0.0) 
        )

    def obtener_por_codigo(self, codigo: str) -> Optional[Insumo]:
        """Recupera un insumo por su código único."""
        return self.get_by('codigo', codigo)

    def obtener_por_filtros(self, categoria: str = None, busqueda: str = None) -> List[Insumo]:
        """Recupera insumos basándose en filtros opcionales."""
        query = self.client.table(self.table_name).select("*").eq('activo', True)
        
        if categoria:
            query = query.eq('categoria', categoria)
        if busqueda:
            query = query.ilike('nombre', f'%{busqueda}%')
            
        response = query.execute()
        return [self._dict_to_model(item) for item in response.data]
    
    def actualizar_stock_en_db(self, item_id: int, nuevo_stock: float) -> bool:
        """
        Actualiza directamente el campo stock_actual en la base de datos.
        Debe ser utilizado por los servicios que calculan el stock total a partir de los lotes.
        """
        try:
            response = self.client.table(self.table_name).update({'stock_actual': nuevo_stock}).eq('id', item_id).execute()
            return len(response.data) > 0
        except Exception as e:
            print(f"Error al actualizar stock en la base de datos: {e}")
            return False

    def update(self, item_id: int, model: Insumo) -> Insumo:
        """
        Sobrescribe el método de actualización base para añadir lógica personalizada para 'updated_at'
        y para evitar la actualización directa de 'stock_actual'.
        """
        data = model.to_dict()
        data['updated_at'] = datetime.now().isoformat()
        
        data.pop('stock_actual', None)
        data.pop('id', None)
        data.pop('created_at', None)

        response = self.client.table(self.table_name).update(data).eq('id', item_id).execute()
        
        if not response.data:
            raise Exception(f"Error al actualizar insumo con id {item_id}")
        
        updated_data = response.data[0]
        updated_data['stock_actual'] = model.stock_actual
        return self._dict_to_model(updated_data)
