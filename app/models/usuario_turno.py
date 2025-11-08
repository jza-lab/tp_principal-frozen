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

    def find_current_shift(self) -> dict:
        """
        Encuentra el turno actual basado en la hora del sistema en UTC-3.
        """
        try:
            from datetime import datetime, time, timedelta
            
            # Obtener la hora actual en UTC y ajustarla a UTC-3 (Argentina)
            now_utc = datetime.utcnow()
            now_argentina = now_utc - timedelta(hours=3)
            current_time_str = now_argentina.strftime('%H:%M:%S')

            # Realizar la consulta a la base de datos
            response = self.db.table(self.get_table_name()).select("*").lte('hora_inicio', current_time_str).gte('hora_fin', current_time_str).execute()
            
            if response.data:
                return {'success': True, 'data': response.data[0]}
            else:
                # Si no hay un turno que cruce la medianoche, esto es suficiente.
                # Para turnos que cruzan la medianoche (ej. 22:00-06:00), se necesitaría una lógica más compleja.
                # Por ahora, se asume que no hay turnos nocturnos que crucen la medianoche.
                return {'success': False, 'error': 'No se encontró un turno activo en este momento.'}
        except Exception as e:
            logger.error(f"Error al buscar el turno actual: {e}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}
