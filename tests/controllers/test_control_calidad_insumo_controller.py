import pytest
from unittest.mock import MagicMock, patch
from app.controllers.control_calidad_insumo_controller import ControlCalidadInsumoController
from app import create_app

@pytest.fixture
def app():
    """Crea y configura una nueva instancia de la aplicación para cada prueba."""
    app = create_app()
    app.config.update({
        "TESTING": True,
        "JWT_SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False
    })
    yield app

@pytest.fixture
def mock_cc_dependencies():
    """Fixture para mockear todas las dependencias externas de ControlCalidadInsumoController."""
    with patch('app.controllers.control_calidad_insumo_controller.ControlCalidadInsumoModel') as MockCCModel, \
         patch('app.controllers.control_calidad_insumo_controller.InventarioModel') as MockInventarioModel, \
         patch('app.controllers.control_calidad_insumo_controller.OrdenCompraController') as MockOCController:

        yield {
            "cc_model": MockCCModel.return_value,
            "inventario_model": MockInventarioModel.return_value,
            "oc_controller": MockOCController.return_value,
        }

@pytest.fixture
def cc_controller(mock_cc_dependencies):
    """Fixture para crear una instancia de ControlCalidadInsumoController con dependencias mockeadas."""
    controller = ControlCalidadInsumoController()
    controller.model = mock_cc_dependencies['cc_model']
    controller.inventario_model = mock_cc_dependencies['inventario_model']
    controller.orden_compra_controller = mock_cc_dependencies['oc_controller']
    return controller

class TestControlCalidadInsumoController:

    # Test para Aceptar un lote completo, cambiando su estado a 'disponible'
    def test_procesar_inspeccion_aceptar_lote_completo(self, cc_controller, mock_cc_dependencies):
        # Arrange
        lote_id = "1"
        usuario_id = 1
        lote_data = {'id_lote': lote_id, 'id_insumo': 100, 'cantidad_actual': 50.0, 'estado': 'EN REVISION'}
        form_data = {'cantidad': '50.0', 'comentarios': 'Todo en orden'}
        
        mock_cc_dependencies['inventario_model'].find_by_id.return_value = {'success': True, 'data': lote_data}
        mock_cc_dependencies['inventario_model'].update.return_value = {'success': True, 'data': {**lote_data, 'estado': 'disponible'}}

        # Act
        response, status_code = cc_controller.procesar_inspeccion(lote_id, 'Aceptar', form_data, None, usuario_id)

        # Assert
        assert status_code == 200
        assert response['success']
        assert response['data']['estado'] == 'disponible'
        # Verificar que se llamó a la actualización del lote con el estado 'disponible'
        mock_cc_dependencies['inventario_model'].update.assert_called_once_with(lote_id, {'estado': 'disponible'}, 'id_lote')
        # Verificar que se recalcula el stock del insumo
        mock_cc_dependencies['inventario_model'].recalcular_stock_para_insumo.assert_called_once_with(100)

    # Test para Rechazar una parte de un lote
    def test_procesar_inspeccion_rechazar_parcialmente(self, cc_controller, mock_cc_dependencies):
        # Arrange
        lote_id = "1"
        usuario_id = 1
        lote_data = {'id_lote': lote_id, 'id_insumo': 100, 'cantidad_actual': 50.0, 'estado': 'EN REVISION'}
        form_data = {'cantidad': '10.0', 'comentarios': '10 unidades defectuosas'}
        
        mock_cc_dependencies['inventario_model'].find_by_id.return_value = {'success': True, 'data': lote_data}
        mock_cc_dependencies['inventario_model'].update.return_value = {'success': True, 'data': {**lote_data, 'cantidad_actual': 40.0}}
        # Mock para la extracción de la OC ID
        with patch.object(cc_controller, '_extraer_oc_id_de_lote', return_value=99):
            # Act
            response, status_code = cc_controller.procesar_inspeccion(lote_id, 'Rechazar', form_data, None, usuario_id)

            # Assert
            assert status_code == 200
            assert response['success']
            # Verificar que se actualizó la cantidad del lote
            mock_cc_dependencies['inventario_model'].update.assert_called_once_with(
                lote_id, {'cantidad_actual': 40.0, 'estado': 'RECHAZADO'}, 'id_lote'
            )
            # Verificar que se creó un registro de C.C.
            mock_cc_dependencies['cc_model'].create_registro.assert_called_once()

    # Test para validar que no se puede procesar una cantidad mayor a la del lote
    def test_procesar_inspeccion_cantidad_invalida(self, cc_controller, mock_cc_dependencies):
        # Arrange
        lote_id = "1"
        usuario_id = 1
        lote_data = {'id_lote': lote_id, 'cantidad_actual': 50.0}
        form_data = {'cantidad': '60.0'} # Cantidad mayor a la existente
        
        mock_cc_dependencies['inventario_model'].find_by_id.return_value = {'success': True, 'data': lote_data}

        # Act
        response, status_code = cc_controller.procesar_inspeccion(lote_id, 'Aceptar', form_data, None, usuario_id)

        # Assert
        assert status_code == 400
        assert not response['success']
        assert 'La cantidad a procesar no es válida' in response['error']

    # Test para verificar que la OC se cierra si todos sus lotes han sido procesados
    def test_cerrar_oc_si_todos_lotes_procesados(self, cc_controller, mock_cc_dependencies):
        # Arrange
        orden_compra_id = 99
        codigo_oc = 'OC-FINALIZADA'
        
        # Mock para la OC
        mock_cc_dependencies['oc_controller'].get_orden.return_value = (
            {'success': True, 'data': {'id': orden_compra_id, 'codigo_oc': codigo_oc}}, 200
        )
        # Mock para los lotes: ninguno está 'EN REVISION'
        lotes_procesados = [
            {'id_lote': 1, 'estado': 'disponible'},
            {'id_lote': 2, 'estado': 'RECHAZADO'}
        ]
        mock_cc_dependencies['inventario_model'].get_all_lotes_for_view.return_value = {'success': True, 'data': lotes_procesados}

        # Act
        cc_controller._verificar_y_cerrar_orden_si_completa(orden_compra_id)

        # Assert
        # Verificar que se llamó al método para marcar la OC como cerrada
        mock_cc_dependencies['oc_controller'].marcar_como_cerrada.assert_called_once_with(orden_compra_id)

    # Test para verificar que la OC NO se cierra si aún quedan lotes pendientes
    def test_no_cerrar_oc_si_quedan_lotes_pendientes(self, cc_controller, mock_cc_dependencies):
        # Arrange
        orden_compra_id = 100
        codigo_oc = 'OC-PENDIENTE'
        
        mock_cc_dependencies['oc_controller'].get_orden.return_value = (
            {'success': True, 'data': {'id': orden_compra_id, 'codigo_oc': codigo_oc}}, 200
        )
        # Mock para los lotes: uno todavía está 'EN REVISION'
        lotes_pendientes = [
            {'id_lote': 1, 'estado': 'disponible'},
            {'id_lote': 2, 'estado': 'EN REVISION'}
        ]
        mock_cc_dependencies['inventario_model'].get_all_lotes_for_view.return_value = {'success': True, 'data': lotes_pendientes}

        # Act
        cc_controller._verificar_y_cerrar_orden_si_completa(orden_compra_id)

        # Assert
        # Verificar que NO se llamó al método para marcar la OC como cerrada
        mock_cc_dependencies['oc_controller'].marcar_como_cerrada.assert_not_called()
