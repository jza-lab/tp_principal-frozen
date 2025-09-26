from app.database import Database
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)

class BaseModel(ABC):
    """Modelo base con operaciones CRUD comunes"""

    def __init__(self):
        self.db = Database().client
        self.table_name = self.get_table_name()

    @abstractmethod
    def get_table_name(self) -> str:
        """Debe retornar el nombre de la tabla"""
        pass

    def create(self, data: Dict) -> Dict:
        """Crear un nuevo registro"""
        try:
            # ✅ Convertir objetos date/datetime a string ISO antes de insertar
            clean_data = self._prepare_data_for_db(data)

            result = self.db.table(self.table_name).insert(clean_data).execute()

            if result.data:
                logger.info(f"Registro creado en {self.table_name}: {result.data[0]}")
                return {'success': True, 'data': result.data[0]}
            else:
                return {'success': False, 'error': 'No se pudo crear el registro'}

        except Exception as e:
            logger.error(f"Error creando en {self.table_name}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _prepare_data_for_db(self, data: Dict) -> Dict:
        """Preparar datos para la base de datos"""
        clean_data = {}
        for key, value in data.items():
            if value is not None:
                if isinstance(value, (date, datetime)):
                    clean_data[key] = value.isoformat()
                else:
                    clean_data[key] = value
        return clean_data

    def find_by_id(self, id_value: str, id_field: str = None) -> Dict:
        """Buscar por ID"""
        try:
            if id_field is None:
                id_field = f"id_{self.table_name.rstrip('s')}"

            result = self.db.table(self.table_name).select('*').eq(id_field, id_value).execute()

            if result.data:
                return {'success': True, 'data': result.data[0]}
            else:
                return {'success': False, 'error': 'Registro no encontrado'}

        except Exception as e:
            logger.error(f"Error buscando en {self.table_name}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_all(self, filters: Optional[Dict] = None, order_by: str = 'created_at',
                 limit: Optional[int] = None) -> Dict:
        """Obtener todos los registros con filtros opcionales"""
        try:
            query = self.db.table(self.table_name).select('*')

            # Aplicar filtros
            if filters:
                for key, value in filters.items():
                    if value is not None:
                        query = query.eq(key, value)

            # Ordenar
            query = query.order(order_by)

            # Límite
            if limit:
                query = query.limit(limit)

            result = query.execute()

            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error obteniendo registros de {self.table_name}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def update(self, id_value: str, data: Dict, id_field: str = None) -> Dict:
        """Actualizar un registro"""
        try:
            if id_field is None:
                id_field = f"id_{self.table_name.rstrip('s')}"

            # Remover campos que no se pueden actualizar
            update_data = {k: v for k, v in data.items()
                          if k not in [id_field, 'created_at', 'updated_at']}

            if not update_data:
                return {'success': False, 'error': 'No hay datos para actualizar'}

            result = self.db.table(self.table_name).update(update_data).eq(id_field, id_value).execute()

            if result.data:
                logger.info(f"Registro actualizado en {self.table_name}: {id_value}")
                return {'success': True, 'data': result.data[0]}
            else:
                return {'success': False, 'error': 'No se pudo actualizar el registro'}

        except Exception as e:
            logger.error(f"Error actualizando en {self.table_name}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def delete(self, id_value: str, id_field: str = None, soft_delete: bool = False) -> Dict:
        """Eliminar un registro (físico o lógico)"""
        try:
            if id_field is None:
                id_field = f"id_{self.table_name.rstrip('s')}"

            if soft_delete:
                # Eliminación lógica
                result = self.db.table(self.table_name).update({'activo': False}).eq(id_field, id_value).execute()
                message = 'Registro desactivado'
            else:
                # Eliminación física
                result = self.db.table(self.table_name).delete().eq(id_field, id_value).execute()
                message = 'Registro eliminado'

            logger.info(f"{message} en {self.table_name}: {id_value}")
            return {'success': True, 'message': message}

        except Exception as e:
            logger.error(f"Error eliminando en {self.table_name}: {str(e)}")
            return {'success': False, 'error': str(e)}