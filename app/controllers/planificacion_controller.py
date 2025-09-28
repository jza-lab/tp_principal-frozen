from collections import defaultdict
from typing import Dict, List, Any
from app.models.pedido import PedidoModel
from app.models.producto import ProductoModel

class PlanificacionController:
    """
    Controlador para la lógica de negocio del módulo de planificación de producción.
    CORREGIDO: Ahora opera sobre pedido_items individuales.
    """

    def __init__(self):
        self.pedido_model = PedidoModel()
        self.producto_model = ProductoModel()

    def obtener_pedidos_para_planificar(self) -> Dict[int, Dict[str, Any]]:
        """
        Obtiene todos los ítems de pedidos con estado 'PENDIENTE', los agrupa por
        producto y retorna un diccionario consolidado para ser usado en la vista.
        """
        # 1. Obtener todos los ítems de pedido pendientes directamente
        resultado = self.pedido_model.find_all_items(filters={'estado': 'PENDIENTE'})
        items_pendientes: List[Dict] = resultado.get('data', [])

        if not items_pendientes:
            return {}

        # 2. Agrupar los ítems por producto_id
        items_agrupados = defaultdict(lambda: {
            'producto_info': None,
            'items': [],
            'cantidad_total': 0.0,
            'pedido_ids': set() 
        })

        for item in items_pendientes:
            producto_id = item['producto_id']
            items_agrupados[producto_id]['items'].append(item)
            items_agrupados[producto_id]['cantidad_total'] += item['cantidad']
            items_agrupados[producto_id]['pedido_ids'].add(item['pedido_id'])

        # 3. Obtener la información de cada producto en una sola consulta
        producto_ids = list(items_agrupados.keys())
        if not producto_ids:
            return {}
            
        productos_result = self.producto_model.find_all(filters={'id': ('in', producto_ids)})
        productos_map = {p['id']: p for p in productos_result.get('data', [])}

        # 4. Enriquecer los datos agrupados con la info del producto
        for producto_id, data in items_agrupados.items():
            data['producto_info'] = productos_map.get(producto_id)
            data['pedido_ids'] = sorted(list(data['pedido_ids']))

        return dict(items_agrupados)