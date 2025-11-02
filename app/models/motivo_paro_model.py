from app.models.base_model import BaseModel

class MotivoParoModel(BaseModel):
    def __init__(self):
        super().__init__(table_name='motivos_paro')

    def get_table_name(self):
        return 'motivos_paro'
