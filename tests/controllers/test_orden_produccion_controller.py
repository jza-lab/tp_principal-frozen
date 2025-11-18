import pytest
from unittest.mock import MagicMock, patch, ANY
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app import create_app
from types import SimpleNamespace
from datetime import date
from flask_jwt_extended import create_access_token

# --- Fixtures ---

@pytest.fixture
def app():
    app = create_app()
    app.config.update({"TESTING": True, "JWT_SECRET_KEY": "test-secret", "WTF_CSRF_ENABLED": False, "SERVER_NAME": "localhost.local"})
    yield app

@pytest.fixture
def mock_current_user():
    user = SimpleNamespace(id=1, roles=['SUPERVISOR'], nombre='Test', apellido='User')
    with patch('flask_jwt_extended.get_current_user', return_value=user):
        yield user

@pytest.fixture
def mock_dependencies():
    with patch('app.controllers.orden_produccion_controller.OrdenProduccionModel') as MockOPModel, \
         patch('app.controllers.orden_produccion_controller.InventarioController') as MockInventarioController, \
         patch('app.controllers.orden_produccion_controller.OrdenCompraController') as MockOCController, \
         patch('app.controllers.orden_produccion_controller.LoteProductoController') as MockLoteController, \
         patch('app.controllers.orden_produccion_controller.PedidoModel') as MockPedidoModel, \
         patch('app.controllers.orden_produccion_controller.RecetaModel') as MockRecetaModel, \
         patch('app.controllers.orden_produccion_controller.RegistroController') as MockRegistroController, \
         patch('app.controllers.orden_produccion_controller.OpCronometroController') as MockCronometroController:
        
        mocks = {
            "op_model": MockOPModel.return_value, "inventario_controller": MockInventarioController.return_value,
            "oc_controller": MockOCController.return_value, "lote_controller": MockLoteController.return_value,
            "pedido_model": MockPedidoModel.return_value, "receta_model": MockRecetaModel.return_value,
            "registro_controller": MockRegistroController.return_value, "cronometro_controller": MockCronometroController.return_value
        }
        yield mocks

@pytest.fixture
def op_controller(mock_dependencies):
    controller = OrdenProduccionController()
    controller.model = mock_dependencies['op_model']
    controller.inventario_controller = mock_dependencies['inventario_controller']
    controller.orden_compra_controller = mock_dependencies['oc_controller']
    controller.lote_producto_controller = mock_dependencies['lote_controller']
    controller.pedido_model = mock_dependencies['pedido_model']
    controller.receta_model = mock_dependencies['receta_model']
    controller.registro_controller = mock_dependencies['registro_controller']
    controller.op_cronometro_controller = mock_dependencies['cronometro_controller']
    return controller

# --- Test Cases ---

def test_crear_orden_exitosa(app, op_controller, mock_dependencies, mock_current_user):
    with app.test_request_context():
        form_data = {'productos': [{'id': 10, 'cantidad': 50}], 'fecha_meta': date.today().isoformat()}
        usuario_id = 1
        with patch('app.controllers.orden_produccion_controller.RecetaModel') as MockReceta:
            MockReceta.return_value.find_all.return_value = {'success': True, 'data': [{'id': 1}]}
            mock_dependencies['op_model'].create.return_value = {'success': True, 'data': {'id': 99, 'codigo': 'OP-TEST'}}
            
            response = op_controller.crear_orden(form_data, usuario_id)

            assert response['success']

def test_aprobar_orden_con_stock_suficiente(app, op_controller, mock_dependencies, mock_current_user):
    with app.app_context():
        # CORRECCIÓN: Crear un token y usar test_request_context para simular un request autenticado
        access_token = create_access_token(identity=mock_current_user.id, additional_claims={'roles': mock_current_user.roles})
        headers = {'Authorization': f'Bearer {access_token}'}
        
        with app.test_request_context(headers=headers):
            orden_id, usuario_id = 1, 1
            orden_data = {'id': orden_id, 'estado': 'PENDIENTE', 'codigo': 'OP-TEST', 'receta_id': 1}
            
            mock_dependencies['op_model'].get_one_enriched.return_value = {'success': True, 'data': orden_data}
            mock_dependencies['oc_controller'].get_all_ordenes.return_value = ({'success': True, 'data': []}, 200)

            stock_suficiente = {'success': True, 'data': {'insumos_faltantes': []}}
            mock_dependencies['inventario_controller'].verificar_stock_para_op.return_value = stock_suficiente
            
            mock_dependencies['op_model'].cambiar_estado.return_value = {'success': True}
            
            response, status_code = op_controller.aprobar_orden(orden_id, usuario_id)
            
            assert status_code == 200
            assert response['success']


def test_pausar_y_reanudar_produccion(app, op_controller, mock_dependencies, mock_current_user):
    with app.app_context():
        access_token = create_access_token(identity=mock_current_user.id, additional_claims={'roles': mock_current_user.roles})
        headers = {'Authorization': f'Bearer {access_token}'}
        
        with app.test_request_context(headers=headers):
            orden_id, usuario_id, motivo_id = 1, 1, 1
            
            orden_en_proceso = {'id': orden_id, 'estado': 'EN_PROCESO', 'codigo': 'OP-TEST'}
            mock_dependencies['op_model'].get_one_enriched.return_value = {'success': True, 'data': orden_en_proceso}
            mock_dependencies['oc_controller'].get_all_ordenes.return_value = ({'success': True, 'data': []}, 200)
            
            with patch('app.controllers.orden_produccion_controller.MotivoParoModel') as MockMotivo, \
                 patch('app.controllers.orden_produccion_controller.RegistroParoModel'):
                MockMotivo.return_value.find_by_id.return_value = {'success': True, 'data': {'descripcion': 'Mantenimiento'}}
                
                op_controller.pausar_produccion(orden_id, motivo_id, usuario_id)
                
                mock_dependencies['op_model'].cambiar_estado.assert_called_with(orden_id, 'PAUSADA')

            orden_pausada = {'id': orden_id, 'estado': 'PAUSADA', 'codigo': 'OP-TEST'}
            mock_dependencies['op_model'].get_one_enriched.return_value = {'success': True, 'data': orden_pausada}
            with patch('app.controllers.orden_produccion_controller.RegistroParoModel') as MockRegistroParo:
                MockRegistroParo.return_value.find_all.return_value = {'success': True, 'data': [{'id': 1}]}
                
                op_controller.reanudar_produccion(orden_id, usuario_id)
                
                mock_dependencies['op_model'].cambiar_estado.assert_called_with(orden_id, 'EN_PROCESO')
