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

    def find_all(self, filters: Optional[Dict] = None, order_by: str = 'nombre', limit: Optional[int] = None, select_columns: Optional[list] = None) -> Dict:
        """
        Sobrescribe find_all para manejar la búsqueda de texto y reutilizar la lógica de BaseModel,
        incluyendo un JOIN con la tabla de proveedores.
        """
        try:
            # Copiar filtros para no modificar el original
            filters_copy = filters.copy() if filters else {}
            
            texto_busqueda = filters_copy.pop('busqueda', None)
            
            # Construir la consulta base con el JOIN
            query = self.db.table(self.get_table_name()).select('*, proveedor:proveedores(*)')

            # Aplicar filtros restantes (excluyendo 'busqueda')
            for key, value in filters_copy.items():
                if isinstance(value, list):
                    query = query.in_(key, value)
                else:
                    query = query.eq(key, value)
            
            # Aplicar búsqueda de texto si existe (contra nombre y código)
            if texto_busqueda:
                search_term = f"%{texto_busqueda}%"
                query = query.or_(f"nombre.ilike.{search_term},codigo_interno.ilike.{search_term}")

            # Aplicar orden y límite
            if order_by:
                # La sintaxis de Supabase es "columna.orden"
                parts = order_by.split('.')
                col = parts[0]
                asc = len(parts) == 1 or parts[1].lower() == 'asc'
                query = query.order(col, desc=not asc)
            if limit:
                query = query.limit(limit)

            # Ejecutar la consulta
            response = query.execute()

            if response.data is not None:
                # La conversión de timestamps ya la hacemos después
                return {'success': True, 'data': self._convert_timestamps(response.data)}
            else:
                # Manejar el caso donde no hay datos pero la consulta fue exitosa
                return {'success': True, 'data': []}

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
        Busca un insumo por su código interno - AHORA CON LOGS
        """
        try:
            logger.info(f"[Modelo] Ejecutando consulta a DB para código: {codigo_interno}")
            result = self.db.table(self.get_table_name()).select(
                "*, proveedor:proveedores(*)"
            ).eq("codigo_interno", codigo_interno).maybe_single().execute()

            # --- LOGS CLAVE ---
            if result and hasattr(result, 'data'):
                logger.debug(f"[Modelo] Datos de la DB: {result.data}")
                logger.debug(f"[Modelo] TIPO de datos de la DB: {type(result.data)}")
            else:
                logger.warning("[Modelo] La consulta a la DB no devolvió datos.")
            # -------------------

            if result and result.data:
                return result.data
            else:
                return None

        except Exception as e:
            logger.error(f"Error buscando insumo por código interno {codigo_interno}: {e}", exc_info=True)
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

    def marcar_en_espera(self, id_insumo: str) -> Dict:
        """
        Marca un insumo como 'en espera de reestock'.
        """
        return self.update(id_insumo, {'en_espera_de_reestock': True}, 'id_insumo')

    def quitar_en_espera(self, id_insumo: str) -> Dict:
        """
        Quita la marca de 'en espera de reestock' de un insumo.
        """
        return self.update(id_insumo, {'en_espera_de_reestock': False}, 'id_insumo')
