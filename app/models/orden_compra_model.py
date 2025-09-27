from dataclasses import dataclass, asdict
from typing import Optional, Dict, List
from datetime import datetime, date
from app.models.base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

def safe_serialize_simple(obj):
    """Serialización simple para datetime y otros tipos no serializables"""
    if obj is None:
        return None
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, (dict)):
        return {k: safe_serialize_simple(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [safe_serialize_simple(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        return safe_serialize_simple(obj.__dict__)
    else:
        try:
            return str(obj)
        except:
            return None

@dataclass
class OrdenCompra:
    """
    Dataclass que representa la estructura real de la tabla ordenes_compra.
    """
    id: Optional[int] = None
    codigo_oc: Optional[str] = None
    proveedor_id: Optional[int] = None
    pedido_id: Optional[int] = None
    orden_produccion_id: Optional[int] = None
    estado: Optional[str] = 'PENDIENTE'
    fecha_emision: Optional[date] = None
    fecha_estimada_entrega: Optional[date] = None
    fecha_real_entrega: Optional[date] = None
    prioridad: Optional[str] = 'NORMAL'
    subtotal: Optional[float] = 0.0
    iva: Optional[float] = 0.0
    total: Optional[float] = 0.0
    observaciones: Optional[str] = None
    usuario_creador_id: Optional[int] = None
    usuario_aprobador_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    fecha_creacion: Optional[datetime] = None

class OrdenCompraModel(BaseModel):
    """
    Modelo para interactuar con la tabla de órdenes de compra en la base de datos.
    """

    def get_table_name(self) -> str:
        return 'ordenes_compra'

    def create(self, orden_data: Dict) -> Dict:
        try:
            # ✅ Mapeo correcto según la estructura real de la tabla
            db_data = {}
            field_mapping = {
                'codigo_oc': 'codigo_oc',
                'proveedor_id': 'proveedor_id',
                'pedido_id': 'pedido_id',
                'orden_produccion_id': 'orden_produccion_id',
                'estado': 'estado',
                'fecha_emision': 'fecha_emision',
                'fecha_estimada_entrega': 'fecha_estimada_entrega',
                'fecha_real_entrega': 'fecha_real_entrega',
                'prioridad': 'prioridad',
                'subtotal': 'subtotal',
                'iva': 'iva',
                'total': 'total',
                'observaciones': 'observaciones',
                'usuario_creador_id': 'usuario_creador_id',
                'usuario_aprobador_id': 'usuario_aprobador_id'
            }

            # Filtrar y convertir datos
            for model_field, db_field in field_mapping.items():
                if model_field in orden_data and orden_data[model_field] is not None:
                    value = orden_data[model_field]
                    if isinstance(value, (datetime, date)):
                        db_data[db_field] = value.isoformat()
                    else:
                        db_data[db_field] = value

            print(f"🔍 DEBUG: Datos para insertar: {db_data}")

            response = self.db.table(self.get_table_name()).insert(db_data).execute()

            if response.data:
                data_serializada = safe_serialize_simple(response.data[0])
                return {'success': True, 'data': data_serializada}
            else:
                return {'success': False, 'error': 'Error creando orden - sin datos de respuesta'}
        except Exception as e:
            logger.error(f"Error creando orden: {e}")
            return {'success': False, 'error': str(e)}

    def find_by_id(self, orden_id: int) -> Dict:
        try:
            response = self.db.table(self.get_table_name()).select("*").eq("id", orden_id).execute()
            if response.data:
                data_serializada = safe_serialize_simple(response.data[0])
                return {'success': True, 'data': data_serializada}
            else:
                return {'success': False, 'error': 'Orden no encontrada'}
        except Exception as e:
            logger.error(f"Error buscando orden por ID: {e}")
            return {'success': False, 'error': str(e)}

    def find_by_codigo(self, codigo_oc: str) -> Dict:
        try:
            result = self.db.table(self.get_table_name()).select('*').eq('codigo_oc', codigo_oc).execute()
            if result.data:
                data_serializada = safe_serialize_simple(result.data[0])
                return {'success': True, 'data': data_serializada}
            else:
                return {'success': False, 'error': 'Orden no encontrada'}
        except Exception as e:
            logger.error(f"Error buscando orden por código: {str(e)}")
            return {'success': False, 'error': str(e)}

    def update(self, orden_id: int, data: Dict) -> Dict:
        try:
            db_data = {}
            field_mapping = {
                'proveedor_id': 'proveedor_id',
                'pedido_id': 'pedido_id',
                'orden_produccion_id': 'orden_produccion_id',
                'estado': 'estado',
                'fecha_emision': 'fecha_emision',
                'fecha_estimada_entrega': 'fecha_estimada_entrega',
                'fecha_real_entrega': 'fecha_real_entrega',
                'prioridad': 'prioridad',
                'subtotal': 'subtotal',
                'iva': 'iva',
                'total': 'total',
                'observaciones': 'observaciones',
                'usuario_aprobador_id': 'usuario_aprobador_id'
            }

            for model_field, db_field in field_mapping.items():
                if model_field in data and data[model_field] is not None:
                    value = data[model_field]
                    if isinstance(value, (datetime, date)):
                        db_data[db_field] = value.isoformat()
                    else:
                        db_data[db_field] = value

            # Agregar updated_at automáticamente
            db_data['updated_at'] = datetime.now().isoformat()

            response = self.db.table(self.get_table_name()).update(db_data).eq("id", orden_id).execute()
            if response.data:
                data_serializada = safe_serialize_simple(response.data[0])
                return {'success': True, 'data': data_serializada}
            else:
                return {'success': False, 'error': 'Orden no encontrada'}
        except Exception as e:
            logger.error(f"Error actualizando orden: {e}")
            return {'success': False, 'error': str(e)}

    def get_all(self, filters: Dict = None) -> Dict:
        try:
            query = self.db.table(self.get_table_name()).select("*")

            if filters:
                if 'estado' in filters:
                    query = query.eq('estado', filters['estado'])
                if 'proveedor_id' in filters:
                    query = query.eq('proveedor_id', filters['proveedor_id'])
                if 'prioridad' in filters:
                    query = query.eq('prioridad', filters['prioridad'])

            response = query.execute()
            data_serializada = safe_serialize_simple(response.data)
            return {'success': True, 'data': data_serializada}
        except Exception as e:
            logger.error(f"Error obteniendo órdenes: {e}")
            return {'success': False, 'error': str(e)}