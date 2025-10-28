import smtplib
from email.mime.text import MIMEText
from flask import current_app

def send_email(to_email, subject, body):
    config = current_app.config
    
    if not config.get('MAIL_SERVER'):
        print("---- SIMULANDO ENVÍO DE EMAIL ----")
        print(f"A: {to_email}")
        print(f"Asunto: {subject}")
        print(f"Cuerpo: {body}")
        print("-----------------------------------")
        return True, "Email simulado. Configura las variables de entorno para envíos reales."

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = config['MAIL_USERNAME']
    msg['To'] = to_email

    try:
        with smtplib.SMTP(config['MAIL_SERVER'], config['MAIL_PORT']) as server:
            server.starttls()
            server.login(config['MAIL_USERNAME'], config['MAIL_PASSWORD'])
            server.send_message(msg)
        return True, "Email enviado correctamente."
    except Exception as e:
        print(f"Error al enviar email: {e}")
        return False, str(e)
