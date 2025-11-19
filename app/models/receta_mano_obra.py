from app.models.base_model import BaseModel
from typing import List, Dict

class RecetaManoObraModel(BaseModel):
    """
    Modelo para interactuar con la tabla receta_mano_obra.
    """
    def get_table_name(self):
        return "receta_mano_obra"

    def find_by_receta_id(self, receta_id: int) -> Dict:
        """
        Obtiene todas las asignaciones de mano de obra para una receta específica.
        La unión con los nombres de los roles se hará en el controlador.
        """
        return self.find_all(filters={'receta_id': receta_id})

    def delete_by_receta_id(self, receta_id: int) -> Dict:
        """
        Elimina todas las asignaciones de mano de obra para una receta.
        """
        try:
            self.db.table(self.get_table_name()).delete().eq('receta_id', receta_id).execute()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def bulk_create_for_receta(self, receta_id: int, mano_de_obra: List[Dict]) -> Dict:
        """
        Crea múltiples asignaciones de mano de obra para una receta.
        'mano_de_obra' es una lista de dicts, cada uno con 'rol_id' y 'horas_estimadas'.
        """
        records = [
            {'receta_id': receta_id, 'rol_id': item['rol_id'], 'horas_estimadas': item['horas_estimadas']}
            for item in mano_de_obra if item.get('rol_id') and item.get('horas_estimadas')
        ]
        
        if not records:
            return {'success': True, 'data': []}

        try:
            result = self.db.table(self.get_table_name()).insert(records).execute()
            if result.data:
                return {'success': True, 'data': result.data}
            return {'success': False, 'error': 'No se pudieron crear los registros de mano de obra.'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
