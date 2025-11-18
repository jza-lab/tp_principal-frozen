import pytest
from unittest.mock import patch, MagicMock
from app.controllers.configuracion_controller import ConfiguracionController
from app import create_app
from types import SimpleNamespace

@pytest.fixture
def app():
    """Crea y configura una nueva instancia de la aplicación para cada prueba."""
    app = create_app()
    app.config.update({"TESTING": True, "JWT_SECRET_KEY": "test-secret"})
    yield app

@pytest.fixture
def mock_config_model():
    """Fixture para mockear el ConfiguracionModel."""
    with patch('app.controllers.configuracion_controller.ConfiguracionModel') as MockModel:
        yield MockModel.return_value

@pytest.fixture
def config_controller(mock_config_model):
    """Fixture para crear una instancia de ConfiguracionController con dependencias mockeadas."""
    # Mockear RegistroController que se instancia dentro del init
    with patch('app.controllers.configuracion_controller.RegistroController') as MockRegistroController:
        controller = ConfiguracionController()
        controller.model = mock_config_model
        controller.registro_controller = MockRegistroController.return_value
        yield controller

# Simular un usuario logueado para que get_current_user() funcione
@pytest.fixture
def mock_current_user():
    user = SimpleNamespace(id=1, nombre='Test', apellido='User', roles=['ADMIN'])
    with patch('app.controllers.configuracion_controller.get_current_user', return_value=user):
        yield

class TestConfiguracionController:

    def test_guardar_dias_vencimiento_exitoso(self, app, config_controller, mock_config_model, mock_current_user):
        with app.app_context():
            dias = 30
            mock_config_model.guardar_valor.return_value = {'success': True}

            response, status_code = config_controller.guardar_dias_vencimiento(dias)

            assert status_code == 200
            assert response['success']
            assert response['data']['dias'] == dias
            mock_config_model.guardar_valor.assert_called_once_with('dias_alerta_vencimiento_lote', str(dias))

    @pytest.mark.parametrize("dias_invalidos", [0, -1, "treinta", 15.5])
    def test_guardar_dias_vencimiento_invalidos(self, app, config_controller, dias_invalidos):
        with app.app_context():
            response, status_code = config_controller.guardar_dias_vencimiento(dias_invalidos)
            assert status_code == 400
            assert not response['success']
            assert 'Los días deben ser un número entero positivo' in response['error']

    def test_obtener_dias_vencimiento_exitoso(self, config_controller, mock_config_model):
        mock_config_model.obtener_valor.return_value = '15'
        dias = config_controller.obtener_dias_vencimiento()
        assert dias == 15
        mock_config_model.obtener_valor.assert_called_once()

    def test_obtener_dias_vencimiento_con_error_usa_default(self, config_controller, mock_config_model):
        mock_config_model.obtener_valor.side_effect = Exception("Error de base de datos")
        dias = config_controller.obtener_dias_vencimiento()
        assert dias == 7 # El valor por defecto
