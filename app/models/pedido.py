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
                        'estado': item.get('estado', 'PENDIENTE')
                    }
                    item_insert_result = self.db.table('pedido_items').insert(item_data).execute()
                    if not item_insert_result.data:
                        logger.error(f"Error creando item para el pedido {new_pedido_id}. Intentando rollback...")
                        self.delete(id_value=new_pedido_id, id_field='id')
                        raise Exception("Error al crear uno de los items del pedido. Se ha deshecho el pedido.")
            except Exception as e:
                logger.error(f"Error en la creación de items para el pedido {new_pedido_id}. Deshaciendo... Error: {e}")
                self.delete(id_value=new_pedido_id, id_field='id')
                return {'success': False, 'error': str(e)}

            logger.info(f"Pedido y {len(items_data)} items creados con éxito. Pedido ID: {new_pedido_id}")
            return self.get_one_with_items(new_pedido_id)

        except Exception as e:
            logger.error(f"Error crítico creando pedido con items: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_all_with_items(self, filtros: Optional[Dict] = None) -> Dict:
        """Obtiene todos los pedidos con sus items, especificando la relación."""
        try:
            query = self.db.table(self.get_table_name()).select(
                # --- LÍNEA CORREGIDA ---
                '*, items:pedido_items!pedido_items_pedido_id_fkey(*, producto_nombre:productos(nombre))'
            )
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
        """Obtiene un pedido con sus items, especificando la relación."""
        try:
            # --- LÍNEA CORREGIDA ---
            result = self.db.table(self.get_table_name()).select(
                '*, cliente:clientes(*), items:pedido_items!pedido_items_pedido_id_fkey(*, producto_nombre:productos(nombre)), direccion:usuario_direccion(*)'
            ).eq('id', pedido_id).single().execute()
            # ------------------------

            if result.data:
                return {'success': True, 'data': result.data}
            else:
                return {'success': False, 'error': 'Pedido no encontrado.'}
        except Exception as e:
            logger.error(f"Error al obtener el pedido {pedido_id} con items: {str(e)}")
            return {'success': False, 'error': str(e)}

    def update_with_items(self, pedido_id: int, pedido_data: Dict, items_data: List[Dict]) -> Dict:
        """
        Actualiza un pedido y sus items.
        """
        try:
            if 'id' in pedido_data:
                pedido_data.pop('id')
            update_result = self.update(id_value=pedido_id, data=pedido_data, id_field='id')
            if not update_result['success']:
                raise Exception(f"Error al actualizar los datos del pedido: {update_result.get('error')}")

            existing_items_raw = self.db.table('pedido_items').select('*').eq('pedido_id', pedido_id).execute().data
            existing_items_by_product = {}
            for item in existing_items_raw:
                pid = item['producto_id']
                if pid not in existing_items_by_product:
                    existing_items_by_product[pid] = []
                existing_items_by_product[pid].append(item)

            incoming_items_by_product = {int(item['producto_id']): item for item in items_data}

            form_product_ids = set(incoming_items_by_product.keys())
            db_product_ids = set(existing_items_by_product.keys())

            # --- Manejar productos eliminados del formulario ---
            products_to_remove_ids = db_product_ids - form_product_ids
            for pid in products_to_remove_ids:
                items_for_deletion = existing_items_by_product.get(pid, [])
                if any(item['estado'] != 'PENDIENTE' for item in items_for_deletion):
                    raise Exception(f"No se puede eliminar el producto ID {pid} porque ya está en producción.")

                item_ids_to_delete = [i['id'] for i in items_for_deletion]
                self.db.table('pedido_items').delete().in_('id', item_ids_to_delete).execute()

            # --- Manejar productos añadidos o actualizados ---
            for pid, new_item_data in incoming_items_by_product.items():
                nueva_cantidad_total = int(new_item_data['cantidad'])
                existing_items = existing_items_by_product.get(pid, [])

                is_simple_case = len(existing_items) == 1 and existing_items[0]['estado'] == 'PENDIENTE'

                if is_simple_case:
                    simple_item = existing_items[0]
                    if nueva_cantidad_total > 0:
                        logger.info(f"Caso simple para producto {pid}: actualizando cantidad a {nueva_cantidad_total}.")
                        self.db.table('pedido_items').update({'cantidad': nueva_cantidad_total}).eq('id', simple_item['id']).execute()
                    else:
                        logger.info(f"Caso simple para producto {pid}: cantidad es 0, eliminando item.")
                        self.db.table('pedido_items').delete().eq('id', simple_item['id']).execute()
                    continue

                cantidad_existente_total = sum(i['cantidad'] for i in existing_items)

                if nueva_cantidad_total > cantidad_existente_total:
                    cantidad_a_anadir = nueva_cantidad_total - cantidad_existente_total
                    self.db.table('pedido_items').insert({
                        'pedido_id': pedido_id, 'producto_id': pid, 'cantidad': cantidad_a_anadir, 'estado': 'PENDIENTE'
                    }).execute()

                elif nueva_cantidad_total < cantidad_existente_total:
                    cantidad_a_reducir = cantidad_existente_total - nueva_cantidad_total
                    items_pendientes = [i for i in existing_items if i['estado'] == 'PENDIENTE']
                    cantidad_pendiente_total = sum(i['cantidad'] for i in items_pendientes)

                    if cantidad_a_reducir > cantidad_pendiente_total:
                        raise Exception(f"No se puede reducir la cantidad para el producto {pid}. Se intentan reducir {cantidad_a_reducir} unidades, pero solo hay {cantidad_pendiente_total} en estado PENDIENTE.")

                    if items_pendientes:
                        self.db.table('pedido_items').delete().in_('id', [i['id'] for i in items_pendientes]).execute()

                    nueva_cantidad_pendiente = cantidad_pendiente_total - cantidad_a_reducir
                    if nueva_cantidad_pendiente > 0:
                        self.db.table('pedido_items').insert({
                            'pedido_id': pedido_id, 'producto_id': pid, 'cantidad': nueva_cantidad_pendiente, 'estado': 'PENDIENTE'
                        }).execute()

            pedido_status = pedido_data.get('estado')
            status_mapping = {
                'EN_PROCESO': 'EN_PRODUCCION',
                'LISTO_PARA_ENTREGA': 'ALISTADO',
                'COMPLETADO': 'COMPLETADO',
                'CANCELADO': 'CANCELADO'
            }

            if pedido_status in status_mapping:
                target_item_status = status_mapping[pedido_status]
                logger.info(f"Propagando estado '{target_item_status}' a items pendientes del pedido {pedido_id}.")
                self.db.table('pedido_items').update(
                    {'estado': target_item_status}
                ).eq('pedido_id', pedido_id).eq('estado', 'PENDIENTE').execute()

            logger.info(f"Pedido {pedido_id} y sus items actualizados correctamente.")
            return self.get_one_with_items(pedido_id)

        except Exception as e:
            logger.error(f"Error actualizando pedido {pedido_id} con items: {str(e)}")
            return {'success': False, 'error': str(e)}

    def cambiar_estado(self, pedido_id: int, nuevo_estado: str) -> Dict:
        """
        Cambia el estado de un pedido.
        Si el nuevo estado es 'CANCELADO', también cancela todos los items pendientes asociados.
        """
        try:
            update_result = self.update(id_value=pedido_id, data={'estado': nuevo_estado}, id_field='id')

            if not update_result['success']:
                return update_result

            if nuevo_estado == 'CANCELADO':
                logger.info(f"Pedido {pedido_id} cancelado. Cancelando sus items 'PENDIENTE'...")

                items_update_result = self.db.table('pedido_items').update(
                    {'estado': 'CANCELADO'}
                ).eq('pedido_id', pedido_id).eq('estado', 'PENDIENTE').execute()

                if items_update_result.data:
                    logger.info(f"Se cancelaron {len(items_update_result.data)} items para el pedido {pedido_id}.")

            return update_result
        except Exception as e:
            logger.error(f"Error cambiando estado del pedido {pedido_id}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def actualizar_estado_agregado(self, pedido_id: int) -> Dict:
        """
        Recalcula y actualiza el estado de un pedido principal basado en el estado
        de todos sus items.
        """
        try:
            items_result = self.db.table('pedido_items').select('estado').eq('pedido_id', pedido_id).execute()

            if not items_result.data:
                logger.warning(f"No se encontraron items para el pedido {pedido_id} al actualizar estado agregado.")
                return {'success': True, 'message': 'No items found.'}

            estados_items = {item['estado'] for item in items_result.data}

            nuevo_estado_pedido = None

            # Lógica de estados:
            # Si TODOS los items están 'ALISTADO', el pedido está listo para entrega.
            if all(estado == 'ALISTADO' for estado in estados_items):
                nuevo_estado_pedido = 'LISTO_PARA_ENTREGA'
            # Si AL MENOS UNO está 'EN_PRODUCCION', el pedido está en proceso.
            elif 'EN_PRODUCCION' in estados_items:
                nuevo_estado_pedido = 'EN_PROCESO'

            if nuevo_estado_pedido:
                logger.info(f"Actualizando estado del pedido {pedido_id} a '{nuevo_estado_pedido}'.")
                return self.cambiar_estado(pedido_id, nuevo_estado_pedido)

            return {'success': True, 'message': 'No state change required.'}

        except Exception as e:
            logger.error(f"Error al actualizar estado agregado para el pedido {pedido_id}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_all_items(self, filters: Optional[Dict] = None) -> Dict:
        """
        Obtiene todos los items de pedido que coinciden con los filtros,
        enriquecidos con el nombre del producto y el cliente.
        """
        try:
            # --- CONSULTA CORREGIDA ---
            # Añadimos '!pedido_items_pedido_id_fkey' para desambiguar la relación con la tabla 'pedidos'.
            query = self.db.table('pedido_items').select(
                '*, producto_nombre:productos(nombre), pedido:pedidos!pedido_items_pedido_id_fkey(nombre_cliente, id)'
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

    def update_item(self, item_id: int, data: Dict) -> Dict:
        """Actualiza un único ítem de pedido."""
        try:
            # Asumiendo que la tabla de items se llama 'pedido_items'
            result = self.db.table('pedido_items').update(data).eq('id', item_id).execute()
            if result.data:
                return {'success': True, 'data': result.data[0]}
            return {'success': False, 'error': 'No se pudo actualizar el ítem o no fue encontrado.'}
        except Exception as e:
            logging.error(f"Error actualizando pedido_item {item_id}: {e}")
            return {'success': False, 'error': str(e)}