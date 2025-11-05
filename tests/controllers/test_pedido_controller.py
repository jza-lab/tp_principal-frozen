import pytest
from unittest.mock import MagicMock, patch, ANY
from app.controllers.pedido_controller import PedidoController
from app import create_app

@pytest.fixture
def app():
    app = create_app()
    app.config.update({"TESTING": True, "JWT_SECRET_KEY": "test-secret", "WTF_CSRF_ENABLED": False})
    yield app

@pytest.fixture
def mock_pedido_dependencies():
    with patch('app.controllers.pedido_controller.PedidoModel') as MockPedidoModel, \
         patch('app.controllers.pedido_controller.LoteProductoController') as MockLoteController, \
         patch('app.controllers.pedido_controller.ProductoModel') as MockProductoModel, \
         patch('app.controllers.pedido_controller.ClienteModel') as MockClienteModel, \
         patch('app.controllers.pedido_controller.DireccionModel') as MockDireccionModel:
        yield {
            "pedido_model": MockPedidoModel.return_value,
            "lote_controller": MockLoteController.return_value,
            "producto_model": MockProductoModel.return_value,
            "cliente_model": MockClienteModel.return_value,
            "direccion_model": MockDireccionModel.return_value
        }

@pytest.fixture
def pedido_controller(mock_pedido_dependencies):
    controller = PedidoController()
    controller.model = mock_pedido_dependencies['pedido_model']
    controller.lote_producto_controller = mock_pedido_dependencies['lote_controller']
    controller.producto_model = mock_pedido_dependencies['producto_model']
    controller.cliente_model = mock_pedido_dependencies['cliente_model']
    controller.direccion_model = mock_pedido_dependencies['direccion_model']
    return controller

class TestPedidoController:
    def test_crear_pedido_con_stock_suficiente(self, pedido_controller, mock_pedido_dependencies):
        usuario_id = 1
        form_data = {'id_cliente': 1, 'items': [{'producto_id': 100, 'cantidad': 10}]}
        mock_pedido_dependencies['cliente_model'].find_by_id.return_value = {'success': True, 'data': {'direccion_id': 1}}
        mock_pedido_dependencies['producto_model'].find_by_id.return_value = {'success': True, 'data': {'stock_min_produccion': 5, 'cantidad_maxima_x_pedido': 50}}
        mock_pedido_dependencies['lote_controller'].obtener_stock_disponible_real.return_value = ({'success': True, 'data': {'stock_disponible_real': 20}}, 200)
        pedido_creado_mock = {'id': 1, 'items': [{'id': 1}]}
        mock_pedido_dependencies['pedido_model'].create_with_items.return_value = {'success': True, 'data': pedido_creado_mock}
        mock_pedido_dependencies['lote_controller'].reservar_stock_para_pedido.return_value = {'success': True}
        response, status_code = pedido_controller.crear_pedido_con_items(form_data, usuario_id)
        assert status_code == 201
        assert response['success']

    @patch('app.controllers.pedido_controller.OrdenProduccionController')
    def test_crear_pedido_sin_stock_inicia_produccion(self, MockOPController, pedido_controller, mock_pedido_dependencies):
        usuario_id = 1
        form_data = {'id_cliente': 1, 'items': [{'producto_id': 100, 'cantidad': 30}]}
        mock_pedido_dependencies['cliente_model'].find_by_id.return_value = {'success': True, 'data': {'direccion_id': 1}}
        mock_pedido_dependencies['producto_model'].find_by_id.return_value = {'success': True, 'data': {'stock_min_produccion': 5, 'cantidad_maxima_x_pedido': 50}}
        mock_pedido_dependencies['lote_controller'].obtener_stock_disponible_real.return_value = ({'success': True, 'data': {'stock_disponible_real': 20}}, 200)
        pedido_creado_mock = {'id': 1, 'items': [{'id': 1, 'producto_id': 100, 'cantidad': 30}]}
        mock_pedido_dependencies['pedido_model'].create_with_items.return_value = {'success': True, 'data': pedido_creado_mock}
        mock_pedido_dependencies['pedido_model'].find_by_id.return_value = {'success': True, 'data': {'estado': 'EN_PROCESO'}}
        mock_op_instance = MockOPController.return_value
        mock_op_instance.crear_orden.return_value = ({'success': True, 'data': {'id': 99}}, 201)
        with patch('app.controllers.pedido_controller.RecetaModel') as MockRecetaModel:
            MockRecetaModel.return_value.find_all.return_value = {'success': True, 'data': [{'id': 1}]}
            response, status_code = pedido_controller.crear_pedido_con_items(form_data, usuario_id)
            assert status_code == 201
            assert response['success']

    def test_cancelar_pedido_libera_stock(self, pedido_controller, mock_pedido_dependencies):
        pedido_id = 1
        mock_pedido_dependencies['pedido_model'].find_by_id.return_value = {'success': True, 'data': {'estado': 'LISTO_PARA_ENTREGA'}}
        mock_pedido_dependencies['lote_controller'].liberar_stock_por_cancelacion_de_pedido.return_value = {'success': True}
        mock_pedido_dependencies['pedido_model'].cambiar_estado.return_value = {'success': True}
        response, status_code = pedido_controller.cancelar_pedido(pedido_id)
        assert status_code == 200
        assert response['success']

    def test_despachar_pedido(self, pedido_controller, mock_pedido_dependencies):
        pedido_id = 1
        form_data = {'conductor_nombre': 'Juan Perez', 'conductor_dni': '12345678', 'vehiculo_patente': 'AB123CD', 'conductor_telefono': '1122334455'}
        mock_pedido_dependencies['pedido_model'].get_one_with_items_and_op_status.return_value = {'success': True, 'data': {'estado': 'LISTO_PARA_ENTREGA'}}
        mock_pedido_dependencies['pedido_model'].find_by_id.return_value = {'success': True, 'data': {'id': 1}}
        mock_pedido_dependencies['lote_controller'].despachar_stock_reservado_por_pedido.return_value = {'success': True}
        with patch('app.controllers.pedido_controller.DespachoModel') as MockDespachoModel:
            MockDespachoModel.return_value.create.return_value = {'success': True}
            mock_pedido_dependencies['pedido_model'].update.return_value = {'success': True}
            response, status_code = pedido_controller.despachar_pedido(pedido_id, form_data)
            assert status_code == 200
            assert response['success']
