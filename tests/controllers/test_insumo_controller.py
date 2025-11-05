import pytest
from unittest.mock import MagicMock, patch
from app.controllers.insumo_controller import InsumoController
from app import create_app

@pytest.fixture
def app():
    """Crea y configura una nueva instancia de la aplicación para cada prueba."""
    app = create_app()
    app.config.update({"TESTING": True, "JWT_SECRET_KEY": "test-secret", "WTF_CSRF_ENABLED": False})
    yield app

@pytest.fixture
def mock_insumo_dependencies():
    """Fixture para mockear las dependencias externas de InsumoController."""
    with patch('app.controllers.insumo_controller.InsumoModel') as MockInsumoModel, \
         patch('app.controllers.insumo_controller.InventarioModel') as MockInventarioModel:
        yield {
            "insumo_model": MockInsumoModel.return_value,
            "inventario_model": MockInventarioModel.return_value,
        }

@pytest.fixture
def insumo_controller(mock_insumo_dependencies):
    """Fixture para crear una instancia de InsumoController con dependencias mockeadas."""
    controller = InsumoController()
    controller.insumo_model = mock_insumo_dependencies['insumo_model']
    controller.inventario_model = mock_insumo_dependencies['inventario_model']
    return controller

class TestInsumoController:

    # Test para crear un insumo exitosamente
    def test_crear_insumo_exitoso(self, insumo_controller, mock_insumo_dependencies):
        # Arrange
        # CORRECCIÓN: Añadido el campo 'unidad_medida' que es obligatorio en el schema
        form_data = {'nombre': 'Harina 000', 'categoria': 'Secos', 'unidad_medida': 'kg'}
        
        mock_insumo_dependencies['insumo_model'].find_all.return_value = {'success': True, 'data': []}
        mock_insumo_dependencies['insumo_model'].find_by_codigo.return_value = {'success': False}
        insumo_creado_mock = {'id_insumo': 1, **form_data, 'codigo_interno': 'INS-SEC-HAR'}
        mock_insumo_dependencies['insumo_model'].create.return_value = {'success': True, 'data': insumo_creado_mock}

        # Act
        response, status_code = insumo_controller.crear_insumo(form_data)

        # Assert
        assert status_code == 201
        assert response['success']
        assert response['data']['id_insumo'] == 1
        create_call_args = mock_insumo_dependencies['insumo_model'].create.call_args[0][0]
        assert 'codigo_interno' in create_call_args
        assert create_call_args['codigo_interno'].startswith('INS-SEC-HAR')

    # Test para fallo al crear insumo con nombre duplicado
    def test_crear_insumo_nombre_duplicado(self, insumo_controller, mock_insumo_dependencies):
        # Arrange
        # CORRECCIÓN: Añadido el campo 'unidad_medida'
        form_data = {'nombre': 'Harina 000', 'categoria': 'Secos', 'unidad_medida': 'kg'}
        
        mock_insumo_dependencies['insumo_model'].find_all.return_value = {'success': True, 'data': [{'id_insumo': 2}]}

        # Act
        response, status_code = insumo_controller.crear_insumo(form_data)

        # Assert
        assert status_code == 409
        assert not response['success']
        assert 'Ya existe un insumo con ese nombre' in response['error']

    # Test para actualizar un insumo
    def test_actualizar_insumo_exitoso(self, insumo_controller, mock_insumo_dependencies):
        # Arrange
        insumo_id = "1"
        form_data = {'descripcion': 'Harina de trigo de alta calidad'}
        
        mock_insumo_dependencies['insumo_model'].update.return_value = {'success': True, 'data': {'id_insumo': insumo_id, **form_data}}

        # Act
        response, status_code = insumo_controller.actualizar_insumo(insumo_id, form_data)

        # Assert
        assert status_code == 200
        assert response['success']
        mock_insumo_dependencies['insumo_model'].update.assert_called_once_with(insumo_id, form_data, 'id_insumo')

    # Test para desactivar (eliminación lógica) un insumo
    def test_desactivar_insumo(self, insumo_controller, mock_insumo_dependencies):
        # Arrange
        insumo_id = "1"
        mock_insumo_dependencies['insumo_model'].update.return_value = {'success': True}

        # Act
        response, status_code = insumo_controller.eliminar_insumo_logico(insumo_id)

        # Assert
        assert status_code == 200
        assert response['success']
        update_call_args = mock_insumo_dependencies['insumo_model'].update.call_args[0]
        assert update_call_args[1] == {'activo': False}

    # Test para reactivar un insumo
    def test_reactivar_insumo(self, insumo_controller, mock_insumo_dependencies):
        # Arrange
        insumo_id = "1"
        mock_insumo_dependencies['insumo_model'].update.return_value = {'success': True}

        # Act
        response, status_code = insumo_controller.habilitar_insumo(insumo_id)

        # Assert
        assert status_code == 200
        assert response['success']
        update_call_args = mock_insumo_dependencies['insumo_model'].update.call_args[0]
        assert update_call_args[1] == {'activo': True}
