from controllers.base_controller import BaseController
from models.pedido import PedidoModel
from models.producto import ProductoModel 
from schemas.pedido_schema import PedidoSchema
from typing import Dict, Optional, List, Any
from marshmallow import ValidationError

class PedidoController(BaseController):
    """
    Controlador para la lógica de negocio de los pedidos de clientes.
    """

    def __init__(self):
        super().__init__()
        self.pedido_model = PedidoModel()
        self.producto_model = ProductoModel()
        self.schema = PedidoSchema()

    def crear_pedido(self, data: Dict) -> Dict:
        """Valida y crea un nuevo pedido."""
        try:
            validated_data = self.schema.load(data)
            return self.pedido_model.create(validated_data)
        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def obtener_pedido_por_id(self, pedido_id: int) -> Optional[Dict]:
        """Obtiene un pedido por su ID."""
        result = self.pedido_model.find_by_id(pedido_id)
        return result.get('data')

    def obtener_todos_los_pedidos(self) -> List[Dict]:
        """
        Obtiene todos los pedidos y enriquece los datos con el nombre del producto.
        """
        pedidos_result = self.pedido_model.find_all(order_by='fecha_solicitud DESC')
        pedidos = pedidos_result.get('data', [])

        # Enriquece cada pedido con el nombre del producto para la vista
        for pedido in pedidos:
            producto_data = self.producto_model.find_by_id(pedido['producto_id'])
            pedido['producto_nombre'] = producto_data['data']['nombre'] if producto_data.get('data') else 'N/A'

        return pedidos

    def obtener_pedidos_por_estado(self, estado: str) -> List[Dict]:
        """Obtiene todos los pedidos que coincidan con un estado."""
        result = self.pedido_model.find_all(filters={'estado': estado})
        return result.get('data', [])

    def actualizar_pedido(self, pedido_id: int, data: Dict) -> Dict:
        """Actualiza un pedido existente."""
        pedido = self.obtener_pedido_por_id(pedido_id)
        if not pedido or pedido.get('estado') != 'PENDIENTE':
            return {'success': False, 'error': 'El pedido no se puede actualizar.'}

        try:
            validated_data = self.schema.load(data, partial=True)
            return self.pedido_model.update(pedido_id, validated_data)
        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def eliminar_pedido(self, pedido_id: int) -> Dict:
        """Elimina un pedido si está en estado PENDIENTE."""
        pedido = self.obtener_pedido_por_id(pedido_id)
        if not pedido:
            return {'success': False, 'error': 'Pedido no encontrado.'}
        if pedido.get('estado') != 'PENDIENTE':
            return {'success': False, 'error': 'Solo se pueden eliminar pedidos pendientes.'}

        return self.pedido_model.delete(pedido_id)