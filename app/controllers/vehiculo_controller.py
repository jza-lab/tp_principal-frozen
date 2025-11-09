import re
from app.controllers.base_controller import BaseController
from app.models.vehiculo import VehiculoModel

class VehiculoController(BaseController):
    def __init__(self):
        super().__init__()
        self.model = VehiculoModel()

    def _validar_datos_vehiculo(self, data):
        """
        Valida los datos de un vehículo.
        Devuelve un diccionario con {'success': True} o {'success': False, 'error': ...}
        """
        # Validación de patente
        patente = data.get('patente', '').strip().upper().replace(' ', '')
        if not re.match(r'^(?:[A-Z]{3}\d{3}|[A-Z]{2}\d{3}[A-Z]{2})$', patente):
            return {'success': False, 'error': 'El formato de la patente no es válido. Use LLLNNN o LLNNNLL.'}
        data['patente'] = patente # Guardar formato normalizado

        # Validación de capacidad_kg
        try:
            capacidad_kg = float(data.get('capacidad_kg'))
            if not 100 <= capacidad_kg <= 500:
                return {'success': False, 'error': 'La capacidad de carga debe estar entre 100 y 500 kg.'}
        except (ValueError, TypeError):
            return {'success': False, 'error': 'La capacidad de carga debe ser un número válido.'}

        # Validación de nombre_conductor
        nombre_conductor = data.get('nombre_conductor', '').strip()
        if not nombre_conductor or len(nombre_conductor) < 3 or not all(c.isalpha() or c.isspace() for c in nombre_conductor):
            return {'success': False, 'error': 'El nombre del conductor es requerido, debe tener al menos 3 letras y no contener números.'}

        # Validación de dni_conductor
        dni_conductor = data.get('dni_conductor', '').strip()
        if not dni_conductor.isdigit() or not (7 <= len(dni_conductor) <= 8):
            return {'success': False, 'error': 'El DNI del conductor debe ser un número de 7 u 8 dígitos.'}

        # Validación de telefono_conductor
        telefono_conductor = data.get('telefono_conductor', '').strip()
        if telefono_conductor and (not telefono_conductor.isdigit() or len(telefono_conductor) < 7):
            return {'success': False, 'error': 'El teléfono del conductor debe ser un número de al menos 7 dígitos.'}
            
        return {'success': True}

    def crear_vehiculo(self, data):
        # Lógica para crear un nuevo vehículo
        validacion = self._validar_datos_vehiculo(data)
        if not validacion['success']:
            return validacion
        data.pop('csrf_token', None) # Eliminar el token CSRF antes de crear
        return self.model.create(data)

    def obtener_vehiculo_por_id(self, vehiculo_id):
        return self.model.find_by_id(vehiculo_id)

    def obtener_todos_los_vehiculos(self):
        return self.model.find_all()

    def actualizar_vehiculo(self, vehiculo_id, data):
        validacion = self._validar_datos_vehiculo(data)
        if not validacion['success']:
            return validacion
        data.pop('csrf_token', None) # Eliminar el token CSRF antes de actualizar
        return self.model.update(vehiculo_id, data)

    def eliminar_vehiculo(self, vehiculo_id):
        return self.model.delete(vehiculo_id)

    def buscar_por_patente(self, patente):
        """
        Busca un vehículo por su patente.
        """
        return self.model.find_all(filters={'patente': patente})
