from dataclasses import dataclass, asdict
from typing import Optional, Dict
from app.models.base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

@dataclass
class Direccion:
    """
    Dataclass que representa una dirección de usuario.
    """
    id: Optional[int] = None
    calle: Optional[str] = None
    altura: Optional[int] = None
    piso: Optional[str] = None
    depto: Optional[str] = None
    codigo_postal: Optional[str] = None
    localidad: Optional[str] = None
    provincia: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None

    def to_dict(self):
        return asdict(self)

class DireccionModel(BaseModel):
    """
    Modelo para interactuar con la tabla de direcciones de usuarios.
    """
    def get_table_name(self) -> str:
        return 'usuario_direccion'

    def create(self, data: Dict) -> Dict:
        """
        Crea un nuevo registro de dirección en la base de datos.
        """
        try:
            # Asegurarse de que no haya valores None que puedan causar problemas
            direccion_data = {k: v for k, v in data.items() if v is not None}

            response = self.db.table(self.get_table_name()).insert(direccion_data).execute()
            
            if response.data:
                return {'success': True, 'data': response.data[0]}
            else:
                # Esto podría ocurrir si la inserción falla silenciosamente o por RLS
                return {'success': False, 'error': 'No se pudo crear la dirección.'}

        except Exception as e:
            logger.error(f"Error creando dirección: {e}")
            # Manejar violación de unicidad
            if 'uq_direccion_completa' in str(e):
                return {'success': False, 'error': 'La dirección ya existe.', 'code': 'duplicate'}
            return {'success': False, 'error': str(e)}

    def find_by_id(self, direccion_id: int) -> Dict:
        """
        Busca una dirección por su ID.
        """
        return self._find_by('id', direccion_id)

    def find_by_full_address(self, calle: str, altura: int, piso: Optional[str], depto: Optional[str], localidad: str, provincia: str) -> Dict:
        """
        Busca una dirección exacta para evitar duplicados.
        """
        try:
            query = self.db.table(self.get_table_name()).select('*')
            query = query.eq('calle', calle)
            query = query.eq('altura', altura)
            query = query.eq('localidad', localidad)
            query = query.eq('provincia', provincia)

            if piso:
                query = query.eq('piso', piso)
            else:
                query = query.is_('piso', 'NULL')
            
            if depto:
                query = query.eq('depto', depto)
            else:
                query = query.is_('depto', 'NULL')

            result = query.execute()

            if result.data:
                return {'success': True, 'data': result.data[0]}
            else:
                return {'success': False, 'error': 'Dirección no encontrada'}

        except Exception as e:
            logger.error(f"Error buscando dirección completa: {str(e)}")
            return {'success': False, 'error': str(e)}


    def _find_by(self, field: str, value) -> Dict:
        """
        Método genérico y privado para buscar una dirección por un campo específico.
        """
        try:
            query = self.db.table(self.get_table_name()).select('*').eq(field, value)
            result = query.execute()
            
            if not result.data:
                return {'success': False, 'error': 'Dirección no encontrada'}

            return {'success': True, 'data': result.data[0]}
            
        except Exception as e:
            logger.error(f"Error buscando dirección por {field}: {str(e)}")
            return {'success': False, 'error': str(e)}