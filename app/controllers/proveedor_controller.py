from app.controllers.base_controller import BaseController
from app.models.proveedor import ProveedorModel
from app.schemas.proveedor_schema import ProveedorSchema
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ProveedorController(BaseController):
    """Controlador para operaciones de proveedores"""

    def __init__(self):
        super().__init__()
        self.model = ProveedorModel()
        self.schema = ProveedorSchema()

    def obtener_proveedores_activos(self) -> tuple:
        """Obtener lista de proveedores activos"""
        try:
            result = self.model.get_all_activos()

            if not result['success']:
                return self.error_response(result['error'])

            serialized_data = self.schema.dump(result['data'], many=True)
            return self.success_response(data=serialized_data)

        except Exception as e:
            logger.error(f"Error obteniendo proveedores: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)


    def buscar_por_identificacion(self, fila: Dict) -> Optional[Dict]:
        """
        Busca proveedor por email o CUIL/CUIT usando el modelo

        Args:
            fila: Diccionario con datos que pueden contener email_proveedor o cuil_proveedor

        Returns:
            Dict con datos del proveedor o None
        """
        try:
            # Usar el método del modelo para buscar
            return self.model.buscar_por_identificacion(fila)

        except Exception as e:
            logger.error(f"Error en controlador buscando proveedor: {str(e)}")
            return None