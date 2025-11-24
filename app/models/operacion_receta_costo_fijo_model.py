from app.models.base_model import BaseModel
from typing import Dict, List

class OperacionRecetaCostoFijoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de costos fijos por operación de receta.
    """

    def get_table_name(self) -> str:
        return "operacion_receta_costos_fijos"

    def find_by_operacion_id(self, operacion_receta_id: int) -> Dict:
        """
        Obtiene todos los costos fijos asignados a una operación de receta.
        """
        return self.find_all(filters={'operacion_receta_id': operacion_receta_id})

    def bulk_create_for_operacion(self, operacion_receta_id: int, costo_fijo_ids: List[int]) -> Dict:
        """
        Crea múltiples asignaciones de costos fijos para una operación de receta.
        """
        records = [
            {'operacion_receta_id': operacion_receta_id, 'costo_fijo_id': cf_id}
            for cf_id in costo_fijo_ids
        ]

        if not records:
            return {'success': True, 'data': []}

        try:
            result = self.db.table(self.get_table_name()).insert(records).execute()
            if result.data:
                return {'success': True, 'data': result.data}
            return {'success': False, 'error': 'No se pudieron crear los registros.'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def delete_by_operacion_id(self, operacion_receta_id: int) -> Dict:
        """
        Elimina todas las asignaciones de costos fijos para una operación de receta.
        """
        try:
            self.db.table(self.get_table_name()).delete().eq('operacion_receta_id', operacion_receta_id).execute()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
