from app.models.base_model import BaseModel
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ProductoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de productos en la base de datos.
    """

    def get_table_name(self) -> str:
        return 'productos'

    def find_all(self, filters: Optional[Dict] = None, order_by: str = 'nombre', limit: Optional[int] = None) -> Dict:
        """
        Sobrescribe find_all para manejar la búsqueda de texto (ilike) y filtros de categoría.
        """
        try:
            query = self.db.table(self.get_table_name()).select('*')

            filters_copy = filters.copy() if filters else {}

            texto_busqueda = filters_copy.pop('busqueda', None)
            categoria = filters_copy.pop('categoria', None)

            # Lógica para la búsqueda de texto (funciona como 'ilike' por nombre/código)
            if texto_busqueda:
                busqueda_pattern = f"%{texto_busqueda}%"
                query = query.or_(f"nombre.ilike.{busqueda_pattern},codigo.ilike.{busqueda_pattern},descripcion.ilike.{busqueda_pattern}")

            # Lógica para el filtro de categoría (coincidencia exacta)
            if categoria:
                query = query.eq('categoria', categoria)

            # Aplicar cualquier otro filtro remanente (e.g., 'activo')
            for key, value in filters_copy.items():
                if value is not None:
                    query = query.eq(key, value)

            query = query.order(order_by)

            if limit:
                query = query.limit(limit)

            result = query.execute()

            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error obteniendo registros de {self.get_table_name()}: {str(e)}")
            return {'success': False, 'error': str(e)}
    def find_by_codigo(self, codigo: str) -> Dict:
        """
        Busca un producto por su código único.
        """
        try:
            result = self.db.table(self.get_table_name()).select('*').eq('codigo', codigo).single().execute()
            if result.data:
                return {'success': True, 'data': result.data}
            else:
                return {'success': False, 'error': 'Producto no encontrado'}
        except Exception as e:
            # Supabase-py puede lanzar un genérico Exception si .single() no encuentra nada
            if "Missing data" in str(e):
                 return {'success': False, 'error': 'Producto no encontrado'}
            logger.error(f"Error buscando producto por código: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_last_by_base_codigo(self, base_codigo: str) -> Dict:
        """
        Busca el último producto cuyo código comience con un prefijo específico.
        """
        try:
            # Usamos `like` para buscar el patrón y ordenamos de forma descendente por el código
            # para obtener el más alto/último primero.
            result = (
                self.db.table(self.get_table_name())
                .select('codigo')
                .like('codigo', f'{base_codigo}-%')
                .order('codigo', desc=True)
                .limit(1)
                .execute()
            )
            if result.data:
                return {'success': True, 'data': result.data[0]}
            else:
                # Si no se encuentra ninguno, no es un error, simplemente no hay códigos previos.
                return {'success': True, 'data': None}
        except Exception as e:
            logger.error(f"Error buscando el último producto por código base: {str(e)}")
            return {'success': False, 'error': str(e)}
        
    def get_distinct_categories(self) -> Dict:
        """
        Obtiene una lista de categorías únicas y no nulas.
        """
        try:
            # Llama a find_all (el método base o sobrescrito) sin filtros de búsqueda
            response = self.find_all(filters={'activo': True}) 

            if response.get('success'):
                productos = response.get('data', [])
                # Extraer, filtrar por nulos, hacer único (set) y ordenar
                all_categories = [producto['categoria'] for producto in productos if producto.get('categoria')]
                unique_categories = sorted(list(set(all_categories)))
                return {'success': True, 'data': unique_categories}
            else:
                error_msg = response.get('error')
                logger.error(f"Error al obtener categorías de productos: {error_msg}")
                return {'success': False, 'error': error_msg}

        except Exception as e:
            logger.error(f"Error obteniendo categorías distintas de productos: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_by_names(self, nombres: list) -> Dict:
        """
        Busca productos por una lista de nombres.
        """
        try:
            if not nombres:
                return {'success': True, 'data': []}
            
            result = self.db.table(self.get_table_name()).select('*').in_('nombre', nombres).execute()
            
            if result.data:
                return {'success': True, 'data': result.data}
            else:
                return {'success': False, 'error': 'No se encontraron productos con esos nombres'}
        except Exception as e:
            logger.error(f"Error buscando productos por nombres: {str(e)}")
            return {'success': False, 'error': str(e)}