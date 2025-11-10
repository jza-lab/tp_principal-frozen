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

    def obtener_mapa_localidades_a_zonas(self):
        """
        Crea un mapa de {nombre_localidad: nombre_zona} para su uso en otros controladores.
        """
        mapa_final = {}
        
        # 1. Obtener todas las relaciones zona-localidad
        relaciones_response = self.zona_localidad_model.find_all()
        if not relaciones_response.get('success'):
            return {'success': False, 'error': 'Error al obtener relaciones zona-localidad'}

        # 2. Obtener un mapa de ID de zona -> nombre de zona
        zonas_response = self.zona_model.find_all()
        if not zonas_response.get('success'):
            return {'success': False, 'error': 'Error al obtener zonas'}
        mapa_zonas = {z['id']: z['nombre'] for z in zonas_response.get('data', [])}

        # 3. Obtener un mapa de ID de localidad -> nombre de localidad
        localidades_response = self.direccion_model.get_distinct_localidades()
        if not localidades_response.get('success'):
            return {'success': False, 'error': 'Error al obtener localidades'}
        mapa_localidades = {loc['id']: loc['localidad'] for loc in localidades_response.get('data', [])}

        # 4. Construir el mapa final
        for relacion in relaciones_response.get('data', []):
            localidad_id = relacion.get('localidad_id')
            zona_id = relacion.get('zona_id')

            if localidad_id in mapa_localidades and zona_id in mapa_zonas:
                nombre_localidad = mapa_localidades[localidad_id]
                nombre_zona = mapa_zonas[zona_id]
                mapa_final[nombre_localidad] = nombre_zona
        
        return {'success': True, 'data': mapa_final}

    def buscar_localidades(self, term):
        # 1. Obtener localidades que coinciden con el término
        localidades_response = self.direccion_model.search_distinct_localidades(term)
        if not localidades_response['success']:
            return localidades_response

        localidades = localidades_response['data']
        if not localidades:
            return {'success': True, 'data': []}

        # 2. Obtener un mapa de todas las localidades que ya están en alguna zona
        mapa_localidades_zonas = self._obtener_mapa_localidades_a_zonas()

        # 3. Enriquecer los resultados de la búsqueda
        # Usamos el ID de la localidad (obtenido de la tabla de direcciones) para el mapeo
        for loc in localidades:
            loc_id = loc.get('id')
            if loc_id and loc_id in mapa_localidades_zonas:
                loc['zona_asignada'] = mapa_localidades_zonas[loc_id]['nombre_zona']
                loc['zona_id'] = mapa_localidades_zonas[loc_id]['id_zona']
            else:
                loc['zona_asignada'] = None
                loc['zona_id'] = None
        
        return {'success': True, 'data': localidades}
        
    def _obtener_mapa_localidades_a_zonas(self):
        """
        Crea un mapa de {localidad_id: {'nombre_zona': '...', 'id_zona': ...}}
        para una búsqueda rápida de pertenencia de localidades a zonas.
        """
        mapa = {}
        # Hacemos un join "manual" para obtener los datos necesarios
        relaciones_response = self.zona_localidad_model.find_all()
        if not relaciones_response['success']:
            return {}

        zonas_response = self.zona_model.find_all()
        if not zonas_response['success']:
            return {}
        
        mapa_zonas = {z['id']: z['nombre'] for z in zonas_response['data']}

        for relacion in relaciones_response['data']:
            localidad_id = relacion.get('localidad_id')
            zona_id = relacion.get('zona_id')
            
            if localidad_id and zona_id in mapa_zonas:
                mapa[localidad_id] = {
                    'nombre_zona': mapa_zonas[zona_id],
                    'id_zona': zona_id
                }
        return mapa
