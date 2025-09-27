from app.models.base_model import BaseModel

class EtapaProduccionModel(BaseModel):
    """
    Modelo para interactuar con la tabla de etapas de producción.
    Hereda la funcionalidad CRUD básica de BaseModel.
    """

    def get_table_name(self) -> str:
        """
        Retorna el nombre de la tabla específica para este modelo.
        """
        return "etapas_produccion"