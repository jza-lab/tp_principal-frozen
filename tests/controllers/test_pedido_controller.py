import pytest
from unittest.mock import MagicMock, patch, ANY
from app.controllers.pedido_controller import PedidoController
from app import create_app
from types import SimpleNamespace
from datetime import date

# --- Fixtures ---

@pytest.fixture
def app():
    app = create_app()
    app.config.update({"TESTING": True, "JWT_SECRET_KEY": "test-secret", "WTF_CSRF_ENABLED": False, "SERVER_NAME": "localhost.local"})
    yield app

@pytest.fixture
def mock_current_user():
    user = SimpleNamespace(id=1, nombre='Test', apellido='User', roles=['VENDEDOR'])
    with patch('app.controllers.pedido_controller.get_current_user', return_value=user) as mock:
        yield mock

@pytest.fixture
def mock_main_dependencies():
    with patch('app.controllers.pedido_controller.PedidoModel') as MockPedidoModel, \
         patch('app.controllers.pedido_controller.LoteProductoController') as MockLoteController, \
         patch('app.controllers.pedido_controller.ProductoModel') as MockProductoModel, \
         patch('app.controllers.pedido_controller.ClienteModel') as MockClienteModel, \
         patch('app.controllers.pedido_controller.DireccionModel') as MockDireccionModel, \
         patch('app.controllers.pedido_controller.DespachoModel') as MockDespachoModel, \
         patch('app.controllers.pedido_controller.RecetaModel') as MockRecetaModel, \
         patch('app.controllers.pedido_controller.NotaCreditoModel') as MockNotaCreditoModel, \
         patch('app.controllers.pedido_controller.RegistroController') as MockRegistroController:
        
        mocks = {
            "pedido_model": MockPedidoModel.return_value, "lote_controller": MockLoteController.return_value,
            "producto_model": MockProductoModel.return_value, "cliente_model": MockClienteModel.return_value,
            "direccion_model": MockDireccionModel.return_value, "despacho_model": MockDespachoModel.return_value,
            "receta_model": MockRecetaModel.return_value, "nota_credito_model": MockNotaCreditoModel.return_value,
            "registro_controller": MockRegistroController.return_value,
        }
        mocks['cliente_model'].find_by_id.return_value = {'success': True, 'data': {'id': 1, 'direccion_id': 123, 'estado_crediticio': 'normal'}}
        mocks['producto_model'].find_by_id.return_value = {'success': True, 'data': {'id': 100, 'nombre': 'Producto Test', 'cantidad_maxima_x_pedido': 100}}
        yield mocks

@pytest.fixture
def pedido_controller(mock_main_dependencies):
    with patch('app.controllers.storage_controller.StorageController') as MockStorageController:
        controller = PedidoController()
        for key, mock_instance in mock_main_dependencies.items():
            setattr(controller, key, mock_instance)
        controller.despacho = mock_main_dependencies['despacho_model']
        controller.storage_controller = MockStorageController.return_value
        yield controller

# --- Test Cases ---

def test_crear_pedido_con_stock_suficiente(app, pedido_controller, mock_main_dependencies, mock_current_user):
    with app.test_request_context():
        form_data = {'id_cliente': 1, 'items': [{'producto_id': 100, 'cantidad': 10}], 'fecha_solicitud': date.today().isoformat()}
        mock_main_dependencies['lote_controller'].obtener_stock_disponible_real_para_productos.return_value = ({'success': True, 'data': {100: 20}}, 200)
        mock_main_dependencies['pedido_model'].create_with_items.return_value = {'success': True, 'data': {'id': 1, 'items': []}}
        mock_main_dependencies['lote_controller'].reservar_stock_para_pedido.return_value = {'success': True}
        
        response, status_code = pedido_controller.crear_pedido_con_items(form_data, 1)
        
        assert status_code == 201
        assert response['success']

