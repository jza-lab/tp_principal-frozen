from typing import Dict, Optional, Any
from app.schemas.responses import ResponseSchema
import logging

logger = logging.getLogger(__name__)

class BaseController:
    """Controlador base con métodos comunes"""

    def __init__(self):
        self.response_schema = ResponseSchema()

    def success_response(self, data=None, message=None, status_code=200):
        """Devuelve una respuesta exitosa"""
        response = {
            'success': True,
            'data': data,
            'message': message
        }
        return response, status_code  # ✅ Tupla (dict, int)

    def error_response(self, error_message, status_code=400):
        """Devuelve una respuesta de error"""
        response = {
            'success': False,
            'error': str(error_message)
        }
        return response, status_code  # ✅ Tupla (dict, int)

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
