from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime
from app.models.base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

@dataclass
class UsuarioSector:
    """
    Dataclass que representa la relación entre usuario y sector.
    """
    id: Optional[int]
    usuario_id: int
    sector_id: int
    created_at: Optional[datetime] = None


class UsuarioSectorModel(BaseModel):
    """
    Modelo para interactuar con la tabla usuario_sectores.
    """
    def get_table_name(self):
        return 'usuario_sectores'

    def find_by_usuario(self, usuario_id: int) -> Dict:
        """Obtiene todos los sectores de un usuario"""
        try:
            response = self.db.table(self.get_table_name()).select('*, sectores(*)').eq('usuario_id', usuario_id).execute()
            return {'success': True, 'data': response.data}
        except Exception as e:
            logger.error(f"Error obteniendo sectores del usuario: {str(e)}")
            return {'success': False, 'error': str(e)}

    def asignar_sector(self, usuario_id: int, sector_id: int) -> Dict:
        """Asigna un sector a un usuario"""
        try:
            data = {
                'usuario_id': usuario_id,
                'sector_id': sector_id
            }
            response = self.db.table(self.get_table_name()).insert(data).execute()
            if response.data:
                return {'success': True, 'data': response.data[0]}
            else:
                return {'success': False, 'error': 'No se pudo asignar el sector'}
        except Exception as e:
            logger.error(f"Error asignando sector al usuario: {str(e)}")
            return {'success': False, 'error': str(e)}

    def eliminar_asignacion(self, usuario_id: int, sector_id: int) -> Dict:
        """Elimina la asignación de un sector a un usuario"""
        try:
            response = self.db.table(self.get_table_name()).delete().eq('usuario_id', usuario_id).eq('sector_id', sector_id).execute()
            return {'success': True, 'data': response.data}
        except Exception as e:
            logger.error(f"Error eliminando asignación de sector: {str(e)}")
            return {'success': False, 'error': str(e)}

    def eliminar_todas_asignaciones(self, usuario_id: int) -> Dict:
        """Elimina todas las asignaciones de sectores de un usuario"""
        try:
            response = self.db.table(self.get_table_name()).delete().eq('usuario_id', usuario_id).execute()
            return {'success': True, 'data': response.data}
        except Exception as e:
            logger.error(f"Error eliminando todas las asignaciones del usuario: {str(e)}")
            return {'success': False, 'error': str(e)}

    def usuario_tiene_sector(self, usuario_id: int, sector_codigo: str) -> bool:
        """Verifica si un usuario tiene un sector específico"""
        try:
            response = self.db.table(self.get_table_name())\
                .select('sectores(*)')\
                .eq('usuario_id', usuario_id)\
                .execute()
            
            if response.data:
                sectores_usuario = [item['sectores'] for item in response.data if item.get('sectores')]
                return any(sector['codigo'] == sector_codigo for sector in sectores_usuario)
            return False
        except Exception as e:
            logger.error(f"Error verificando sector del usuario: {str(e)}")
            return False