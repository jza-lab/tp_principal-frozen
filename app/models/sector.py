from dataclasses import dataclass, asdict
from typing import Optional, Dict, List
from datetime import datetime
from app.models.base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

@dataclass
class Sector:
    """
    Dataclass que representa un sector de la empresa.
    """
    id: Optional[int]
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    created_at: Optional[datetime] = None

    def to_dict(self):
        d = asdict(self)
        for key, value in d.items():
            if isinstance(value, datetime):
                d[key] = value.isoformat() if value else None
        return d


class SectorModel(BaseModel):
    """
    Modelo para interactuar con la tabla de sectores.
    """
    def get_table_name(self):
        return 'sectores'

    def find_all(self, filtros: Dict = None) -> Dict:
        """Obtiene todos los sectores"""
        try:
            query = self.db.table(self.get_table_name()).select('*')
            if filtros:
                for key, value in filtros.items():
                    query = query.eq(key, value)
            response = query.execute()
            return {'success': True, 'data': response.data}
        except Exception as e:
            logger.error(f"Error obteniendo sectores: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_by_id(self, sector_id: int) -> Dict:
        """Busca un sector por su ID"""
        try:
            response = self.db.table(self.get_table_name()).select('*').eq('id', sector_id).execute()
            if response.data:
                return {'success': True, 'data': response.data[0]}
            else:
                return {'success': False, 'error': 'Sector no encontrado'}
        except Exception as e:
            logger.error(f"Error buscando sector por ID: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_by_codigo(self, codigo: str) -> Dict:
        """Busca un sector por su código"""
        try:
            response = self.db.table(self.get_table_name()).select('*').eq('codigo', codigo).execute()
            if response.data:
                return {'success': True, 'data': response.data[0]}
            else:
                return {'success': False, 'error': 'Sector no encontrado'}
        except Exception as e:
            logger.error(f"Error buscando sector por código: {str(e)}")
            return {'success': False, 'error': str(e)}