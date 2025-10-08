import requests
from app.controllers.base_controller import BaseController

class GeorefController(BaseController):
    def __init__(self):
        super().__init__()
        self.base_url = "https://apis.datos.gob.ar/georef/api"

    def normalizar_direccion(self, direccion, localidad, provincia):
        """
        Normaliza una dirección utilizando la API de GEOREF.
        """
        params = {
            'direccion': direccion,
            'localidad': localidad,
            'provincia': provincia,
            'campos': 'completo'
        }
        
        try:
            response = requests.get(f"{self.base_url}/direcciones", params=params)
            response.raise_for_status()  # Lanza una excepción para códigos de error HTTP
            data = response.json()

            if data['cantidad'] == 0:
                return {'success': False, 'message': "No se pudo normalizar la dirección. Verifique los datos ingresados."}

            # Tomar el primer resultado que es el más preciso
            direccion_normalizada = data['direcciones'][0]

            return {'success': True, 'data': direccion_normalizada}

        except requests.exceptions.RequestException as e:
            # Manejar errores de conexión, timeout, etc.
            return {'success': False, 'message': f"Error al conectar con la API de GEOREF: {e}"}
        except Exception as e:
            # Manejar otros errores inesperados
            return {'success': False, 'message': f"Ocurrió un error inesperado: {e}"}