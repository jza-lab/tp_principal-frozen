from app.controllers.base_controller import BaseController
from app.models.despacho import DespachoModel
from app.models.base_model import BaseModel as GenericBaseModel

class DespachoController(BaseController):
    def __init__(self):
        super().__init__()
        self.model = DespachoModel()
        self._pedido_controller = None
        self._producto_controller = None
        self._zona_controller = None

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

    @property
    def zona_controller(self):
        if self._zona_controller is None:
            from app.controllers.zona_controller import ZonaController
            self._zona_controller = ZonaController()
        return self._zona_controller

    def obtener_pedidos_para_despacho(self):
        """
        Obtiene todos los pedidos en estado 'LISTO PARA ENTREGAR', les asigna su
        zona y calcula su peso total de forma optimizada.
        """
        # 1. Obtener los pedidos base
        pedidos_response, _ = self.pedido_controller.obtener_pedidos(filtros={'estado': 'LISTO_PARA_ENTREGA'})
        if not pedidos_response.get('success'):
            return pedidos_response

        pedidos = pedidos_response.get('data', [])
        if not pedidos:
            return {'success': True, 'data': []}

        # 2. Recolectar todos los IDs de productos únicos
        producto_ids = set()
        for pedido in pedidos:
            for item in pedido.get('pedido_items', []):
                if item.get('producto_id'):
                    producto_ids.add(item['producto_id'])

        # 3. Obtener los pesos de todos los productos en una sola consulta
        pesos_map = {}
        if producto_ids:
            producto_model = self.producto_controller.model
            table_name = producto_model.get_table_name()
            try:
                # Usamos 'in_' para buscar múltiples IDs
                response = producto_model.db.table(table_name).select('id, peso_total_gramos').in_('id', list(producto_ids)).execute()
                productos_data = response.data
                # Crear un mapa de id -> peso para búsqueda rápida
                for prod in productos_data:
                    pesos_map[prod['id']] = prod.get('peso_total_gramos', 0) or 0
            except Exception as e:
                # Si la consulta de pesos falla, es mejor registrar el error y continuar
                # asignando peso 0 que romper toda la funcionalidad.
                print(f"Error al obtener pesos de productos: {e}")

        # 4. Obtener el mapa de zonas
        zona_map_response = self.zona_controller.obtener_mapa_localidades_a_zonas()
        zona_map = zona_map_response.get('data', {}) if zona_map_response.get('success') else {}

        # 5. Enriquecer cada pedido con su zona y peso total calculado
        pedidos_enriquecidos = []
        for pedido in pedidos:
            # Asignar zona
            localidad = pedido.get('direccion', {}).get('localidad', 'Sin Localidad')
            pedido['zona'] = {'nombre': zona_map.get(localidad, 'Sin Zona Asignada')}

            # Calcular peso total usando el mapa de pesos
            peso_total_gramos = 0
            for item in pedido.get('pedido_items', []):
                cantidad = item.get('cantidad', 0)
                peso_unitario = pesos_map.get(item.get('producto_id'), 0)
                peso_total_gramos += cantidad * peso_unitario
            
            pedido['peso_total_calculado_kg'] = round(peso_total_gramos / 1000, 2)
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

    def generar_hoja_de_ruta_pdf(self, despacho_id):
        """
        Genera un archivo PDF para la Hoja de Ruta de un despacho específico.
        """
        from flask import render_template, make_response
        from xhtml2pdf import pisa
        import io
        from datetime import datetime

        # 1. Obtener datos del despacho
        response = self.model.get_by_id(despacho_id, 
            related_entities=['vehiculo:vehiculo_id(patente,marca,modelo,conductor:conductor_id(*))', 'despacho_items:despacho_id(pedido:pedido_id(*,cliente:cliente_id(*),direccion:direccion_id(*)))']
        )
        if not response['success'] or not response['data']:
            return {'success': False, 'error': 'Despacho no encontrado'}
        
        despacho_data = response['data'][0]
        
        # Simplificar estructura de datos para la plantilla
        despacho_data['pedidos'] = [item['pedido'] for item in despacho_data.get('despacho_items', [])]
        
        # 2. Renderizar la plantilla HTML
        html = render_template('despachos/hoja_de_ruta.html', 
                               despacho=despacho_data, 
                               fecha_emision=datetime.now().strftime('%d/%m/%Y'))

        # 3. Convertir HTML a PDF
        result = io.BytesIO()
        pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
        
        if pdf.err:
            return {'success': False, 'error': 'Error al generar el PDF'}

        # 4. Crear la respuesta HTTP
        response = make_response(result.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=Hoja_de_Ruta_{despacho_id}.pdf'
        
        return response
