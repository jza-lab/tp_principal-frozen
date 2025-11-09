from app.models.base_model import BaseModel

class VehiculoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de vehículos en la base de datos.
    """

    def get_table_name(self) -> str:
        return 'vehiculos'
