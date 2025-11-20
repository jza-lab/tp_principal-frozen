from app.models.base_model import BaseModel
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class RecetaIngredienteModel(BaseModel):
    """
    Modelo para interactuar con la tabla pivote de receta_ingredientes.
    """
    def get_table_name(self) -> str:
        return 'receta_ingredientes'

    def find_by_receta_id_with_insumo(self, receta_id: int) -> Dict:
        """
        Obtiene todos los ingredientes para una receta dada, haciendo un JOIN
        para incluir los detalles completos de cada insumo.
        """
        try:
            # La sintaxis correcta para el join en Supabase es:
            # 'nombre_tabla_externa:nombre_columna_fk(*)'
            # En nuestro caso, la FK 'id_insumo' apunta a 'insumos_catalogo'.
            query = self.db.table(self.get_table_name()).select(
                '*, insumo:insumos_catalogo(*)'
            ).eq('receta_id', receta_id)
            
            response = query.execute()

            if not response.data:
                return {'success': True, 'data': []}
            
            return {'success': True, 'data': response.data}
            
        except Exception as e:
            logger.error(f"Error obteniendo ingredientes para receta ID {receta_id}: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e), 'data': []}
