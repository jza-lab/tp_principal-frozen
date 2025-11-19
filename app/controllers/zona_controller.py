from app.controllers.base_controller import BaseController
from app.models.zona import ZonaModel

class ZonaController(BaseController):
    def __init__(self):
        super().__init__()
        self.zona_model = ZonaModel()

    def obtener_zonas(self):
        """
        Obtiene todas las zonas de envío.
        """
        return self.zona_model.find_all()

    def obtener_zona_por_id(self, zona_id):
        """
        Obtiene una zona por su ID.
        """
        return self.zona_model.find_by_id(zona_id)

    def crear_o_actualizar_zona(self, data, zona_id=None):
        """
        Crea o actualiza una zona con sus rangos de códigos postales y precio.
        """
        nombre = data.get('nombre')
        precio = data.get('precio')
        codigo_postal_inicio = data.get('codigo_postal_inicio')
        codigo_postal_fin = data.get('codigo_postal_fin')

        if not all([nombre, precio, codigo_postal_inicio, codigo_postal_fin]):
            return {'success': False, 'error': 'Todos los campos son requeridos.'}

        try:
            zona_data = {
                'nombre': nombre,
                'precio': float(precio),
                'codigo_postal_inicio': int(codigo_postal_inicio),
                'codigo_postal_fin': int(codigo_postal_fin)
            }
        except (ValueError, TypeError):
            return {'success': False, 'error': 'Precio y códigos postales deben ser números válidos.'}

        if zona_id:
            response = self.zona_model.update(zona_id, zona_data)
        else:
            response = self.zona_model.create(zona_data)
        
        return response

    def eliminar_zona(self, zona_id):
        """
        Elimina una zona.
        """
        return self.zona_model.delete(zona_id)

    def obtener_costo_por_codigo_postal(self, codigo_postal):
        """
        Busca una zona que corresponda al código postal y devuelve su precio.
        """
        try:
            cp = int(codigo_postal)
        except (ValueError, TypeError):
            return {'success': False, 'error': 'Código postal inválido.', 'data': {'precio': 0.00}}

        response = self.zona_model.find_by_postal_code(cp)
        
        if response.get('success') and response.get('data'):
            precio = response['data'].get('precio', 0.00)
            return {'success': True, 'data': {'precio': precio}}
        
        # Si no se encuentra zona o hay un error, el costo es 0.
        return {'success': True, 'data': {'precio': 0.00}}

    def obtener_zona_por_codigo_postal(self, codigo_postal):
        """
        Busca una zona que corresponda al código postal y devuelve el objeto de zona completo.
        """
        try:
            cp = int(codigo_postal)
        except (ValueError, TypeError):
            return {'success': False, 'error': 'Código postal inválido.'}

        return self.zona_model.find_by_postal_code(cp)
