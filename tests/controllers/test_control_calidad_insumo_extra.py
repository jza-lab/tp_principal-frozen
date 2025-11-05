import io
from unittest.mock import patch, MagicMock

import pytest

from app.controllers.control_calidad_insumo_controller import ControlCalidadInsumoController


@pytest.fixture
def mock_cc_dependencies():
    with patch('app.controllers.control_calidad_insumo_controller.ControlCalidadInsumoModel') as MockCCModel, \
         patch('app.controllers.control_calidad_insumo_controller.InventarioModel') as MockInventarioModel, \
         patch('app.controllers.control_calidad_insumo_controller.OrdenCompraController') as MockOCController:

        yield {
            'cc_model': MockCCModel.return_value,
            'inventario_model': MockInventarioModel.return_value,
            'oc_controller': MockOCController.return_value,
        }


@pytest.fixture
def cc_controller(mock_cc_dependencies):
    controller = ControlCalidadInsumoController()
    controller.model = mock_cc_dependencies['cc_model']
    controller.inventario_model = mock_cc_dependencies['inventario_model']
    controller.orden_compra_controller = mock_cc_dependencies['oc_controller']
    return controller


def make_file(filename='foto.jpg', content=b'JPEGDATA', mimetype='image/jpeg'):
    f = io.BytesIO(content)
    f.filename = filename
    f.mimetype = mimetype
    return f


def test_subir_foto_y_obtener_url_success(cc_controller, mock_cc_dependencies):
    # Prepare a fake DB client with storage behavior
    fake_storage = MagicMock()
    fake_storage.upload.return_value = MagicMock(status_code=200, json=lambda: {})
    fake_storage.get_public_url.return_value = 'https://supabase.storage/foto.jpg'

    fake_db = MagicMock()
    fake_db.storage.from_.return_value = fake_storage

    with patch('app.controllers.control_calidad_insumo_controller.Database') as MockDB:
        MockDB.return_value.client = fake_db
        file = make_file()
        url = cc_controller._subir_foto_y_obtener_url(file, lote_id=123)
        assert url == 'https://supabase.storage/foto.jpg'
        fake_storage.upload.assert_called_once()
        fake_storage.get_public_url.assert_called_once()


def test_subir_foto_y_obtener_url_upload_failure(cc_controller, mock_cc_dependencies):
    fake_storage = MagicMock()
    fake_storage.upload.return_value = MagicMock(status_code=500, json=lambda: {'message': 'err'})
    fake_db = MagicMock()
    fake_db.storage.from_.return_value = fake_storage

    with patch('app.controllers.control_calidad_insumo_controller.Database') as MockDB:
        MockDB.return_value.client = fake_db
        file = make_file()
        url = cc_controller._subir_foto_y_obtener_url(file, lote_id=1)
        assert url is None


def test_subir_foto_y_obtener_url_no_file(cc_controller):
    assert cc_controller._subir_foto_y_obtener_url(None, lote_id=1) is None


def test_procesar_inspeccion_update_fails_returns_500(cc_controller, mock_cc_dependencies):
    lote_id = 'L1'
    lote_data = {'id_lote': lote_id, 'id_insumo': 5, 'cantidad_actual': 10.0}
    mock_cc_dependencies['inventario_model'].find_by_id.return_value = {'success': True, 'data': lote_data}
    # Simulate update failure
    mock_cc_dependencies['inventario_model'].update.return_value = {'success': False, 'error': 'db error'}

    response, status_code = cc_controller.procesar_inspeccion(lote_id, 'Aceptar', {'cantidad': '10'}, None, usuario_id=1)
    assert status_code == 500 or not response['success']


def test_extraer_oc_id_de_lote_handles_missing_codigo(cc_controller, mock_cc_dependencies):
    lote = {'id_lote': 'L2', 'documento_ingreso': None}
    # Should not raise and return None
    assert cc_controller._extraer_oc_id_de_lote(lote) is None
