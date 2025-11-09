from app.models.base_model import BaseModel

class DespachoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de despachos en la base de datos.
    Un despacho agrupa varios pedidos para un solo envío.
    """

    def get_table_name(self) -> str:
        return 'despachos'
