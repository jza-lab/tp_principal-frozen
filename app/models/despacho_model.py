from app.models.base_model import BaseModel

class DespachoModel(BaseModel):
    def __init__(self):
        super().__init__(table_name='despachos')

    def create(self, data):
        """
        Crea un nuevo registro de despacho.
        """
        return super().create(data)
