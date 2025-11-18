import pytest
from unittest.mock import MagicMock, patch, ANY
from app.controllers.orden_compra_controller import OrdenCompraController
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
    user = SimpleNamespace(id=1, roles=['COMPRAS'], nombre="Test", apellido="User")
    with patch('app.controllers.orden_compra_controller.get_current_user', return_value=user):
        yield user

@pytest.fixture
def mock_dependencies():
    with patch('app.controllers.orden_compra_controller.OrdenCompraModel') as MockOCModel, \
         patch('app.controllers.orden_compra_controller.InventarioController') as MockInventarioController, \
         patch('app.controllers.insumo_controller.InsumoController') as MockInsumoController, \
         patch('app.controllers.orden_compra_controller.UsuarioController') as MockUsuarioController, \
         patch('app.controllers.orden_compra_controller.RegistroController') as MockRegistroController, \
         patch('app.controllers.orden_compra_controller.ReclamoProveedorController') as MockReclamoController:
        
        MockOCModel.return_value.item_model = MagicMock()
        mocks = {
            "oc_model": MockOCModel.return_value, "inventario_controller": MockInventarioController.return_value,
            "insumo_controller": MockInsumoController.return_value, "usuario_controller": MockUsuarioController.return_value,
            "registro_controller": MockRegistroController.return_value, "reclamo_controller": MockReclamoController.return_value,
        }
        yield mocks

@pytest.fixture
def oc_controller(mock_dependencies):
    controller = OrdenCompraController()
    controller.model = mock_dependencies['oc_model']
    controller.inventario_controller = mock_dependencies['inventario_controller']
    controller.insumo_controller = mock_dependencies['insumo_controller']
    controller.usuario_controller = mock_dependencies['usuario_controller']
    controller.registro_controller = mock_dependencies['registro_controller']
    controller.reclamo_proveedor_controller = mock_dependencies['reclamo_controller']
    return controller

# --- Test Cases ---

def test_crear_orden_compra_exitoso(app, oc_controller, mock_current_user, mock_dependencies):
    with app.test_request_context():
        orden_data = {'proveedor_id': 1, 'fecha_emision': date.today().isoformat()}
        items_data = [{'insumo_id': 1, 'cantidad_solicitada': 10, 'precio_unitario': 5}]
        usuario_id = 1
        mock_dependencies['oc_model'].create_with_items.return_value = {'success': True, 'data': {'id': 1, 'codigo_oc': 'OC-TEST'}}
        
        response = oc_controller.crear_orden(orden_data, items_data, usuario_id)
        
        assert response['success']

def test_cancelar_orden_compra_pendiente(app, oc_controller, mock_current_user, mock_dependencies):
    with app.test_request_context(json={'motivo': 'Test'}):
        orden_id = 1
        # CORRECCIÓN: Devolver solo el diccionario
        mock_dependencies['oc_model'].find_by_id.return_value = {'success': True, 'data': {'id': orden_id, 'estado': 'PENDIENTE', 'codigo_oc': 'OC-TEST'}}
        mock_dependencies['oc_model'].update.return_value = {'success': True}
        
        response, status_code = oc_controller.cancelar_orden(orden_id)
        
        assert status_code == 200
        assert response['success']

@patch('app.models.control_calidad_insumo.ControlCalidadInsumoModel')
def test_procesar_recepcion_paso2_exitoso(MockCCModel, app, oc_controller, mock_dependencies, mock_current_user):
    with app.test_request_context():
        orden_id, usuario_id = 1, 1
        orden_data = {'id': orden_id, 'codigo_oc': 'OC-123', 'estado': 'EN_RECEPCION', 'paso_recepcion': 1, 'orden_produccion_id': 10}
        form_data = {
            'paso': '2', 'item_id[]': ['101'], 'cantidad_aprobada[]': ['100'], 'cantidad_cuarentena[]': ['0'], 
            'cantidad_rechazada[]': ['0'], 'resultado_inspeccion[]': ['Aprobado'], 'comentarios[]': ['Todo OK']
        }
        mock_op_controller = MagicMock()
        
        # CORRECCIÓN: Devolver solo el diccionario
        mock_dependencies['oc_model'].get_one_with_details.return_value = {'success': True, 'data': orden_data}
        mock_dependencies['inventario_controller'].crear_lote.return_value = ({'success': True, 'data': {'id_lote': 201}}, 201)
        mock_dependencies['oc_model'].update.return_value = {'success': True}
        MockCCModel.return_value.create.return_value = {'success': True}

        response, status_code = oc_controller.procesar_recepcion(orden_id, form_data, None, usuario_id, mock_op_controller)

        assert status_code == 200
        assert response['success']
