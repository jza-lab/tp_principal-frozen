from app.models.base_model import BaseModel
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class PedidoModel(BaseModel):
    """
    Modelo para gestionar las operaciones de las tablas `pedidos` y `pedido_items`.
    """

    def get_table_name(self) -> str:
        """Devuelve el nombre de la tabla principal."""
        return 'pedidos'

    def create_with_items(self, pedido_data: Dict, items_data: List[Dict]) -> Dict:
        """
        Crea un nuevo pedido junto con sus items.
        Simula una transacción ejecutando las operaciones secuencialmente.
        """
        try:
            if 'id' in pedido_data:
                pedido_data.pop('id')
            # 1. Crear el pedido principal
            pedido_result = self.create(pedido_data)
            if not pedido_result['success']:
                raise Exception(f"Error al crear el pedido principal: {pedido_result.get('error')}")
            
            new_pedido = pedido_result['data']
            new_pedido_id = new_pedido['id']

            # 2. Crear los items del pedido
            try:
                for item in items_data:
                    item_data = {
                        'pedido_id': new_pedido_id,
                        'producto_id': item['producto_id'],
                        'cantidad': item['cantidad'],
                        # FIX: Asegurar que el estado se incluye
                        'estado': item.get('estado', 'PENDIENTE')
                    }
                    # Usamos el cliente de Supabase directamente para insertar en pedido_items
                    item_insert_result = self.db.table('pedido_items').insert(item_data).execute()
                    if not item_insert_result.data:
                        # Si un item falla, intentamos deshacer el pedido principal.
                        logger.error(f"Error creando item para el pedido {new_pedido_id}. Intentando rollback...")
                        self.delete(id_value=new_pedido_id, id_field='id')
                        raise Exception("Error al crear uno de los items del pedido. Se ha deshecho el pedido.")
            except Exception as e:
                # Si la creación de items falla, eliminamos el pedido que acabamos de crear.
                logger.error(f"Error en la creación de items para el pedido {new_pedido_id}. Deshaciendo... Error: {e}")
                self.delete(id_value=new_pedido_id, id_field='id')
                return {'success': False, 'error': str(e)}

            logger.info(f"Pedido y {len(items_data)} items creados con éxito. Pedido ID: {new_pedido_id}")
            return self.get_one_with_items(new_pedido_id)

        except Exception as e:
            logger.error(f"Error crítico creando pedido con items: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_all_with_items(self, filtros: Optional[Dict] = None) -> Dict:
        """
        Obtiene todos los pedidos, cada uno con una lista de sus items.
        """
        try:
            query = self.db.table(self.table_name).select("*, items:pedido_items(*, productos(nombre))")

            if filtros:
                for key, value in filtros.items():
                    if value is not None:
                        query = query.eq(key, value)

            query = query.order("fecha_solicitud", desc=True).order("id", desc=True)
            result = query.execute()

            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error al obtener pedidos con items: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_one_with_items(self, pedido_id: int) -> Dict:
        """
        Obtiene un pedido específico con todos sus items y datos relacionados.
        """
        try:
            response = self.db.table(self.table_name).select(
                "*, items:pedido_items(*, producto_nombre:productos(nombre))"
            ).eq("id", pedido_id).maybe_single().execute()
            
            result = response.data

            if result:
                for item in result.get('items', []):
                    if item.get('producto_nombre'):
                        # El resultado de la subconsulta es un dict, necesitamos extraer el valor.
                        item['producto_nombre'] = item['producto_nombre']['nombre']
                    else:
                        item['producto_nombre'] = 'N/A'
                return {'success': True, 'data': result}
            else:
                return {'success': False, 'error': f"Pedido con id {pedido_id} no encontrado."}

        except Exception as e:
            logger.error(f"Error al obtener el pedido {pedido_id} con items: {str(e)}")
            return {'success': False, 'error': str(e)}

    def update_with_items(self, pedido_id: int, pedido_data: Dict, items_data: List[Dict]) -> Dict:
        """
        Actualiza un pedido y sus items.
        """
        try:
            # 1. Actualizar el pedido principal

            if 'id' in pedido_data:
                pedido_data.pop('id')
                
            update_result = self.update(id_value=pedido_id, data=pedido_data, id_field='id')
            if not update_result['success']:
                raise Exception(f"Error al actualizar el pedido principal: {update_result.get('error')}")

            # 2. Eliminar los items antiguos (Estrategia de eliminación y reinserción)
            delete_result = self.db.table('pedido_items').delete().eq('pedido_id', pedido_id).execute()
            # No es necesario revisar delete_result a menos que se quiera manejar una falla crítica de DB.

            # 3. Insertar los nuevos items
            for item in items_data:
                item_data = {
                    'pedido_id': pedido_id,
                    'producto_id': item['producto_id'],
                    'cantidad': item['cantidad'],
                    'estado': item['estado'] 
                }
                
                item_insert_result = self.db.table('pedido_items').insert(item_data).execute()
                if not item_insert_result.data:
                    # Si un item falla, una solución real requeriría una transacción a nivel de base de datos.
                    logger.error(f"Error al insertar un nuevo item para el pedido {pedido_id} durante la actualización.")
                    # En este punto, los items antiguos ya se borraron, se debe manejar el error.
                    raise Exception(f"Error al insertar un nuevo item para el pedido {pedido_id} durante la actualización.")

            logger.info(f"Pedido {pedido_id} y sus items actualizados correctamente.")
            return self.get_one_with_items(pedido_id)

        except Exception as e:
            logger.error(f"Error actualizando pedido {pedido_id} con items: {str(e)}")
            return {'success': False, 'error': str(e)}

    def cambiar_estado(self, pedido_id: int, nuevo_estado: str) -> Dict:
        """
        Cambia el estado de un pedido.
        """
        try:
            return self.update(id_value=pedido_id, data={'estado': nuevo_estado}, id_field='id')
        except Exception as e:
            logger.error(f"Error cambiando estado del pedido {pedido_id}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_all_items(self, filters: Optional[Dict] = None) -> Dict:
        """
        Obtiene todos los items de pedido que coinciden con los filtros,
        enriquecidos con el nombre del producto y el cliente.
        """
        try:
            # Seleccionamos campos de pedido_items, el nombre del producto y el nombre del cliente del pedido.
            query = self.db.table('pedido_items').select(
                "*, producto_nombre:productos(nombre), pedido:pedidos(nombre_cliente)"
            )

            if filters:
                for key, value in filters.items():
                    if isinstance(value, tuple) and len(value) == 2:
                        operator, filter_value = value
                        if operator == 'eq':
                            query = query.eq(key, filter_value)
                        elif operator == 'in':
                            query = query.in_(key, filter_value)
                        elif operator == 'is':
                            query = query.is_(key, filter_value)
                    else:
                        query = query.eq(key, value)

            result = query.order("id", desc=True).execute()
            
            # Limpiar y aplanar los datos anidados para un uso más fácil en la plantilla
            for item in result.data:
                # Extraer el nombre del producto
                prod_nombre_data = item.get('producto_nombre')
                if isinstance(prod_nombre_data, dict):
                    item['producto_nombre'] = prod_nombre_data.get('nombre') or 'N/A'
                elif not prod_nombre_data:
                    item['producto_nombre'] = 'N/A'
                
                # Extraer el nombre del cliente
                pedido_data = item.get('pedido')
                if isinstance(pedido_data, dict):
                    item['cliente'] = pedido_data.get('nombre_cliente') or 'N/A'
                else:
                    item['cliente'] = 'N/A'
                # Eliminar el objeto 'pedido' anidado después de extraer el cliente
                item.pop('pedido', None)

            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error al obtener items de pedido: {str(e)}")
            return {'success': False, 'error': str(e)}

    def update_items(self, item_ids: List[int], data: Dict) -> Dict:
        """
        Actualiza múltiples items de pedido en un solo lote.
        """
        try:
            result = self.db.table('pedido_items').update(data).in_('id', item_ids).execute()
            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error al actualizar items de pedido: {str(e)}")
            return {'success': False, 'error': str(e)}