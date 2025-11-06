from app.controllers.base_controller import BaseController
import logging
from app.database import Database

logger = logging.getLogger(__name__)

class StorageController(BaseController):
    def __init__(self):
        super().__init__()
        from app.config import Config
        from supabase import create_client
        
        # Crear un cliente de Supabase con la clave de servicio para tener permisos de administrador
        self.supabase_admin = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_KEY)

    def upload_file(self, file, bucket_name: str, destination_path: str):
        try:
            # Usar el cliente de administrador para la subida
            response = self.supabase_admin.storage.from_(bucket_name).upload(
                path=destination_path,
                file_options={"content-type": file.mimetype},
                file=file.read(),
            )

            # Usar el cliente de administrador también para obtener la URL pública
            public_url_res = self.supabase_admin.storage.from_(bucket_name).get_public_url(destination_path)
            
            return {"success": True, "url": public_url_res}, 200

        except Exception as e:
            logger.error(f"Error al subir archivo a Supabase Storage: {e}", exc_info=True)
            error_message = str(e)
            return {"success": False, "error": f"Error interno: {error_message}"}, 500
