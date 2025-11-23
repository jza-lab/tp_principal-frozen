import unittest
from unittest.mock import MagicMock, patch
from app.controllers.vehiculo_controller import VehiculoController

class TestVehiculoController(unittest.TestCase):
    def setUp(self):
        self.controller = VehiculoController()
        self.controller.model = MagicMock()

    def test_cambiar_estado_deactivate(self):
        # Setup: Vehículo está activo (o no tiene campo activo, asume True)
        self.controller.model.find_by_id.return_value = {'success': True, 'data': {'id': 1, 'activo': True}}
        self.controller.model.update.return_value = {'success': True, 'data': {'id': 1, 'activo': False}}

        # Action
        result = self.controller.cambiar_estado(1)

        # Assert
        self.controller.model.find_by_id.assert_called_with(1)
        self.controller.model.update.assert_called_with(1, {'activo': False})
        self.assertTrue(result['success'])

    def test_cambiar_estado_activate(self):
        # Setup: Vehículo está inactivo
        self.controller.model.find_by_id.return_value = {'success': True, 'data': {'id': 1, 'activo': False}}
        self.controller.model.update.return_value = {'success': True, 'data': {'id': 1, 'activo': True}}

        # Action
        result = self.controller.cambiar_estado(1)

        # Assert
        self.controller.model.update.assert_called_with(1, {'activo': True})

    def test_cambiar_estado_not_found(self):
        self.controller.model.find_by_id.return_value = {'success': False, 'error': 'Not found'}
        result = self.controller.cambiar_estado(999)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Vehículo no encontrado.')

    def test_buscar_por_patente_filtra_inactivos(self):
        # Setup: Lista de vehiculos simulada
        # Mock de datetime en _enrich_vehicle_data es dificil sin patchear datetime, 
        # pero podemos poner fechas muy lejanas para asegurar que no esten vencidas
        vehiculos_mock = [
            {'id': 1, 'patente': 'ABC123', 'activo': True, 'vtv_vencimiento': '2030-01-01', 'licencia_vencimiento': '2030-01-01'},
            {'id': 2, 'patente': 'DEF456', 'activo': False, 'vtv_vencimiento': '2030-01-01', 'licencia_vencimiento': '2030-01-01'}, # Inactivo
            {'id': 3, 'patente': 'GHI789', 'activo': True, 'vtv_vencimiento': '2000-01-01', 'licencia_vencimiento': '2030-01-01'}  # VTV Vencida (seguro vencida en 2025)
        ]
        self.controller.model.find_all.return_value = {'success': True, 'data': vehiculos_mock}

        # Action
        response = self.controller.buscar_por_patente(search='ABC')

        # Assert
        self.assertTrue(response['success'])
        data = response['data']
        # Deben filtrarse el inactivo (2) y el vencido (3)
        self.assertEqual(len(data), 1) 
        self.assertEqual(data[0]['id'], 1)
