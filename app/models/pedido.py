from dataclasses import dataclass, asdict, fields
from typing import Optional, List, Dict
from datetime import date, datetime
import json
from app.models.base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

@dataclass
class PedidoItem:
    """Representa un ítem de producto dentro de un pedido."""
    id: Optional[int] = None
    pedido_id: Optional[int] = None
    producto_id: int
    cantidad: float

@dataclass
class Pedido:
    """Representa un pedido de un cliente que puede contener múltiples productos."""
    id: Optional[int] = None
    nombre_cliente: str
    fecha_solicitud: date
    items: List[PedidoItem]
    estado: str = 'PENDIENTE'
    orden_produccion_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convierte la instancia del modelo a un diccionario, incluyendo los items."""
        d = asdict(self)
        d['items'] = [asdict(item) for item in self.items]
        for key, value in d.items():
            if isinstance(value, (datetime, date)):
                d[key] = value.isoformat() if value else None
        return d

class PedidoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de pedidos y sus ítems en la base de datos.
    Utiliza el cliente de Supabase para realizar las operaciones.
    """
    def get_table_name(self) -> str:
        """Retorna el nombre de la tabla principal de pedidos."""
        return "pedidos"

    def _get_items_table_name(self) -> str:
        """Retorna el nombre de la tabla de ítems de pedido."""
        return "pedido_items"

    def create(self, pedido: Pedido) -> dict:
        """
        Crea un nuevo pedido con sus ítems llamando a una función de la base de datos.
        """
        if not isinstance(pedido, Pedido) or not pedido.items:
            return {'success': False, 'error': 'Datos de pedido inválidos o sin ítems.'}

        try:
            # Preparamos los datos para la función de la BD
            items_json = json.dumps([{'producto_id': item.producto_id, 'cantidad': item.cantidad} for item in pedido.items])

            # Llamamos a la función RPC de Supabase
            result = self.db.rpc('crear_pedido_con_items', {
                'p_nombre_cliente': pedido.nombre_cliente,
                'p_fecha_solicitud': pedido.fecha_solicitud.isoformat(),
                'p_items': items_json
            }).execute()

            if result.data:
                new_pedido_id = result.data
                # Devolvemos el pedido completo buscándolo por el nuevo ID
                return self.find_by_id(new_pedido_id)
            else:
                # El error puede estar en la respuesta de Supabase o en la ejecución
                error_msg = 'No se pudo crear el pedido. La función no retornó un ID.'
                logger.error(error_msg)
                return {'success': False, 'error': error_msg}

        except Exception as e:
            logger.error(f"Error de base de datos al crear pedido: {e}")
            return {'success': False, 'error': f"Error de base de datos: {e}"}

    def find_by_id(self, pedido_id: int) -> dict:
        """
        Busca un pedido por su ID y carga todos sus ítems asociados usando una consulta anidada.
        """
        try:
            # Supabase permite seleccionar de tablas relacionadas
            result = self.db.table(self.get_table_name())\
                .select('*, pedido_items(*)').eq('id', pedido_id).execute()

            if result.data:
                pedido_data = result.data[0]
                pedido_obj = self._create_pedido_from_dict(pedido_data)
                return {'success': True, 'data': pedido_obj}
            else:
                return {'success': False, 'error': 'Pedido no encontrado'}
        except Exception as e:
            logger.error(f"Error buscando pedido por ID {pedido_id}: {e}")
            return {'success': False, 'error': str(e)}

    def find_all(self, filters: Optional[Dict] = None, order_by: str = 'created_at', limit: Optional[int] = None) -> Dict:
        """
        Busca todos los pedidos y carga sus ítems para evitar el problema N+1.
        """
        try:
            query = self.db.table(self.get_table_name()).select('*, pedido_items(*)')

            # Aplicar filtros si existen
            if filters:
                for key, value in filters.items():
                    if isinstance(value, tuple) and len(value) == 2:
                        operator, filter_value = value
                        if operator.lower() == 'in':
                            query = query.in_(key, filter_value)
                    else:
                        query = query.eq(key, value)

            query = query.order(order_by, desc=True)

            if limit:
                query = query.limit(limit)

            result = query.execute()

            if result.data:
                pedidos_list = [self._create_pedido_from_dict(p) for p in result.data]
                return {'success': True, 'data': pedidos_list}
            else:
                return {'success': True, 'data': []} # No es un error si no hay pedidos

        except Exception as e:
            logger.error(f"Error obteniendo todos los pedidos: {e}")
            return {'success': False, 'error': str(e)}

    def _create_item_from_dict(self, data: dict) -> PedidoItem:
        """Crea un objeto PedidoItem a partir de un diccionario."""
        if not data:
            return None
        item_fields = {f.name for f in fields(PedidoItem)}
        filtered_data = {k: v for k, v in data.items() if k in item_fields}
        return PedidoItem(**filtered_data)

    def _create_pedido_from_dict(self, data: dict) -> Pedido:
        """Crea un objeto Pedido a partir de un diccionario, incluyendo sus ítems."""
        if not data:
            return None

        # Supabase devuelve la tabla relacionada con su nombre ('pedido_items')
        item_dicts = data.get('pedido_items', [])
        items = [self._create_item_from_dict(item_data) for item_data in item_dicts]

        pedido_fields = {f.name for f in fields(Pedido)}
        filtered_data = {k: v for k, v in data.items() if k in pedido_fields}

        # Manejo de fechas que vienen como string
        if 'fecha_solicitud' in filtered_data and isinstance(filtered_data['fecha_solicitud'], str):
            filtered_data['fecha_solicitud'] = date.fromisoformat(filtered_data['fecha_solicitud'])
        if 'created_at' in filtered_data and isinstance(filtered_data['created_at'], str):
            filtered_data['created_at'] = datetime.fromisoformat(filtered_data['created_at'])
        if 'updated_at' in filtered_data and filtered_data['updated_at'] and isinstance(filtered_data['updated_at'], str):
            filtered_data['updated_at'] = datetime.fromisoformat(filtered_data['updated_at'])

        filtered_data['items'] = items

        return Pedido(**filtered_data)