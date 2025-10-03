from app.models.base_model import BaseModel
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class InsumoModel(BaseModel):
    """Modelo para la tabla insumos_catalogo"""

    def get_table_name(self) -> str:
        return 'insumos_catalogo'
    
    def find_all(self, filters: Optional[Dict] = None, order_by: str = 'nombre', limit: Optional[int] = None) -> Dict:
        """
        Sobrescribe find_all para manejar la búsqueda de texto junto con otros filtros.
        """
        try:
            query = self.db.table(self.get_table_name()).select('*')
            
            filters_copy = filters.copy() if filters else {}
            
            texto_busqueda = filters_copy.pop('busqueda', None)

            if texto_busqueda:
                busqueda_pattern = f"%{texto_busqueda}%"
                query = query.or_(f"nombre.ilike.{busqueda_pattern},codigo_interno.ilike.{busqueda_pattern},descripcion.ilike.{busqueda_pattern}")

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
        
    def find_by_codigo(self, codigo: str, tipo_codigo: str = 'interno') -> Dict:
        """Buscar insumo por código interno o EAN"""
        try:
            campo = 'codigo_interno' if tipo_codigo == 'interno' else 'codigo_ean'
            result = self.db.table(self.table_name).select('*').eq(campo, codigo).execute()

            if result.data:
                return {'success': True, 'data': result.data[0]}
            else:
                return {'success': False, 'error': 'Insumo no encontrado'}

        except Exception as e:
            logger.error(f"Error buscando por código: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_criticos(self) -> Dict:
        """Obtener insumos marcados como críticos"""
        return self.find_all(filters={'es_critico': True, 'activo': True})

    def find_by_categoria(self, categoria: str) -> Dict:
        """Obtener insumos por categoría"""
        return self.find_all(filters={'categoria': categoria, 'activo': True})

    def get_distinct_categories(self) -> Dict:
        """
        Obtiene una lista de categorías únicas y no nulas.
        """
        try:
            response = self.find_all() 

            if response.get('success'):
                insumos = response.get('data', [])
                all_categories = [insumo['categoria'] for insumo in insumos if insumo.get('categoria')]
                unique_categories = sorted(list(set(all_categories)))
                return {'success': True, 'data': unique_categories}
            else:
                error_msg = response.get('error')
                logger.error(f"Error subyacente en find_all al obtener categorías: {error_msg}")
                return {'success': False, 'error': error_msg}

        except Exception as e:
            logger.error(f"Error crítico obteniendo categorías distintas: {str(e)}")
            return {'success': False, 'error': str(e)}

    def delete(self, id_value: str, id_field: str = 'id_insumo', soft_delete: bool = True) -> Dict:
        """Override para manejar eliminación con inventario asociado"""
        try:
            inventario_check = (self.db.table('insumos_inventario')
                               .select('id_lote')
                               .eq('id_insumo', id_value)
                               .limit(1)
                               .execute())

            if inventario_check.data:
                return super().delete(id_value, id_field, soft_delete=True)
            else:
                return super().delete(id_value, id_field, soft_delete)

        except Exception as e:
            logger.error(f"Error en eliminación personalizada: {str(e)}")
            return {'success': False, 'error': str(e)}