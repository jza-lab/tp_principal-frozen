from typing import Dict, Any, Optional
from datetime import datetime
from models.asistencia import AsistenciaRegistro
from .base_repository import BaseRepository

class AsistenciaRepository(BaseRepository[AsistenciaRegistro]):
    """
    Repositorio para gestionar las operaciones CRUD de la entidad AsistenciaRegistro.
    """
    @property
    def table_name(self) -> str:
        return 'asistencia_registros'

    @property
    def uses_activo_filter(self) -> bool:
        return False

    def _dict_to_model(self, data: Dict[str, Any]) -> AsistenciaRegistro:
        """Convierte un diccionario en una instancia del modelo AsistenciaRegistro."""
        return AsistenciaRegistro(
            id=data.get('id'),
            usuario_id=data.get('usuario_id'),
            tipo=data.get('tipo'),
            fecha_hora=datetime.fromisoformat(data['fecha_hora']) if data.get('fecha_hora') else None,
            observaciones=data.get('observaciones')
        )

    def obtener_ultimo_registro(self, usuario_id: int) -> Optional[AsistenciaRegistro]:
        """
        Recupera el último registro de asistencia para un usuario específico.
        """
        response = self.client.table(self.table_name).select("*") \
            .eq('usuario_id', usuario_id) \
            .order('fecha_hora', desc=True) \
            .limit(1) \
            .execute()

        if not response.data:
            return None

        return self._dict_to_model(response.data[0])
