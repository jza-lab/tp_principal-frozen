from .base_model import BaseModel

class NotaCreditoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de notas_credito.
    """
    def __init__(self):
        super().__init__()

    @classmethod
    def get_table_name(cls):
        return "notas_credito"

    @classmethod
    def get_id_column(cls):
        return "id"
