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

    def find_all_with_pedido_id(self, filters: dict) -> dict:
        """
        Busca todas las asignaciones que coinciden con los filtros y, crucialmente,
        se une con la tabla `pedido_items` para obtener el `pedido_id` de cada asignación.
        """
        try:
            query = self.db.table(self.get_table_name()).select(
                '*, item:pedido_items(pedido_id)'
            )
            for key, value in filters.items():
                query = query.eq(key, value)
            
            result = query.execute()

            if result.data:
                # Aplanar la respuesta para que sea más fácil de usar en el controlador
                processed_data = []
                for row in result.data:
                    if row.get('item'):
                        row['pedido_id'] = row['item'].get('pedido_id')
                    processed_data.append(row)
                return {'success': True, 'data': processed_data}
            
            return {'success': True, 'data': []}
        except Exception as e:
            return {'success': False, 'error': str(e)}
