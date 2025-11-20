from app.models.base_model import BaseModel
from typing import Dict, List

class OperacionRecetaRolModel(BaseModel):
    """
    Modelo para interactuar con la tabla de roles por operacion de receta.
    """

    def get_table_name(self) -> str:
        """
        Retorna el nombre de la tabla específica para este modelo.
        """
        return "operacion_receta_roles"

    def find_by_operacion_id(self, operacion_receta_id: int) -> Dict:
        """
        Obtiene todos los roles asignados a una operacion de receta específica.
        """
        return self.find_all(filters={'operacion_receta_id': operacion_receta_id})

    def bulk_create_for_operacion(self, operacion_receta_id: int, rol_ids: List[int]) -> Dict:
        """
        Crea múltiples asignaciones de roles para una operacion de receta.
        """
        records = [
            {'operacion_receta_id': operacion_receta_id, 'rol_id': rol_id}
            for rol_id in rol_ids
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
        Elimina todas las asignaciones de roles para una operacion de receta.
        """
        try:
            self.db.table(self.get_table_name()).delete().eq('operacion_receta_id', operacion_receta_id).execute()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}