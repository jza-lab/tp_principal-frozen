from app.database import Database
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
import logging
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

logger = logging.getLogger(__name__)

class BaseModel(ABC):
    """
    Clase base abstracta que proporciona una interfaz común y una implementación
    genérica para las operaciones CRUD (Crear, Leer, Actualizar, Eliminar)
    en la base de datos.
    """

    def __init__(self):
        """
        Inicializa el modelo base, estableciendo la conexión con la base de datos
        y obteniendo el nombre de la tabla a través del método abstracto.
        """
        self.db = Database().client
        self.table_name = self.get_table_name()

    def _get_query_builder(self):
        """
        Devuelve el constructor de consultas para la tabla del modelo.
        Puede ser sobrescrito por subclases para especificar un esquema.
        """
        return self.db.table(self.table_name)

    @abstractmethod
    def get_table_name(self) -> str:
        """
        Método abstracto que debe ser implementado por las clases hijas.
        Debe devolver el nombre de la tabla de la base de datos con la que
        el modelo interactuará.
        """
        pass

    def _prepare_data_for_db(self, data: Dict) -> Dict:
        """
        Prepara un diccionario de datos para ser enviado a la base de datos.
        Convierte tipos de datos específicos de Python (Decimal, datetime, UUID)
        a formatos compatibles con JSON (strings).
        """
        clean_data = {}
        for key, value in data.items():
            if value is not None:
                if isinstance(value, UUID):
                    clean_data[key] = str(value)
                elif isinstance(value, Decimal):
                    clean_data[key] = str(value)
                elif isinstance(value, (date, datetime)):
                    clean_data[key] = value.isoformat()
                else:
                    clean_data[key] = value
        return clean_data

    def create(self, data: Dict) -> Dict:
        """
        Crea un nuevo registro en la tabla.
        """
        try:
            clean_data = self._prepare_data_for_db(data)
            result = self._get_query_builder().insert(clean_data, returning="representation").execute()

            if result.data:
                logger.info(f"Registro creado en {self.table_name}: {result.data[0]}")
                return {'success': True, 'data': result.data[0]}

            return {'success': False, 'error': 'No se pudo crear el registro'}

        except Exception as e:
            logger.error(f"Error al crear en {self.table_name}: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def find_by_id(self, id_value: Any, id_field: str = None) -> Dict:
        """
        Busca un registro por su campo de identificación.
        """
        try:
            if id_field is None:
                id_field = "id"

            result = self._get_query_builder().select('*').eq(id_field, id_value).execute()

            if result.data:
                return {'success': True, 'data': result.data[0]}

            return {'success': False, 'error': 'Registro no encontrado'}

        except Exception as e:
            logger.error(f"Error al buscar en {self.table_name}: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def find_all(self, filters: Optional[Dict] = None, order_by: str = None, limit: Optional[int] = None, select_columns: Optional[List[str]] = None, select_query: Optional[str] = None) -> Dict:
        """
        Obtiene todos los registros que coinciden con los filtros, con opciones
        de ordenación y límite.
        Permite una consulta de selección compleja a través de `select_query`.
        """
        try:
            # Determinar qué columnas seleccionar. `select_query` tiene prioridad.
            columns_to_select = select_query if select_query else (','.join(select_columns) if select_columns else '*')
            query = self._get_query_builder().select(columns_to_select)

            if filters:
                for key, value in filters.items():
                    if value is None:
                        continue

                    # --- INICIO DE LA CORRECCIÓN ---
                    # Mapa de operadores conocidos
                    op_map = {
                        'eq': query.eq, 'gt': query.gt, 'gte': query.gte,
                        'lt': query.lt, 'lte': query.lte, 'in': query.in_,
                        'ilike': query.ilike,
                        'neq': query.neq  # <-- ¡AÑADIR ESTA LÍNEA!
                    }

                    # Dividir solo si la ÚLTIMA parte es un operador conocido
                    parts = key.split('_')
                    operator = parts[-1]

                    if len(parts) > 1 and operator in op_map:
                        # Es un operador (ej. 'fecha_gte')
                        column_name = '_'.join(parts[:-1]) # 'fecha'
                        query = op_map[operator](column_name, value)
                        continue # Importante: saltar al siguiente filtro
                    # --- FIN DE LA CORRECCIÓN ---

                    # Lógica original para filtros simples (ej. 'receta_id') y tuplas
                    elif isinstance(value, tuple) and len(value) == 2:
                        operator, filter_value = value
                        if operator.lower() in op_map:
                            query = op_map[operator.lower()](key, filter_value)

                    # Lógica para listas (siempre es 'in')
                    elif isinstance(value, list):
                        query = query.in_(key, value)

                    # Filtro de igualdad simple (ahora maneja 'receta_id' correctamente)
                    else:
                        query = query.eq(key, value)

            if order_by:
                column, *direction = order_by.split('.')
                descending = len(direction) > 0 and direction[0].lower() == 'desc'
                query = query.order(column, desc=descending)

            if limit:
                query = query.limit(limit)

            result = query.execute()
            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error al obtener registros de {self.table_name}: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def update(self, id_value: Any, data: Dict, id_field: str = None) -> Dict:
        """
        Actualiza un registro existente.
        """
        try:
            if id_field is None:
                id_field = "id"

            if not data:
                return {'success': False, 'error': 'No se proporcionaron datos para actualizar.'}

            clean_data = self._prepare_data_for_db(data)
            result = self._get_query_builder().update(clean_data).eq(id_field, id_value).execute()

            if result.data:
                logger.info(f"Registro actualizado en {self.table_name}: {id_value}")
                return {'success': True, 'data': result.data[0]}

            return {'success': False, 'error': 'No se pudo actualizar el registro o no se encontró.'}

        except Exception as e:
            logger.error(f"Error al actualizar en {self.table_name}: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def delete(self, id_value: Any, id_field: str = None, soft_delete: bool = False) -> Dict:
        """
        Elimina un registro, de forma física o lógica.
        """
        try:
            if id_field is None:
                id_field = "id"

            if soft_delete:
                result = self._get_query_builder().update({'activo': False}).eq(id_field, id_value).execute()
                message = 'Registro desactivado (eliminación lógica).'
            else:
                result = self._get_query_builder().delete().eq(id_field, id_value).execute()
                message = 'Registro eliminado físicamente.'

            logger.info(f"{message} ID: {id_value} en tabla: {self.table_name}")
            return {'success': True, 'message': message}

        except Exception as e:
            logger.error(f"Error al eliminar en {self.table_name}: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def get_count(self, filtros: Optional[Dict] = None) -> Dict:
        """
        Cuenta el número de registros que coinciden con los filtros.
        """
        try:
            query = self._get_query_builder().select('id', count='exact')

            if filtros:
                for key, value in filtros.items():
                    if value is not None:
                        query = query.eq(key, value)

            response = query.execute()

            return {'success': True, 'data': response.count}
        except Exception as e:
            logger.error(f"Error contando registros en {self.table_name}: {e}")
            return {'success': False, 'error': str(e)}
