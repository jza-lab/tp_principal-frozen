from app.models.base_model import BaseModel

class RegistroDesperdicioModel(BaseModel):
    def __init__(self):
        super().__init__(table_name='registros_desperdicio')

    def get_table_name(self):
        return 'registros_desperdicio'
