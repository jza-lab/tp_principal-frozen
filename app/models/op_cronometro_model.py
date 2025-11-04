from app.models.base_model import BaseModel
from typing import Dict, Any, Optional

class OpCronometroModel(BaseModel):
    """
    Modelo para gestionar los intervalos de tiempo del cronómetro de las órdenes de producción.
    """

    def get_table_name(self) -> str:
        """Devuelve el nombre de la tabla de la base de datos."""
        return 'op_cronometro'

    def get_schema_name(self) -> str:
        """Devuelve el nombre del esquema de la base de datos."""
        return 'mes_kanban'

    def _get_query_builder(self):
        """
        Sobrescribe el método base para especificar el esquema 'mes_kanban'.
        """
        return self.db.schema(self.get_schema_name()).table(self.table_name)

    def create_intervalo(self, op_id: int, start_time: str) -> Dict:
        """
        Crea un nuevo registro de intervalo de tiempo para una orden de producción.
        """
        data = {
            'op_id': op_id,
            'start_time': start_time
        }
        return self.create(data)

    def update_intervalo(self, intervalo_id: int, end_time: str) -> Dict:
        """
        Actualiza un registro de intervalo de tiempo con la hora de finalización.
        """
        data = {'end_time': end_time}
        return self.update(intervalo_id, data, 'id')

    def get_ultimo_intervalo_abierto(self, op_id: int) -> Dict:
        """
        Obtiene el último intervalo de tiempo que no tiene un end_time.
        """
        try:
            result = self._get_query_builder() \
                .select('*') \
                .eq('op_id', op_id) \
                .is_('end_time', None) \
                .order('start_time', desc=True) \
                .limit(1) \
                .execute()
            
            if result.data:
                return {'success': True, 'data': result.data[0]}
            return {'success': True, 'data': None}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_intervalos_por_op(self, op_id: int) -> Dict:
        """
        Obtiene todos los intervalos de tiempo para una orden de producción.
        """
        try:
            result = self._get_query_builder() \
                .select('*') \
                .eq('op_id', op_id) \
                .execute()
            
            return {'success': True, 'data': result.data}
        except Exception as e:
            return {'success': False, 'error': str(e)}

