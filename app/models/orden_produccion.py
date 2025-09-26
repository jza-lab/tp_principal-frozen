from models.base_model import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class OrdenProduccionModel(BaseModel):
    """
    Modelo para gestionar las operaciones de la tabla `ordenes_produccion` en la base de datos."""

    def get_table_name(self) -> str:
        """Devuelve el nombre de la tabla de la base de datos."""
        return 'ordenes_produccion'

    def cambiar_estado(self, orden_id: int, nuevo_estado: str, observaciones: Optional[str] = None) -> Dict:
        """
        Cambia el estado de una orden de producción y actualiza fechas si es necesario.
        """
        try:
            update_data = {'estado': nuevo_estado}
            if observaciones:
                update_data['observaciones'] = observaciones

            if nuevo_estado == 'EN_PROCESO':
                update_data['fecha_inicio'] = datetime.now().isoformat()
            elif nuevo_estado == 'COMPLETADA':
                update_data['fecha_fin'] = datetime.now().isoformat()

            return self.update(id_value=orden_id, data=update_data, id_field='id')
        except Exception as e:
            logger.error(f"Error cambiando estado de la orden {orden_id}: {str(e)}")
            return {'success': False, 'error': str(e)}