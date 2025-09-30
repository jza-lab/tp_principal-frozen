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
        filtros = filtros or {}
        if 'activo' not in filtros:
            filtros['activo'] = True # Por defecto, solo mostrar activos
        result = self.model.find_all(filtros, order_by='nombre')
        return result.get('data', [])

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

    def eliminar_producto(self, producto_id: int) -> Dict:
        """
        Desactiva un producto (eliminación lógica).
        No se elimina físicamente para mantener la integridad referencial en recetas y órdenes.
        """
        return self.model.delete(producto_id, 'id', soft_delete=True)