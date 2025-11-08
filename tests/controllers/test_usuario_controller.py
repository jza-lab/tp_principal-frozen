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

    def test_crear_usuario_exitoso(self, app, usuario_controller, mock_user_dependencies):
        form_data = {
            'nombre': 'Juan', 'apellido': 'Perez', 'email': 'juan.perez@test.com',
            'password': 'password123', 'legajo': '12345', 'role_id': 1, 'sectores': [1, 2]
        }
        mock_user_dependencies['user_model'].find_by_email.return_value = {'success': False}
        mock_user_dependencies['user_model'].find_by_legajo.return_value = {'success': False}
        mock_user_dependencies['user_model'].create.return_value = {'success': True, 'data': {'id': 1, **form_data}}
        mock_user_dependencies['user_sector_model'].asignar_sector.return_value = {'success': True}
        # FIX: Restaurar mock para la respuesta final del controlador.
        mock_user_dependencies['user_model'].find_by_id.return_value = {'success': True, 'data': {'id': 1, **form_data}}

        with app.app_context():
            # FIX: Mockear get_current_user y el logger para evitar llamadas de red.
            with patch('app.controllers.usuario_controller.get_current_user', return_value={'id': 99, 'nombre': 'Admin'}), \
                 patch.object(usuario_controller.registro_controller, 'crear_registro'):
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

    def test_crear_usuario_legajo_duplicado(self, usuario_controller, mock_user_dependencies):
        form_data = {
            'nombre': 'Carlos', 'apellido': 'Ruiz', 'email': 'carlos.ruiz@test.com',
            'password': 'password123', 'legajo': '12345', 'role_id': 1
        }
        mock_user_dependencies['user_model'].find_by_email.return_value = {'success': False}
        mock_user_dependencies['user_model'].find_by_legajo.return_value = {'success': False} # Mock faltante
        mock_user_dependencies['user_model'].find_by_legajo.return_value = {'success': True, 'data': {'id': 3}}
        # CORRECCIÓN: Asegurarse de que la respuesta sea un diccionario de error.
        # El controlador ahora tiene una lógica de verificación de duplicados que necesita ser mockeada
        mock_user_dependencies['user_model'].find_by_email.return_value = {'success': False}
        mock_user_dependencies['user_model'].find_by_legajo.return_value = {'success': True, 'data': {'id': 3}}

        response = usuario_controller.crear_usuario(form_data)
        
        # El controlador no devuelve un error de duplicado de legajo, sino que debería hacerlo.
        # Por ahora, vamos a asumir que el test debe fallar si no hay error.
        # Esto expone un bug en el controlador. Para que el test pase, lo marco como xfail.
        # pytest.xfail("El controlador no está verificando legajos duplicados")

        # La aserción correcta debería ser:
        assert isinstance(response, dict)
        assert not response['success']
        assert 'El legajo ya está en uso' in response['error']

    @pytest.mark.parametrize("campo, valor_invalido", [
        ("cuil_cuit", "20-12345678-A"), # Letra en dígito verificador
        ("cuil_cuit", "20123456789"),   # Sin guiones
        ("cuil_cuit", "20-1234567-89"), # Formato incorrecto
        ("telefono", "123"),           # Muy corto
        ("telefono", "1234567890123456"), # Muy largo
        ("telefono", "once-doce-trece"), # Con letras y guiones
    ])
    def test_crear_usuario_formatos_invalidos(self, usuario_controller, campo, valor_invalido):
        form_data = {
            'nombre': 'Test', 'apellido': 'User', 'email': 'test.user@test.com',
            'password': 'password123', 'legajo': '99999', 'role_id': 1,
            'cuil_cuit': '20-99999999-9', 'telefono': '1122334455'
        }
        form_data[campo] = valor_invalido
        response = usuario_controller.crear_usuario(form_data)
        assert not response['success']
        assert 'Datos inválidos' in response['error']
        # El error de Marshmallow debería especificar el campo
        assert campo in response['error']

    @pytest.mark.parametrize("campo_direccion, valor_invalido", [
        ("altura", -100),         # Altura negativa
        ("altura", 0),            # Altura cero
        ("altura", "mil"),        # Altura no numérica
        ("piso", "un piso muy largo"), # Piso excede longitud
        ("piso", "piso-5*"),       # Piso con caracteres inválidos
    ])
    def test_crear_usuario_direccion_invalida(self, usuario_controller, mock_user_dependencies, campo_direccion, valor_invalido):
        form_data = {
            'nombre': 'Direccion', 'apellido': 'Test', 'email': 'direccion.test@test.com',
            'password': 'password123', 'legajo': '11111', 'role_id': 1,
            'calle': 'Calle Falsa', 'altura': 123, 'piso': '5', 'localidad': 'CABA', 'provincia': 'BsAs'
        }
        form_data[campo_direccion] = valor_invalido

        # CORRECCIÓN: Mockear todas las llamadas previas a la validación.
        mock_user_dependencies['user_model'].find_by_email.return_value = {'success': False}
        mock_user_dependencies['user_model'].find_by_legajo.return_value = {'success': False}
        mock_user_dependencies['direccion_model'].create.return_value = {'success': True, 'data': {'id': 1}}


        response = usuario_controller.crear_usuario(form_data)

        # CORRECCIÓN: La respuesta debe ser un diccionario de error.
        assert isinstance(response, dict)
        assert not response['success']
        assert 'Datos inválidos' in response['error']
        assert campo_direccion in response['error']

    def test_actualizar_usuario_exitoso(self, app, usuario_controller, mock_user_dependencies):
        usuario_id = 1
        form_data = {
            'nombre': 'Juan Carlos', 'apellido': 'Perez', 'email': 'juan.perez@test.com',
            'telefono': '1122334455', 'legajo': '12345', 'cuil_cuit': '20-12345678-9',
            'sectores': '[3]'
        }
        usuario_existente = {'id': usuario_id, 'nombre': 'Juan', 'apellido': 'Perez', 'legajo': '12345', 'sectores': [{'id': 1}, {'id': 2}]}
        usuario_actualizado = {**usuario_existente, 'nombre': 'Juan Carlos'}

        # FIX: find_by_id es llamado dos veces. La primera para obtener los datos, la segunda para el log.
        mock_user_dependencies['user_model'].find_by_id.side_effect = [
            {'success': True, 'data': usuario_existente},
            {'success': True, 'data': usuario_actualizado}
        ]
        
        with app.app_context():
            with patch('app.controllers.usuario_controller.get_current_user', return_value={'id': 99, 'nombre': 'Admin'}), \
                 patch.object(usuario_controller.registro_controller, 'crear_registro'), \
                 patch.object(usuario_controller, '_actualizar_sectores_usuario', return_value={'success': True}) as mock_sectores, \
                 patch.object(usuario_controller, '_actualizar_direccion_usuario', return_value={'success': True, 'direccion_id': None}), \
                 patch.object(usuario_controller, '_actualizar_datos_principales', return_value={'success': True, 'data': usuario_actualizado}):
                response = usuario_controller.actualizar_usuario(usuario_id, form_data)
        
        assert response['success']
        assert response['data']['nombre'] == 'Juan Carlos'
        mock_sectores.assert_called_once()

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
