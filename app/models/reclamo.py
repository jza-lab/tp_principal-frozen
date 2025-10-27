from app.models.base_model import BaseModel
from datetime import datetime

class ReclamoModel(BaseModel):
    """
    Modelo para gestionar los reclamos en la base de datos.
    """
    def get_table_name(self) -> str:
        return 'reclamos'
    
