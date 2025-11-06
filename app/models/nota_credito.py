from .base_model import BaseModel

class NotaCreditoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de notas_credito.
    """
    def __init__(self):
        super().__init__()

    @classmethod
    def get_table_name(cls):
        return "notas_credito"

    @classmethod
    def get_id_column(cls):
        return "id"
    
    def get_items_by_nc_id(self, nc_id):
        """
        Obtiene los items detallados de una nota de crédito específica.
        """
        try:
            res = self.db.table('nota_credito_items').select(
                '*, productos:producto_id(nombre), lotes_productos:lote_producto_id(numero_lote)'
            ).eq('nota_credito_id', nc_id).execute()
            
            return res.data if res.data else []
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error al obtener items de NC {nc_id}: {e}", exc_info=True)
            return []