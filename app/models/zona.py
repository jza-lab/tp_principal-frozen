from app.models.base_model import BaseModel

class ZonaModel(BaseModel):
    def get_table_name(self):
        return 'zonas'

class ZonaLocalidadModel(BaseModel):
    def get_table_name(self):
        return 'zonas_localidades'

