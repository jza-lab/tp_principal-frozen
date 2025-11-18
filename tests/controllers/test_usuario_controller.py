import pytest
from unittest.mock import MagicMock, patch, ANY
from app.controllers.producto_controller import ProductoController
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
    user = SimpleNamespace(id=1, nombre='Admin', apellido='User', roles=['JEFE_DE_PRODUCCION'])
    with patch('app.controllers.producto_controller.get_current_user', return_value=user):
        yield user

@pytest.fixture
def mock_dependencies():
    with patch('app.controllers.producto_controller.ProductoModel') as MockProductoModel, \
         patch('app.controllers.producto_controller.RecetaController') as MockRecetaController, \
         patch('app.controllers.producto_controller.RecetaModel') as MockRecetaModel, \
         patch('app.controllers.producto_controller.OperacionRecetaModel') as MockOperacionModel, \
         patch('app.controllers.producto_controller.RegistroController') as MockRegistroController:
        
        mocks = {
            "producto_model": MockProductoModel.return_value, "receta_controller": MockRecetaController.return_value,
            "receta_model": MockRecetaModel.return_value, "operacion_receta_model": MockOperacionModel.return_value,
            "registro_controller": MockRegistroController.return_value,
        }
        yield mocks

@pytest.fixture
def producto_controller(mock_dependencies):
    controller = ProductoController()
    controller.model = mock_dependencies['producto_model']
    controller.receta_controller = mock_dependencies['receta_controller']
    controller.receta_model = mock_dependencies['receta_model']
    controller.operacion_receta_model = mock_dependencies['operacion_receta_model']
    controller.registro_controller = mock_dependencies['registro_controller']
    return controller

# --- Test Cases ---

def test_crear_producto_con_receta_y_pasos(app, producto_controller, mock_dependencies, mock_current_user):
    with app.test_request_context():
        form_data = {
            'nombre': 'Pastel de Manzana', 'unidad_medida': 'un', 'categoria': 'Pasteleria',
            'precio_unitario': 25.5, 'iva': True,
            'receta_items': [{'insumo_id': 1, 'cantidad': 100}],
            'pasos_receta': [{'secuencia': 1, 'nombre_operacion': 'Mezclar'}],
        }
        
        mock_dependencies['producto_model'].create.return_value = {'success': True, 'data': {'id': 99, 'nombre': 'Pastel de Manzana'}}
        mock_dependencies['receta_model'].create.return_value = {'success': True, 'data': {'id': 199}}
        mock_dependencies['receta_controller'].gestionar_ingredientes_para_receta.return_value = {'success': True}
        
        mock_insert_result = MagicMock()
        mock_insert_result.data = [{'id': 1}]
        mock_dependencies['operacion_receta_model'].db.table.return_value.insert.return_value.execute.return_value = mock_insert_result

        response, status_code = producto_controller.crear_producto(form_data)
        
        assert status_code == 201
        assert response['success']


def test_crear_producto_con_generacion_automatica_de_codigo(app, producto_controller, mock_dependencies, mock_current_user):
    with app.test_request_context():
        form_data = {
            'nombre': 'Bizcocho', 'unidad_medida': 'un', 'categoria': 'Panaderia',
            'precio_unitario': 15.0, 'iva': False
        }
        
        mock_dependencies['producto_model'].find_last_by_base_codigo.return_value = {'success': False}
        mock_dependencies['producto_model'].create.return_value = {'success': True, 'data': {'id': 1, 'nombre': 'Bizcocho'}}
        mock_dependencies['receta_model'].create.return_value = {'success': True, 'data': {'id': 1}}

        producto_controller.crear_producto(form_data)
        
        create_call_args = mock_dependencies['producto_model'].create.call_args[0][0]
        assert 'codigo' in create_call_args
        assert create_call_args['codigo'] == 'PROD-BIZC-0001'

def test_eliminar_y_habilitar_producto(app, producto_controller, mock_dependencies, mock_current_user):
    with app.test_request_context():
        producto_id = 1
        producto_data = {'id': producto_id, 'nombre': 'Producto Test'}
        
        mock_dependencies['producto_model'].update.return_value = {'success': True, 'data': producto_data}

        response_del, _ = producto_controller.eliminar_producto_logico(producto_id)
        assert response_del['success']
        
        response_hab, _ = producto_controller.habilitar_producto(producto_id)
        assert response_hab['success']
        
        assert mock_dependencies['registro_controller'].crear_registro.call_count == 2
