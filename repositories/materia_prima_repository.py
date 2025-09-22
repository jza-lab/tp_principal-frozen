from typing import List, Optional, Dict, Any
from datetime import datetime
from models.materia_prima import MateriaPrima
from .base_repository import BaseRepository

class MateriaPrimaRepository(BaseRepository[MateriaPrima]):
    
    @property
    def table_name(self) -> str:
        return 'materias_primas'

    def _dict_to_model(self, data: Dict[str, Any]) -> MateriaPrima:
        """Convierte un diccionario en una instancia del modelo MateriaPrima."""
        return MateriaPrima(
            id=data['id'],
            codigo=data['codigo'],
            nombre=data['nombre'],
            unidad_medida=data['unidad_medida'],
            categoria=data['categoria'],
            stock_actual=data.get('stock_actual'),  # Usar .get por seguridad
            stock_minimo=data['stock_minimo'],
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None,
            activo=data['activo']
        )

    def obtener_por_codigo(self, codigo: str) -> Optional[MateriaPrima]:
        """Recupera una materia prima por su código único."""
        return self.get_by('codigo', codigo)

    def obtener_por_filtros(self, categoria: str = None, busqueda: str = None) -> List[MateriaPrima]:
        """Recupera materias primas basándose en filtros opcionales."""
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

    def update(self, item_id: int, model: MateriaPrima) -> MateriaPrima:
        """
        Sobrescribe el método de actualización base para añadir lógica personalizada para 'updated_at'
        y para evitar la actualización directa de 'stock_actual'.
        """
        data = model.to_dict()
        data['updated_at'] = datetime.now().isoformat()
        
        # Nos aseguramos de no intentar actualizar el stock desde aquí
        data.pop('stock_actual', None)

        # El método de actualización de la clase base es demasiado genérico para este caso,
        # así que realizamos la actualización directamente.
        data.pop('id', None)
        data.pop('created_at', None)

        response = self.client.table(self.table_name).update(data).eq('id', item_id).execute()
        
        if not response.data:
            raise Exception(f"Error al actualizar materia prima con id {item_id}")
        
        updated_data = response.data[0]
        # El stock actual no se devuelve en la respuesta de actualización, lo mantenemos del objeto original
        updated_data['stock_actual'] = model.stock_actual
        return self._dict_to_model(updated_data)
