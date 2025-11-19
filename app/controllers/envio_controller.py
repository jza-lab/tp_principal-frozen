from app.controllers.vehiculo_controller import VehiculoController
from app.controllers.zona_controller import ZonaController

class EnvioController:
    def __init__(self):
        self.vehiculo_controller = VehiculoController()
        self.zona_controller = ZonaController()

    def obtener_datos_para_vista_gestion(self):
        """
        Orquesta la obtención de datos de vehículos y zonas para la vista de gestión de envíos.
        """
        vehiculos_response = self.vehiculo_controller.obtener_todos_los_vehiculos()
        zonas_response = self.zona_controller.obtener_zonas()

        vehiculos = vehiculos_response.get('data', []) if vehiculos_response.get('success') else []
        zonas = zonas_response.get('data', []) if zonas_response.get('success') else []
        
        errors = []
        if not vehiculos_response.get('success'):
            errors.append(vehiculos_response.get('error', 'Error desconocido al obtener vehículos.'))
        if not zonas_response.get('success'):
            errors.append(zonas_response.get('error', 'Error desconocido al obtener zonas.'))

        if errors:
            return {
                'success': False,
                'error': ' y '.join(errors),
                'data': {
                    'vehiculos': vehiculos,
                    'zonas': zonas
                }
            }
            
        return {
            'success': True,
            'data': {
                'vehiculos': vehiculos,
                'zonas': zonas
            }
        }
