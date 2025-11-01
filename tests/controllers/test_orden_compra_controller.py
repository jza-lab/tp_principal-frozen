import pytest
from unittest.mock import MagicMock, patch
from app.controllers.orden_compra_controller import OrdenCompraController
from datetime import date
from app import create_app

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app()
    app.config.update({
        "TESTING": True,
        "JWT_SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False  # Disable CSRF for tests
    })
    yield app

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def mock_oc_dependencies():
    """Fixture to mock all external dependencies of OrdenCompraController."""
    with patch('app.controllers.orden_compra_controller.OrdenCompraModel') as MockOCModel, \
         patch('app.controllers.orden_compra_controller.InventarioController') as MockInventarioController, \
         patch('app.controllers.orden_compra_controller.InsumoController') as MockInsumoController, \
         patch('app.controllers.orden_compra_controller.UsuarioController') as MockUsuarioController:

        yield {
            "oc_model": MockOCModel.return_value,
            "inventario_controller": MockInventarioController.return_value,
            "insumo_controller": MockInsumoController.return_value,
            "usuario_controller": MockUsuarioController.return_value,
        }

@pytest.fixture
def oc_controller(mock_oc_dependencies):
    """Fixture to create an instance of OrdenCompraController with mocked dependencies."""
    return OrdenCompraController()

class TestOrdenCompraController:
    # Test para crear una orden de compra exitosamente
    def test_crear_orden_compra_exitoso(self, oc_controller, mock_oc_dependencies):
        # Arrange
        orden_data = {
            'proveedor_id': 1,
            'fecha_emision': date.today().isoformat(),
        }
        items_data = [{'insumo_id': 1, 'cantidad_solicitada': 10, 'precio_unitario': 5}]
        usuario_id = 1

        mock_oc_dependencies['oc_model'].create_with_items.return_value = {'success': True, 'data': {'id': 1}}

        # Act
        response = oc_controller.crear_orden(orden_data, items_data, usuario_id)

        # Assert
        assert response['success']
        assert response['data']['id'] == 1
        mock_oc_dependencies['oc_model'].create_with_items.assert_called_once()

    # Test para aprobar una orden de compra
    def test_aprobar_orden_compra(self, oc_controller, mock_oc_dependencies):
        # Arrange
        orden_id = 1
        usuario_id = 1
        
        mock_oc_dependencies['oc_model'].update.return_value = {'success': True}

        # Act
        response = oc_controller.aprobar_orden(orden_id, usuario_id)

        # Assert
        assert response['success']
        mock_oc_dependencies['oc_model'].update.assert_called_once()
        # Verificar que el estado se haya cambiado a 'APROBADA'
        update_call_args = mock_oc_dependencies['oc_model'].update.call_args[0][1]
        assert update_call_args['estado'] == 'APROBADA'

    # Test para cancelar una orden de compra
    def test_cancelar_orden_compra(self, app, oc_controller, mock_oc_dependencies):
        # Arrange
        orden_id = 1
        
        with app.test_request_context(json={'motivo': 'Test cancellation'}):
            mock_oc_dependencies['oc_model'].find_by_id.return_value = {'success': True, 'data': {'id': orden_id, 'estado': 'PENDIENTE'}}
            mock_oc_dependencies['oc_model'].update.return_value = {'success': True, 'data': {'id': orden_id, 'estado': 'CANCELADA'}}

            # Act
            response = oc_controller.cancelar_orden(orden_id)

            # Assert
            assert response.status_code == 200
            response_data = response.get_json()
            assert response_data['success']
            mock_oc_dependencies['oc_model'].update.assert_called_once()
            update_call_args = mock_oc_dependencies['oc_model'].update.call_args[0][1]
            assert update_call_args['estado'] == 'CANCELADA'
