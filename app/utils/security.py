from flask import current_app
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature

def generate_signed_token(data):
    """
    Genera un token firmado y seguro a partir de un diccionario de datos.
    """
    secret_key = current_app.config.get('SECRET_KEY', 'default-secret-key-for-dev')
    serializer = URLSafeTimedSerializer(secret_key)
    return serializer.dumps(data)

def verify_signed_token(token, max_age=None):
    """
    Verifica un token firmado y devuelve los datos originales.
    Si el token es inválido o ha expirado, devuelve None.
    
    :param token: El token a verificar.
    :param max_age: La edad máxima del token en segundos. Si es None, no se comprueba la expiración.
    """
    secret_key = current_app.config.get('SECRET_KEY', 'default-secret-key-for-dev')
    serializer = URLSafeTimedSerializer(secret_key)
    try:
        # El argumento 'max_age' se pasa al método loads()
        data = serializer.loads(token, max_age=max_age)
        return data
    except (SignatureExpired, BadTimeSignature, Exception):
        # Captura firmas inválidas, tokens expirados o cualquier otro error de parsing
        return None
