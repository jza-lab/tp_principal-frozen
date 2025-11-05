import pytest
from unittest.mock import MagicMock, patch
from app.controllers.lote_producto_controller import LoteProductoController
from app import create_app
from datetime import date

@pytest.fixture
def app():
    app = create_app()
    app.config.update({"TESTING": True, "JWT_SECRET_KEY": "test-secret", "WTF_CSRF_ENABLED": False})
    yield app

@pytest.fixture
def mock_lote_dependencies():
    with patch('app.controllers.lote_producto_controller.LoteProductoModel') as MockLoteModel, \
         patch('app.controllers.lote_producto_controller.ProductoModel') as MockProductoModel, \
         patch('app.controllers.lote_producto_controller.ReservaProductoModel') as MockReservaModel:
        yield {
            "lote_model": MockLoteModel.return_value,
            "producto_model": MockProductoModel.return_value,
            "reserva_model": MockReservaModel.return_value,
        }

@pytest.fixture
def lote_controller(mock_lote_dependencies):
    controller = LoteProductoController()
    controller.model = mock_lote_dependencies['lote_model']
    controller.producto_model = mock_lote_dependencies['producto_model']
    controller.reserva_model = mock_lote_dependencies['reserva_model']
    return controller

class TestLoteProductoController:

    def test_crear_lote_exitoso(self, lote_controller, mock_lote_dependencies):
        # CORRECCIÓN: Añadir todos los campos requeridos por el schema, como fecha_produccion
        form_data = {
            'producto_id': 1,
            'numero_lote': 'LOTE-001',
            'cantidad_inicial': 100,
            'fecha_produccion': date.today().isoformat()
        }
        mock_lote_dependencies['producto_model'].find_by_id.return_value = {'success': True, 'data': {'id': 1}}
        mock_lote_dependencies['lote_model'].find_by_numero_lote.return_value = {'success': False}
        lote_creado_mock = {'id_lote': 1, **form_data}
        mock_lote_dependencies['lote_model'].create.return_value = {'success': True, 'data': lote_creado_mock}
        response, status_code = lote_controller.crear_lote(form_data)
        assert status_code == 201
        assert response['success']

    def test_reservar_stock_agota_lote(self, lote_controller, mock_lote_dependencies):
        pedido_id, pedido_item_id, producto_id, usuario_id = 1, 1, 100, 1
        cantidad_a_reservar = 50.0
        lote_disponible = {'id_lote': 1, 'cantidad_actual': 50.0, 'numero_lote': 'LOTE-TEST'}
        mock_lote_dependencies['lote_model'].find_all.return_value = {'success': True, 'data': [lote_disponible]}
        mock_lote_dependencies['reserva_model'].create.return_value = {'success': True}
        result = lote_controller.reservar_stock_para_item(pedido_id, pedido_item_id, producto_id, cantidad_a_reservar, usuario_id)
        assert result['success']

    def test_liberar_stock_por_cancelacion(self, lote_controller, mock_lote_dependencies):
        pedido_id = 1
        reserva_a_cancelar = {'id': 1, 'lote_producto_id': 1, 'cantidad_reservada': 50.0}
        lote_agotado = {'id_lote': 1, 'cantidad_actual': 0.0, 'estado': 'AGOTADO', 'numero_lote': 'LOTE-TEST'}
        mock_lote_dependencies['reserva_model'].find_all.return_value = {'success': True, 'data': [reserva_a_cancelar]}
        mock_lote_dependencies['lote_model'].find_by_id.return_value = {'success': True, 'data': lote_agotado}
        mock_lote_dependencies['lote_model'].update.return_value = {'success': True}
        mock_lote_dependencies['reserva_model'].update.return_value = {'success': True}
        result = lote_controller.liberar_stock_por_cancelacion_de_pedido(pedido_id)
        assert result['success']

    def test_despachar_stock_reservado(self, lote_controller, mock_lote_dependencies):
        pedido_id = 1
        reserva_activa = {'id': 1, 'lote_producto_id': 1, 'cantidad_reservada': 30.0}
        lote_con_stock = {'id_lote': 1, 'cantidad_actual': 30.0, 'estado': 'DISPONIBLE', 'numero_lote': 'LOTE-TEST'}
        mock_lote_dependencies['reserva_model'].find_all.return_value = {'success': True, 'data': [reserva_activa]}
        mock_lote_dependencies['lote_model'].find_by_id.return_value = {'success': True, 'data': lote_con_stock}
        mock_lote_dependencies['lote_model'].update.return_value = {'success': True}
        mock_lote_dependencies['reserva_model'].update.return_value = {'success': True}
        result = lote_controller.despachar_stock_reservado_por_pedido(pedido_id)
        assert result['success']
