import logging
from app.controllers.base_controller import BaseController
from app.models.configuracion import ConfiguracionModel
from typing import Tuple, Any
from app.controllers.registro_controller import RegistroController
from flask_jwt_extended import get_current_user

logger = logging.getLogger(__name__)

DIAS_ALERTA_VENCIMIENTO_LOTE = 'dias_alerta_vencimiento_lote'
DEFAULT_DIAS_ALERTA = 7
TOLERANCIA_SOBREPRODUCCION_PORCENTAJE = 'tolerancia_sobreproduccion_porcentaje'
DEFAULT_TOLERANCIA_SOBREPRODUCCION = 0.0


class ConfiguracionController(BaseController):
    """
    Controlador para la gestión de valores de configuración persistentes.
    """

    def __init__(self):
        super().__init__()
        self.model = ConfiguracionModel()
        self.registro_controller = RegistroController()

    def obtener_valor_configuracion(self, clave: str, default: Any) -> Any:
        """
        Obtiene un valor de configuración genérico de la base de datos.
        """
        try:
            valor_str = self.model.obtener_valor(clave, str(default))
            # Intenta convertir al tipo del default para mantener consistencia
            if valor_str is None:
                return default
            # Handle float conversion specifically for safety
            if isinstance(default, float):
                return float(valor_str)
            return type(default)(valor_str)
        except (ValueError, TypeError) as e:
            logger.error(f"Error convirtiendo valor para clave '{clave}', usando default '{default}': {str(e)}")
            return default
        except Exception as e:
            logger.error(f"Error obteniendo configuración para clave '{clave}', usando default '{default}': {str(e)}")
            return default

    def actualizar_valor_configuracion(self, clave: str, valor: Any) -> Tuple[dict, int]:
        """
        Guarda un valor de configuración genérico en la base de datos.
        """
        try:
            # Validación simple
            if not clave or valor is None:
                return self.error_response('La clave y el valor son requeridos.', 400)

            result = self.model.guardar_valor(clave, str(valor))

            if result.get('success'):
                return self.success_response(
                    message=f"Configuración '{clave}' actualizada correctamente.",
                    data={'clave': clave, 'valor': valor}
                )
            else:
                return self.error_response(result.get('error', f"Error al guardar la configuración '{clave}'."), 500)

        except Exception as e:
            logger.error(f"Error en actualizar_valor_configuracion para clave '{clave}': {str(e)}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

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
                if not isinstance(dias, int) or not (0 < dias <= 30):
                    # Retorna (dict, 400)
                    return self.error_response('Los días deben ser un número entero positivo y no exceder de 30.', 400)
                
                # 2. Guardar el valor
                result = self.model.guardar_valor(DIAS_ALERTA_VENCIMIENTO_LOTE, str(dias))
                
                if result.get('success'):
                    detalle = f"Se cambió el umbral de alerta de vencimiento de lotes a {dias} días."
                    self.registro_controller.crear_registro(get_current_user(), 'Alertas Lotes', 'Configuración', detalle)
                    # CORRECCIÓN AQUÍ: self.success_response ya retorna (dict, 200).
                    return self.success_response(message="Días de alerta de vencimiento guardados correctamente.", data={'dias': dias})
                else:
                    # Retorna (dict, 500)
                    return self.error_response(result.get('error', 'Error al guardar la configuración.'), 500)
                    
            except Exception as e:
                logger.error(f"Error en guardar_dias_vencimiento: {str(e)}", exc_info=True)
                # Retorna (dict, 500)
                return self.error_response('Error interno del servidor', 500)