from abc import ABC, abstractmethod
from typing import List, Optional, TypeVar, Generic, Dict, Any
from db import get_supabase_client

T = TypeVar('T')

class BaseRepository(Generic[T], ABC):
    """
    Clase repositorio genérica que proporciona operaciones CRUD básicas para un modelo dado.
    """
    def __init__(self):
        self.client = get_supabase_client()

    @property
    @abstractmethod
    def table_name(self) -> str:
        """El nombre de la tabla de la base de datos."""
        pass

    @property
    def uses_activo_filter(self) -> bool:
        """Determina si los métodos de lista deben filtrar por el campo 'activo'. Por defecto es True."""
        return True

    @abstractmethod
    def _dict_to_model(self, data: Dict[str, Any]) -> T:
        """Convierte un diccionario en una instancia del modelo."""
        pass

    def create(self, model: T) -> T:
        """Crea un nuevo registro en la base de datos."""
        data = model.to_dict()
        data.pop('id', None)

        response = self.client.table(self.table_name).insert(data).execute()

        if not response.data:
            raise Exception(f"Error al crear un item en {self.table_name}")

        return self._dict_to_model(response.data[0])

    def get_by_id(self, item_id: int) -> Optional[T]:
        """Recupera un único registro por su ID, independientemente de su estado 'activo'."""
        query = self.client.table(self.table_name).select("*").eq('id', item_id)
        response = query.limit(1).execute()

        if not response.data:
            return None

        return self._dict_to_model(response.data[0])

    def get_all(self) -> List[T]:
        """Recupera todos los registros de la tabla, opcionalmente filtrando por estado 'activo'."""
        query = self.client.table(self.table_name).select("*")
        if self.uses_activo_filter:
            query = query.eq('activo', True)

        response = query.execute()
        return [self._dict_to_model(item) for item in response.data]

    def update(self, item_id: int, model: T) -> T:
        """Actualiza un registro por su ID."""
        data = model.to_dict()
        data.pop('id', None)
        data.pop('created_at', None)

        response = self.client.table(self.table_name).update(data).eq('id', item_id).execute()

        if not response.data:
            raise Exception(f"Error al actualizar el item con id {item_id} en {self.table_name}")

        return self._dict_to_model(response.data[0])

    def delete(self, item_id: int) -> bool:
        """
        Realiza un borrado lógico estableciendo 'activo' en False.
        Falla si el repositorio no usa el filtro 'activo'.
        """
        if not self.uses_activo_filter:
            raise NotImplementedError("El borrado lógico no está soportado para este repositorio.")

        response = self.client.table(self.table_name).update({'activo': False}).eq('id', item_id).execute()

        return len(response.data) > 0

    def get_by(self, column: str, value: Any) -> Optional[T]:
        """Recupera un único registro por una columna y valor específicos, independientemente de su estado 'activo'."""
        query = self.client.table(self.table_name).select("*").eq(column, value)
        response = query.limit(1).execute()

        if not response.data:
            return None

        return self._dict_to_model(response.data[0])

    def get_all_by(self, column: str, value: Any) -> List[T]:
        """Recupera todos los registros por una columna y valor específicos, opcionalmente filtrando por estado 'activo'."""
        query = self.client.table(self.table_name).select("*").eq(column, value)
        if self.uses_activo_filter:
            query = query.eq('activo', True)

        response = query.execute()

        return [self._dict_to_model(item) for item in response.data]
