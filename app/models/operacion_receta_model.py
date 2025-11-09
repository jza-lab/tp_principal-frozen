from .base_model import BaseModel
from typing import List, Optional, Dict

# --- ¡AÑADE ESTAS DOS LÍNEAS! ---
import logging
logger = logging.getLogger(__name__)
# ---------------------------------

class OperacionRecetaModel(BaseModel):


    # --- MÉTODO REQUERIDO ---
    def get_table_name(self) -> str:
        # Devuelve el nombre exacto de tu tabla en la base de datos
        return "operacionesreceta"
    # -------------------------

    def find_by_receta_id(self, receta_id: int) -> dict:
        """ Obtiene todas las operaciones de una receta, ordenadas por secuencia. """
        return self.find_all(filters={'receta_id': receta_id}, order_by='secuencia')

    def find_by_receta_ids(self, receta_ids: List[int]) -> Dict:
        """
        Obtiene todas las operaciones para una LISTA de IDs de receta
        en una sola consulta de base de datos.
        """
        if not receta_ids:
            # --- ¡CORRECCIÓN! Devolver dict simple ---
            return {'success': True, 'data': []}
        try:
            receta_ids_unicos = list(set(receta_ids))

            query = self.db.table('operacionesreceta').select('*').in_('receta_id', receta_ids_unicos)

            result = query.execute()

            # --- ¡CORRECCIÓN! Devolver dict simple ---
            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error al buscar operaciones por IDs de receta: {e}", exc_info=True)
            # --- ¡CORRECCIÓN! Devolver dict simple ---
            return {'success': False, 'error': f"Error al buscar operaciones por IDs de receta: {e}"}