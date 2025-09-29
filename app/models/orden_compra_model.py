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
    def __init__(self):
        super().__init__()
        self.item_model = OrdenCompraItemModel()

    def get_table_name(self) -> str:
        return 'ordenes_compra'

    def create_with_items(self, orden_data: Dict, items_data: List[Dict]) -> Dict:
        """
        Crea una nueva orden de compra junto con sus items, simulando una transacción.
        """
        try:
            # Eliminar 'id' si existe para permitir que la BD lo genere.
            if 'id' in orden_data:
                orden_data.pop('id')

            # 1. Crear la orden de compra principal usando el método de BaseModel
            orden_result = super().create(orden_data)
            if not orden_result.get('success'):
                raise Exception(f"Error al crear la orden de compra principal: {orden_result.get('error')}")
            
            new_orden = orden_result['data']
            new_orden_id = new_orden['id']

            # 2. Preparar y crear los items
            if items_data:
                for item in items_data:
                    item['orden_compra_id'] = new_orden_id
                
                items_result = self.item_model.create_many(items_data)
                
                if not items_result.get('success'):
                    # Rollback: eliminar la orden principal si falla la creación de items
                    logger.error(f"Error creando items para la orden {new_orden_id}. Deshaciendo...")
                    super().delete(id_value=new_orden_id, id_field='id')
                    raise Exception(f"Error al crear los ítems de la orden: {items_result.get('error')}")

            logger.info(f"Orden de compra y {len(items_data)} items creados con éxito. Orden ID: {new_orden_id}")
            return {'success': True, 'data': new_orden}

        except Exception as e:
            logger.error(f"Error crítico creando orden con items: {str(e)}")
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
        """
        Obtiene todas las órdenes de compra con detalles del proveedor y del usuario creador.
        """
        try:
            query = self.db.table(self.get_table_name()).select(
                "*, proveedor:proveedores(nombre), usuario_creador:usuarios!usuario_creador_id(nombre)"
            )

            if filters:
                if 'estado' in filters and filters['estado']:
                    query = query.eq('estado', filters['estado'])
                if 'proveedor_id' in filters and filters['proveedor_id']:
                    query = query.eq('proveedor_id', filters['proveedor_id'])
                if 'prioridad' in filters and filters['prioridad']:
                    query = query.eq('prioridad', filters['prioridad'])

            response = query.order('fecha_emision', desc=True).execute()
            
            for orden in response.data:
                if orden.get('proveedor'):
                    orden['proveedor_nombre'] = orden['proveedor']['nombre']
                    del orden['proveedor']
                else:
                    orden['proveedor_nombre'] = 'N/A'
                
                if orden.get('usuario_creador'):
                    orden['usuario_creador_nombre'] = orden['usuario_creador']['nombre']
                    del orden['usuario_creador']
                else:
                    orden['usuario_creador_nombre'] = 'N/A'

            return {'success': True, 'data': response.data}
        except Exception as e:
            logger.error(f"Error obteniendo órdenes con detalles: {e}")
            return {'success': False, 'error': str(e)}

    def get_one_with_details(self, orden_id: int) -> Dict:
        """
        Obtiene una orden de compra específica con detalles del proveedor y los items.
        """
        try:
            query = self.db.table(self.get_table_name()).select(
                "*, proveedor:proveedores(nombre), items:orden_compra_items(*, insumo:insumos_catalogo(nombre)), usuario_creador:usuarios!usuario_creador_id(nombre), usuario_aprobador:usuarios!usuario_aprobador_id(nombre)"
            )
            response = query.eq("id", orden_id).maybe_single().execute()

            orden = response.data
            if not orden:
                return {'success': False, 'error': 'Orden no encontrada'}

            if orden.get('proveedor'):
                orden['proveedor_nombre'] = orden['proveedor']['nombre']
            else:
                orden['proveedor_nombre'] = 'N/A'
            
            if orden.get('usuario_creador'):
                orden['usuario_creador_nombre'] = orden['usuario_creador']['nombre']
            else:
                orden['usuario_creador_nombre'] = 'N/A'
            
            if orden.get('usuario_aprobador'):
                orden['usuario_aprobador_nombre'] = orden['usuario_aprobador']['nombre']
            else:
                orden['usuario_aprobador_nombre'] = 'N/A'

            if orden.get('items'):
                for item in orden['items']:
                    if item.get('insumo'):
                        item['insumo_nombre'] = item['insumo']['nombre']
                    else:
                        item['insumo_nombre'] = 'N/A'

            return {'success': True, 'data': orden}
        except Exception as e:
            logger.error(f"Error obteniendo orden {orden_id} con detalles: {e}")
            return {'success': False, 'error': str(e)}

    def update_with_items(self, orden_id: int, orden_data: Dict, items_data: List[Dict]) -> Dict:
        """
        Actualiza una orden de compra y sus items.
        """
        try:
            # 1. Actualizar la orden de compra principal
            if 'id' in orden_data:
                orden_data.pop('id')
            
            update_result = self.update(orden_id, orden_data)
            if not update_result.get('success'):
                raise Exception(f"Error al actualizar la orden de compra principal: {update_result.get('error')}")

            # 2. Eliminar los items antiguos
            self.db.table('orden_compra_items').delete().eq('orden_compra_id', orden_id).execute()

            # 3. Insertar los nuevos items
            if items_data:
                for item in items_data:
                    item['orden_compra_id'] = orden_id
                
                items_result = self.item_model.create_many(items_data)
                if not items_result.get('success'):
                    # This is not a true rollback, but we raise an error.
                    raise Exception(f"Error al re-insertar los ítems de la orden: {items_result.get('error')}")

            logger.info(f"Orden de compra {orden_id} y sus items actualizados correctamente.")
            return self.get_one_with_details(orden_id)

        except Exception as e:
            logger.error(f"Error actualizando orden {orden_id} con items: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_codigos_by_insumo_id(self, insumo_id: str) -> Dict:
        """
        Encuentra los códigos de las órdenes de compra y el precio unitario 
        que contienen un insumo específico.
        """
        try:
            # Usamos un join para obtener el codigo_oc de la tabla de órdenes
            query = self.db.table('orden_compra_items').select(
                'precio_unitario, orden:ordenes_compra!orden_compra_id(codigo_oc)'
            ).eq('insumo_id', insumo_id)
            
            response = query.execute()

            if not response.data:
                return {'success': True, 'data': []}

            # Procesar la respuesta para aplanarla y que sea más fácil de usar
            processed_data = []
            for item in response.data:
                if item.get('orden') and item['orden'].get('codigo_oc'):
                    processed_data.append({
                        'codigo_oc': item['orden']['codigo_oc'],
                        'precio_unitario': item['precio_unitario']
                    })
            
            return {'success': True, 'data': processed_data}

        except Exception as e:
            logger.error(f"Error buscando códigos de OC y precios por insumo_id: {e}")
            return {'success': False, 'error': str(e)}

@dataclass
class OrdenCompraItem:
    """
    Dataclass que representa un ítem de una orden de compra.
    """
    id: Optional[int] = None
    orden_compra_id: Optional[int] = None
    insumo_id: Optional[str] = None
    cantidad_solicitada: float = 0.0
    cantidad_recibida: float = 0.0
    precio_unitario: float = 0.0
    subtotal: float = 0.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OrdenCompraItemModel(BaseModel):
    """
    Modelo para los ítems de una orden de compra.
    """
    def get_table_name(self) -> str:
        return 'orden_compra_items'

    def create_many(self, items: List[Dict]) -> Dict:
        """
        Crea múltiples ítems de orden de compra.
        """
        try:
            clean_items = [self._prepare_data_for_db(item) for item in items]
            
            result = self.db.table(self.get_table_name()).insert(clean_items).execute()
            
            if result.data:
                logger.info(f"Creados {len(result.data)} ítems para la orden.")
                return {'success': True, 'data': result.data}
            else:
                return {'success': False, 'error': 'No se pudieron crear los ítems'}
        except Exception as e:
            logger.error(f"Error creando ítems de orden: {str(e)}")
            return {'success': False, 'error': str(e)}