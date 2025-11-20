from app.controllers.base_controller import BaseController
from app.models.costo_fijo import CostoFijoModel

class CostoFijoController(BaseController):
    """
    Controlador para gestionar la lógica de negocio de los costos fijos.
    """
    def __init__(self):
        super().__init__()
        self.model = CostoFijoModel()

    def get_costo_fijo_by_id(self, costo_fijo_id):
        """
        Obtiene un costo fijo por su ID.
        """
        result = self.model.find_by_id(costo_fijo_id)
        if result.get('success'):
            return self.success_response(result['data'])
        return self.error_response(result.get('error', 'Costo fijo no encontrado.'), 404)

    def get_all_costos_fijos(self, filters=None):
        """
        Obtiene todos los costos fijos, opcionalmente aplicando filtros.
        """
        result = self.model.find_all(filters=filters)
        if result.get('success'):
            return self.success_response(result['data'])
        return self.error_response(result.get('error', 'Error al obtener los costos fijos.'))

    def create_costo_fijo(self, data):
        """
        Crea un nuevo registro de costo fijo.
        """
        # Aquí se podría añadir validación con un schema de Marshmallow.
        result = self.model.create(data)
        if result.get('success'):
            return self.success_response(result['data'], "Costo fijo creado exitosamente.", 201)
        return self.error_response(result.get('error', 'No se pudo crear el costo fijo.'))

    def update_costo_fijo(self, costo_fijo_id, data):
        """
        Actualiza un costo fijo existente.
        """
        result = self.model.update(costo_fijo_id, data)
        if result.get('success'):
            return self.success_response(result['data'], "Costo fijo actualizado exitosamente.")
        return self.error_response(result.get('error', 'No se pudo actualizar el costo fijo.'))

    def delete_costo_fijo(self, costo_fijo_id):
        """
        Desactiva un costo fijo (soft delete).
        """
        result = self.model.delete(costo_fijo_id, soft_delete=True)
        if result.get('success'):
            return self.success_response(message="Costo fijo desactivado exitosamente.")
        return self.error_response(result.get('error', 'No se pudo desactivar el costo fijo.'))
    def reactivate_costo_fijo(self, costo_fijo_id):
            """
            Reactiva un costo fijo (undo soft delete).
            """
            # Forzamos el update del campo 'activo' a True
            result = self.model.update(costo_fijo_id, {'activo': True})
            
            if result.get('success'):
                return self.success_response(message="Costo fijo reactivado exitosamente.")
            return self.error_response(result.get('error', 'No se pudo reactivar el costo fijo.'))