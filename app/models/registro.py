from app.models.base_model import BaseModel
from typing import Dict, List

class RegistroModel(BaseModel):
    
    def get_table_name(self) -> str:
        return "registros_sistema"

    def create(self, data: Dict) -> Dict:
        """
        Crea un nuevo registro en la tabla de registros.
        """
        return super().create(data)

    def find_by_categoria(self, categoria: str) -> Dict:
        """
        Busca todos los registros de una categoría específica, ordenados por fecha descendente.
        """
        try:
            query = self._get_query_builder().select('*').eq('categoria', categoria).order('fecha', desc=True)
            result = query.execute()
            return {'success': True, 'data': result.data}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def find_all_ordered_by_date(self) -> Dict:
        """
        Busca todos los registros, ordenados por fecha descendente.
        """
        try:
            query = self._get_query_builder().select('*').order('fecha', desc=True)
            result = query.execute()
            return {'success': True, 'data': result.data}
        except Exception as e:
            return {'success': False, 'error': str(e)}
