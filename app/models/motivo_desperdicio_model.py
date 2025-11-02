from app.models.base_model import BaseModel

class MotivoDesperdicioModel(BaseModel):
    def __init__(self):
        super().__init__(table_name='motivos_desperdicio')

    def get_table_name(self):
        return 'motivos_desperdicio'
