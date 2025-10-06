from venv import logger
from app.controllers.base_controller import BaseController
from app.models.producto import ProductoModel
from app.schemas.producto_schema import ProductoSchema
from typing import Dict, Optional, List
from marshmallow import ValidationError

class ProductoController(BaseController):
    """
    Controlador para la lógica de negocio de los productos.
    """

    def __init__(self):
        super().__init__()
        self.model = ProductoModel()
        self.schema = ProductoSchema()

    def crear_producto(self, data: Dict) -> Dict:
        """Valida y crea un nuevo producto."""
        try:
            validated_data = self.schema.load(data)

            # Verificar si el código ya existe
            if self.model.find_by_codigo(validated_data['codigo']).get('data'):
                return {'success': False, 'error': 'El código del producto ya está en uso.'}

            return self.model.create(validated_data)
        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def obtener_producto_por_id(self, producto_id: int) -> Optional[Dict]:
        """Obtiene un producto por su ID."""
        result = self.model.find_by_id(producto_id, 'id')
        return result.get('data')

    def obtener_todos_los_productos(self, filtros: Optional[Dict] = None) -> List[Dict]:
        """Obtiene una lista de todos los productos."""
        try:
            filtros = filtros or {}
            result = self.model.find_all(filtros)
            if not result['success']:
                return self.error_response(result['error'])
            datos = result['data']
            sorted_data = sorted(datos, key=lambda x: x.get('activo', False), reverse=True)
            # Serializar y responder
            serialized_data = self.schema.dump(sorted_data, many=True)
            return self.success_response(data=serialized_data)
        except Exception as e:
            # logger.error(f"Error obteniendo productos: {str(e)}", exc_info=True)
            return self.error_response(f'Error interno', 500)

    def actualizar_producto(self, producto_id: int, data: Dict) -> Dict:
        """Actualiza un producto existente."""
        try:
            validated_data = self.schema.load(data, partial=True)

            # Verificar unicidad del código si se está cambiando
            if 'codigo' in validated_data:
                existing = self.model.find_by_codigo(validated_data['codigo']).get('data')
                if existing and existing['id'] != producto_id:
                    return {'success': False, 'error': 'El código del producto ya está en uso.'}

            return self.model.update(producto_id, validated_data, 'id')
        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def eliminar_producto_logico(self, producto_id: int) -> Dict:
        """
        Desactiva un producto (eliminación lógica).
        No se elimina físicamente para mantener la integridad referencial en recetas y órdenes.
        """
        try:

            data = {'activo': False}
            result = self.model.update(producto_id, data, 'id')

            if result['success']:
                logger.info(f"Producto eliminado: {producto_id}")
                return self.success_response(message="Producto desactivado correctamente.")
            else:
                return self.error_response(result['error'])

        except Exception as e:
            logger.error(f"Error eliminando producto: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def habilitar_producto(self, producto_id: int) -> Dict:
        """
        Desactiva un producto (eliminación lógica).
        No se elimina físicamente para mantener la integridad referencial en recetas y órdenes.
        """
        try:

            data = {'activo': True}
            result = self.model.update(producto_id, data, 'id')

            if result['success']:
                logger.info(f"Producto habilitardo: {producto_id}")
                return self.success_response(message="Producto activado correctamente.")
            else:
                return self.error_response(result['error'])

        except Exception as e:
            logger.error(f"Error habilitado producto: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)
