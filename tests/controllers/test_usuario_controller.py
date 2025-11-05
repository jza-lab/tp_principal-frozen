import pytest
from unittest.mock import MagicMock, patch, ANY
from app.controllers.usuario_controller import UsuarioController
from app import create_app
from werkzeug.security import check_password_hash

@pytest.fixture
def app():
    app = create_app()
    app.config.update({"TESTING": True, "JWT_SECRET_KEY": "test-secret", "WTF_CSRF_ENABLED": False})
    app.config['BYPASS_LOGIN_CHECKS'] = True
    yield app

@pytest.fixture
def mock_user_dependencies():
    with patch('app.controllers.usuario_controller.UsuarioModel') as MockUserModel, \
         patch('app.controllers.usuario_controller.TotemSesionModel') as MockTotemModel, \
         patch('app.controllers.usuario_controller.SectorModel') as MockSectorModel, \
         patch('app.controllers.usuario_controller.UsuarioSectorModel') as MockUserSectorModel, \
         patch('app.controllers.usuario_controller.DireccionModel') as MockDireccionModel:
        yield {
            "user_model": MockUserModel.return_value,
            "totem_model": MockTotemModel.return_value,
            "sector_model": MockSectorModel.return_value,
            "user_sector_model": MockUserSectorModel.return_value,
            "direccion_model": MockDireccionModel.return_value
        }

@pytest.fixture
def usuario_controller(mock_user_dependencies):
    controller = UsuarioController()
    controller.model = mock_user_dependencies['user_model']
    controller.totem_sesion = mock_user_dependencies['totem_model']
    controller.sector_model = mock_user_dependencies['sector_model']
    controller.usuario_sector_model = mock_user_dependencies['user_sector_model']
    controller.direccion_model = mock_user_dependencies['direccion_model']
    return controller

class TestUsuarioController:

    def test_crear_usuario_exitoso(self, usuario_controller, mock_user_dependencies):
        form_data = {
            'nombre': 'Juan', 'apellido': 'Perez', 'email': 'juan.perez@test.com',
            'password': 'password123', 'legajo': '12345', 'role_id': 1, 'sectores': [1, 2]
        }
        mock_user_dependencies['user_model'].find_by_email.return_value = {'success': False}
        mock_user_dependencies['user_model'].create.return_value = {'success': True, 'data': {'id': 1}}
        mock_user_dependencies['user_sector_model'].asignar_sector.return_value = {'success': True}
        mock_user_dependencies['user_model'].find_by_id.return_value = {'success': True, 'data': {'id': 1, **form_data}}
        response = usuario_controller.crear_usuario(form_data)
        assert response['success']
        assert response['data']['id'] == 1
        create_call_args = mock_user_dependencies['user_model'].create.call_args[0][0]
        assert 'password_hash' in create_call_args
        assert check_password_hash(create_call_args['password_hash'], 'password123')
        assert mock_user_dependencies['user_sector_model'].asignar_sector.call_count == 2

    def test_crear_usuario_email_duplicado(self, usuario_controller, mock_user_dependencies):
        # CORRECCIÓN: Usar una contraseña válida y añadir todos los campos requeridos
        form_data = {
            'nombre': 'Ana', 'apellido': 'Gomez', 'email': 'ana.gomez@test.com',
            'password': 'passwordValida', 'legajo': '54321', 'role_id': 1
        }
        mock_user_dependencies['user_model'].find_by_email.return_value = {'success': True, 'data': {'id': 2}}
        response = usuario_controller.crear_usuario(form_data)
        assert not response['success']
        assert 'El correo electrónico ya está en uso' in response['error']

    def test_actualizar_usuario_exitoso(self, usuario_controller, mock_user_dependencies):
        usuario_id = 1
        form_data = {
            'nombre': 'Juan Carlos', 'apellido': 'Perez', 'email': 'juan.perez@test.com',
            'telefono': '1122334455', 'legajo': '12345', 'cuil_cuit': '20-12345678-9',
            'sectores': '[3]'
        }
        usuario_existente = {'id': usuario_id, 'nombre': 'Juan', 'sectores': [{'id': 1}, {'id': 2}]}
        mock_user_dependencies['user_model'].find_by_id.return_value = {'success': True, 'data': usuario_existente}
        with patch.object(usuario_controller, '_actualizar_sectores_usuario', return_value={'success': True}), \
             patch.object(usuario_controller, '_actualizar_direccion_usuario', return_value={'success': True, 'direccion_id': None}), \
             patch.object(usuario_controller, '_actualizar_datos_principales', return_value={'success': True}):
            response = usuario_controller.actualizar_usuario(usuario_id, form_data)
            assert response['success']
            usuario_controller._actualizar_sectores_usuario.assert_called_once()

    def test_autenticar_usuario_web_exitoso(self, app, usuario_controller, mock_user_dependencies):
        legajo = '12345'
        password = 'password123'
        user_data = {'id': 1, 'legajo': legajo, 'roles': {'codigo': 'OPERARIO'}}
        with patch.object(usuario_controller, '_autenticar_credenciales_base', return_value={'success': True, 'data': user_data}), \
             patch.object(usuario_controller, '_preparar_datos_sesion_usuario', return_value={'success': True, 'data': {'id': 1, 'nombre': 'Juan'}}) as mock_preparar_sesion, \
             app.app_context():
            response = usuario_controller.autenticar_usuario_web(legajo, password)
            assert response['success']
            assert response['data']['id'] == 1
            mock_user_dependencies['user_model'].update.assert_called_once_with(1, {'ultimo_login_web': ANY})
            mock_preparar_sesion.assert_called_once_with(user_data)

    def test_autenticar_usuario_web_fallido(self, app, usuario_controller):
        legajo = '12345'
        password = 'wrongpassword'
        with patch.object(usuario_controller, '_autenticar_credenciales_base', return_value={'success': False, 'error': 'Credenciales incorrectas'}), \
             app.app_context():
            response = usuario_controller.autenticar_usuario_web(legajo, password)
            assert not response['success']
            assert 'Credenciales incorrectas' in response['error']
