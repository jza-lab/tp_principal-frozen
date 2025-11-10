from app.controllers.base_controller import BaseController
from app.models.trazabilidad import TrazabilidadModel
import logging

logger = logging.getLogger(__name__)

class TrazabilidadController(BaseController):
    def __init__(self):
        super().__init__()
        self.trazabilidad_model = TrazabilidadModel()

    def obtener_trazabilidad(self, tipo_entidad, id_entidad, nivel):
        """
        Endpoint unificado que llama al nuevo método del modelo para obtener los datos de trazabilidad.
        """
        try:
            # Validar que el nivel sea uno de los valores permitidos
            if nivel not in ['simple', 'completo']:
                return {"success": False, "error": "El parámetro 'nivel' debe ser 'simple' o 'completo'."}, 400

            data = self.trazabilidad_model.obtener_trazabilidad_unificada(tipo_entidad, id_entidad, nivel)

            if data:
                return {"success": True, "data": data}, 200
            else:
                return {"success": False, "error": f"No se encontraron datos de trazabilidad para {tipo_entidad} con ID {id_entidad}."}, 404

        except Exception as e:
            logger.error(f"Error en trazabilidad para {tipo_entidad} {id_entidad}: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno del servidor: {str(e)}"}, 500
