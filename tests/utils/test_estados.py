import pytest
from app.utils.estados import (
    traducir_a_int,
    traducir_a_cadena,
    OV_MAP_STRING_TO_INT,
    OP_MAP_STRING_TO_INT,
    OC_MAP_STRING_TO_INT,
)

class TestEstados:
    # Pruebas para traducir de cadena a entero
    @pytest.mark.parametrize("estado_str, estado_int", OV_MAP_STRING_TO_INT.items())
    def test_traducir_a_int_ov(self, estado_str, estado_int):
        assert traducir_a_int(estado_str, 'OV') == estado_int

    @pytest.mark.parametrize("estado_str, estado_int", OP_MAP_STRING_TO_INT.items())
    def test_traducir_a_int_op(self, estado_str, estado_int):
        assert traducir_a_int(estado_str, 'OP') == estado_int

    @pytest.mark.parametrize("estado_str, estado_int", OC_MAP_STRING_TO_INT.items())
    def test_traducir_a_int_oc(self, estado_str, estado_int):
        assert traducir_a_int(estado_str, 'OC') == estado_int

    def test_traducir_a_int_invalido(self):
        assert traducir_a_int('ESTADO_INEXISTENTE', 'OV') is None
        assert traducir_a_int('PENDIENTE', 'TIPO_INVALIDO') is None

    # Pruebas para traducir de entero a cadena
    @pytest.mark.parametrize("estado_str, estado_int", OV_MAP_STRING_TO_INT.items())
    def test_traducir_a_cadena_ov(self, estado_str, estado_int):
        assert traducir_a_cadena(estado_int, 'OV') == estado_str

    @pytest.mark.parametrize("estado_str, estado_int", OP_MAP_STRING_TO_INT.items())
    def test_traducir_a_cadena_op(self, estado_str, estado_int):
        assert traducir_a_cadena(estado_int, 'OP') == estado_str

    @pytest.mark.parametrize("estado_str, estado_int", OC_MAP_STRING_TO_INT.items())
    def test_traducir_a_cadena_oc(self, estado_str, estado_int):
        assert traducir_a_cadena(estado_int, 'OC') == estado_str

    def test_traducir_a_cadena_invalido(self):
        assert traducir_a_cadena(9999, 'OV') is None
        assert traducir_a_cadena(10, 'TIPO_INVALIDO') is None
