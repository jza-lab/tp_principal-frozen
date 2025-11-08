from app.controllers.base_controller import BaseController
from app.models.vehiculo import VehiculoModel

class VehiculoController(BaseController):
    def __init__(self):
        super().__init__()
        self.model = VehiculoModel()

    def crear_vehiculo(self, data):
        # Lógica para crear un nuevo vehículo
        return self.model.create(data)

    def obtener_vehiculo_por_id(self, vehiculo_id):
        return self.model.find_by_id(vehiculo_id)

    def obtener_todos_los_vehiculos(self):
        return self.model.find_all()

    def actualizar_vehiculo(self, vehiculo_id, data):
        return self.model.update(vehiculo_id, data)

    def eliminar_vehiculo(self, vehiculo_id):
        return self.model.delete(vehiculo_id)

    def buscar_por_patente(self, patente):
        """
        Busca un vehículo por su patente.
        """
        return self.model.find_all(filters={'patente': patente})
