from typing import Dict, Optional, Any
from app.schemas.responses import ResponseSchema
from app.models.direccion import DireccionModel
from app.schemas.direccion_schema import DireccionSchema
import logging

logger = logging.getLogger(__name__)

class BaseController:
    """Controlador base con métodos comunes"""

    def __init__(self):
        self.response_schema = ResponseSchema()
        self.direccion_model = DireccionModel()
        self.direccion_schema = DireccionSchema()

    def _actualizar_direccion(self, direccion_id: int, direccion_data: Dict) -> bool:
        """Actualiza una dirección existente."""
        if not direccion_data or not direccion_id:
            return False
        
        validated_address = self.direccion_schema.load(direccion_data)
        update_result = self.direccion_model.update(direccion_id, validated_address, 'id')
        return update_result.get('success', False)
        
    def _get_or_create_direccion(self, direccion_data: Dict) -> Optional[int]:
        """Busca una dirección existente o crea una nueva si no se encuentra."""
        if not direccion_data:
            return None

        # Extraer latitud y longitud antes de la validación
        latitud = direccion_data.pop('latitud', None)
        longitud = direccion_data.pop('longitud', None)
        
        validated_address = self.direccion_schema.load(direccion_data)

        existing_address_result = self.direccion_model.find_by_full_address(
            calle=validated_address['calle'],
            altura=validated_address['altura'],
            piso=validated_address.get('piso'),
            depto=validated_address.get('depto'),
            localidad=validated_address['localidad'],
            provincia=validated_address['provincia']
        )

        if existing_address_result['success']:
            return existing_address_result['data']['id']
        else:
            # Re-agregar latitud y longitud para la creación
            if latitud is not None:
                validated_address['latitud'] = latitud
            if longitud is not None:
                validated_address['longitud'] = longitud

            new_address_result = self.direccion_model.create(validated_address)
            if new_address_result['success']:
                return new_address_result['data']['id']
        return None

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
