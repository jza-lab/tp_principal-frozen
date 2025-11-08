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

    def crear_registro_control_calidad(self, data: Dict) -> tuple:
        """
        Crea un registro en la tabla de control de calidad de productos a partir de un diccionario.
        """
        try:
            # Asegurarse de que los campos obligatorios estén presentes
            required_fields = ['lote_producto_id', 'usuario_supervisor_id', 'decision_final']
            if not all(field in data for field in required_fields):
                return self.error_response("Faltan campos obligatorios para crear el registro de calidad.", 400)

            # Normalizar la decisión
            if 'decision_final' in data:
                data['decision_final'] = data['decision_final'].upper().replace(' ', '_')

            resultado = self.model.create_registro(data)

            if resultado.get('success'):
                return self.success_response(data=resultado.get('data'), message="Registro de control de calidad de producto creado con éxito.")
            else:
                return self.error_response(resultado.get('error'), 500)
        except Exception as e:
            lote_id = data.get('lote_producto_id', 'desconocido')
            logger.error(f"Error crítico al crear registro de control de calidad para el lote de producto {lote_id}: {e}", exc_info=True)
            return self.error_response('Error interno del servidor.', 500)

    def obtener_registros_por_lote_producto(self, lote_producto_id: int) -> tuple:
        """
        Obtiene todos los registros de control de calidad asociados a un lote de producto específico.
        """
        try:
            resultado = self.model.find_all(filters={'lote_producto_id': lote_producto_id}, order_by='created_at.desc')
            if resultado.get('success'):
                return self.success_response(data=resultado.get('data'))
            else:
                return self.error_response(resultado.get('error'), 500)
        except Exception as e:
            logger.error(f"Error al obtener registros de CC para el lote {lote_producto_id}: {e}", exc_info=True)
            return self.error_response('Error interno del servidor.', 500)
