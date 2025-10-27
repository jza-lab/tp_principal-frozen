from app.models.base_model import BaseModel
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class ReclamoMensajeModel(BaseModel):
    """
    Modelo para la tabla reclamo_mensajes.
    """
    def get_table_name(self) -> str:
        return 'reclamo_mensajes'

    def find_by_reclamo_id(self, reclamo_id: int) -> Dict:
        """
        Obtiene todos los mensajes de un reclamo, uniendo los datos
        del remitente (ya sea admin o cliente).
        """
        try:
            # --- SECCIÓN CORREGIDA ---
            select_query = """
                *,
                autor_admin:usuarios ( nombre, apellido ),
                autor_cliente:clientes ( nombre )
            """
            # --- FIN SECCIÓN CORREGIDA ---
            
            query = self.db.table(self.get_table_name()).select(
                select_query
            ).eq('reclamo_id', reclamo_id).order('created_at', desc=False)
            
            response = query.execute()
            
            return {'success': True, 'data': response.data or []}
        except Exception as e:
            logger.error(f"Error al obtener mensajes del reclamo {reclamo_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def create_mensaje(self, data: Dict) -> Dict:
        """
        Crea un nuevo mensaje de reclamo.
        'data' debe contener 'reclamo_id', 'mensaje' y
        o 'usuario_id' (si responde admin) o 'cliente_id' (si responde cliente).
        """
        try:
            return super().create(data)
        except Exception as e:
            logger.error(f"Error al crear mensaje: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}