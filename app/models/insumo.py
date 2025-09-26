from app.models.base_model import BaseModel
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class InsumoModel(BaseModel):
    """Modelo para la tabla insumos_catalogo"""

    def get_table_name(self) -> str:
        return 'insumos_catalogo'

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

    def buscar_texto(self, texto: str) -> Dict:
        """Búsqueda de texto en nombre, código interno o descripción"""
        try:
            busqueda = f"%{texto}%"
            result = (self.db.table(self.table_name)
                     .select('*')
                     .or_(f"nombre.ilike.{busqueda},codigo_interno.ilike.{busqueda},descripcion.ilike.{busqueda}")
                     .eq('activo', True)
                     .order('nombre')
                     .execute())

            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error en búsqueda de texto: {str(e)}")
            return {'success': False, 'error': str(e)}

    def delete(self, id_value: str, id_field: str = 'id_insumo', soft_delete: bool = True) -> Dict:
        """Override para manejar eliminación con inventario asociado"""
        try:
            # Verificar si tiene inventario asociado
            inventario_check = (self.db.table('insumos_inventario')
                               .select('id_lote')
                               .eq('id_insumo', id_value)
                               .limit(1)
                               .execute())

            if inventario_check.data:
                # Forzar eliminación lógica si tiene inventario
                return super().delete(id_value, id_field, soft_delete=True)
            else:
                # Permitir eliminación física si no tiene inventario
                return super().delete(id_value, id_field, soft_delete)

        except Exception as e:
            logger.error(f"Error en eliminación personalizada: {str(e)}")
            return {'success': False, 'error': str(e)}
