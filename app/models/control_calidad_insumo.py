from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime
from app.models.base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

@dataclass
class ControlCalidadInsumo:
    """
    Dataclass que representa la estructura de un registro de control de calidad para un lote de insumo.
    """
    id: Optional[int] = None
    lote_insumo_id: Optional[str] = None
    orden_compra_id: Optional[int] = None
    usuario_supervisor_id: Optional[int] = None
    resultado_inspeccion: Optional[str] = None
    comentarios: Optional[str] = None
    foto_url: Optional[str] = None
    decision_final: Optional[str] = None  # EN CUARENTENA, RECHAZADO
    fecha_inspeccion: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ControlCalidadInsumoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de control de calidad de insumos en la base de datos.
    """

    def get_table_name(self) -> str:
        return 'control_calidad_insumos'

    def create_registro(self, data: Dict) -> Dict:
        """
        Crea un nuevo registro de control de calidad.
        """
        try:
            # Asegurarse de que los campos requeridos estén presentes
            required_fields = ['lote_insumo_id', 'usuario_supervisor_id', 'decision_final']
            for field in required_fields:
                if field not in data or data[field] is None:
                    raise ValueError(f"El campo '{field}' es obligatorio.")

            # Preparar datos para la inserción
            db_data = {
                'lote_insumo_id': data['lote_insumo_id'],
                'orden_compra_id': data.get('orden_compra_id'),
                'usuario_supervisor_id': data['usuario_supervisor_id'],
                'decision_final': data['decision_final'],
                'resultado_inspeccion': data.get('resultado_inspeccion'),
                'comentarios': data.get('comentarios'),
                'foto_url': data.get('foto_url'),
                'fecha_inspeccion': datetime.now().isoformat()
            }

            result = self.db.table(self.get_table_name()).insert(db_data).execute()

            if result.data:
                logger.info(f"Registro de control de calidad creado con éxito para el lote {data['lote_insumo_id']}.")
                return {'success': True, 'data': result.data[0]}
            else:
                raise Exception("La inserción no devolvió datos.")

        except ValueError as ve:
            logger.warning(f"Intento de crear registro de C.C. con datos inválidos: {ve}")
            return {'success': False, 'error': str(ve)}
        except Exception as e:
            logger.error(f"Error crítico creando registro de control de calidad: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def find_by_lote_id(self, lote_id: str) -> Dict:
        """
        Busca si ya existe un registro de control de calidad para un lote específico.
        """
        try:
            result = self.db.table(self.get_table_name()).select('*').eq('lote_insumo_id', lote_id).execute()
            
            if result.data:
                return {'success': True, 'data': result.data[0]}
            else:
                return {'success': False, 'error': 'No se encontró registro para este lote.'}
        
        except Exception as e:
            logger.error(f"Error buscando registro de C.C. por lote_id {lote_id}: {e}")
            return {'success': False, 'error': str(e)}

    def find_by_orden_compra_id(self, orden_id: int) -> Dict:
        """
        Obtiene todos los registros de control de calidad asociados a una orden de compra.
        """
        try:
            query = self.db.table(self.get_table_name()).select(
                "*, "
                "lote:insumos_inventario(*, insumo:insumos_catalogo(nombre)), "
                "supervisor:usuarios(*)"
            ).eq('orden_compra_id', orden_id)
            
            result = query.execute()

            # Procesar datos anidados para facilitar su uso en la vista
            for record in result.data:
                if record.get('lote') and record['lote'].get('insumo'):
                    record['insumo_nombre'] = record['lote']['insumo']['nombre']
                
                if record.get('supervisor'):
                    record['supervisor_nombre'] = record['supervisor'].get('nombre', 'N/A')
            
            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error buscando registros de C.C. por orden_compra_id {orden_id}: {e}")
            return {'success': False, 'error': str(e)}
