from .base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

class UsuarioTurnoModel(BaseModel):
    def get_table_name(self) -> str:
        return 'usuarios_turnos'

    def __init__(self):
        super().__init__()

    def find_all(self):
        """
        Recupera todos los turnos de la base de datos.
        """
        try:
            response = self.db.table(self.table_name).select("*").order("hora_inicio").execute()
            if response.data:
                return {'success': True, 'data': response.data}
            return {'success': True, 'data': []}
        except Exception as e:
            logger.error(f"Error al buscar todos los turnos: {e}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}

    def find_by_id(self, turno_id: int):
        """
        Busca un turno por su ID.
        """
        try:
            response = self.db.table(self.table_name).select("*").eq("id", turno_id).execute()
            if response.data:
                return {'success': True, 'data': response.data[0]}
            return {'success': False, 'error': 'Turno no encontrado.'}
        except Exception as e:
            logger.error(f"Error al buscar turno por ID {turno_id}: {e}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}