from app.models.base_model import BaseModel

class RegistroParoModel(BaseModel):
    def __init__(self):
        super().__init__(table_name='registros_paro')

    def get_table_name(self):
        return 'registros_paro'
