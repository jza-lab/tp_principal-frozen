import pytest
from unittest.mock import MagicMock, patch, ANY
from app.controllers.orden_produccion_controller import OrdenProduccionController
from datetime import date

@pytest.fixture
def mock_op_dependencies():
    with patch('app.controllers.orden_produccion_controller.OrdenProduccionModel') as MockOPModel, \
         patch('app.controllers.orden_produccion_controller.LoteProductoController') as MockLoteController, \
         patch('app.controllers.orden_produccion_controller.PedidoModel') as MockPedidoModel, \
         patch('app.controllers.orden_produccion_controller.RecetaModel') as MockRecetaModel:
        yield {
            "op_model": MockOPModel.return_value,
            "lote_controller": MockLoteController.return_value,
            "pedido_model": MockPedidoModel.return_value,
            "receta_model": MockRecetaModel.return_value
        }

@pytest.fixture
def op_controller(mock_op_dependencies):
    controller = OrdenProduccionController()
    controller.model = mock_op_dependencies['op_model']
    controller.lote_producto_controller = mock_op_dependencies['lote_controller']
    controller.pedido_model = mock_op_dependencies['pedido_model']
    controller.receta_model = mock_op_dependencies['receta_model']
    return controller

class TestOrdenProduccionController:
    def test_crear_orden_produccion_exitoso(self, op_controller, mock_op_dependencies):
        form_data = {'producto_id': 1, 'cantidad': 100, 'fecha_meta': '2025-12-31'}
        usuario_id = 1
        mock_op_dependencies['receta_model'].find_all.return_value = {'success': True, 'data': [{'id': 1}]}
        mock_op_dependencies['op_model'].create.return_value = {'success': True, 'data': {'id': 1}}
        response = op_controller.crear_orden(form_data, usuario_id)
        assert response['success']

    @patch('app.controllers.orden_produccion_controller.InventarioController')
    def test_aprobar_orden_con_stock_disponible(self, MockInventarioController, op_controller):
        orden_id, usuario_id = 1, 1
        orden_data = {'id': orden_id, 'estado': 'PENDIENTE'}
        mock_inv_instance = MockInventarioController.return_value
        op_controller.inventario_controller = mock_inv_instance
        with patch.object(op_controller, '_validar_estado_para_aprobacion', return_value=(orden_data, None)):
            mock_inv_instance.verificar_stock_para_op.return_value = {'success': True, 'data': {'insumos_faltantes': []}}
            mock_inv_instance.reservar_stock_insumos_para_op.return_value = {'success': True}
            op_controller.model.cambiar_estado.return_value = {'success': True}
            response, status_code = op_controller.aprobar_orden(orden_id, usuario_id)
            assert status_code == 200
            assert response['success']

    @patch('app.controllers.orden_produccion_controller.InventarioController')
    def test_aprobar_orden_sin_stock_genera_oc(self, MockInventarioController, op_controller):
        orden_id, usuario_id = 1, 1
        orden_data = {'id': orden_id, 'estado': 'PENDIENTE'}
        mock_inv_instance = MockInventarioController.return_value
        op_controller.inventario_controller = mock_inv_instance
        with patch.object(op_controller, '_validar_estado_para_aprobacion', return_value=(orden_data, None)):
            mock_inv_instance.verificar_stock_para_op.return_value = {'success': True, 'data': {'insumos_faltantes': [{'id': 1}]}}
            with patch.object(op_controller, '_generar_orden_de_compra_automatica', return_value={'success': True, 'data': {}}) as mock_generar:
                op_controller.model.cambiar_estado.return_value = {'success': True}
                response, status_code = op_controller.aprobar_orden(orden_id, usuario_id)
                assert status_code == 200
                assert response['success']
                mock_generar.assert_called_once()

    def test_completar_orden_genera_lote(self, op_controller, mock_op_dependencies):
        orden_id = 1
        orden_data = {'id': orden_id, 'estado': 'CONTROL_DE_CALIDAD', 'producto_id': 1, 'cantidad_planificada': 100}
        mock_op_dependencies['op_model'].get_one_enriched.return_value = {'success': True, 'data': orden_data}
        mock_op_dependencies['pedido_model'].find_all_items.return_value = {'success': True, 'data': []}
        mock_op_dependencies['lote_controller'].crear_lote_desde_formulario.return_value = ({'success': True, 'data': {'numero_lote': 'LOTE-50'}}, 201)
        mock_op_dependencies['op_model'].cambiar_estado.return_value = {'success': True}
        with patch('app.controllers.orden_produccion_controller.PedidoController'):
            response, status_code = op_controller.cambiar_estado_orden(orden_id, 'COMPLETADA')
            assert status_code == 200
            assert response['success']

    def test_reportar_avance_y_finalizar(self, op_controller, mock_op_dependencies):
        orden_id = 1
        usuario_id = 1
        orden_data = {'cantidad_planificada': 100.0, 'cantidad_producida': 80.0}
        form_data = {'cantidad_buena': '20.0', 'finalizar_orden': True}
        mock_op_dependencies['op_model'].find_by_id.return_value = {'success': True, 'data': orden_data}
        response, status_code = op_controller.reportar_avance(orden_id, form_data, usuario_id)
        assert status_code == 200
        assert response['success']
