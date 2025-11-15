# Este archivo hace que el directorio 'models' sea un paquete de Python.

from .orden_produccion import OrdenProduccionModel
from .control_calidad_producto import ControlCalidadProducto
from .registro_desperdicio_lote_producto_model import RegistroDesperdicioLoteProductoModel
from .receta import RecetaModel
from .insumo_inventario import InsumoInventarioModel
from .reserva_insumo import ReservaInsumoModel

__all__ = [
    'OrdenProduccionModel',
    'ControlCalidadProducto',
    'RegistroDesperdicioLoteProductoModel',
    'RecetaModel',
    'InsumoInventarioModel',
    'ReservaInsumoModel'
]
