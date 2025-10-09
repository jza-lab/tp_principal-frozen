from app.models.notificacion import NotificacionModel
import logging

logger = logging.getLogger(__name__)

class NotificacionController:
    def __init__(self):
        self.model = NotificacionModel()

    def obtener_notificaciones_no_leidas(self):
        """
        Obtiene todas las notificaciones que no han sido marcadas como leídas.
        """
        resultado = self.model.find_unread()
        return resultado.get('data', [])

    def marcar_como_leida(self, notificacion_id: int):
        """
        Marca una notificación específica como leída.
        """
        return self.model.mark_as_read(notificacion_id)