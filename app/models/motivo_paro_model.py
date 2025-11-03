from .base_model import BaseModel
from typing import Dict, List
import logging 

class MotivoParoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de motivos de paro en la base de datos.
    """
    # --- 2. Añadir constructor para inicializar el logger ---
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
    # --------------------------------------------------------

    def get_table_name(self):
        return "motivos_paro"

    def get_schema_name(self):
        return "mes_kanban"

    def find_all(self, filters: Dict = None, order_by: str = 'id.asc') -> Dict[str, List[Dict]]:
        """
        Sobrescribe el método base para asegurar que la consulta se realiza
        correctamente sobre la tabla con esquema.
        """
        try:
            # --- 3. Corregir la forma de llamar a la tabla con esquema ---
            table_with_schema = f"{self.get_schema_name()}.{self.get_table_name()}"
            query = self.db.table(table_with_schema).select("*")
            
            # Aplicar filtros si se proporcionan
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            
            # Aplicar ordenamiento
            if order_by:
                col,_ , order = order_by.partition('.')
                query = query.order(col, desc= (order.lower() == 'desc'))

            response = query.execute()
            
            return {'success': True, 'data': response.data}
        except Exception as e:
            self.logger.error(f"Error en find_all para {self.get_table_name()}: {e}", exc_info=True)
            return {'success': False, 'error': str(e), 'data': []}
