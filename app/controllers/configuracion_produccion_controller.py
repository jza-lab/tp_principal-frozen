from app.controllers.base_controller import BaseController
from app.models.configuracion_produccion import ConfiguracionProduccionModel

class ConfiguracionProduccionController(BaseController):
    """
    Controlador para gestionar la lógica de negocio de la configuración de producción.
    """
    def __init__(self):
        super().__init__()
        self.model = ConfiguracionProduccionModel()

    def get_configuracion_produccion(self):
        """
        Obtiene toda la configuración de producción (los 7 días de la semana).
        """
        result = self.model.find_all(order_by='id.asc') # Asume un orden por día
        if result.get('success'):
            return self.success_response(result['data'])
        return self.error_response(result.get('error', 'Error al obtener la configuración.'))

    def update_configuracion_produccion(self, configs_data):
        """
        Actualiza la configuración para múltiples días.
        'configs_data' debe ser una lista de diccionarios, cada uno con 'id' y 'horas'.
        """
        updated_configs = []
        for config in configs_data:
            config_id = config.get('id')
            data_to_update = {'horas': config.get('horas')}
            result = self.model.update(config_id, data_to_update)
            if not result.get('success'):
                return self.error_response(f"Error al actualizar la configuración para el día ID {config_id}.")
            updated_configs.append(result['data'])
        
        return self.success_response(updated_configs, "Configuración de producción actualizada exitosamente.")
