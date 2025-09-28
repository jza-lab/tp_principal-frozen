from collections import defaultdict
from typing import Dict, List, Any
from app.models.pedido import PedidoModel, Pedido
from app.models.producto import ProductoModel

class PlanificacionController:
    """
    Controlador para la lógica de negocio del módulo de planificación de producción.
    """

    def __init__(self):
        self.pedido_model = PedidoModel()
        self.producto_model = ProductoModel()

    def obtener_pedidos_para_planificar(self) -> Dict[int, Dict[str, Any]]:
        """
        Obtiene todos los pedidos pendientes, los agrupa por producto y retorna
        un diccionario de diccionarios para ser usado en la vista.
        """
        # 1. Obtener todos los pedidos con estado 'PENDIENTE'
        resultado = self.pedido_model.find_all(filters={'estado': 'PENDIENTE'})
        pedidos_pendientes: List[Pedido] = resultado.get('data', [])

        if not pedidos_pendientes:
            return {}

        # 2. Agrupar los pedidos por producto_id
        pedidos_agrupados = defaultdict(lambda: {
            'producto_info': None,
            'pedidos': [],
            'cantidad_total': 0
        })

        for pedido in pedidos_pendientes:
            producto_id = pedido.producto_id
            # Se convierte el objeto a diccionario para mantener la consistencia
            pedidos_agrupados[producto_id]['pedidos'].append(pedido.to_dict())
            pedidos_agrupados[producto_id]['cantidad_total'] += pedido.cantidad

        # 3. Obtener la información de cada producto
        producto_ids = list(pedidos_agrupados.keys())
        productos_result = self.producto_model.find_all(filters={'id': ('in', producto_ids)})
        productos = {p['id']: p for p in productos_result.get('data', [])}

        for producto_id, data in pedidos_agrupados.items():
            # La información del producto ya es un diccionario, así que está bien
            data['producto_info'] = productos.get(producto_id)

        return dict(pedidos_agrupados)