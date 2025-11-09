from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime
from app.models.base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

@dataclass
class ControlCalidadProducto:
    """
    Dataclass que representa la estructura de un registro de control de calidad para un lote de producto.
    """
    id: Optional[int] = None
    lote_producto_id: Optional[int] = None
    orden_produccion_id: Optional[int] = None
    usuario_supervisor_id: Optional[int] = None
    resultado_inspeccion: Optional[str] = None
    comentarios: Optional[str] = None
    foto_url: Optional[str] = None
    decision_final: Optional[str] = None
    fecha_inspeccion: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ControlCalidadProductoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de control de calidad de productos en la base de datos.
    """

    def get_table_name(self) -> str:
        return 'control_calidad_productos'

    def create_registro(self, data: Dict) -> Dict:
        """
        Crea un nuevo registro de control de calidad.
        """
        try:
            required_fields = ['lote_producto_id', 'usuario_supervisor_id', 'decision_final']
            for field in required_fields:
                if field not in data or data[field] is None:
                    raise ValueError(f"El campo '{field}' es obligatorio.")

            db_data = {
                'lote_producto_id': data['lote_producto_id'],
                'orden_produccion_id': data.get('orden_produccion_id'),
                'usuario_supervisor_id': data['usuario_supervisor_id'],
                'decision_final': data['decision_final'],
                'resultado_inspeccion': data.get('resultado_inspeccion'),
                'comentarios': data.get('comentarios'),
                'foto_url': data.get('foto_url'),
                'fecha_inspeccion': datetime.now().isoformat()
            }

            result = self.db.table(self.get_table_name()).insert(db_data).execute()

            if result.data:
                logger.info(f"Registro de control de calidad creado con éxito para el lote de producto {data['lote_producto_id']}.")
                return {'success': True, 'data': result.data[0]}
            else:
                raise Exception("La inserción no devolvió datos.")

        except ValueError as ve:
            logger.warning(f"Intento de crear registro de C.C. de producto con datos inválidos: {ve}")
            return {'success': False, 'error': str(ve)}
        except Exception as e:
            logger.error(f"Error crítico creando registro de control de calidad de producto: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
