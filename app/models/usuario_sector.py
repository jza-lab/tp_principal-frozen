from typing import Dict, List
from app.models.base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

class UsuarioSectorModel(BaseModel):
    """
    Modelo para interactuar con la tabla de relación 'usuario_sectores'.
    Esta tabla gestiona las asignaciones de múltiples sectores a múltiples usuarios.
    """
    def get_table_name(self) -> str:
        """Retorna el nombre de la tabla de la base de datos."""
        return 'usuario_sectores'

    def find_by_usuario(self, usuario_id: int) -> Dict[str, bool | List | str]:
        """
        Obtiene todas las asignaciones de sectores para un usuario específico,
        incluyendo los detalles completos de cada sector.
        """
        try:
            response = self.db.table(self.get_table_name()).select('*, sectores(*)').eq('usuario_id', usuario_id).execute()
            return {'success': True, 'data': response.data or []}
        except Exception as e:
            logger.error(f"Error al obtener sectores del usuario {usuario_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def asignar_sector(self, usuario_id: int, sector_id: int) -> Dict[str, bool | Dict | str]:
        """
        Crea una nueva asignación de un sector a un usuario.
        """
        try:
            data = {'usuario_id': usuario_id, 'sector_id': sector_id}
            # Utiliza upsert para evitar errores de clave duplicada si la asignación ya existe.
            response = self.db.table(self.get_table_name()).upsert(data).execute()
            
            if response.data:
                return {'success': True, 'data': response.data[0]}

            return {'success': False, 'error': 'No se pudo asignar el sector.'}
        except Exception as e:
            logger.error(f"Error al asignar sector {sector_id} a usuario {usuario_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def eliminar_asignacion(self, usuario_id: int, sector_id: int) -> Dict[str, bool | str]:
        """
        Elimina una asignación específica de un sector a un usuario.
        """
        try:
            self.db.table(self.get_table_name()).delete().eq('usuario_id', usuario_id).eq('sector_id', sector_id).execute()
            return {'success': True, 'message': 'Asignación eliminada correctamente.'}
        except Exception as e:
            logger.error(f"Error al eliminar asignación de sector {sector_id} para usuario {usuario_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def eliminar_todas_asignaciones(self, usuario_id: int) -> Dict[str, bool | str]:
        """
        Elimina todas las asignaciones de sectores para un usuario específico.
        Útil al actualizar los sectores de un usuario.
        """
        try:
            self.db.table(self.get_table_name()).delete().eq('usuario_id', usuario_id).execute()
            return {'success': True, 'message': f'Se eliminaron todas las asignaciones para el usuario {usuario_id}.'}
        except Exception as e:
            logger.error(f"Error al eliminar todas las asignaciones del usuario {usuario_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def check_user_sector_assignment(self, usuario_id: int, sector_id: int) -> bool:
        """
        Verifica de manera eficiente si un usuario está asignado a un sector específico.
        """
        try:
            query = self.db.table(self.get_table_name())\
                .select("count", count='exact')\
                .eq("usuario_id", usuario_id)\
                .eq("sector_id", sector_id)\
                .execute()
            
            return query.count > 0
        except Exception as e:
            logger.error(f"Error al verificar asignación de sector para usuario {usuario_id}: {e}", exc_info=True)
            return False