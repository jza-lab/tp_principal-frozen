import pytest
from unittest.mock import patch
from app.controllers.configuracion_controller import ConfiguracionController

@pytest.fixture
def mock_config_model():
    """Fixture para mockear el ConfiguracionModel."""
    with patch('app.controllers.configuracion_controller.ConfiguracionModel') as MockModel:
        yield MockModel.return_value

@pytest.fixture
def config_controller(mock_config_model):
    """Fixture para crear una instancia de ConfiguracionController con dependencias mockeadas."""
    controller = ConfiguracionController()
    controller.model = mock_config_model
    return controller

class TestConfiguracionController:

    def test_guardar_dias_vencimiento_exitoso(self, config_controller, mock_config_model):
        # Arrange
        dias = 30
        mock_config_model.guardar_valor.return_value = {'success': True}

        # Act
        response, status_code = config_controller.guardar_dias_vencimiento(dias)

        # Assert
        assert status_code == 200
        assert response['success']
        assert response['data']['dias'] == dias
        mock_config_model.guardar_valor.assert_called_once_with('dias_alerta_vencimiento_lote', str(dias))

    @pytest.mark.parametrize("dias_invalidos, is_valid", [
        (0, False),
        (-1, False),
        (-100, False),
        ("treinta", False),
        (15.5, False),
        (999999, True) # Prueba de número alto
    ])
    def test_guardar_dias_vencimiento_invalidos(self, config_controller, mock_config_model, dias_invalidos, is_valid):
        # Arrange
        if is_valid:
            mock_config_model.guardar_valor.return_value = {'success': True}

        # Act
        response, status_code = config_controller.guardar_dias_vencimiento(dias_invalidos)

        # Assert
        if is_valid:
            assert status_code == 200
            assert response['success']
        else:
            assert status_code == 400
            assert not response['success']
            assert 'Los días deben ser un número entero positivo' in response['error']

    def test_obtener_dias_vencimiento_exitoso(self, config_controller, mock_config_model):
        # Arrange
        mock_config_model.obtener_valor.return_value = '15'

        # Act
        dias = config_controller.obtener_dias_vencimiento()

        # Assert
        assert dias == 15
        mock_config_model.obtener_valor.assert_called_once()

    def test_obtener_dias_vencimiento_con_error_usa_default(self, config_controller, mock_config_model):
        # Arrange
        mock_config_model.obtener_valor.side_effect = Exception("Error de base de datos")

        # Act
        dias = config_controller.obtener_dias_vencimiento()

        # Assert
        assert dias == 7 # El valor por defecto
