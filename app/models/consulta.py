from .base_model import BaseModel

class ConsultaModel(BaseModel):
    def get_table_name(self):
        return "consultas"

    def __init__(self):
        super().__init__()

    def create(self, data):
        return super().create(data)

    def get_all(self):
        return self.find_all()

    def get_by_id(self, id):
        return self.find_by_id(id)

    def update_estado(self, id, estado, respuesta):
        return self.update(id, {'estado': estado, 'respuesta': respuesta})

    def get_by_cliente_id(self, cliente_id):
        return self.find_all(filters={'cliente_id': cliente_id})