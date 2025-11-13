import math
from app.controllers.base_controller import BaseController
from app.models.despacho import DespachoModel
from app.models.base_model import BaseModel as GenericBaseModel

class DespachoController(BaseController):
    DEPOSITO_LAT = -34.603722
    DEPOSITO_LNG = -58.381592

    def _calcular_distancia(self, lat2, lng2):
        """Calcula la distancia Haversine en km."""
        if lat2 is None or lng2 is None:
            return 0
        
        lat1 = self.DEPOSITO_LAT
        lng1 = self.DEPOSITO_LNG
        
        R = 6371
        dLat = math.radians(lat2 - lat1)
        dLng = math.radians(lng2 - lng1)
        a = (math.sin(dLat / 2) * math.sin(dLat / 2) +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dLng / 2) * math.sin(dLng / 2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distancia = R * c
        return round(distancia, 1)

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
            cliente = pedido.get('cliente')
            if not cliente: continue

            direccion = cliente.get('direccion')
            if not direccion or not direccion.get('latitud') or not direccion.get('longitud'): continue


            # Asignar zona
            localidad = direccion.get('localidad', 'Sin Localidad')
            pedido['zona'] = {'nombre': zona_map.get(localidad, 'Sin Zona Asignada')}

            # Calcular peso total usando el mapa de pesos
            peso_total_gramos = 0
            for item in pedido.get('pedido_items', []):
                cantidad = item.get('cantidad', 0)
                peso_unitario = pesos_map.get(item.get('producto_id'), 0)
                peso_total_gramos += cantidad * peso_unitario

            pedido['peso_total_calculado_kg'] = round(peso_total_gramos / 1000, 2)

            # Calcular distancia y tiempo estimado
            latitud = direccion.get('latitud')
            longitud = direccion.get('longitud')
            distancia = self._calcular_distancia(latitud, longitud)
            pedido['distancia_km'] = distancia
            # Estimación simple de tiempo: 2.5 minutos por km + 5 minutos fijos por parada
            pedido['tiempo_estimado'] = f"{round(distancia * 2.5 + 5)} min"

            pedidos_enriquecidos.append(pedido)

        # DEBUG: Añadir un pedido de prueba si la lista está vacía para asegurar que el frontend siempre reciba datos
        if not pedidos_enriquecidos:
            pedidos_enriquecidos.append({
                "id": 9999,
                "cliente": {"nombre": "Cliente de Prueba"},
                "direccion": {
                    "calle": "Calle Falsa", "altura": "123", "localidad": "Pruebalandia",
                    "latitud": -34.60, "longitud": -58.45
                },
                "peso_total_calculado_kg": 10.5,
                "distancia_km": 5.2,
                "tiempo_estimado": "20 min",
                "prioridad": "media",
                "zona": {"nombre": "ZONA TEST"}
            })

        return {'success': True, 'data': pedidos_enriquecidos}

    def get_all(self):
        """
        Obtiene todos los despachos existentes, incluyendo información del vehículo
        y los pedidos asociados.
        """
        try:
            # Columnas a seleccionar para enriquecer la información del despacho
            select_columns = '*, vehiculo:vehiculo_id(patente, tipo_vehiculo, capacidad_kg, nombre_conductor, dni_conductor), despacho_items(*, pedido:pedido_id(*))'

            # Corrección: Construir la consulta con select() en lugar de usar find_all con parámetros.
            result = self.model.db.table(self.model.get_table_name()).select(select_columns).execute()
            
            # El resultado de execute() es un objeto con un atributo 'data'.
            if hasattr(result, 'data'):
                return self.success_response(result.data)
            else:
                # Manejar el caso en que la respuesta no es la esperada.
                return self.error_response('Error al obtener despachos: la respuesta no contiene datos.', 500)

        except Exception as e:
            # Capturar cualquier excepción inesperada durante el proceso
            return self.error_response(f"Error excepcional en DespachoController.get_all: {e}", 500)

    def crear_despacho_y_actualizar_pedidos(self, vehiculo_id, pedido_ids, observaciones):
        """
        Crea un nuevo despacho y actualiza el estado de los pedidos a 'EN_TRANSITO'.
        """
        despacho_data = {'vehiculo_id': vehiculo_id, 'observaciones': observaciones}
        despacho_response = self.model.create(despacho_data)
        
        if not despacho_response['success']:
            return despacho_response

        despacho_id = despacho_response['data']['id']
        
        # Se define una clase de modelo concreta para despacho_items
        class DespachoItemModel(GenericBaseModel):
            def get_table_name(self):
                return 'despacho_items'

        despacho_items_model = DespachoItemModel()

        for pedido_id in pedido_ids:
            # Asociar pedido al despacho
            despacho_items_model.create({'despacho_id': despacho_id, 'pedido_id': pedido_id})
            
            # Actualizar estado del pedido
            # Esto asegura que el stock se consuma y las reservas se actualicen.
            # Pasamos form_data=None porque los datos del transportista ya están en la tabla 'despachos'.
            despacho_pedido_res, _ = self.pedido_controller.despachar_pedido(pedido_id, form_data=None)

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
        response = self.model.db.table(self.model.get_table_name()) \
            .select('*, vehiculo:vehiculo_id(patente, tipo_vehiculo, capacidad_kg, nombre_conductor, dni_conductor), despacho_items(*, pedido:pedido_id(*, cliente:clientes(*), direccion:usuario_direccion(*)))') \
            .filter('id', 'eq', despacho_id) \
            .execute()

        if not response.data:
            return {'success': False, 'error': 'Despacho no encontrado'}
        
        despacho_data = response.data[0]
        
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
