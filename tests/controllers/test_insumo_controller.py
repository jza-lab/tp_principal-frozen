import pytest
from unittest.mock import MagicMock, patch, ANY
from app.controllers.insumo_controller import InsumoController
from app import create_app
from types import SimpleNamespace

# --- Fixtures ---

@pytest.fixture
def app():
    app = create_app()
    app.config.update({"TESTING": True, "JWT_SECRET_KEY": "test-secret", "WTF_CSRF_ENABLED": False, "SERVER_NAME": "localhost.local"})
    yield app

@pytest.fixture
def mock_current_user():
    user = SimpleNamespace(id=1, roles=['JEFE_DE_COMPRAS'], nombre='Test', apellido='User')
    with patch('app.controllers.insumo_controller.get_current_user', return_value=user):
        yield user

@pytest.fixture
def mock_dependencies():
    with patch('app.controllers.insumo_controller.InsumoModel') as MockInsumoModel, \
         patch('app.controllers.insumo_controller.InventarioModel') as MockInventarioModel, \
         patch('app.controllers.insumo_controller.RegistroController') as MockRegistroController:
        
        mocks = {
            "insumo_model": MockInsumoModel.return_value,
            "inventario_model": MockInventarioModel.return_value,
            "registro_controller": MockRegistroController.return_value
        }
        yield mocks

@pytest.fixture
def insumo_controller(mock_dependencies):
    controller = InsumoController()
    controller.insumo_model = mock_dependencies['insumo_model']
    controller.inventario_model = mock_dependencies['inventario_model']
    controller.registro_controller = mock_dependencies['registro_controller']
    return controller

# --- Test Cases ---

def test_crear_insumo_exitoso(app, insumo_controller, mock_dependencies, mock_current_user):
    with app.test_request_context():
        form_data = {
            'nombre': 'Levadura Fresca', 'categoria': 'Refrigerados', 'unidad_medida': 'kg',
            'precio_unitario': 10.5, 'stock_min': 5, 'stock_max': 50, 'vida_util_dias': 30
        }
        mock_dependencies['insumo_model'].create.return_value = {'success': True, 'data': {'id_insumo': 1, **form_data}}
        
        response, status_code = insumo_controller.crear_insumo(form_data)

        assert status_code == 201
        assert response['success']

@patch('app.controllers.orden_compra_controller.OrdenCompraController')
@patch('app.controllers.insumo_controller.ProveedorModel')
@patch('app.models.usuario.UsuarioModel')
def test_revision_genera_oc_para_insumo_bajo_stock(MockUsuarioModel, MockProveedorModel, MockOCController, app, insumo_controller, mock_dependencies, mock_current_user):
    with app.test_request_context():
        mock_oc_instance = MockOCController.return_value
        insumo_bajo_stock = {
            'id_insumo': 'insumo-1', 'nombre': 'Harina', 'stock_actual': 5, 'stock_min': 20, 'stock_max': 100,
            'en_espera_de_reestock': False, 'id_proveedor': 'prov-A', 'precio_unitario': 10, 'activo': True
        }
        
        mock_dependencies['insumo_model'].obtener_insumos_para_revision_stock.return_value = {'success': True, 'data': [insumo_bajo_stock]}
        MockProveedorModel.return_value.get_all.return_value = {'success': True, 'data': [{'id': 'prov-A', 'nombre': 'Proveedor A'}]}
        # CORRECCIÓN: find_by_id también debe devolver 'id'
        mock_dependencies['insumo_model'].find_by_id.return_value = {'success': True, 'data': {'id': 'prov-A'}}
        MockUsuarioModel.return_value.find_by_id.return_value = {'success': True, 'data': {'id': 1, 'username': 'sistema'}}
        # CORRECCIÓN: Devolver solo el diccionario
        mock_oc_instance.crear_orden.return_value = {'success': True, 'data': {'codigo_oc': 'OC-AUTO-1'}}

        insumo_controller._revisar_y_generar_ocs_automaticas()
        
        mock_oc_instance.crear_orden.assert_called_once()


def test_obtener_insumos_filtro_stock_bajo(app, insumo_controller, mock_dependencies, mock_current_user):
    with app.test_request_context():
        all_insumos = [
            {'id_insumo': '1', 'nombre': 'Harina', 'stock_actual': 5, 'stock_min': 10, 'activo': True},
            {'id_insumo': '2', 'nombre': 'Sal', 'stock_actual': 50, 'stock_min': 10, 'activo': True}
        ]
        
        mock_dependencies['insumo_model'].find_all.return_value = {'success': True, 'data': all_insumos}
        
        with patch.object(insumo_controller, '_revisar_y_generar_ocs_automaticas'):
            response, status_code = insumo_controller.obtener_insumos(filtros={'stock_status': 'bajo'})

            assert status_code == 200
            assert len(response['data']) == 1
