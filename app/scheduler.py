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

# ==================================================================
# === 1. AÑADE ESTA NUEVA FUNCIÓN DE JOB ===
# ==================================================================
def job_planificacion_adaptativa(app: Flask):
    """
    La tarea programada que se ejecuta cada N minutos.
    Verifica si las OPs ya planificadas aún caben (ej. por ausentismo).
    """
    with app.app_context():
        logger.info(f"--- [JOB ADAPTATIVO] Iniciando Job de Planificación Adaptativa (Usuario: {SISTEMA_USER_ID}) ---")

        if getattr(job_planificacion_adaptativa, 'running', False):
            logger.warning("[JOB ADAPTATIVO] Ya está en ejecución. Omitiendo.")
            return

        setattr(job_planificacion_adaptativa, 'running', True)

        try:
            # Importar el controlador aquí
            from app.controllers.planificacion_controller import PlanificacionController
            controller = PlanificacionController()

            # Llamar a la nueva función que creamos en el controlador
            response, status_code = controller.ejecutar_planificacion_adaptativa(
                usuario_id=SISTEMA_USER_ID
            )

            if status_code == 200:
                logger.info(f"--- [JOB ADAPTATIVO] Completado. Resumen: {response.get('data')} ---")
            else:
                logger.error(f"--- [JOB ADAPTATIVO] Completado con ERROR. {response.get('error')} ---")

        except Exception as e:
            logger.error(f"¡CRÍTICO! El [JOB ADAPTATIVO] falló: {e}", exc_info=True)
        finally:
            setattr(job_planificacion_adaptativa, 'running', False)

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

    # --- JOB 1: PLANIFICACIÓN DIARIA (Tu job existente) ---
    if app.config.get('AUTO_PLAN_ENABLED', False):
        hour = app.config.get('AUTO_PLAN_HOUR', 5)   # 5 AM por defecto
        minute = app.config.get('AUTO_PLAN_MINUTE', 0) # en punto
        logger.info(f"Inicializando Scheduler. Job [planificacion_diaria] programado para {hour:02d}:{minute:02d} todos los días.")

        scheduler.add_job(
            id='planificacion_diaria',
            func=job_planificacion_diaria,
            args=[app],
            trigger='cron',
            hour=hour,
            minute=minute,
            replace_existing=True
        )
    else:
        logger.info("Scheduler de planificación DIARIA está DESHABILITADO.")

    # ==================================================================
    # === 2. AÑADE ESTE BLOQUE PARA EL NUEVO JOB ===
    # ==================================================================
    if app.config.get('ADAPTIVE_PLAN_ENABLED', True): # Habilitado por defecto
        minutes = app.config.get('ADAPTIVE_PLAN_MINUTES', 10) # 10 minutos por defecto
        logger.info(f"Inicializando Scheduler. Job [planificacion_adaptativa] programado para cada {minutes} minutos.")

        scheduler.add_job(
            id='planificacion_adaptativa',
            func=job_planificacion_adaptativa,
            args=[app],
            trigger='interval', # <-- Disparador por intervalo
            minutes=minutes,
            replace_existing=True
        )
    else:
        logger.info("Scheduler de planificación ADAPTATIVA está DESHABILITADO.")
    # ==================================================================

    scheduler.start()