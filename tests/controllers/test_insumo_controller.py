import pytest
import uuid
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

    @pytest.mark.parametrize("stock_min, stock_max, is_valid", [
        (10, 20, True),          # Válido
        (0, 1, True),            # Límite inferior
        (10, 10, False),         # Mínimo igual a máximo
        (20, 10, False),         # Mínimo mayor a máximo
        (-5, 10, False),         # Mínimo negativo
        (10, -5, False),         # Máximo negativo
        ("diez", 20, False),     # Mínimo no numérico
        (10, "veinte", False),   # Máximo no numérico
    ])
    def test_crear_insumo_validacion_stock(self, insumo_controller, mock_insumo_dependencies, stock_min, stock_max, is_valid):
        # Arrange
        form_data = {
            'nombre': f'Insumo Stock {stock_min}-{stock_max}',
            'categoria': 'Test',
            'unidad_medida': 'un',
            'stock_min': stock_min,
            'stock_max': stock_max
        }
        mock_insumo_dependencies['insumo_model'].find_all.return_value = {'success': True, 'data': []}
        mock_insumo_dependencies['insumo_model'].find_by_codigo.return_value = {'success': False}
        mock_insumo_dependencies['insumo_model'].create.return_value = {'success': True, 'data': {'id_insumo': 99}}

        # Act
        response, status_code = insumo_controller.crear_insumo(form_data)

        # Assert
        if is_valid:
            assert status_code == 201
            assert response['success']
        else:
            assert status_code == 422
            assert not response['success']
            assert 'Datos inválidos' in response['error']

    def test_eliminar_insumo_fisico(self, insumo_controller, mock_insumo_dependencies):
        # Arrange
        insumo_id = "1"
        mock_insumo_dependencies['insumo_model'].delete.return_value = {'success': True}

        # Act
        response, status_code = insumo_controller.eliminar_insumo(insumo_id, forzar_eliminacion=True)

        # Assert
        assert status_code == 200
        assert response['success']
        mock_insumo_dependencies['insumo_model'].delete.assert_called_once_with(insumo_id, 'id_insumo', soft_delete=False)

    def test_obtener_insumos_filtro_stock_bajo(self, insumo_controller, mock_insumo_dependencies):
        # Arrange
        uuid1 = uuid.uuid4()
        uuid2 = uuid.uuid4()

        insumos_solo_stock = [
            {'id_insumo': uuid1, 'nombre': 'Harina', 'stock_actual': 5, 'stock_min': 10, 'estado_stock': 'BAJO'},
            {'id_insumo': uuid2, 'nombre': 'Azucar', 'stock_actual': 2, 'stock_min': 5, 'estado_stock': 'BAJO'},
        ]
        mock_insumo_dependencies['inventario_model'].obtener_stock_consolidado.return_value = {
            'success': True, 'data': insumos_solo_stock
        }
        
        # CRÍTICO: Los id_insumo deben ser UUID y las fechas deben ser objetos datetime
        from datetime import datetime
        insumos_catalogo_completos = [
            {'id_insumo': uuid1, 'nombre': 'Harina', 'activo': True, 'id_proveedor': 1, 'unidad_medida': 'kg', 'categoria': 'Secos', 'precio_unitario': 100, 'created_at': datetime(2024, 1, 1, 12, 0, 0), 'updated_at': datetime(2024, 1, 1, 12, 0, 0)},
            {'id_insumo': uuid2, 'nombre': 'Azucar', 'activo': True, 'id_proveedor': 1, 'unidad_medida': 'kg', 'categoria': 'Secos', 'precio_unitario': 80, 'created_at': datetime(2024, 1, 1, 12, 0, 0), 'updated_at': datetime(2024, 1, 1, 12, 0, 0)}
        ]
        
        # CORRECCIÓN: Mockear correctamente toda la cadena de llamadas
        mock_execute = MagicMock()
        mock_execute.data = insumos_catalogo_completos
        
        mock_query = MagicMock()
        mock_query.in_.return_value = mock_query
        mock_query.execute.return_value = mock_execute
        
        mock_select = MagicMock()
        mock_select.return_value = mock_query
        
        mock_table = MagicMock()
        mock_table.select = mock_select
        
        # Mockear db.table() para que retorne nuestro mock_table
        mock_db = MagicMock()
        mock_db.table.return_value = mock_table
        mock_insumo_dependencies['insumo_model'].db = mock_db
        
        # Mockear get_table_name() para que retorne el nombre de la tabla
        mock_insumo_dependencies['insumo_model'].get_table_name.return_value = 'catalogo_insumos'
        
        # CRÍTICO: Mockear _convert_timestamps para que retorne los datos sin modificar
        mock_insumo_dependencies['insumo_model']._convert_timestamps.return_value = insumos_catalogo_completos
        
        # Mockear calcular_y_actualizar_stock_general
        mock_insumo_dependencies['inventario_model'].calcular_y_actualizar_stock_general.return_value = {'success': True}
        
        with patch.object(insumo_controller, '_revisar_y_generar_ocs_automaticas') as mock_auto_oc:
            # Act
            filtros = {'stock_status': 'bajo'}
            response, status_code = insumo_controller.obtener_insumos(filtros)

            # Assert
            mock_auto_oc.assert_called_once()
            
            # Verificar que se llamó a db.table
            assert mock_db.table.called
            
            # Verificar que se llamó a select
            assert mock_select.called
            
            # La lista de IDs que se pasa a `.in_` debe ser de UUIDs
            mock_query.in_.assert_called_once_with('id_insumo', [uuid1, uuid2])
            
            # Verificar que se ejecutó la query
            mock_query.execute.assert_called_once()
            
            # Verificar que se llamó a _convert_timestamps
            mock_insumo_dependencies['insumo_model']._convert_timestamps.assert_called_once_with(insumos_catalogo_completos)
            
            assert status_code == 200
            assert response['success']
            assert len(response['data']) == 2
            
            harina_data = next((item for item in response['data'] if item['nombre'] == 'Harina'), None)
            assert harina_data is not None
            assert harina_data['stock_actual'] == 5.0
            assert harina_data['stock_min'] == 10