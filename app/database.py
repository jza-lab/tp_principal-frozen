from supabase import create_client, Client
from app.config import Config
import logging


logger = logging.getLogger(__name__)

class Database:
    """Singleton para manejar la conexión con Supabase"""
    _instance = None
    _client: Client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            try:
                cls._client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
                logger.info("Conexión a Supabase establecida exitosamente")
            except Exception as e:
                logger.error(f"Error conectando a Supabase: {str(e)}")
                raise
        return cls._instance

    @property
    def client(self) -> Client:
        return self._client
