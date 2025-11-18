from .base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

class PagoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de pagos.
    """
    def __init__(self):
        """
        Inicializa el modelo estableciendo la conexión a la BD
        y el nombre de la tabla.
        """
        super().__init__()

    def get_table_name(self) -> str:
        """
        Devuelve el nombre de la tabla de la base de datos.
        """
        return "pagos"

    def get_pagos_by_pedido_id(self, id_pedido: int) -> dict:
        """
        Obtiene todos los pagos asociados a un ID de pedido, incluyendo
        el nombre del usuario que registró el pago.
        """
        try:
            query = self.db.table(self.get_table_name()).select(
                "*, usuario_registro:id_usuario_registro(nombre)"
            ).eq("id_pedido", id_pedido).order("created_at", desc=True)
            
            result = query.execute()
            
            # El BaseModel no tiene _handle_response, devolvemos directamente
            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error al obtener pagos para el pedido {id_pedido}: {e}", exc_info=True)
            # Retornar un diccionario de error estándar
            return {'success': False, 'error': str(e)}
