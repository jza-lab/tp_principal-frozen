from app.controllers.base_controller import BaseController
from app.models.etapa_produccion import EtapaProduccionModel
from typing import List, Dict

class EtapaProduccionController(BaseController):
    """
    Controlador para la lógica de negocio de las etapas de producción.
    """

    def __init__(self):
        super().__init__()
        self.model = EtapaProduccionModel()

    def obtener_etapas_por_orden(self, orden_id: int) -> List[Dict]:
        """
        Obtiene todas las etapas de producción asociadas a una orden específica.
        """
        resultado = self.model.find_all(
            filters={'orden_produccion_id': orden_id},
            order_by='id' # Ordenar por ID para mantener el orden de creación
        )
        return resultado.get('data', [])