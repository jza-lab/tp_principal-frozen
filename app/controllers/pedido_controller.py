from app.controllers.base_controller import BaseController
from app.models.pedido import Pedido, PedidoModel
from app.models.producto import ProductoModel
from app.schemas.pedido_schema import PedidoSchema
from typing import Dict, Optional, List
from marshmallow import ValidationError

class PedidoController(BaseController):
    """
    Controlador para la lógica de negocio de los pedidos de clientes.
    Adaptado para manejar pedidos con múltiples productos.
    """

    def __init__(self):
        super().__init__()
        self.pedido_model = PedidoModel()
        self.producto_model = ProductoModel()
        self.schema = PedidoSchema()

    def crear_pedido(self, data: Dict) -> Dict:
        """Valida y crea un nuevo pedido con sus ítems."""
        try:
            # El schema ahora retorna un objeto Pedido con una lista de PedidoItem
            pedido_obj = self.schema.load(data)
            return self.pedido_model.create(pedido_obj)
        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def obtener_pedido_por_id(self, pedido_id: int) -> Optional[Dict]:
        """Obtiene un Pedido por su ID, enriquecido con datos del producto."""
        result = self.pedido_model.find_by_id(pedido_id)
        if not result.get('success'):
            return None

        pedido_obj = result.get('data')
        # _enrich_pedidos_with_product_names espera una lista y devuelve una lista
        enriched_list = self._enrich_pedidos_with_product_names([pedido_obj])
        return enriched_list[0] if enriched_list else None

    def obtener_todos_los_pedidos(self) -> List[Dict]:
        """
        Obtiene todos los pedidos y los enriquece con los nombres de los productos.
        Optimizado para evitar el problema N+1.
        """
        pedidos_result = self.pedido_model.find_all(order_by='fecha_solicitud DESC')
        pedidos: List[Pedido] = pedidos_result.get('data', [])
        return self._enrich_pedidos_with_product_names(pedidos)

    def obtener_pedidos_por_estado(self, estado: str) -> List[Dict]:
        """
        Obtiene todos los pedidos que coincidan con un estado, enriquecidos
        con la información de los productos.
        """
        result = self.pedido_model.find_all(filters={'estado': estado})
        pedidos: List[Pedido] = result.get('data', [])
        return self._enrich_pedidos_with_product_names(pedidos)

    def _enrich_pedidos_with_product_names(self, pedidos: List[Pedido]) -> List[Dict]:
        """
        Toma una lista de objetos Pedido y la enriquece con los nombres
        de los productos para cada ítem.
        """
        if not pedidos:
            return []

        producto_ids = {item.producto_id for pedido in pedidos for item in pedido.items}

        #Obtener todos los productos necesarios en una sola consulta
        productos_data = []
        if producto_ids:
            # BaseModel.find_all soporta el filtro 'in'
            productos_result = self.producto_model.find_all(filters={'id': ('in', list(producto_ids))})
            if productos_result.get('success'):
                productos_data = productos_result.get('data', [])

        producto_map = {p['id']: p['nombre'] for p in productos_data}
        pedidos_dict_list = []
        for pedido in pedidos:
            pedido_dict = pedido.to_dict()
            for item_dict in pedido_dict.get('items', []):
                item_dict['producto_nombre'] = producto_map.get(item_dict['producto_id'], 'Producto no encontrado')
            pedidos_dict_list.append(pedido_dict)

        return pedidos_dict_list

    def actualizar_pedido(self, pedido_id: int, data: Dict) -> Dict:
        """
        Actualiza los datos principales de un pedido.
        NOTA: Esta función no modifica los ítems del pedido.
        """
        result = self.pedido_model.find_by_id(pedido_id)
        if not result.get('success') or not result.get('data'):
            return {'success': False, 'error': 'El pedido no existe o no se puede actualizar.'}

        pedido: Pedido = result.get('data')
        if pedido.estado != 'PENDIENTE':
            return {'success': False, 'error': 'El estado del pedido no permite la actualización.'}

        try:
            validated_data = self.schema.load(data, partial=True)
            validated_data.pop('items', None) # No soportamos la actualización de items aquí
            if not validated_data:
                return {'success': False, 'error': 'No hay datos válidos para actualizar.'}

            return self.pedido_model.update(pedido_id, validated_data, id_field='id')
        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def eliminar_pedido(self, pedido_id: int) -> Dict:
        """
        Elimina un pedido si está en estado PENDIENTE.
        La eliminación de ítems se maneja por 'ON DELETE CASCADE' en la BD.
        """
        result = self.pedido_model.find_by_id(pedido_id)
        if not result.get('success') or not result.get('data'):
            return {'success': False, 'error': 'Pedido no encontrado.'}

        pedido: Pedido = result.get('data')
        if pedido.estado != 'PENDIENTE':
            return {'success': False, 'error': 'Solo se pueden eliminar pedidos pendientes.'}

        return self.pedido_model.delete(pedido_id, id_field='id')