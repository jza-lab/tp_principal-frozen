from app.controllers.base_controller import BaseController
from app.models.zona import ZonaModel, ZonaLocalidadModel
from app.models.direccion import DireccionModel

class ZonaController(BaseController):
    def __init__(self):
        super().__init__()
        self.zona_model = ZonaModel()
        self.zona_localidad_model = ZonaLocalidadModel()
        self.direccion_model = DireccionModel()

    def obtener_zonas_con_localidades(self):
        zonas_response = self.zona_model.find_all()
        if not zonas_response['success']:
            return zonas_response

        zonas = zonas_response['data']
        for zona in zonas:
            localidades_response = self.zona_localidad_model.find_all(filters={'zona_id': zona['id']})
            if localidades_response['success']:
                zona['localidades'] = localidades_response['data']
            else:
                zona['localidades'] = []
        
        return {'success': True, 'data': zonas}

    def obtener_zona_por_id(self, zona_id):
        zona_response = self.zona_model.find_by_id(zona_id)
        if not zona_response['success']:
            return zona_response
        
        zona = zona_response['data']
        localidades_response = self.zona_localidad_model.find_all(filters={'zona_id': zona['id']})
        if localidades_response['success']:
            zona['localidades_ids'] = [item['localidad_id'] for item in localidades_response['data']]
        else:
            zona['localidades_ids'] = []
            
        return {'success': True, 'data': zona}

    def crear_o_actualizar_zona(self, data, zona_id=None):
        nombre = data.get('nombre')
        localidades_ids = data.get('localidades_ids', [])

        if not nombre:
            return {'success': False, 'error': 'El nombre de la zona es requerido.'}

        zona_data = {'nombre': nombre}
        if zona_id:
            response = self.zona_model.update(zona_id, zona_data)
        else:
            response = self.zona_model.create(zona_data)
        
        if not response['success']:
            return response
        
        new_zona_id = zona_id if zona_id else response['data']['id']
        
        # Actualizar localidades
        items_a_eliminar = self.zona_localidad_model.find_all(filters={'zona_id': new_zona_id})
        if items_a_eliminar['success']:
            for item in items_a_eliminar['data']:
                self.zona_localidad_model.delete(item['id'])

        for loc_id in localidades_ids:
            self.zona_localidad_model.create({'zona_id': new_zona_id, 'localidad_id': loc_id})
            
        return {'success': True, 'data': {'id': new_zona_id}}

    def eliminar_zona(self, zona_id):
        items_a_eliminar = self.zona_localidad_model.find_all(filters={'zona_id': zona_id})
        if items_a_eliminar['success']:
            for item in items_a_eliminar['data']:
                self.zona_localidad_model.delete(item['id'])
        return self.zona_model.delete(zona_id)

    def buscar_localidades(self, term):
        return self.direccion_model.search_distinct_localidades(term)
        
    def obtener_mapa_localidades_a_zonas(self):
        response = self.zona_localidad_model.find_all()
        if not response['success']:
            return response
        
        mapa = {}
        for item in response['data']:
            zona_id = item.get('zona_id')
            localidad_id = item.get('localidad_id')
            
            if zona_id and localidad_id:
                zona_resp = self.zona_model.find_by_id(zona_id)
                localidad_resp = self.direccion_model.find_by_id(localidad_id) # Asumiendo que las localidades se guardan en la tabla de direcciones
                
                if zona_resp['success'] and localidad_resp['success']:
                    mapa[localidad_resp['data']['localidad']] = zona_resp['data']['nombre']

        return {'success': True, 'data': mapa}
