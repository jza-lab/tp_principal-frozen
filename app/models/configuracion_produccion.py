from app.models.base_model import BaseModel

class ConfiguracionProduccionModel(BaseModel):
    """
    Modelo para interactuar con la tabla de configuración de producción.
    Almacena las horas de producción estándar por día.
    """
    def get_table_name(self):
        """
        Devuelve el nombre de la tabla de la base de datos.
        """
        return "configuracion_produccion"
