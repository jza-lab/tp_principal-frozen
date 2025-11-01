import pytest
from unittest.mock import MagicMock, patch
from app.controllers.orden_produccion_controller import OrdenProduccionController
from datetime import date

@pytest.fixture
def mock_op_dependencies():
    """Fixture to mock all external dependencies of OrdenProduccionController."""
    with patch('app.controllers.orden_produccion_controller.OrdenProduccionModel') as MockOPModel, \
         patch('app.controllers.orden_produccion_controller.ProductoController') as MockProductoController, \
         patch('app.controllers.orden_produccion_controller.RecetaController') as MockRecetaController, \
         patch('app.controllers.orden_produccion_controller.UsuarioController') as MockUsuarioController, \
         patch('app.controllers.orden_produccion_controller.InventarioController') as MockInventarioController, \
         patch('app.controllers.orden_produccion_controller.OrdenCompraController') as MockOCController, \
         patch('app.controllers.orden_produccion_controller.InsumoController') as MockInsumoController, \
         patch('app.controllers.orden_produccion_controller.LoteProductoController') as MockLoteController, \
         patch('app.controllers.orden_produccion_controller.PedidoModel') as MockPedidoModel, \
         patch('app.controllers.orden_produccion_controller.RecetaModel') as MockRecetaModel:

        yield {
            "op_model": MockOPModel.return_value,
            "producto_controller": MockProductoController.return_value,
            "receta_controller": MockRecetaController.return_value,
            "usuario_controller": MockUsuarioController.return_value,
            "inventario_controller": MockInventarioController.return_value,
            "oc_controller": MockOCController.return_value,
            "insumo_controller": MockInsumoController.return_value,
            "lote_controller": MockLoteController.return_value,
            "pedido_model": MockPedidoModel.return_value,
            "receta_model": MockRecetaModel.return_value
        }

@pytest.fixture
def op_controller(mock_op_dependencies):
    """Fixture to create an instance of OrdenProduccionController with mocked dependencies."""
    return OrdenProduccionController()

class TestOrdenProduccionController:
    # Test para crear una orden de producción exitosamente
    def test_crear_orden_produccion_exitoso(self, op_controller, mock_op_dependencies):
        # Arrange
        form_data = {
            'producto_id': 1,
            'cantidad': 100,
            'fecha_meta': '2025-12-31'
        }
        usuario_id = 1
        
        mock_op_dependencies['receta_model'].find_all.return_value = {'success': True, 'data': [{'id': 1}]}
        mock_op_dependencies['op_model'].create.return_value = {'success': True, 'data': {'id': 1, 'codigo': 'OP-20250101-1'}}

        # Act
        response = op_controller.crear_orden(form_data, usuario_id)

        # Assert
        assert response['success']
        assert response['data']['id'] == 1
        mock_op_dependencies['op_model'].create.assert_called_once()

    # Test para aprobar una orden de producción con stock disponible
    def test_aprobar_orden_con_stock(self, op_controller, mock_op_dependencies):
        # Arrange
        orden_id = 1
        usuario_id = 1
        orden_produccion_data = {
            'id': orden_id,
            'estado': 'PENDIENTE',
            'producto_id': 1,
            'cantidad_planificada': 100
        }
        
        # Mock para obtener_orden_por_id
        with patch.object(op_controller, 'obtener_orden_por_id', return_value={'success': True, 'data': orden_produccion_data}):
            mock_op_dependencies['inventario_controller'].verificar_stock_para_op.return_value = {'success': True, 'data': {'insumos_faltantes': []}}
            mock_op_dependencies['inventario_controller'].reservar_stock_insumos_para_op.return_value = {'success': True}
            mock_op_dependencies['op_model'].cambiar_estado.return_value = {'success': True}

            # Act
            response, status_code = op_controller.aprobar_orden(orden_id, usuario_id)

            # Assert
            assert status_code == 200
            assert response['success']
            assert "La orden está 'LISTA PARA PRODUCIR'" in response['message']
            mock_op_dependencies['inventario_controller'].reservar_stock_insumos_para_op.assert_called_once()
            mock_op_dependencies['op_model'].cambiar_estado.assert_called_once_with(orden_id, 'LISTA PARA PRODUCIR')

    # Test para aprobar una orden que genera una OC
    def test_aprobar_orden_genera_oc(self, op_controller, mock_op_dependencies):
        # Arrange
        orden_id = 1
        usuario_id = 1
        orden_produccion_data = {
            'id': orden_id,
            'estado': 'PENDIENTE',
            'producto_id': 1,
            'cantidad_planificada': 100
        }
        insumos_faltantes = [{'insumo_id': 1, 'cantidad_faltante': 10}]

        with patch.object(op_controller, 'obtener_orden_por_id', return_value={'success': True, 'data': orden_produccion_data}):
            mock_op_dependencies['inventario_controller'].verificar_stock_para_op.return_value = {'success': True, 'data': {'insumos_faltantes': insumos_faltantes}}
            
            # Mock para el helper que genera la OC
            with patch.object(op_controller, '_generar_orden_de_compra_automatica', return_value={'success': True, 'data': {'id': 20, 'codigo_oc': 'OC-123'}}) as mock_generar_oc:
                mock_op_dependencies['op_model'].cambiar_estado.return_value = {'success': True}
                mock_op_dependencies['op_model'].update.return_value = {'success': True}

                # Act
                response, status_code = op_controller.aprobar_orden(orden_id, usuario_id)

                # Assert
                assert status_code == 200
                assert response['success']
                assert "Se generó OC y la OP está 'En Espera'" in response['message']
                mock_generar_oc.assert_called_once_with(insumos_faltantes, usuario_id, orden_id)
                mock_op_dependencies['op_model'].cambiar_estado.assert_called_once_with(orden_id, 'EN ESPERA')

    # Test para cancelar (rechazar) una orden de producción
    def test_cancelar_orden_produccion(self, op_controller, mock_op_dependencies):
        # Arrange
        orden_id = 1
        motivo = "Cancelación de prueba"
        
        mock_op_dependencies['op_model'].cambiar_estado.return_value = {'success': True}

        # Act
        response = op_controller.rechazar_orden(orden_id, motivo)

        # Assert
        assert response['success']
        mock_op_dependencies['op_model'].cambiar_estado.assert_called_once_with(
            orden_id, 
            'CANCELADA', 
            observaciones=f"Rechazada: {motivo}"
        )
