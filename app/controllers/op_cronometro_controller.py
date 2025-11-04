# app/controllers/op_cronometro_controller.py
from app.controllers.base_controller import BaseController
from app.models.op_cronometro_model import OpCronometroModel
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class OpCronometroController(BaseController):
    """
    Controlador para la lógica de negocio del cronómetro de las Órdenes de Producción.
    """

    def __init__(self):
        super().__init__()
        self.op_cronometro_model = OpCronometroModel()

    def registrar_inicio(self, op_id: int) -> tuple:
        """
        Registra el inicio de un intervalo de trabajo para una OP.
        Crea una nueva fila en la tabla op_cronometro.
        Es idempotente: si ya existe un intervalo abierto, no crea otro.
        """
        try:
            # Verificar si ya hay un intervalo abierto para evitar duplicados
            intervalo_existente_res = self.op_cronometro_model.get_ultimo_intervalo_abierto(op_id)
            if not intervalo_existente_res.get('success'):
                return self.error_response(f"Error al verificar intervalos existentes: {intervalo_existente_res.get('error')}", 500)

            if intervalo_existente_res.get('data') is not None:
                logger.warning(f"Se intentó iniciar un cronómetro para la OP {op_id} pero ya había un intervalo abierto.")
                return self.success_response(data=intervalo_existente_res.get('data'), message="El cronómetro ya estaba iniciado.")

            # Crear el nuevo intervalo
            resultado = self.op_cronometro_model.create_intervalo(op_id, datetime.now(timezone.utc).isoformat())
            
            if resultado.get('success'):
                return self.success_response(data=resultado.get('data'), message="Cronómetro iniciado correctamente.")
            else:
                return self.error_response(f"No se pudo iniciar el cronómetro: {resultado.get('error')}", 500)

        except Exception as e:
            logger.error(f"Error crítico en registrar_inicio para OP {op_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def registrar_fin(self, op_id: int) -> tuple:
        """
        Registra el fin de un intervalo de trabajo para una OP.
        Actualiza la última fila abierta con la hora de finalización.
        Es idempotente: si no hay un intervalo abierto, devuelve éxito.
        """
        try:
            # Obtener el último intervalo que no tiene end_time
            intervalo_abierto_res = self.op_cronometro_model.get_ultimo_intervalo_abierto(op_id)
            if not intervalo_abierto_res.get('success'):
                return self.error_response(f"Error al buscar intervalo abierto: {intervalo_abierto_res.get('error')}", 500)

            intervalo_abierto = intervalo_abierto_res.get('data')

            if not intervalo_abierto:
                logger.warning(f"Se intentó detener un cronómetro para la OP {op_id} pero no había ninguno activo.")
                return self.success_response(message="El cronómetro ya estaba detenido.")

            # Actualizar el intervalo con la hora de finalización
            intervalo_id = intervalo_abierto['id']
            resultado = self.op_cronometro_model.update_intervalo(intervalo_id, datetime.now(timezone.utc).isoformat())

            if resultado.get('success'):
                return self.success_response(data=resultado.get('data'), message="Cronómetro detenido correctamente.")
            else:
                return self.error_response(f"No se pudo detener el cronómetro: {resultado.get('error')}", 500)

        except Exception as e:
            logger.error(f"Error crítico en registrar_fin para OP {op_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)
