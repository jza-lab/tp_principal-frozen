from .base_model import BaseModel
from datetime import date
import logging

logger = logging.getLogger(__name__)

class AutorizacionIngresoModel(BaseModel):
    def __init__(self):
        super().__init__('u_autorizaciones_ingreso')

    def find_by_usuario_and_fecha(self, usuario_id: int, fecha: date):
        """
        Busca una autorización de ingreso para un usuario en una fecha específica.
        """
        try:
            response = self.db.table(self.table_name)\
                .select("*")\
                .eq("usuario_id", usuario_id)\
                .eq("fecha_autorizada", fecha.isoformat())\
                .execute()
            
            if response.data:
                return {'success': True, 'data': response.data[0]}
            return {'success': False, 'error': 'Autorización no encontrada.'}
        except Exception as e:
            logger.error(f"Error al buscar autorización para usuario {usuario_id} en fecha {fecha}: {e}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}

    def create(self, data: dict):
        """
        Crea un nuevo registro de autorización de ingreso.
        """
        try:
            # Asegurarse de que no exista una autorización para el mismo usuario y fecha
            existing = self.find_by_usuario_and_fecha(data['usuario_id'], data['fecha_autorizada'])
            if existing.get('success'):
                # Si ya existe, la actualizamos (update or insert)
                response = self.db.table(self.table_name)\
                    .update(data)\
                    .eq("id", existing['data']['id'])\
                    .execute()
            else:
                # Si no existe, la creamos
                response = self.db.table(self.table_name).insert(data).execute()

            if response.data:
                return {'success': True, 'data': response.data[0]}
            return {'success': False, 'error': 'No se pudo crear o actualizar la autorización.'}
        except Exception as e:
            logger.error(f"Error al crear autorización: {e}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}