import logging
from app.models.base_model import BaseModel

logger = logging.getLogger(__name__)

class CalendarioExcepcionModel(BaseModel):
    """
    Modelo para gestionar excepciones al calendario laboral (días libres extra o días extra laborables).
    """
    def get_table_name(self) -> str:
        return 'calendario_excepciones'
