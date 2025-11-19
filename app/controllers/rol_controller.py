from app.controllers.base_controller import BaseController
from app.models.rol import RoleModel

class RolController(BaseController):
    """
    Controlador para gestionar la lógica de negocio de los roles.
    """
    def __init__(self):
        super().__init__()
        self.model = RoleModel()

    def get_rol_by_id(self, rol_id):
        """
        Obtiene un rol por su ID.
        """
        result = self.model.find_by_id(rol_id)
        if result.get('success'):
            return self.success_response(result['data'])
        return self.error_response(result.get('error', 'Rol no encontrado.'), 404)

    def get_all_roles(self):
        """
        Obtiene todos los roles.
        """
        result = self.model.find_all()
        if result.get('success'):
            return self.success_response(result['data'])
        return self.error_response(result.get('error', 'Error al obtener los roles.'))

    def create_rol(self, data):
        """
        Crea un nuevo rol.
        """
        # Aquí se podría añadir validación con un schema.
        result = self.model.create(data)
        if result.get('success'):
            return self.success_response(result['data'], "Rol creado exitosamente.", 201)
        return self.error_response(result.get('error', 'No se pudo crear el rol.'))

    def update_rol(self, rol_id, data):
        """
        Actualiza un rol existente.
        """
        # Asegurarse de que el campo 'costo_hora' se maneje correctamente.
        if 'costo_hora' in data and data['costo_hora'] == '':
            data['costo_hora'] = None
        
        result = self.model.update(rol_id, data)
        if result.get('success'):
            return self.success_response(result['data'], "Rol actualizado exitosamente.")
        return self.error_response(result.get('error', 'No se pudo actualizar el rol.'))

    def delete_rol(self, rol_id):
        """
        Elimina un rol.
        """
        # Considerar si se debe permitir eliminar roles o solo desactivarlos.
        # Por ahora, se elimina físicamente.
        result = self.model.delete(rol_id)
        if result.get('success'):
            return self.success_response(message="Rol eliminado exitosamente.")
        return self.error_response(result.get('error', 'No se pudo eliminar el rol.'))
