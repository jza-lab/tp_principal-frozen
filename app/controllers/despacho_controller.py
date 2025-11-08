from app.controllers.base_controller import BaseController
from app.models.despacho import DespachoModel
from app.models.base_model import BaseModel as GenericBaseModel

class DespachoController(BaseController):
    def __init__(self):
        super().__init__()
        self.model = DespachoModel()
        self._pedido_controller = None
        self._producto_controller = None

    @property
    def pedido_controller(self):
        if self._pedido_controller is None:
            from app.controllers.pedido_controller import PedidoController
            self._pedido_controller = PedidoController()
        return self._pedido_controller

    @property
    def producto_controller(self):
        if self._producto_controller is None:
            from app.controllers.producto_controller import ProductoController
            self._producto_controller = ProductoController()
        return self._producto_controller

    def obtener_pedidos_para_despacho(self):
        """
        Obtiene todos los pedidos que están en estado 'LISTO PARA ENTREGAR'
        y calcula el peso total de cada uno.
        """
        response, _ = self.pedido_controller.obtener_pedidos(filtros={'estado': 'LISTO_PARA_ENTREGA'})
        
        if not response.get('success'):
            return response

        pedidos_enriquecidos = []
        for pedido in response['data']:
            peso_total = 0
            if 'pedido_items' in pedido and pedido['pedido_items']:
                for item in pedido['pedido_items']:
                    producto_id = item.get('producto_id')
                    cantidad = item.get('cantidad', 0)
                    
                    if producto_id:
                        producto_data = self.producto_controller.obtener_producto_por_id(producto_id)
                        if producto_data:
                            peso_unitario = producto_data.get('peso_por_paquete_valor', 0)
                            peso_total += (peso_unitario or 0) * cantidad
            
            pedido['peso_total_calculado'] = round(peso_total, 2)
            pedidos_enriquecidos.append(pedido)

        return {'success': True, 'data': pedidos_enriquecidos}

    def crear_despacho_y_actualizar_pedidos(self, vehiculo_id, pedido_ids, observaciones):
        """
        Crea un nuevo despacho y actualiza el estado de los pedidos a 'EN_TRANSITO'.
        """
        despacho_data = {'vehiculo_id': vehiculo_id, 'observaciones': observaciones}
        despacho_response = self.model.create(despacho_data)
        
        if not despacho_response['success']:
            return despacho_response

        despacho_id = despacho_response['data'][0]['id']
        
        # Usamos un modelo genérico para la tabla de items del despacho
        despacho_items_model = GenericBaseModel()
        despacho_items_model.get_table_name = lambda: 'despacho_items'

        for pedido_id in pedido_ids:
            # Asociar pedido al despacho
            despacho_items_model.create({'despacho_id': despacho_id, 'pedido_id': pedido_id})
            
            # Actualizar estado del pedido
            self.pedido_controller.actualizar_estado_pedido(pedido_id, 'EN_TRANSITO')

        return {'success': True, 'data': {'despacho_id': despacho_id}}
