import pytest
from unittest.mock import MagicMock, patch, ANY
from app.controllers.producto_controller import ProductoController
from app import create_app

@pytest.fixture
def app():
    app = create_app()
    app.config.update({"TESTING": True, "JWT_SECRET_KEY": "test-secret", "WTF_CSRF_ENABLED": False})
    yield app

@pytest.fixture
def mock_producto_dependencies():
    with patch('app.controllers.producto_controller.ProductoModel') as MockProductoModel, \
         patch('app.controllers.producto_controller.RecetaController') as MockRecetaController, \
         patch('app.controllers.producto_controller.RecetaModel') as MockRecetaModel:
        yield {
            "producto_model": MockProductoModel.return_value,
            "receta_controller": MockRecetaController.return_value,
            "receta_model": MockRecetaModel.return_value,
        }

@pytest.fixture
def producto_controller(mock_producto_dependencies):
    controller = ProductoController()
    controller.model = mock_producto_dependencies['producto_model']
    controller.receta_controller = mock_producto_dependencies['receta_controller']
    controller.receta_model = mock_producto_dependencies['receta_model']
    return controller

class TestProductoController:

    def test_crear_producto_exitoso(self, producto_controller, mock_producto_dependencies):
        form_data = {'nombre': 'Torta', 'codigo': 'PROD-TORT-0001', 'unidad_medida': 'un', 'categoria': 'Pasteleria', 'precio_unitario': 100, 'stock_min_produccion': 10, 'cantidad_maxima_x_pedido': 5, 'iva': True}
        mock_producto_dependencies['producto_model'].find_by_codigo.return_value = {'success': False}
        mock_producto_dependencies['producto_model'].create.return_value = {'success': True, 'data': {'id': 1, 'nombre': 'Torta'}}
        mock_producto_dependencies['receta_model'].create.return_value = {'success': True, 'data': {'id': 1}}
        response, status_code = producto_controller.crear_producto(form_data)
        assert status_code == 201
        assert response['success']

    def test_crear_producto_codigo_duplicado(self, producto_controller, mock_producto_dependencies):
        form_data = {'nombre': 'Muffin', 'codigo': 'PROD-MUFF-0001', 'unidad_medida': 'un', 'categoria': 'Pasteleria', 'precio_unitario': 50, 'stock_min_produccion': 20, 'cantidad_maxima_x_pedido': 10, 'iva': True}
        mock_producto_dependencies['producto_model'].find_by_codigo.return_value = {'success': True, 'data': {'id': 2}}
        response, status_code = producto_controller.crear_producto(form_data)
        assert status_code == 409
        assert not response['success']

    def test_crear_producto_sin_iva(self, producto_controller, mock_producto_dependencies):
        form_data = {
            'nombre': 'Torta Sin IVA', 'codigo': 'PROD-TORT-0002', 'unidad_medida': 'un',
            'categoria': 'Pasteleria', 'precio_unitario': 100, 'stock_min_produccion': 10,
            'cantidad_maxima_x_pedido': 5, 'iva': False
        }
        mock_producto_dependencies['producto_model'].find_by_codigo.return_value = {'success': False}
        mock_producto_dependencies['producto_model'].create.return_value = {'success': True, 'data': {'id': 2, 'nombre': 'Torta Sin IVA'}}
        mock_producto_dependencies['receta_model'].create.return_value = {'success': True, 'data': {'id': 2}}
        
        response, status_code = producto_controller.crear_producto(form_data)
        
        assert status_code == 201
        assert response['success']
        # Assert that the `create` method was called with iva=False
        # CORRECCIÓN: El schema añade valores por defecto, la aserción debe incluirlos.
        validated_data = {
            'nombre': 'Torta Sin IVA', 'codigo': 'PROD-TORT-0002', 'unidad_medida': 'un',
            'categoria': 'Pasteleria', 'precio_unitario': 100.0, 'stock_min_produccion': 10,
            'cantidad_maxima_x_pedido': 5, 'iva': False,
            # Campos añadidos por el schema con load_default
            'unidades_por_paquete': 1,
            'peso_por_paquete_valor': 0.0,
            'peso_por_paquete_unidad': ''
        }
        # El controlador puede pasar los datos en un orden diferente, así que usamos ANY
        mock_producto_dependencies['producto_model'].create.assert_called_with(ANY)
        # Verificación más robusta de los datos pasados al mock
        called_args, _ = mock_producto_dependencies['producto_model'].create.call_args
        assert called_args[0] == validated_data

    @pytest.mark.parametrize("campo, valor_invalido", [
        ("precio_unitario", 0),
        ("precio_unitario", -50.5),
        ("precio_unitario", "texto"),
        ("stock_min_produccion", -1),
        ("stock_min_produccion", "texto"),
        ("cantidad_maxima_x_pedido", -1),
        ("cantidad_maxima_x_pedido", "texto"),
    ])
    def test_crear_producto_campos_numericos_invalidos(self, producto_controller, mock_producto_dependencies, campo, valor_invalido):
        form_data = {
            'nombre': 'Producto Invalido', 'unidad_medida': 'un', 'categoria': 'Test',
            'precio_unitario': 100, 'stock_min_produccion': 10, 'cantidad_maxima_x_pedido': 5,
            'iva': True
        }
        form_data[campo] = valor_invalido
        
        # CORRECCIÓN: Mockear find_by_codigo para aislar el error de validación del de código duplicado.
        mock_producto_dependencies['producto_model'].find_by_codigo.return_value = {'success': False}
        
        response, status_code = producto_controller.crear_producto(form_data)
        
        assert status_code == 422 # Unprocessable Entity from validation
        assert not response['success']
        assert "Datos inválidos" in response['error']

    def test_actualizar_producto_exitoso(self, producto_controller, mock_producto_dependencies):
        producto_id = 1
        form_data = {'nombre': 'Torta de Vainilla'}
        mock_producto_dependencies['producto_model'].find_by_id.return_value = {'success': True, 'data': {'codigo': 'PROD-TORT-0001'}}
        mock_producto_dependencies['producto_model'].update.return_value = {'success': True, 'data': {}}
        mock_producto_dependencies['receta_model'].find_all.return_value = {'success': True, 'data': [{'id': 1}]}
        response, status_code = producto_controller.actualizar_producto(producto_id, form_data)
        assert status_code == 200
        assert response['success']

    def test_desactivar_producto(self, producto_controller, mock_producto_dependencies):
        producto_id = 1
        mock_producto_dependencies['producto_model'].update.return_value = {'success': True}
        response, status_code = producto_controller.eliminar_producto_logico(producto_id)
        assert status_code == 200
        assert response['success']

    def test_reactivar_producto(self, producto_controller, mock_producto_dependencies):
        producto_id = 1
        mock_producto_dependencies['producto_model'].update.return_value = {'success': True}
        response, status_code = producto_controller.habilitar_producto(producto_id)
        assert status_code == 200
        assert response['success']

    @pytest.mark.parametrize("costo_base, porcentaje_extra, iva, costo_final_esperado", [
        (100, 0, False, 100.00),
        (100, 0, True, 121.00),
        (100, 50, False, 150.00),
        (100, 50, True, 181.50),
        (250, 20, True, 363.00),
        (100, -10, True, 108.90), # Prueba con porcentaje negativo
        (100, 101, False, 201.00), # Prueba con porcentaje > 100
    ])
    def test_actualizar_costo_producto_calculo(self, producto_controller, mock_producto_dependencies, costo_base, porcentaje_extra, iva, costo_final_esperado):
        producto_id = 1
        # Mock de la receta y su costo
        mock_producto_dependencies['receta_model'].find_all.return_value = {'success': True, 'data': [{'id': 99}]}
        mock_producto_dependencies['receta_controller'].calcular_costo_total_receta.return_value = {'success': True, 'data': {'costo_total': costo_base}}
        
        # Mock del producto a actualizar
        producto_mock = {'id': producto_id, 'porcentaje_extra': porcentaje_extra, 'iva': iva}
        mock_producto_dependencies['producto_model'].find_by_id.return_value = {'success': True, 'data': producto_mock}
        
        # Mock del update para capturar el resultado
        mock_producto_dependencies['producto_model'].update.return_value = {'success': True}
        
        # Ejecutar el método
        response, status_code = producto_controller.actualizar_costo_producto(producto_id)
        
        # Verificar el resultado
        assert status_code == 200
        assert response['success']
        
        # Verificar que se llamó al update con el precio calculado correcto
        mock_producto_dependencies['producto_model'].update.assert_called_once_with(
            producto_id, {'precio_unitario': costo_final_esperado}, 'id'
        )

    def test_obtener_todos_los_productos_con_filtro_nombre(self, producto_controller, mock_producto_dependencies):
        # Arrange
        # CORRECCIÓN: El mock debe simular el filtrado.
        productos_filtrados = [
            {'id': 1, 'nombre': 'Torta de Chocolate', 'activo': True},
            {'id': 3, 'nombre': 'Torta de Fresa', 'activo': False},
        ]
        mock_producto_dependencies['producto_model'].find_all.return_value = {'success': True, 'data': productos_filtrados}
        
        # Act: Búsqueda de "Torta"
        filtros = {'nombre': 'Torta'}
        response, status_code = producto_controller.obtener_todos_los_productos(filtros)
        
        # Assert
        assert status_code == 200
        assert response['success']
        # El controlador ordena por 'activo' descendente
        assert response['data'] == [
            {'id': 1, 'nombre': 'Torta de Chocolate', 'activo': True},
            {'id': 3, 'nombre': 'Torta de Fresa', 'activo': False},
        ]
        # Verificar que el modelo fue llamado con el filtro correcto
        mock_producto_dependencies['producto_model'].find_all.assert_called_with(filtros)

    def test_obtener_todos_los_productos_sin_resultados(self, producto_controller, mock_producto_dependencies):
        # Arrange
        mock_producto_dependencies['producto_model'].find_all.return_value = {'success': True, 'data': []}
        
        # Act: Búsqueda de algo que no existe
        filtros = {'nombre': 'Galleta'}
        response, status_code = producto_controller.obtener_todos_los_productos(filtros)
        
        # Assert
        assert status_code == 200
        assert response['success']
        assert response['data'] == []
        mock_producto_dependencies['producto_model'].find_all.assert_called_with(filtros)

    def test_obtener_todos_los_productos_sin_filtro(self, producto_controller, mock_producto_dependencies):
        # Arrange
        todos_los_productos = [
            {'id': 1, 'nombre': 'Torta', 'activo': True},
            {'id': 2, 'nombre': 'Muffin', 'activo': True},
            {'id': 3, 'nombre': 'Galleta', 'activo': False},
        ]
        mock_producto_dependencies['producto_model'].find_all.return_value = {'success': True, 'data': todos_los_productos}
        
        # Act: Llamar sin filtros
        response, status_code = producto_controller.obtener_todos_los_productos()
        
        # Assert
        assert status_code == 200
        assert response['success']
        assert len(response['data']) == 3
        # Verificar que el modelo fue llamado con un diccionario vacío
        mock_producto_dependencies['producto_model'].find_all.assert_called_with({})
