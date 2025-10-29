from app.models.base_model import BaseModel
from app.utils.date_utils import get_now_in_argentina
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import random
import string
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class Totem2FATokenModel(BaseModel):
    """
    Modelo para gestionar los tokens de autenticación de dos factores para el tótem.

    Esta clase se encarga de crear, validar y anular los tokens de un solo uso
    enviados por correo electrónico durante el proceso de fichaje manual.
    """
    def __init__(self):
        self.table_name = "totem_2fa_tokens"
        super().__init__()

    def get_table_name(self) -> str:
        return self.table_name

    def generate_token(self) -> str:
        """Genera un código numérico aleatorio de 6 dígitos."""
        return ''.join(random.choices(string.digits, k=6))

    def create_token(self, user_id: int) -> Dict:
        """
        Crea un nuevo token 2FA para un usuario, lo guarda hasheado y devuelve el original.
        """
        try:
            # Anular cualquier token activo previo para este usuario
            self.invalidate_active_tokens(user_id)

            token = self.generate_token()
            token_hash = generate_password_hash(token)
            now = get_now_in_argentina()
            expires_at = now + timedelta(minutes=5)

            new_token_data = {
                'user_id': user_id,
                'token_hash': token_hash,
                'created_at': now.isoformat(),
                'expires_at': expires_at.isoformat(),
                'attempts': 0,
                'used': False
            }

            response = self.db.table(self.table_name).insert(new_token_data).execute()

            if response.data:
                logger.info(f"Token 2FA creado para el usuario ID: {user_id}")
                return {'success': True, 'token': token, 'data': response.data[0]}
            
            logger.error(f"No se pudo crear el token 2FA en la BD para el usuario ID: {user_id}")
            return {'success': False, 'error': 'Error al guardar el token en la base de datos.'}

        except Exception as e:
            logger.error(f"Excepción al crear token 2FA para usuario {user_id}: {e}", exc_info=True)
            return {'success': False, 'error': f'Error interno del servidor: {str(e)}'}

    def find_active_token(self, user_id: int) -> Optional[Dict]:
        """
        Busca el token activo más reciente para un usuario, sin importar los intentos.
        Un token está activo si no ha sido usado y no ha expirado.
        """
        try:
            now_iso = get_now_in_argentina().isoformat()
            
            response = self.db.table(self.table_name).select("*") \
                .eq('user_id', user_id) \
                .eq('used', False) \
                .gte('expires_at', now_iso) \
                .order('created_at', desc=True) \
                .limit(1) \
                .execute()
            
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error al buscar token activo para usuario {user_id}: {e}", exc_info=True)
            return None

    def verify_token(self, user_id: int, token: str) -> Dict:
        """
        Verifica si un token proporcionado es válido para un usuario.
        """
        token_data = self.find_active_token(user_id)

        if not token_data:
            return {'success': False, 'error': 'No se encontró un código activo. Por favor, solicita uno nuevo.'}

        if token_data['attempts'] >= 3:
            return {'success': False, 'error': 'Has agotado tus intentos. Por favor, solicita un nuevo código.'}

        if check_password_hash(token_data['token_hash'], token):
            self.mark_as_used(token_data['id'])
            return {'success': True}
        else:
            new_attempts = self.increment_attempts(token_data['id'], token_data['attempts'])
            if new_attempts is None:
                # Si falla la actualización en la BD, es un error del servidor.
                return {'success': False, 'error': 'Error del servidor al procesar el intento.'}

            remaining_attempts = 3 - new_attempts
            if remaining_attempts <= 0:
                # Marcar como usado para invalidar el token después de agotar los intentos
                self.mark_as_used(token_data['id'])
                return {'success': False, 'error': 'Código incorrecto. Has agotado tus intentos. Por favor, solicita un nuevo código.'}
            
            return {'success': False, 'error': f'Código incorrecto. Te quedan {remaining_attempts} intentos.'}

    def increment_attempts(self, token_id: int, current_attempts: int) -> Optional[int]:
        """Incrementa el contador de intentos fallidos para un token."""
        try:
            new_attempts = current_attempts + 1
            response = self.db.table(self.table_name).update({'attempts': new_attempts}).eq('id', token_id).execute()
            
            if response.data:
                logger.info(f"Incrementados los intentos a {new_attempts} para el token ID: {token_id}")
                return new_attempts
            
            logger.warning(f"La actualización de intentos para el token ID {token_id} no retornó datos, falló la operación.")
            return None
        except Exception as e:
            logger.error(f"Excepción al incrementar los intentos para el token ID: {token_id}: {e}", exc_info=True)
            return None

    def mark_as_used(self, token_id: int):
        """Marca un token como usado."""
        try:
            self.db.table(self.table_name).update({'used': True}).eq('id', token_id).execute()
        except Exception as e:
            logger.error(f"No se pudo marcar como usado el token ID: {token_id}: {e}", exc_info=True)
    
    def invalidate_active_tokens(self, user_id: int):
        """Invalida todos los tokens activos de un usuario."""
        try:
            self.db.table(self.table_name) \
                .update({'used': True}) \
                .eq('user_id', user_id) \
                .eq('used', False) \
                .execute()
        except Exception as e:
            logger.error(f"No se pudieron invalidar tokens para el usuario {user_id}: {e}", exc_info=True)

    def count_recent_tokens(self, user_id: int, minutes: int = 10) -> int:
        """Cuenta cuántos tokens se han creado para un usuario en los últimos X minutos."""
        try:
            time_threshold = get_now_in_argentina() - timedelta(minutes=minutes)
            response = self.db.table(self.table_name).select("id", count='exact') \
                .eq('user_id', user_id) \
                .gte('created_at', time_threshold.isoformat()) \
                .execute()
            
            return response.count if response.count is not None else 0
        except Exception as e:
            logger.error(f"Error al contar tokens recientes para el usuario {user_id}: {e}", exc_info=True)
            return 0

