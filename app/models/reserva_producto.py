from .base_model import BaseModel

class ReservaProductoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de reservas de productos.
    Implementa el método abstracto requerido por BaseModel.
    """

    def get_table_name(self):
        """
        Devuelve el nombre de la tabla para cumplir con el contrato de BaseModel.
        """
        return 'reservas_productos'