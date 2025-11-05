import pytest
from app.utils.estados import (
    traducir_a_int,
    traducir_a_cadena,
    OV_MAP_STRING_TO_INT,
    OC_MAP_STRING_TO_INT,
    OP_MAP_STRING_TO_INT
)

# Construir los diccionarios inversos dinámicamente
OV_MAP_INT_TO_STR = {v: k for k, v in OV_MAP_STRING_TO_INT.items()}
OC_MAP_INT_TO_STR = {v: k for k, v in OC_MAP_STRING_TO_INT.items()}
OP_MAP_INT_TO_STR = {v: k for k, v in OP_MAP_STRING_TO_INT.items()}

class TestEstados:
    @pytest.mark.parametrize("estado_str, estado_int", OV_MAP_STRING_TO_INT.items())
    def test_traducir_a_entero_ov(self, estado_str, estado_int):
        assert traducir_a_int(estado_str, 'OV') == estado_int

    @pytest.mark.parametrize("estado_int, estado_str", OV_MAP_INT_TO_STR.items())
    def test_traducir_a_cadena_ov(self, estado_int, estado_str):
        assert traducir_a_cadena(estado_int, 'OV') == estado_str

    @pytest.mark.parametrize("estado_str, estado_int", OC_MAP_STRING_TO_INT.items())
    def test_traducir_a_entero_oc(self, estado_str, estado_int):
        assert traducir_a_int(estado_str, 'OC') == estado_int

    @pytest.mark.parametrize("estado_int, estado_str", OC_MAP_INT_TO_STR.items())
    def test_traducir_a_cadena_oc(self, estado_int, estado_str):
        assert traducir_a_cadena(estado_int, 'OC') == estado_str

    @pytest.mark.parametrize("estado_str, estado_int", OP_MAP_STRING_TO_INT.items())
    def test_traducir_a_entero_op(self, estado_str, estado_int):
        assert traducir_a_int(estado_str, 'OP') == estado_int

    # CORRECCIÓN: Usar un test parametrizado que refleje la lógica real
    @pytest.mark.parametrize("estado_int, estado_str", OP_MAP_INT_TO_STR.items())
    def test_traducir_a_cadena_op(self, estado_int, estado_str):
        assert traducir_a_cadena(estado_int, 'OP') == estado_str

    def test_valores_invalidos(self):
        assert traducir_a_int('ESTADO_INEXISTENTE', 'OV') is None
        assert traducir_a_cadena(9999, 'OC') is None
