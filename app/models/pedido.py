from app.models.base_model import BaseModel
from typing import Dict, Any, List, Optional
import logging
from app.utils import estados

logger = logging.getLogger(__name__)

class PedidoModel(BaseModel):
    """
    Modelo para gestionar las operaciones de las tablas `pedidos` y `pedido_items`.
    """

    def get_table_name(self) -> str:
        """Devuelve el nombre de la tabla principal."""
        return 'pedidos'

    def _traducir_estado_a_int(self, record: Dict) -> Dict:
        """Traduce el estado de cadena (DB) a entero (lógica) para un registro."""
        if record and 'estado' in record and isinstance(record['estado'], str):
            record['estado'] = estados.traducir_a_int(record['estado'])
        
        if record and 'items' in record:
            for item in record['items']:
                if 'estado' in item and isinstance(item['estado'], str):
                    item['estado'] = estados.traducir_a_int(item['estado'])
        return record

    def _traducir_lista_estados_a_int(self, records: List[Dict]) -> List[Dict]:
        """Aplica la traducción de estado a una lista de registros."""
        return [self._traducir_estado_a_int(record) for record in records]

    def _traducir_estado_a_cadena(self, record: Dict) -> Dict:
        """Traduce el estado de entero (lógica) a cadena (DB) para un registro."""
        if record and 'estado' in record and isinstance(record['estado'], int):
            record['estado'] = estados.traducir_a_cadena(record['estado'])
        return record

    def _traducir_item_estado_a_cadena(self, item: Dict) -> Dict:
        """Traduce el estado de un item de entero a cadena."""
        if item and 'estado' in item and isinstance(item['estado'], int):
            item['estado'] = estados.traducir_a_cadena(item['estado'])
        return item

    def get_one_with_items_and_op_status(self, pedido_id: int) -> Dict:
        """
        Obtiene un pedido con sus items, y para cada item vinculado a una OP,
        añade el estado de esa OP. También añade una bandera 'todas_ops_completadas'
        al diccionario principal del pedido.
        """
        from app.models.orden_produccion import OrdenProduccionModel # Importación local

        pedido_result = self.get_one_with_items(pedido_id) # Reutiliza tu método existente

        if not pedido_result.get('success'):
            return pedido_result # Devolver el error original

        pedido_data = pedido_result['data']
        items = pedido_data.get('items', [])

        # 1. Recolectar IDs de OPs vinculadas
        op_ids_vinculadas = []
        for item in items:
            op_id = item.get('orden_produccion_id')
            if op_id:
                op_ids_vinculadas.append(op_id)

        # 2. Si hay OPs vinculadas, obtener sus estados
        op_estados = {}
        todas_completadas = True # Asumir True inicialmente

        if op_ids_vinculadas:
            op_model = OrdenProduccionModel()
            # Usamos find_by_ids para obtener todas las OPs en una sola consulta
            ops_result = op_model.find_by_ids(list(set(op_ids_vinculadas))) # set() para evitar duplicados

            if ops_result.get('success'):
                ops_encontradas = ops_result.get('data', [])
                for op in ops_encontradas:
                    op_estados[op['id']] = op['estado']
            else:
                # Error crítico si no podemos obtener las OPs
                return {'success': False, 'error': f"Error al obtener estados de OPs vinculadas: {ops_result.get('error')}"}

            # Verificar si todas están completadas
            if len(op_estados) != len(set(op_ids_vinculadas)):
                 # Si no encontramos todas las OPs que esperábamos
                 todas_completadas = False
                 logging.warning(f"Pedido {pedido_id}: No se encontraron todas las OPs vinculadas en la BD.")


            for op_id in op_ids_vinculadas:
                estado = op_estados.get(op_id)
                if estado != 'COMPLETADA':
                    todas_completadas = False
                    break # Basta con una que no esté completada
        else:
             # Si no hay NINGUNA OP vinculada, consideramos que está listo (ej: solo productos comprados)
             todas_completadas = True


        # 3. Añadir estado a cada item y la bandera al pedido
        for item in items:
            op_id = item.get('orden_produccion_id')
            if op_id:
                item['op_estado'] = op_estados.get(op_id, 'DESCONOCIDO') # Añadir estado al item
            else:
                item['op_estado'] = None # No aplica

        pedido_data['todas_ops_completadas'] = todas_completadas

        # Traducir estados a enteros antes de devolver
        pedido_data = self._traducir_estado_a_int(pedido_data)

        return {'success': True, 'data': pedido_data}

    def contar_pedidos_direccion(self, direccion_id: int, exclude_pedido_id: Optional[int] = None) -> int:
        """
        Cuenta cuántos pedidos están asociados a una dirección.
        Opcionalmente, puede excluir un ID de pedido del conteo.
        """
        try:
            query = self.db.table(self.get_table_name()) \
                .select('id', count='exact') \
                .eq('id_direccion_entrega', direccion_id)

            # Si se proporciona un ID de pedido para excluir, se añade un filtro 'not equals'.
            if exclude_pedido_id is not None:
                query = query.not_.eq('id', exclude_pedido_id)

            response = query.execute()

            return response.count if response.count is not None else 0

        except Exception as e:
            logger.error(f"Error contando pedidos por direccion_id {direccion_id}: {e}")
            return 0
    def create_with_items(self, pedido_data: Dict, items_data: List[Dict]) -> Dict:
        """
        Crea un nuevo pedido junto con sus items.
        Simula una transacción ejecutando las operaciones secuencialmente.
        """
        try:
            # Traducir estado del pedido principal a cadena antes de crear
            pedido_data = self._traducir_estado_a_cadena(pedido_data)

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
                    # Asignar estado PENDIENTE por defecto si no viene
                    if 'estado' not in item:
                        item['estado'] = estados.PENDIENTE
                    
                    # Traducir estado del item a cadena
                    item_traducido = self._traducir_item_estado_a_cadena(item)

                    item_data = {
                        'pedido_id': new_pedido_id,
                        'producto_id': item_traducido['producto_id'],
                        'cantidad': item_traducido['cantidad'],
                        'estado': item_traducido.get('estado') 
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
                        if key == 'fecha_desde':
                            query = query.gte('fecha_solicitud', value)
                        elif key == 'fecha_hasta':
                            query = query.lte('fecha_solicitud', value)
                        else:
                            query = query.eq(key, value)
            query = query.order("fecha_solicitud", desc=True).order("id", desc=True)
            result = query.execute()
            
            # Traducir estados a enteros
            translated_data = self._traducir_lista_estados_a_int(result.data)
            
            return {'success': True, 'data': translated_data}
        except Exception as e:
            logger.error(f"Error al obtener pedidos con items: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_one_with_items(self, pedido_id: int) -> Dict:
        """Obtiene un pedido con sus items, especificando la relación."""
        try:

            result = self.db.table(self.get_table_name()).select(
                '*, cliente:clientes(*), items:pedido_items!pedido_items_pedido_id_fkey(*, producto_nombre:productos(nombre, precio_unitario, unidad_medida)), direccion:usuario_direccion(*)'
            ).eq('id', pedido_id).single().execute()


            if result.data:
                # Traducir estados a enteros
                translated_data = self._traducir_estado_a_int(result.data)
                return {'success': True, 'data': translated_data}
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
            # Traducir estado del pedido a cadena antes de actualizar
            pedido_data = self._traducir_estado_a_cadena(pedido_data)

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
                if any(estados.traducir_a_int(item['estado']) != estados.PENDIENTE for item in items_for_deletion):
                    raise Exception(f"No se puede eliminar el producto ID {pid} porque ya está en producción.")

                item_ids_to_delete = [i['id'] for i in items_for_deletion]
                self.db.table('pedido_items').delete().in_('id', item_ids_to_delete).execute()

            # --- Manejar productos añadidos o actualizados ---
            for pid, new_item_data in incoming_items_by_product.items():
                nueva_cantidad_total = int(new_item_data['cantidad'])
                existing_items = existing_items_by_product.get(pid, [])

                # Traducir los estados de los items existentes a enteros para la lógica
                for item in existing_items:
                    item['estado'] = estados.traducir_a_int(item['estado'])

                is_simple_case = len(existing_items) == 1 and existing_items[0]['estado'] == estados.PENDIENTE

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
                        'pedido_id': pedido_id, 'producto_id': pid, 'cantidad': cantidad_a_anadir, 'estado': estados.traducir_a_cadena(estados.PENDIENTE)
                    }).execute()

                elif nueva_cantidad_total < cantidad_existente_total:
                    cantidad_a_reducir = cantidad_existente_total - nueva_cantidad_total
                    items_pendientes = [i for i in existing_items if i['estado'] == estados.PENDIENTE]
                    cantidad_pendiente_total = sum(i['cantidad'] for i in items_pendientes)

                    if cantidad_a_reducir > cantidad_pendiente_total:
                        raise Exception(f"No se puede reducir la cantidad para el producto {pid}. Se intentan reducir {cantidad_a_reducir} unidades, pero solo hay {cantidad_pendiente_total} en estado PENDIENTE.")

                    if items_pendientes:
                        self.db.table('pedido_items').delete().in_('id', [i['id'] for i in items_pendientes]).execute()

                    nueva_cantidad_pendiente = cantidad_pendiente_total - cantidad_a_reducir
                    if nueva_cantidad_pendiente > 0:
                        self.db.table('pedido_items').insert({
                            'pedido_id': pedido_id, 'producto_id': pid, 'cantidad': nueva_cantidad_pendiente, 'estado': estados.traducir_a_cadena(estados.PENDIENTE)
                        }).execute()

            pedido_status_str = pedido_data.get('estado')
            pedido_status = estados.traducir_a_int(pedido_status_str)
            
            status_mapping = {
                estados.EN_PROCESO: estados.EN_PRODUCCION,
                estados.LISTO_PARA_ENTREGAR: estados.ALISTADO,
                estados.COMPLETADO: estados.COMPLETADO,
                estados.CANCELADA: estados.CANCELADA
            }

            if pedido_status in status_mapping:
                target_item_status = status_mapping[pedido_status]
                target_item_status_str = estados.traducir_a_cadena(target_item_status)
                logger.info(f"Propagando estado '{target_item_status_str}' a items pendientes del pedido {pedido_id}.")
                self.db.table('pedido_items').update(
                    {'estado': target_item_status_str}
                ).eq('pedido_id', pedido_id).eq('estado', estados.traducir_a_cadena(estados.PENDIENTE)).execute()

            logger.info(f"Pedido {pedido_id} y sus items actualizados correctamente.")
            return self.get_one_with_items(pedido_id)

        except Exception as e:
            logger.error(f"Error actualizando pedido {pedido_id} con items: {str(e)}")
            return {'success': False, 'error': str(e)}

    def cambiar_estado(self, pedido_id: int, nuevo_estado: int) -> Dict:
        """
        Cambia el estado de un pedido. Recibe el estado como entero.
        Si el nuevo estado es 'CANCELADO', también cancela todos los items pendientes asociados.
        """
        try:
            nuevo_estado_str = estados.traducir_a_cadena(nuevo_estado)
            update_result = self.update(id_value=pedido_id, data={'estado': nuevo_estado_str}, id_field='id')

            if not update_result['success']:
                return update_result

            if nuevo_estado == estados.CANCELADA:
                logger.info(f"Pedido {pedido_id} cancelado. Cancelando sus items 'PENDIENTE'...")
                
                estado_cancelado_str = estados.traducir_a_cadena(estados.CANCELADA)
                estado_pendiente_str = estados.traducir_a_cadena(estados.PENDIENTE)

                items_update_result = self.db.table('pedido_items').update(
                    {'estado': estado_cancelado_str}
                ).eq('pedido_id', pedido_id).eq('estado', estado_pendiente_str).execute()

                if items_update_result.data:
                    logger.info(f"Se cancelaron {len(items_update_result.data)} items para el pedido {pedido_id}.")

            return update_result
        except Exception as e:
            logger.error(f"Error cambiando estado del pedido {pedido_id}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def actualizar_estado_agregado(self, pedido_id: int) -> Dict:
        """
        Recalcula y actualiza el estado de un pedido principal basado en el estado
        de todos sus items, incorporando la nueva lógica de estados.
        """
        try:
            items_result = self.db.table('pedido_items').select('estado').eq('pedido_id', pedido_id).execute()

            if not items_result.data:
                logger.warning(f"No se encontraron items para el pedido {pedido_id} al actualizar estado agregado.")
                return {'success': True, 'message': 'No items found.'}

            estados_items_int = {estados.traducir_a_int(item['estado']) for item in items_result.data}
            nuevo_estado_pedido = None

            # --- NUEVA LÓGICA DE ESTADOS ---
            if estados.EN_PRODUCCION in estados_items_int:
                nuevo_estado_pedido = estados.EN_PROCESO
            elif all(estado == estados.ALISTADO for estado in estados_items_int):
                nuevo_estado_pedido = estados.LISTO_PARA_ARMAR
            elif estados.ALISTADO in estados_items_int and estados.EN_PRODUCCION not in estados_items_int:
                 pass

            if nuevo_estado_pedido is not None:
                pedido_actual_res = self.find_by_id(pedido_id, 'id')
                if pedido_actual_res.get('success'):
                    estado_actual_int = estados.traducir_a_int(pedido_actual_res['data'].get('estado'))
                    if estado_actual_int != nuevo_estado_pedido:
                        logger.info(f"Actualizando estado del pedido {pedido_id} a '{estados.traducir_a_cadena(nuevo_estado_pedido)}'.")
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
            # Traducir estados a enteros antes de procesar
            translated_data = self._traducir_lista_estados_a_int(result.data)

            for item in translated_data:
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
            # Traducir estado a cadena antes de enviar a la BD
            data = self._traducir_estado_a_cadena(data)

            # Asumiendo que la tabla de items se llama 'pedido_items'
            result = self.db.table('pedido_items').update(data).eq('id', item_id).execute()
            if result.data:
                translated_data = self._traducir_estado_a_int(result.data[0])
                return {'success': True, 'data': translated_data}
            return {'success': False, 'error': 'No se pudo actualizar el ítem o no fue encontrado.'}
        except Exception as e:
            logging.error(f"Error actualizando pedido_item {item_id}: {e}")
            return {'success': False, 'error': str(e)}

    def find_by_cliente(self, id_cliente: int):
        try:
            result = self.db.table(self.get_table_name()).select('*').eq('id_cliente', id_cliente).execute()
            if result.data:
                return {'success': True, 'data': result.data}
            else:
                return {'success': False, 'error': 'Orden no encontrada'}
        except Exception as e:
            logger.error(f"Error buscando orden por código: {str(e)}")
            return {'success': False, 'error': str(e)}

    def devolver_pedidos_segun_orden(self, id_orden_produccion: int) -> Dict:
        try:
            # Asumiendo que la tabla de items se llama 'pedido_items'
            result = self.db.table('pedido_items').select('pedido_id').eq('orden_produccion_id', id_orden_produccion).execute()
            if result.data:
                # Extrae los IDs de pedido únicos en una lista
                pedido_ids = list(set([item['pedido_id'] for item in result.data]))

                return {'success': True, 'data': pedido_ids}
            return {'success': True, 'data': []}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def find_by_id_list(self, pedido_ids: List[int]) -> Dict:
        """
        Busca pedidos de venta completos basándose en una lista de IDs.
        """
        if not pedido_ids:
            return {'success': True, 'data': []}

        try:

            query = self.db.table(self.get_table_name()).select('*').in_('id', pedido_ids)

            result = query.execute()

            if result.data:

                return {'success': True, 'data': result.data}
            else:
                return {'success': True, 'data': []}

        except Exception as e:
            logger.error(f"Error buscando pedidos por lista de IDs: {str(e)}")
            return {'success': False, 'error': str(e)}

    # --- MÉTODO NUEVO A AÑADIR ---
    def update_items_by_pedido_id(self, pedido_id: int, data: dict) -> dict:
        """
        Actualiza todos los ítems de un pedido específico.
        """
        try:
            # Traducir estado a cadena antes de la actualización
            data = self._traducir_estado_a_cadena(data)

            # Asumiendo que la tabla de items se llama 'pedido_items'
            result = self.db.table('pedido_items').update(data).eq('pedido_id', pedido_id).execute()

            # La operación de actualización devuelve los datos modificados
            if result.data:
                # Traducir la respuesta de vuelta a enteros
                translated_data = self._traducir_lista_estados_a_int(result.data)
                return {'success': True, 'data': translated_data}
            else:
                # Esto puede ocurrir si el pedido no tenía ítems, lo cual no es un error.
                return {'success': True, 'data': [], 'message': 'No se encontraron ítems para el ID de pedido proporcionado.'}
        except Exception as e:
            logger.error(f"Error actualizando los ítems del pedido {pedido_id}: {e}")
            return {'success': False, 'error': str(e)}
    # --- FIN DEL MÉTODO NUEVO ---