@patch('app.controllers.orden_produccion_controller.OrdenProduccionController')
def test_crear_pedido_sin_stock_inicia_produccion(MockOPController, app, pedido_controller, mock_main_dependencies, mock_current_user):
    with app.test_request_context():
        mock_op_instance = MockOPController.return_value
        mock_op_instance.crear_orden.return_value = {'success': True, 'data': [{'id': 99}]}
        
        form_data = {'id_cliente': 1, 'items': [{'producto_id': 100, 'cantidad': 30}], 'fecha_solicitud': date.today().isoformat()}
        mock_main_dependencies['lote_controller'].obtener_stock_disponible_real_para_productos.return_value = ({'success': True, 'data': {100: 0}}, 200)
        mock_main_dependencies['pedido_model'].create_with_items.return_value = {'success': True, 'data': {'id': 1, 'items': [{'id': 1, 'producto_id': 100, 'cantidad': 30, 'estado': 'PENDIENTE_PRODUCCION'}]}}
        mock_main_dependencies['pedido_model'].find_by_id.return_value = {'success': True, 'data': {'estado': 'PENDIENTE'}}
        mock_main_dependencies['receta_model'].find_all.return_value = {'success': True, 'data': [{'id': 1}]}
        
        response, status_code = pedido_controller.crear_pedido_con_items(form_data, 1)
        
        assert status_code == 201
        assert response['success']
        mock_op_instance.crear_orden.assert_called_once()


def test_cancelar_pedido_libera_stock(app, pedido_controller, mock_main_dependencies, mock_current_user):
    with app.test_request_context():
        pedido_id = 1
        mock_main_dependencies['pedido_model'].find_by_id.return_value = {'success': True, 'data': {'estado': 'LISTO_PARA_ENTREGA', 'codigo_ov': 'OV-123'}}
        mock_main_dependencies['lote_controller'].liberar_stock_por_cancelacion_de_pedido.return_value = {'success': True}
        mock_main_dependencies['pedido_model'].cambiar_estado.return_value = {'success': True}
        
        response, status_code = pedido_controller.cancelar_pedido(pedido_id)
        
        assert status_code == 200
        assert response['success']


def test_despachar_pedido(app, pedido_controller, mock_main_dependencies, mock_current_user):
    with app.test_request_context():
        pedido_id = 1
        form_data = {'conductor_nombre': 'Juan Perez', 'conductor_dni': '12345678', 'vehiculo_patente': 'AB123CD', 'conductor_telefono': '1122334455'}
        mock_main_dependencies['pedido_model'].get_one_with_items_and_op_status.return_value = {'success': True, 'data': {'estado': 'LISTO_PARA_ENTREGA', 'id_pedido': 1, 'codigo_ov': 'OV-123'}}
        mock_main_dependencies['lote_controller'].despachar_stock_reservado_por_pedido.return_value = {'success': True}
        mock_main_dependencies['pedido_model'].cambiar_estado.return_value = {'success': True}
        mock_main_dependencies['despacho_model'].create.return_value = {'success': True}

        response, status_code = pedido_controller.despachar_pedido(pedido_id, form_data)
        
        assert status_code == 200
        assert response['success']

def test_registrar_pago_con_comprobante(app, pedido_controller, mock_main_dependencies, mock_current_user):
    with app.test_request_context():
        pedido_id = 1
        pago_data = {'monto': 1000, 'metodo_pago': 'transferencia'}
        mock_file = MagicMock()
        
        pedido_controller.storage_controller.upload_file.return_value = {'success': True, 'url': 'http://example.com/comprobante.jpg'}
        mock_main_dependencies['pedido_model'].find_by_id.return_value = {'success': True, 'data': {'id': 1, 'codigo_ov': 'OV-123'}}
        mock_main_dependencies['pedido_model'].registrar_pago.return_value = {'success': True}

        response, status_code = pedido_controller.registrar_pago(pedido_id, pago_data, mock_file)
        
        assert status_code == 200
        assert response['success']
        mock_main_dependencies['pedido_model'].registrar_pago.assert_called_with(pedido_id, {'monto': 1000, 'metodo_pago': 'transferencia', 'url_comprobante': 'http://example.com/comprobante.jpg'})
