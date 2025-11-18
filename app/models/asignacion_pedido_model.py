from app.models.base_model import BaseModel

class AsignacionPedidoModel(BaseModel):
    """
    Modelo para registrar las asignaciones de producción desde una Orden de Producción
    hacia un ítem de pedido de cliente específico.

    Esta tabla actúa como un registro de trazabilidad para saber cuántas unidades
    de una OP consolidada se han destinado a cada pedido individual.
    """

    def get_table_name(self):
        return "asignaciones_pedidos"

    def __init__(self):
        super().__init__()
