import pytest
from unittest.mock import MagicMock, patch, ANY
from app.controllers.producto_controller import ProductoController
from app import create_app

@pytest.fixture
def app():
    app = create_app()
    app.config.update({"TESTING": True, "JWT_SECRET_KEY": "test-secret", "WTF_CSRF_ENABLED": False})
    yield app

@pytest.fixture
def mock_producto_dependencies():
    with patch('app.controllers.producto_controller.ProductoModel') as MockProductoModel, \
         patch('app.controllers.producto_controller.RecetaController') as MockRecetaController, \
         patch('app.controllers.producto_controller.RecetaModel') as MockRecetaModel:
        yield {
            "producto_model": MockProductoModel.return_value,
            "receta_controller": MockRecetaController.return_value,
            "receta_model": MockRecetaModel.return_value,
        }

@pytest.fixture
def producto_controller(mock_producto_dependencies):
    controller = ProductoController()
    controller.model = mock_producto_dependencies['producto_model']
    controller.receta_controller = mock_producto_dependencies['receta_controller']
    controller.receta_model = mock_producto_dependencies['receta_model']
    return controller

class TestProductoController:

    def test_crear_producto_exitoso(self, producto_controller, mock_producto_dependencies):
        form_data = {'nombre': 'Torta', 'codigo': 'PROD-TORT-0001', 'unidad_medida': 'un', 'categoria': 'Pasteleria', 'precio_unitario': 100, 'stock_min_produccion': 10, 'cantidad_maxima_x_pedido': 5, 'iva': True}
        mock_producto_dependencies['producto_model'].find_by_codigo.return_value = {'success': False}
        mock_producto_dependencies['producto_model'].create.return_value = {'success': True, 'data': {'id': 1, 'nombre': 'Torta'}}
        mock_producto_dependencies['receta_model'].create.return_value = {'success': True, 'data': {'id': 1}}
        response, status_code = producto_controller.crear_producto(form_data)
        assert status_code == 201
        assert response['success']

    def test_crear_producto_codigo_duplicado(self, producto_controller, mock_producto_dependencies):
        form_data = {'nombre': 'Muffin', 'codigo': 'PROD-MUFF-0001', 'unidad_medida': 'un', 'categoria': 'Pasteleria', 'precio_unitario': 50, 'stock_min_produccion': 20, 'cantidad_maxima_x_pedido': 10, 'iva': True}
        mock_producto_dependencies['producto_model'].find_by_codigo.return_value = {'success': True, 'data': {'id': 2}}
        response, status_code = producto_controller.crear_producto(form_data)
        assert status_code == 409
        assert not response['success']

    def test_actualizar_producto_exitoso(self, producto_controller, mock_producto_dependencies):
        producto_id = 1
        form_data = {'nombre': 'Torta de Vainilla'}
        mock_producto_dependencies['producto_model'].find_by_id.return_value = {'success': True, 'data': {'codigo': 'PROD-TORT-0001'}}
        mock_producto_dependencies['producto_model'].update.return_value = {'success': True, 'data': {}}
        mock_producto_dependencies['receta_model'].find_all.return_value = {'success': True, 'data': [{'id': 1}]}
        response, status_code = producto_controller.actualizar_producto(producto_id, form_data)
        assert status_code == 200
        assert response['success']

    def test_desactivar_producto(self, producto_controller, mock_producto_dependencies):
        producto_id = 1
        mock_producto_dependencies['producto_model'].update.return_value = {'success': True}
        response, status_code = producto_controller.eliminar_producto_logico(producto_id)
        assert status_code == 200
        assert response['success']

    def test_reactivar_producto(self, producto_controller, mock_producto_dependencies):
        producto_id = 1
        mock_producto_dependencies['producto_model'].update.return_value = {'success': True}
        response, status_code = producto_controller.habilitar_producto(producto_id)
        assert status_code == 200
        assert response['success']
