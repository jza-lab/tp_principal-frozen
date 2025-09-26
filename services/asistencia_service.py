from typing import Optional
from datetime import datetime
from models.asistencia import AsistenciaRegistro
from repositories.asistencia_repository import AsistenciaRepository

class AsistenciaService:

    def __init__(self, repository: AsistenciaRepository):
        self.repository = repository

    def registrar_entrada(self, usuario_id: int, observaciones: str = None) -> AsistenciaRegistro:
        """Registra una entrada para un usuario."""
        ultimo_registro = self.repository.obtener_ultimo_registro(usuario_id)
        if ultimo_registro and ultimo_registro.tipo == 'ENTRADA':
            raise ValueError("El usuario ya tiene una entrada registrada sin una salida correspondiente.")

        nuevo_registro = AsistenciaRegistro(
            id=None,
            usuario_id=usuario_id,
            tipo='ENTRADA',
            fecha_hora=datetime.now(),
            observaciones=observaciones
        )
        return self.repository.create(nuevo_registro)

    def registrar_salida(self, usuario_id: int, observaciones: str = None) -> AsistenciaRegistro:
        """Registra una salida para un usuario."""
        ultimo_registro = self.repository.obtener_ultimo_registro(usuario_id)
        if not ultimo_registro or ultimo_registro.tipo == 'SALIDA':
            raise ValueError("No se puede registrar una salida sin una entrada previa.")

        nuevo_registro = AsistenciaRegistro(
            id=None,
            usuario_id=usuario_id,
            tipo='SALIDA',
            fecha_hora=datetime.now(),
            observaciones=observaciones
        )
        return self.repository.create(nuevo_registro)

    def obtener_ultimo_registro(self, usuario_id: int) -> Optional[AsistenciaRegistro]:
        """Obtiene el último registro de asistencia de un usuario."""
        return self.repository.obtener_ultimo_registro(usuario_id)
