import pytest
from unittest.mock import MagicMock, patch
from app.controllers.control_calidad_insumo_controller import ControlCalidadInsumoController
from app import create_app

@pytest.fixture
def app():
    app = create_app()
    app.config.update({"TESTING": True, "JWT_SECRET_KEY": "test-secret", "WTF_CSRF_ENABLED": False})
    yield app

@pytest.fixture
def mock_cc_dependencies():
    with patch('app.controllers.control_calidad_insumo_controller.ControlCalidadInsumoModel') as MockCCModel, \
         patch('app.controllers.control_calidad_insumo_controller.InventarioModel') as MockInventarioModel, \
         patch('app.controllers.control_calidad_insumo_controller.OrdenCompraController') as MockOCController, \
         patch('app.controllers.control_calidad_insumo_controller.InsumoController') as MockInsumoController:

        yield {
            "cc_model": MockCCModel.return_value,
            "inventario_model": MockInventarioModel.return_value,
            "oc_controller": MockOCController.return_value,
            "insumo_controller": MockInsumoController.return_value,
        }

@pytest.fixture
def cc_controller(mock_cc_dependencies):
    controller = ControlCalidadInsumoController()
    controller.model = mock_cc_dependencies['cc_model']
    controller.inventario_model = mock_cc_dependencies['inventario_model']
    controller.orden_compra_controller = mock_cc_dependencies['oc_controller']
    controller.insumo_controller = mock_cc_dependencies['insumo_controller']
    return controller

class TestControlCalidadInsumoController:

    def test_procesar_inspeccion_aceptar_lote_completo(self, cc_controller, mock_cc_dependencies):
        lote_id = "1"
        usuario_id = 1
        lote_data = {'id_lote': lote_id, 'id_insumo': 100, 'cantidad_actual': 50.0, 'estado': 'EN REVISION'}
        form_data = {'cantidad': '50.0', 'comentarios': 'Todo en orden'}
        
        mock_cc_dependencies['inventario_model'].find_by_id.return_value = {'success': True, 'data': lote_data}
        mock_cc_dependencies['inventario_model'].update.return_value = {'success': True, 'data': {**lote_data, 'estado': 'disponible'}}
        mock_cc_dependencies['insumo_controller'].actualizar_stock_insumo.return_value = ({'success': True}, 200)

        with patch.object(cc_controller, '_extraer_oc_id_de_lote', return_value=99), \
             patch.object(cc_controller, '_verificar_y_finalizar_orden_si_corresponde') as mock_verificar:
            response, status_code = cc_controller.procesar_inspeccion(lote_id, 'Aceptar', form_data, None, usuario_id)

            assert status_code == 200
            assert response['success']
            mock_verificar.assert_called_once_with(99, usuario_id)

    def test_procesar_inspeccion_rechazar_parcialmente(self, cc_controller, mock_cc_dependencies):
        lote_id = "1"
        usuario_id = 1
        lote_data = {'id_lote': lote_id, 'id_insumo': 100, 'cantidad_actual': 50.0, 'estado': 'EN REVISION'}
        form_data = {'cantidad': '10.0', 'comentarios': '10 unidades defectuosas', 'resultado_inspeccion': 'DAÑADO'}
        
        mock_cc_dependencies['inventario_model'].find_by_id.return_value = {'success': True, 'data': lote_data}
        mock_cc_dependencies['inventario_model'].update.return_value = {'success': True, 'data': {**lote_data, 'cantidad_actual': 40.0}}
        mock_cc_dependencies['insumo_controller'].actualizar_stock_insumo.return_value = ({'success': True}, 200)

        with patch.object(cc_controller, '_extraer_oc_id_de_lote', return_value=99), \
             patch.object(cc_controller, '_verificar_y_finalizar_orden_si_corresponde') as mock_verificar, \
             patch.object(cc_controller, '_subir_foto_y_obtener_url', return_value=None):
            
            response, status_code = cc_controller.procesar_inspeccion(lote_id, 'Rechazar', form_data, None, usuario_id)

            assert status_code == 200
            assert response['success']
            mock_cc_dependencies['cc_model'].create_registro.assert_called_once()
            mock_verificar.assert_called_once_with(99, usuario_id)

    def test_finalizar_oc_si_todos_lotes_procesados(self, cc_controller, mock_cc_dependencies):
        orden_compra_id = 99
        usuario_id = 1
        mock_cc_dependencies['oc_controller'].get_orden.return_value = ({'success': True, 'data': {'id': orden_compra_id, 'codigo_oc': 'OC-TEST'}}, 200)
        lotes_procesados = [{'id_lote': 1, 'estado': 'disponible'}]
        mock_cc_dependencies['inventario_model'].find_all.return_value = {'success': True, 'data': lotes_procesados}

        cc_controller._verificar_y_finalizar_orden_si_corresponde(orden_compra_id, usuario_id)

        mock_cc_dependencies['oc_controller'].finalizar_proceso_recepcion.assert_called_once_with(orden_compra_id, usuario_id)

    def test_no_finalizar_oc_si_quedan_lotes_pendientes(self, cc_controller, mock_cc_dependencies):
        orden_compra_id = 100
        usuario_id = 1
        mock_cc_dependencies['oc_controller'].get_orden.return_value = ({'success': True, 'data': {'id': orden_compra_id, 'codigo_oc': 'OC-PENDIENTE'}}, 200)
        lotes_pendientes = [{'id_lote': 1, 'estado': 'EN REVISION'}]
        mock_cc_dependencies['inventario_model'].find_all.return_value = {'success': True, 'data': lotes_pendientes}

        cc_controller._verificar_y_finalizar_orden_si_corresponde(orden_compra_id, usuario_id)

        mock_cc_dependencies['oc_controller'].finalizar_proceso_recepcion.assert_not_called()

