from typing import Dict, Optional, Any
from app.schemas.responses import ResponseSchema
import logging

logger = logging.getLogger(__name__)

class BaseController:
    """Controlador base con métodos comunes"""

    def __init__(self):
        self.response_schema = ResponseSchema()

    def success_response(self, data: Any = None, message: str = '', status_code: int = 200) -> tuple:
        """Generar respuesta exitosa estandarizada"""
        response_data = {
            'success': True,
            'data': data,
            'message': message
        }
        return self.response_schema.dump(response_data), status_code

    def error_response(self, error: str, status_code: int = 400, details: Dict = None) -> tuple:
        """Generar respuesta de error estandarizada"""
        response_data = {
            'success': False,
            'error': error,
            'details': details
        }
        return self.response_schema.dump(response_data), status_code

    def paginate_results(self, data: list, page: int, page_size: int) -> Dict:
        """Paginar resultados"""
        total = len(data)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            'items': data[start:end],
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'pages': (total + page_size - 1) // page_size
            }
        }
