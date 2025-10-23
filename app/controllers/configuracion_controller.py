import logging
from app.controllers.base_controller import BaseController
from app.models.configuracion import ConfiguracionModel 
from typing import Tuple

logger = logging.getLogger(__name__)

DIAS_ALERTA_VENCIMIENTO_LOTE = 'dias_alerta_vencimiento_lote'
DEFAULT_DIAS_ALERTA = 7 

class ConfiguracionController(BaseController):
    """
    Controlador para la gestión de valores de configuración persistentes.
    """
    def __init__(self):
        super().__init__()
        self.model = ConfiguracionModel()

    def obtener_dias_vencimiento(self) -> int:
        """Obtiene el umbral de días para la alerta de vencimiento de lotes."""
        try:
            # Llama al modelo para obtener el valor de la DB
            valor_str = self.model.obtener_valor(DIAS_ALERTA_VENCIMIENTO_LOTE, str(DEFAULT_DIAS_ALERTA)) 
            return int(valor_str)
        except Exception as e:
            logger.error(f"Error obteniendo días de vencimiento, usando default {DEFAULT_DIAS_ALERTA}: {str(e)}")
            return DEFAULT_DIAS_ALERTA

    def guardar_dias_vencimiento(self, dias: int) -> Tuple[dict, int]:
            """Guarda el umbral de días para la alerta de vencimiento de lotes."""
            try:
                # 1. Validación de datos 
                if not isinstance(dias, int) or dias <= 0:
                    # Retorna (dict, 400)
                    return self.error_response('Los días deben ser un número entero positivo.', 400)
                
                # 2. Guardar el valor
                result = self.model.guardar_valor(DIAS_ALERTA_VENCIMIENTO_LOTE, str(dias))
                
                if result.get('success'):
                    # CORRECCIÓN AQUÍ: self.success_response ya retorna (dict, 200).
                    return self.success_response(message="Días de alerta de vencimiento guardados correctamente.", data={'dias': dias})
                else:
                    # Retorna (dict, 500)
                    return self.error_response(result.get('error', 'Error al guardar la configuración.'), 500)
                    
            except Exception as e:
                logger.error(f"Error en guardar_dias_vencimiento: {str(e)}", exc_info=True)
                # Retorna (dict, 500)
                return self.error_response('Error interno del servidor', 500)