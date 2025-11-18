import pytest
from unittest.mock import MagicMock, patch
from app.controllers.inventario_controller import InventarioController
from app import create_app
import uuid
from decimal import Decimal

# --- Fixtures ---

@pytest.fixture
def app():
    app = create_app()
    app.config.update({"TESTING": True, "JWT_SECRET_KEY": "test-secret", "WTF_CSRF_ENABLED": False})
    yield app

@pytest.fixture
def mock_inventario_dependencies():
    with patch('app.controllers.inventario_controller.InventarioModel') as MockInventarioModel, \
         patch('app.controllers.inventario_controller.InsumoModel') as MockInsumoModel, \
         patch('app.controllers.inventario_controller.RecetaModel') as MockRecetaModel, \
         patch('app.controllers.inventario_controller.ReservaInsumoModel') as MockReservaInsumoModel:
        yield {
            "inventario_model": MockInventarioModel.return_value,
            "insumo_model": MockInsumoModel.return_value,
            "receta_model": MockRecetaModel.return_value,
            "reserva_insumo_model": MockReservaInsumoModel.return_value,
        }

@pytest.fixture
def inventario_controller(mock_inventario_dependencies):
    with patch('app.controllers.inventario_controller.InsumoController') as MockInsumoController:
        controller = InventarioController()
        controller.inventario_model = mock_inventario_dependencies['inventario_model']
        controller.insumo_model = mock_inventario_dependencies['insumo_model']
        controller.receta_model = mock_inventario_dependencies['receta_model']
        controller.reserva_insumo_model = mock_inventario_dependencies['reserva_insumo_model']
        controller.insumo_controller = MockInsumoController.return_value
        yield controller

# --- Test Cases ---

def test_verificar_stock_para_op_suficiente(app, inventario_controller, mock_inventario_dependencies):
    with app.app_context():
        orden_produccion = {'receta_id': 1, 'cantidad_planificada': 10}
        ingredientes = [{'id_insumo': 1, 'cantidad': 5}]
        mock_inventario_dependencies['receta_model'].get_ingredientes.return_value = {'success': True, 'data': ingredientes}
        lotes_disponibles = [{'id_lote': 'lote-1', 'cantidad_actual': 100, 'disponibilidad': 100}]
        mock_inventario_dependencies['inventario_model'].find_all.return_value = {'success': True, 'data': lotes_disponibles}
        
        result = inventario_controller.verificar_stock_para_op(orden_produccion)
        
        assert result['success']
        assert len(result['data']['insumos_faltantes']) == 0

def test_verificar_stock_para_op_insuficiente(app, inventario_controller, mock_inventario_dependencies):
    with app.app_context():
        orden_produccion = {'receta_id': 1, 'cantidad_planificada': 10}
        ingredientes = [{'id_insumo': 1, 'cantidad': 5, 'nombre_insumo': 'Harina'}]
        mock_inventario_dependencies['receta_model'].get_ingredientes.return_value = {'success': True, 'data': ingredientes}
        lotes_disponibles = [{'id_lote': 'lote-1', 'cantidad_actual': 30, 'disponibilidad': 30}]
        mock_inventario_dependencies['inventario_model'].find_all.return_value = {'success': True, 'data': lotes_disponibles}
        
        result = inventario_controller.verificar_stock_para_op(orden_produccion)
        
        assert result['success']
        assert len(result['data']['insumos_faltantes']) == 1
        faltante = result['data']['insumos_faltantes'][0]
        assert faltante['cantidad_faltante'] == 20.0

def test_reservar_stock_insumos_para_op_exitoso(app, inventario_controller, mock_inventario_dependencies):
    with app.app_context():
        op = {'id': 1, 'receta_id': 1, 'cantidad_planificada': 10}
        usuario_id = 1
        ingredientes = [{'id_insumo': 'insumo-1', 'cantidad': 5}]
        
        mock_inventario_dependencies['receta_model'].get_ingredientes.return_value = {'success': True, 'data': ingredientes}
        lotes_disponibles = [{'id_lote': 'lote-1', 'cantidad_actual': 100, 'disponibilidad': 100}]
        mock_inventario_dependencies['inventario_model'].find_all.return_value = {'success': True, 'data': lotes_disponibles}
        mock_inventario_dependencies['reserva_insumo_model'].create.return_value = {'success': True}

        result = inventario_controller.reservar_stock_insumos_para_op(op, usuario_id)

        assert result['success']
        mock_inventario_dependencies['reserva_insumo_model'].create.assert_called_once()
        reserva_args = mock_inventario_dependencies['reserva_insumo_model'].create.call_args[0][0]
        assert reserva_args['lote_inventario_id'] == 'lote-1'

def test_crear_lote_insumo(app, inventario_controller, mock_inventario_dependencies):
    with app.app_context():
        usuario_id = 1
        id_insumo_valido = str(uuid.uuid4())
        form_data = {'id_insumo': id_insumo_valido, 'cantidad_inicial': '100', 'estado': 'EN REVISION'}
        
        mock_inventario_dependencies['insumo_model'].find_by_id.return_value = {'success': True, 'data': {'codigo_interno': 'INS-TEST'}}
        lote_creado_mock = {'id_lote': 1, **form_data}
        lote_creado_con_uuid = {'id_insumo': uuid.UUID(id_insumo_valido), 'cantidad_inicial': Decimal('100'), 'estado': 'EN REVISION'}
        # CORRECCIÓN: Devolver solo el diccionario
        mock_inventario_dependencies['inventario_model'].create.return_value = {'success': True, 'data': lote_creado_mock}
        
        with patch.object(inventario_controller.schema, 'load', return_value=lote_creado_con_uuid):
            response, status_code = inventario_controller.crear_lote(form_data, usuario_id)

            assert status_code == 201
            assert response['success']
