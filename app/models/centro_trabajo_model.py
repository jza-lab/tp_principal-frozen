from .base_model import BaseModel

class CentroTrabajoModel(BaseModel):

    # --- MÉTODO REQUERIDO ---
    def get_table_name(self) -> str:
        # Devuelve el nombre exacto de tu tabla en la base de datos
        return "CentrosTrabajo"
    # -------------------------