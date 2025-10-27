from app.models.base_model import BaseModel

class DespachoModel(BaseModel):
    def get_table_name(self) -> str:
        return 'despachos'

    def create(self, data):
        """
        Crea un nuevo registro de despacho.
        """
        return super().create(data)
