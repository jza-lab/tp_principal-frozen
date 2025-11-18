import pytest
from unittest.mock import MagicMock, patch
from app.controllers.planificacion_controller import PlanificacionController
from app import create_app
from types import SimpleNamespace
from datetime import date, timedelta
from decimal import Decimal

# --- Fixtures ---

@pytest.fixture
def app():
    app = create_app()
    app.config.update({"TESTING": True, "JWT_SECRET_KEY": "test-secret", "WTF_CSRF_ENABLED": False, "SERVER_NAME": "localhost.local"})
    yield app

@pytest.fixture
def mock_current_user():
    user = SimpleNamespace(id=1, roles=['PLANIFICADOR'], nombre="Test", apellido="User")
    with patch('flask_jwt_extended.get_current_user', return_value=user):
        yield user

@pytest.fixture
def mock_dependencies():
    with patch('app.controllers.planificacion_controller.OrdenProduccionController') as MockOPController, \
         patch('app.controllers.planificacion_controller.InventarioController') as MockInventarioController, \
         patch('app.controllers.planificacion_controller.CentroTrabajoModel') as MockCentroTrabajoModel, \
         patch('app.controllers.planificacion_controller.OperacionRecetaModel') as MockOperacionRecetaModel, \
         patch('app.controllers.planificacion_controller.IssuePlanificacionModel') as MockIssueModel, \
         patch('app.controllers.planificacion_controller.BloqueoCapacidadModel') as MockBloqueoModel, \
         patch('holidays.country_holidays', return_value={}):
        
        mocks = {
            "op_controller": MockOPController.return_value, "inventario_controller": MockInventarioController.return_value,
            "centro_trabajo_model": MockCentroTrabajoModel.return_value, "operacion_receta_model": MockOperacionRecetaModel.return_value,
            "issue_model": MockIssueModel.return_value, "bloqueo_model": MockBloqueoModel.return_value
        }
        yield mocks

@pytest.fixture
def planificacion_controller(mock_dependencies):
    controller = PlanificacionController()
    controller.orden_produccion_controller = mock_dependencies['op_controller']
    controller.inventario_controller = mock_dependencies['inventario_controller']
    controller.centro_trabajo_model = mock_dependencies['centro_trabajo_model']
    controller.operacion_receta_model = mock_dependencies['operacion_receta_model']
    controller.issue_planificacion_model = mock_dependencies['issue_model']
    controller.bloqueo_capacidad_model = mock_dependencies['bloqueo_model']
    return controller

# --- Test Cases ---

def test_replanificacion_mueve_op_por_falta_capacidad(app, planificacion_controller, mock_dependencies, mock_current_user):
    with app.test_request_context():
        fecha_conflicto = date(2024, 1, 10)
        usuario_id = 1
        op_a_mover = {
            'id': 99, 'codigo': 'OP-99', 'linea_asignada': 1, 'receta_id': 1, 
            'cantidad_planificada': 10, 'fecha_inicio_planificada': fecha_conflicto.isoformat(),
            'fecha_meta': (fecha_conflicto + timedelta(days=5)).isoformat()
        }
        
        mock_dependencies['op_controller'].obtener_ordenes.return_value = ({'success': True, 'data': [op_a_mover]}, 200)
        mock_dependencies['op_controller'].obtener_orden_por_id.return_value = {'success': True, 'data': op_a_mover}

        with patch.object(planificacion_controller, 'obtener_capacidad_disponible', return_value={1: {fecha_conflicto.isoformat(): {'neta': 0.0}}}), \
             patch.object(planificacion_controller, '_calcular_carga_op', return_value=Decimal('100')), \
             patch.object(planificacion_controller, '_simular_asignacion_carga', return_value={'success': True, 'fecha_inicio_real': fecha_conflicto + timedelta(days=1), 'fecha_fin_estimada': fecha_conflicto + timedelta(days=1)}):
            
            planificacion_controller._verificar_y_replanificar_ops_por_fecha(fecha_conflicto, usuario_id)

            mock_dependencies['op_controller'].model.update.assert_called_with(99, {'fecha_inicio_planificada': (fecha_conflicto + timedelta(days=1)).isoformat()}, 'id')


def test_ejecutar_planificacion_adaptativa_dispara_verificacion(app, planificacion_controller, mock_current_user):
    with app.test_request_context():
        usuario_id = mock_current_user.id
        
        with patch.object(planificacion_controller, '_verificar_y_replanificar_ops_por_fecha') as mock_replanificar, \
             patch.object(planificacion_controller, '_es_dia_laborable', return_value=True):
            
            response, status_code = planificacion_controller.ejecutar_planificacion_adaptativa(usuario_id)

            assert status_code == 200
            assert response['success']
            # Debería llamarse para hoy y los próximos 14 días (total 15 veces)
            assert mock_replanificar.call_count == 15
