import unittest
from app.controllers.vehiculo_controller import VehiculoController
from unittest.mock import MagicMock

class TestVehiculoValidation(unittest.TestCase):
    def setUp(self):
        self.controller = VehiculoController()
        self.controller.model = MagicMock()

    def test_validar_tipo_y_capacidad(self):
        # Valid
        # Include required fields for full validation
        base_data = {
            'patente': 'ABC123',
            'nombre_conductor': 'Juan',
            'dni_conductor': '12345678',
            'telefono_conductor': '11223344'
        }

        data = {**base_data, 'tipo_vehiculo': 'Camioneta', 'capacidad_kg': '100'}
        res = self.controller._validar_datos_vehiculo(data)
        self.assertTrue(res['success'], f"Failed valid Camioneta: {res.get('error')}")

        data = {**base_data, 'tipo_vehiculo': 'Combi', 'capacidad_kg': '300'}
        res = self.controller._validar_datos_vehiculo(data)
        self.assertTrue(res['success'])

        data = {**base_data, 'tipo_vehiculo': 'Camión', 'capacidad_kg': '500'}
        res = self.controller._validar_datos_vehiculo(data)
        self.assertTrue(res['success'])

        # Invalid Capacity
        data = {**base_data, 'tipo_vehiculo': 'Camioneta', 'capacidad_kg': '300'}
        res = self.controller._validar_datos_vehiculo(data)
        self.assertFalse(res['success'])
        self.assertIn('capacidad', res['error'])

        data = {**base_data, 'tipo_vehiculo': 'Combi', 'capacidad_kg': '100'}
        res = self.controller._validar_datos_vehiculo(data)
        self.assertFalse(res['success'])

        data = {**base_data, 'tipo_vehiculo': 'Camión', 'capacidad_kg': '900'}
        res = self.controller._validar_datos_vehiculo(data)
        self.assertFalse(res['success'])

        # Invalid Type
        data = {**base_data, 'tipo_vehiculo': 'Moto', 'capacidad_kg': '100'}
        res = self.controller._validar_datos_vehiculo(data)
        self.assertFalse(res['success'])
        self.assertIn('tipo', res['error'])
