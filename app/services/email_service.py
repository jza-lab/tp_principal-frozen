# app/services/email_service.py
import smtplib
from email.mime.text import MIMEText
from flask import current_app
import logging

logger = logging.getLogger(__name__)

def send_email(to_email, subject, body, config_prefix='MAIL'):
    config = current_app.config
    
    server_key = f'{config_prefix}_SERVER'
    port_key = f'{config_prefix}_PORT'
    user_key = f'{config_prefix}_USERNAME'
    password_key = f'{config_prefix}_PASSWORD'

    if not config.get(server_key):
        logger.warning(f"---- SIMULANDO ENVÍO DE EMAIL ({config_prefix}) ----")
        logger.warning(f"A: {to_email}")
        logger.warning(f"Asunto: {subject}")
        logger.warning("-----------------------------------")
        return True, "Email simulado. Configura las variables de entorno para envíos reales."

    msg = MIMEText(body, 'html')
    msg['Subject'] = subject
    msg['From'] = config.get(user_key)
    msg['To'] = to_email

    try:
        logger.info(f"Conectando al servidor de correo ({config_prefix}): {config.get(server_key)}:{config.get(port_key)}")
        with smtplib.SMTP(config.get(server_key), config.get(port_key)) as server:
            logger.info(f"Iniciando TLS para la conexión ({config_prefix})...")
            server.starttls()
            logger.info(f"Iniciando sesión con el usuario ({config_prefix}): {config.get(user_key)}...")
            server.login(config.get(user_key), config.get(password_key))
            logger.info(f"Enviando correo ({config_prefix}) a: {to_email}...")
            server.send_message(msg)
            logger.info(f"Correo ({config_prefix}) enviado exitosamente a {to_email}.")
        return True, "Email enviado correctamente."
    except Exception as e:
        logger.error(f"Error crítico al enviar email con config {config_prefix}: {e}", exc_info=True)
        return False, str(e)