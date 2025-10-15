from typing import Dict, Optional, Any
from app.schemas.responses import ResponseSchema
from app.models.direccion import DireccionModel
from app.schemas.direccion_schema import DireccionSchema
import logging

logger = logging.getLogger(__name__)

class BaseController:
    """
    Controlador base que proporciona métodos de utilidad comunes heredables
    por otros controladores de la aplicación.
    """

    def __init__(self):
        """
        Inicializa el controlador base, preparando esquemas y modelos comunes.
        """
        self.response_schema = ResponseSchema()
        self.direccion_model = DireccionModel()
        self.direccion_schema = DireccionSchema()

    def _get_or_create_direccion(self, direccion_data: Dict) -> Optional[int]:
        """
        Busca una dirección que coincida exactamente con los datos proporcionados.
        Si no se encuentra, crea un nuevo registro de dirección.
        Este método es esencial para la reutilización de direcciones y evitar datos duplicados en la base de datos.
        """
        if not direccion_data:
            return None

        latitud = direccion_data.pop('latitud', None)
        longitud = direccion_data.pop('longitud', None)

        existing_address_result = self.direccion_model.find_by_full_address(
            calle=direccion_data.get('calle'),
            altura=direccion_data.get('altura'),
            piso=direccion_data.get('piso'),
            depto=direccion_data.get('depto'),
            localidad=direccion_data.get('localidad'),
            provincia=direccion_data.get('provincia')
        )

        if existing_address_result.get('success'):
            return existing_address_result['data']['id']
        else:
            if latitud is not None:
                direccion_data['latitud'] = latitud
            if longitud is not None:
                direccion_data['longitud'] = longitud

            new_address_result = self.direccion_model.create(direccion_data)
            if new_address_result.get('success'):
                return new_address_result['data']['id']
        
        logger.error(f"Error crítico al obtener o crear dirección con datos: {direccion_data}")
        return None

    def success_response(self, data: Any = None, message: str = "Acción exitosa", status_code: int = 200) -> tuple:
        """
        Genera una tupla de respuesta HTTP estándar para operaciones exitosas.
        """
        response = {
            'success': True,
            'data': data,
            'message': message
        }
        return response, status_code 

    def error_response(self, error_message: str, status_code: int = 400) -> tuple:
        """
        Genera una tupla de respuesta HTTP estándar para operaciones fallidas.
        """
        response = {
            'success': False,
            'error': str(error_message)
        }
        return response, status_code

    def paginate_results(self, data: list, page: int, page_size: int) -> Dict:
        """
        Aplica paginación a una lista de resultados.
        """
        total = len(data)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            'items': data[start:end],
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_items': total,
                'total_pages': (total + page_size - 1) // page_size
            }
        }
