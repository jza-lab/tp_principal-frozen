import logging
import os
from flask_apscheduler import APScheduler
from flask import Flask
from datetime import date

# Configurar logger para el scheduler
logger = logging.getLogger("scheduler")

# El ID del usuario "Sistema" para auditoría
# Es mejor leerlo desde las variables de entorno
SISTEMA_USER_ID = int(os.environ.get('SISTEMA_USER_ID', 1))

# Variable global para el scheduler
scheduler = APScheduler()

def job_planificacion_diaria(app: Flask):
    """
    La tarea programada que se ejecuta diariamente.
    """
    # Necesitamos un contexto de aplicación para acceder a la DB y los controladores
    with app.app_context():
        logger.info(f"--- Iniciando Job de Planificación Diaria (Usuario: {SISTEMA_USER_ID}) ---")

        # Un simple flag para evitar ejecuciones múltiples si el scheduler se reinicia
        # (Mejoraría con un flag en la DB, pero esto es un inicio)
        if getattr(job_planificacion_diaria, 'running', False):
            logger.warning("Job de planificación ya está en ejecución. Omitiendo.")
            return

        setattr(job_planificacion_diaria, 'running', True)

        try:
            # Importar el controlador aquí para evitar importaciones circulares
            from app.controllers.planificacion_controller import PlanificacionController

            controller = PlanificacionController()

            # Ejecutar la lógica central con un horizonte de 1 día
            resumen = controller._ejecutar_planificacion_automatica(
                usuario_id=SISTEMA_USER_ID,
                dias_horizonte=1 # El job diario solo planifica para "hoy"
            )

            logger.info(f"--- Job de Planificación Diaria Completado. Resumen: {resumen} ---")

        except Exception as e:
            logger.error(f"¡CRÍTICO! El Job de Planificación Diaria falló: {e}", exc_info=True)
        finally:
            setattr(job_planificacion_diaria, 'running', False)


def init_scheduler(app: Flask):
    """
    Inicializa el scheduler y añade el job diario.
    """
    if not app.config.get('AUTO_PLAN_ENABLED', False):
        logger.info("Scheduler de planificación automática está DESHABILITADO.")
        return

    hour = app.config.get('AUTO_PLAN_HOUR', 5)   # 5 AM por defecto
    minute = app.config.get('AUTO_PLAN_MINUTE', 0) # en punto

    logger.info(f"Inicializando Scheduler. Job 'planificacion_diaria' programado para {hour:02d}:{minute:02d} todos los días.")

    scheduler.init_app(app)

    # Añadimos el job
    scheduler.add_job(
        id='planificacion_diaria',
        func=job_planificacion_diaria,
        args=[app], # Pasar la app al job para crear el contexto
        trigger='cron',
        hour=hour,
        minute=minute,
        replace_existing=True # Evita duplicados si la app se reinicia
    )
    
    scheduler.add_job(
        id='actualizacion_crediticia_diaria',
        func=job_actualizacion_crediticia_diaria,
        args=[app],
        trigger='cron',
        hour=app.config.get('CREDIT_UPDATE_HOUR', 1), # 1 AM por defecto
        minute=app.config.get('CREDIT_UPDATE_MINUTE', 0),
        replace_existing=True
    )
    scheduler.start()

    
def job_actualizacion_crediticia_diaria(app: Flask):
    """
    Tarea programada para actualizar pedidos vencidos y el estado crediticio de los clientes.
    """
    with app.app_context():
        logger.info("--- Iniciando Job de Actualización Crediticia Diaria ---")
        try:
            from app.controllers.pedido_controller import PedidoController
            from app.controllers.cliente_controller import ClienteController

            pedido_controller = PedidoController()
            cliente_controller = ClienteController()

            # 1. Marcar pedidos como vencidos
            logger.info("Marcando pedidos vencidos...")
            pedidos_actualizados = pedido_controller.marcar_pedidos_vencidos()
            logger.info(f"Se marcaron {pedidos_actualizados} pedidos como vencidos.")

            # 2. Recalcular estado crediticio de todos los clientes
            logger.info("Recalculando estado crediticio de los clientes...")
            clientes_afectados = cliente_controller.recalcular_estado_crediticio_todos_los_clientes()
            logger.info(f"Se recalculó el estado crediticio. {clientes_afectados} clientes fueron actualizados.")

            logger.info("--- Job de Actualización Crediticia Diaria Completado ---")

        except Exception as e:
            logger.error(f"¡CRÍTICO! El Job de Actualización Crediticia Diaria falló: {e}", exc_info=True)