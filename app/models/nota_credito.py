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
            res = self.db.table('notas_credito_items').select(
                '*, productos:producto_id(nombre), lotes_productos:lote_producto_id(numero_lote)'
            ).eq('nota_credito_id', nc_id).execute()
            
            return res.data if res.data else []
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error al obtener items de NC {nc_id}: {e}", exc_info=True)
            return []
    
    def create_with_items(self, nc_data, items_data):
        try:
            # Crear la nota de crédito principal
            nc_res = self.db.table(self.get_table_name()).insert(nc_data).execute()
            if not nc_res.data:
                return {'success': False, 'error': 'No se pudo crear la Nota de Crédito.'}
            
            nueva_nc = nc_res.data[0]
            
            # Preparar y crear los items asociados
            for item in items_data:
                item['nota_credito_id'] = nueva_nc['id']
            
            items_res = self.db.table('notas_credito_items').insert(items_data).execute()
            if not items_res.data:
                # Opcional: rollback o marcar la NC como inválida si los items fallan
                return {'success': False, 'error': 'NC creada pero fallaron los items.'}

            return {'success': True, 'data': nueva_nc}
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error en create_with_items: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}