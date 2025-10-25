from .base_model import BaseModel

class OperacionRecetaModel(BaseModel):

    # --- MÉTODO REQUERIDO ---
    def get_table_name(self) -> str:
        # Devuelve el nombre exacto de tu tabla en la base de datos
        return "operacionesreceta"
    # -------------------------

    def find_by_receta_id(self, receta_id: int) -> dict:
        """ Obtiene todas las operaciones de una receta, ordenadas por secuencia. """
        return self.find_all(filters={'receta_id': receta_id}, order_by='secuencia')