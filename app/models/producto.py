from app.models.base_model import BaseModel
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class ProductoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de productos en la base de datos.
    """

    def get_table_name(self) -> str:
        return 'productos'

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