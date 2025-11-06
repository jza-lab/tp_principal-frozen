from app.models.base_model import BaseModel
from typing import Dict, Optional

class TraspasoTurnoModel(BaseModel):
    """
    Modelo para gestionar los registros de traspasos de turno en la base de datos.
    """
    def __init__(self):
        self.schema = 'mes_kanban'
        self.table_name = 'traspasos_turno'
        super().__init__()

    def get_table_name(self) -> str:
        """
        Devuelve el nombre completo de la tabla, incluyendo el esquema.
        """
        return f'{self.schema}.{self.table_name}'

    def find_latest_pending_by_op_id(self, orden_produccion_id: int) -> Dict:
        """
        Busca el último traspaso pendiente (sin receptor) para una OP específica.
        """
        try:
            query = self.db.table(self.table_name).select(
                "*, usuario_saliente:usuario_saliente_id(nombre, apellido)"
            ).eq(
                'orden_produccion_id', orden_produccion_id
            ).is_(
                'usuario_entrante_id', None
            ).order(
                'fecha_traspaso', desc=True
            ).limit(1)

            result = query.execute()
            
            if result.data:
                return {'success': True, 'data': result.data[0]}
            else:
                return {'success': False, 'error': "No se encontró un traspaso pendiente.", 'status_code': 404}

        except Exception as e:
            return {'success': False, 'error': f"Error al buscar traspaso pendiente: {e}"}
