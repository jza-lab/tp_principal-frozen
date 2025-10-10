from .base_model import BaseModel

class ReservaInsumoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de reservas de insumos.
    Hereda de BaseModel e implementa el método abstracto requerido.
    """

    def get_table_name(self) -> str:
        """
        Devuelve el nombre de la tabla para que el BaseModel sepa con qué tabla trabajar.
        """
        return 'reservas_insumos'
