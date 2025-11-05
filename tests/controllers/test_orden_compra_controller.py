import pytest
from unittest.mock import MagicMock, patch, ANY
from app.controllers.orden_compra_controller import OrdenCompraController
from datetime import date
from app import create_app
from flask import Flask

# Clase para simular el objeto request.form de Flask
class MockFormData:
    def __init__(self, data):
        self._data = data
    def get(self, key, default=None):
        return self._data.get(key, default)
    def getlist(self, key):
        return self._data.get(key, [])

@pytest.fixture
def app():
    app = create_app()
    app.config.update({"TESTING": True, "JWT_SECRET_KEY": "test-secret", "WTF_CSRF_ENABLED": False})
    yield app

@pytest.fixture
def mock_oc_dependencies():
    with patch('app.controllers.orden_compra_controller.OrdenCompraModel') as MockOCModel, \
         patch('app.controllers.orden_compra_controller.InventarioController') as MockInventarioController, \
         patch('app.controllers.orden_compra_controller.InsumoController') as MockInsumoController, \
         patch('app.controllers.orden_compra_controller.UsuarioController') as MockUsuarioController:
        MockOCModel.return_value.item_model = MagicMock()
        yield {
            "oc_model": MockOCModel.return_value,
            "inventario_controller": MockInventarioController.return_value,
            "insumo_controller": MockInsumoController.return_value,
            "usuario_controller": MockUsuarioController.return_value,
        }

@pytest.fixture
def oc_controller(mock_oc_dependencies):
    controller = OrdenCompraController()
    controller.model = mock_oc_dependencies['oc_model']
    controller.inventario_controller = mock_oc_dependencies['inventario_controller']
    controller.insumo_controller = mock_oc_dependencies['insumo_controller']
    controller.usuario_controller = mock_oc_dependencies['usuario_controller']
    return controller

class TestOrdenCompraController:
    def test_crear_orden_compra_exitoso(self, oc_controller):
        orden_data = {'proveedor_id': 1, 'fecha_emision': date.today().isoformat()}
        items_data = [{'insumo_id': 1, 'cantidad_solicitada': 10, 'precio_unitario': 5}]
        usuario_id = 1
        oc_controller.model.create_with_items.return_value = {'success': True, 'data': {'id': 1}}
        response = oc_controller.crear_orden(orden_data, items_data, usuario_id)
        assert response['success']

    def test_aprobar_orden_compra(self, oc_controller):
        orden_id = 1
        usuario_id = 1
        oc_controller.model.update.return_value = {'success': True}
        response = oc_controller.aprobar_orden(orden_id, usuario_id)
        assert response['success']

    def test_cancelar_orden_compra_pendiente(self, app: Flask, oc_controller):
        orden_id = 1
        with app.test_request_context(json={'motivo': 'Test cancellation'}):
            oc_controller.model.find_by_id.return_value = {'success': True, 'data': {'id': orden_id, 'estado': 'PENDIENTE'}}
            oc_controller.model.update.return_value = {'success': True, 'data': {}}
            response = oc_controller.cancelar_orden(orden_id)
            assert response.status_code == 200
            json_data = response.get_json()
            assert json_data['success']

    def test_cancelar_orden_completada_falla(self, app: Flask, oc_controller):
        orden_id = 1
        with app.test_request_context(json={'motivo': 'Test cancellation'}):
            oc_controller.model.find_by_id.return_value = {'success': True, 'data': {'id': orden_id, 'estado': 'COMPLETADA'}}
            response, status_code = oc_controller.cancelar_orden(orden_id)
            assert status_code == 400
            assert not response.get_json()['success']

    def test_recepcionar_orden_completa(self, oc_controller, mock_oc_dependencies):
        orden_id = 1
        usuario_id = 1
        orden_data = {'id': orden_id, 'codigo_oc': 'OC-TEST-1', 'items': [{'id': 10, 'insumo_id': 100, 'cantidad_solicitada': 50.0}]}
        form_data = MockFormData({'accion': 'aceptar', 'observaciones': 'Todo OK', 'item_id[]': ['10'], 'cantidad_recibida[]': ['50.0']})
        mock_oc_dependencies['oc_model'].get_one_with_details.return_value = {'success': True, 'data': orden_data}
        mock_oc_dependencies['usuario_controller'].obtener_usuario_por_id.return_value = {'roles': {'codigo': 'DEPOSITO'}}
        mock_oc_dependencies['inventario_controller'].crear_lote.return_value = ({'success': True}, 201)
        response = oc_controller.procesar_recepcion(orden_id, form_data, usuario_id, MagicMock())
        assert response['success']

    def test_recepcionar_orden_incompleta_crea_oc_complementaria(self, oc_controller, mock_oc_dependencies):
        orden_id = 1
        usuario_id = 1
        orden_data = {'id': orden_id, 'codigo_oc': 'OC-TEST-1', 'items': [{'id': 10, 'insumo_id': 100, 'cantidad_solicitada': 50.0, 'precio_unitario': 10.0}]}
        form_data = MockFormData({'accion': 'aceptar', 'observaciones': 'Faltaron insumos', 'item_id[]': ['10'], 'cantidad_recibida[]': ['30.0']})
        mock_oc_dependencies['oc_model'].get_one_with_details.return_value = {'success': True, 'data': orden_data}
        mock_oc_dependencies['usuario_controller'].obtener_usuario_por_id.return_value = {'roles': {'codigo': 'DEPOSITO'}}
        with patch.object(oc_controller, '_crear_orden_complementaria', return_value={'success': True, 'data': {'codigo_oc': 'OC-COMP-2'}}):
            response = oc_controller.procesar_recepcion(orden_id, form_data, usuario_id, MagicMock())
            assert response['success']

    def test_iniciar_control_de_calidad(self, oc_controller, mock_oc_dependencies):
        orden_id = 1
        usuario_id = 1
        orden_data = {'id': orden_id, 'estado': 'RECEPCION_COMPLETA'}
        # CORRECCIÓN: Simular el retorno correcto de get_orden (tupla)
        with patch.object(oc_controller, 'get_orden', return_value=({'success': True, 'data': orden_data}, 200)):
            with patch.object(oc_controller, '_marcar_cadena_como_en_control_calidad') as mock_marcar_calidad:
                response = oc_controller.iniciar_control_de_calidad(orden_id, usuario_id)
                assert response['success']
                mock_marcar_calidad.assert_called_once()
                
    def test_marcar_como_cerrada(self, oc_controller, mock_oc_dependencies):
        orden_id = 1
        orden_data = {'id': orden_id, 'estado': 'EN_CONTROL_CALIDAD'}
        mock_oc_dependencies['oc_model'].find_by_id.return_value = {'success': True, 'data': orden_data}
        with patch.object(oc_controller, '_reiniciar_bandera_stock_recibido'):
            response = oc_controller.marcar_como_cerrada(orden_id)
            assert response['success']

