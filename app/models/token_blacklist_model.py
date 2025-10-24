from .base_model import BaseModel
from datetime import datetime

class TokenBlacklistModel(BaseModel):
    """
    Modelo para gestionar la blacklist de tokens JWT.
    """
    def get_table_name(self) -> str:
        return 'token_blacklist'

    @staticmethod
    def add_to_blacklist(jti: str, exp: int):
        """
        Añade el JTI de un token a la blacklist.

        Args:
            jti (str): El identificador único del token JWT.
            exp (int): El timestamp de expiración del token.
        """
        try:
            exp_datetime = datetime.fromtimestamp(exp)
            
            # Instanciamos el modelo para usar sus métodos de acceso a DB.
            model = TokenBlacklistModel()
            model.create({'jti': jti, 'exp': exp_datetime.isoformat()})

        except Exception as e:
            # En un entorno de producción, sería ideal loggear este error.
            print(f"Error al añadir token a la blacklist: {e}")
            # Se podría relanzar la excepción o manejarla según la política de la app.
            raise

    @staticmethod
    def is_blacklisted(jti: str) -> bool:
        """
        Verifica si un JTI de token está en la blacklist.

        Args:
            jti (str): El identificador único del token JWT.

        Returns:
            bool: True si el token está en la blacklist, False en caso contrario.
        """
        try:
            model = TokenBlacklistModel()
            result = model.find_all(filters={'jti': jti})
            return result.get('success') and bool(result.get('data'))

        except Exception as e:
            print(f"Error al verificar token en la blacklist: {e}")
            # En caso de error en la BD, es más seguro asumir que el token podría
            # ser inválido. Se podría devolver True o relanzar. Por simplicidad,
            # relanzamos para que el decorador JWT lo maneje como un error interno.
            raise
