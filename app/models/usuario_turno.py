from .base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

class UsuarioTurnoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de turnos de trabajo (`usuarios_turnos`).
    Este modelo hereda la funcionalidad CRUD básica de `BaseModel` y la especializa
    para la gestión de turnos.
    """
    def get_table_name(self) -> str:
        """Retorna el nombre de la tabla de la base de datos."""
        return 'usuarios_turnos'

    def __init__(self):
        """Inicializa el modelo de turnos."""
        super().__init__()

    def find_all(self) -> dict:
        """
        Recupera todos los turnos de la base de datos, ordenados por hora de inicio.
        """
        try:
            response = self.db.table(self.get_table_name()).select("*").order("hora_inicio").execute()
            return {'success': True, 'data': response.data or []}
        except Exception as e:
            logger.error(f"Error al buscar todos los turnos: {e}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}

    def find_by_id(self, turno_id: int) -> dict:
        """
        Busca un turno específico por su ID.
        """
        return super().find_by_id(turno_id, id_field='id')
