from app.models.base_model import BaseModel

class CostoFijoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de costos fijos en la base de datos.
    Hereda la funcionalidad CRUD básica de BaseModel.
    """
    def get_table_name(self):
        """
        Devuelve el nombre de la tabla de la base de datos para los costos fijos.
        """
        return "costos_fijos"
