from typing import Dict
from app.controllers.base_controller import BaseController
from app.models.control_calidad_producto import ControlCalidadProductoModel
import logging

logger = logging.getLogger(__name__)

class ControlCalidadProductoController(BaseController):
    """
    Controlador para la lógica de negocio del control de calidad de productos.
    """
    def __init__(self):
        super().__init__()
        self.model = ControlCalidadProductoModel()

    def crear_registro_control_calidad(self, lote_id: int, usuario_id: int, decision: str, orden_produccion_id: int, comentarios: str = None) -> tuple:
        """
        Crea un registro en la tabla de control de calidad de productos.
        """
        try:
            registro_data = {
                'lote_producto_id': lote_id,
                'orden_produccion_id': orden_produccion_id,
                'usuario_supervisor_id': usuario_id,
                'decision_final': decision.upper().replace(' ', '_'),
                'comentarios': comentarios
            }
            resultado = self.model.create_registro(registro_data)
            if resultado.get('success'):
                return self.success_response(data=resultado.get('data'), message="Registro de control de calidad de producto creado con éxito.")
            else:
                return self.error_response(resultado.get('error'), 500)
        except Exception as e:
            logger.error(f"Error crítico al crear registro de control de calidad para el lote de producto {lote_id}: {e}", exc_info=True)
            return self.error_response('Error interno del servidor.', 500)
