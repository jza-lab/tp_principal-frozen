from app.models.base_model import BaseModel
from typing import Dict, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class InsumoModel(BaseModel):
    """Modelo para la tabla insumos_catalogo"""

    def get_table_name(self) -> str:
        return 'insumos_catalogo'

    def _convert_timestamps(self, data):
        """Convierte campos de fecha de string a datetime para un registro o una lista."""
        if not data:
            return data

        records = data if isinstance(data, list) else [data]
        for record in records:
            if record.get('created_at') and isinstance(record['created_at'], str):
                record['created_at'] = datetime.fromisoformat(record['created_at'])
            if record.get('updated_at') and isinstance(record['updated_at'], str):
                record['updated_at'] = datetime.fromisoformat(record['updated_at'])
        return data

    def find_all(self, filters: Optional[Dict] = None, order_by: str = 'nombre', limit: Optional[int] = None) -> Dict:
        """
        Sobrescribe find_all para manejar la búsqueda de texto junto con otros filtros.
        """
        try:
            query_select = "*, proveedor:id_proveedor(*)"
            query = self.db.table(self.get_table_name()).select(query_select)

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

            return {'success': True, 'data': self._convert_timestamps(result.data)}

        except Exception as e:
            logger.error(f"Error obteniendo registros de {self.get_table_name()}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_by_id(self, id_value: str, id_field: str = 'id_insumo') -> Dict:
        """Sobrescribe find_by_id para convertir timestamps."""
        result = super().find_by_id(id_value, id_field)
        if result.get('success'):
            result['data'] = self._convert_timestamps(result['data'])
        return result

    def find_by_codigo(self, codigo: str, tipo_codigo: str = 'interno') -> Dict:
        """Buscar insumo por código interno o EAN"""
        try:
            campo = 'codigo_interno' if tipo_codigo == 'interno' else 'codigo_ean'
            query_select = "*, proveedor:id_proveedor(*)"
            result = self.db.table(self.table_name).select(query_select).eq(campo, codigo).execute()

            if result.data:
                return {'success': True, 'data': self._convert_timestamps(result.data[0])}
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


    def buscar_por_codigo_interno(self, codigo_interno: str) -> Optional[Dict]:
        """
        Busca insumo por código interno (exacto)
        """
        try:
            if not codigo_interno:
                return None

            query_select = "*, proveedor:id_proveedor(*)"
            response = self.db.table(self.get_table_name())\
                           .select(query_select)\
                           .eq('codigo_interno', codigo_interno.strip().upper())\
                           .execute()

            return self._convert_timestamps(response.data[0]) if response.data else None

        except Exception as e:
            logger.error(f"Error buscando insumo {codigo_interno}: {str(e)}")
            return None

    def actualizar_precio(self, id_insumo: str, precio_nuevo: float) -> bool:
        """
        Actualiza el precio de un insumo
        """
        try:
            response = self.db.table(self.get_table_name())\
                           .update({
                               'precio_unitario': precio_nuevo,
                               'updated_at': 'now()'
                           })\
                           .eq('id_insumo', id_insumo)\
                           .execute()

            return len(response.data) > 0

        except Exception as e:
            logger.error(f"Error actualizando precio insumo {id_insumo}: {str(e)}")
            return False

    def buscar_por_codigo_proveedor(self, codigo_proveedor: str, proveedor_id: str = None) -> Optional[Dict]:
        """
        Busca insumo por código de proveedor
        """
        try:
            if not codigo_proveedor:
                return None
            query_select = "*, proveedor:id_proveedor(*)"
            query = self.db.table(self.get_table_name())\
                          .select(query_select)\
                          .eq('codigo_proveedor', codigo_proveedor.strip())

            # Si se proporciona proveedor_id, filtrar también por proveedor
            if proveedor_id:
                query = query.eq('proveedor_id', proveedor_id)

            response = query.execute()

            return self._convert_timestamps(response.data[0]) if response.data else None

        except Exception as e:
            logger.error(f"Error buscando insumo por código proveedor {codigo_proveedor}: {str(e)}")
            return None
