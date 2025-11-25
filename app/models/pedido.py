from app.models.base_model import BaseModel
from typing import Dict, Any, List, Optional
import logging
from postgrest.exceptions import APIError
from datetime import date, timedelta, datetime
from app.utils import estados

from decimal import Decimal # Importar Decimal
logger = logging.getLogger(__name__)

class PedidoModel(BaseModel):
    """
    Modelo para gestionar las operaciones de las tablas `pedidos` y `pedido_items`.
    """

    def get_table_name(self) -> str:
        """Devuelve el nombre de la tabla principal."""
        return 'pedidos'

    def get_one_with_items_and_op_status(self, pedido_id: int) -> Dict:
        """
        Obtiene un pedido con sus items y todas las OPs asociadas (padre e hijas).
        Cada item tendrá una lista `ordenes_produccion` con los detalles de las OPs.
        """
        from app.models.orden_produccion import OrdenProduccionModel
        from app.models.asignacion_pedido_model import AsignacionPedidoModel
        from collections import defaultdict
        from decimal import Decimal

        pedido_result = self.get_one_with_items(pedido_id)

        if not pedido_result.get('success'):
            return pedido_result

        pedido_data = pedido_result['data']
        items = pedido_data.get('items', [])

        if not items:
            pedido_data['todas_ops_completadas'] = True
            return {'success': True, 'data': pedido_data}

        # 1. Para cada item del pedido, recolectar las OPs directamente asignadas
        all_op_ids = set()
        ops_por_item = defaultdict(set)
        item_ids = [item['id'] for item in items]

        # Buscar en la tabla de asignaciones, que es la fuente de verdad
        asignacion_model = AsignacionPedidoModel()
        asignaciones_res = asignacion_model.find_all(filters={'pedido_item_id': ('in', item_ids)})

        if asignaciones_res.get('success') and asignaciones_res.get('data'):
            for asignacion in asignaciones_res['data']:
                op_id = asignacion['orden_produccion_id']
                item_id = asignacion['pedido_item_id']
                all_op_ids.add(op_id)
                ops_por_item[item_id].add(op_id)

        # Asegurar que la OP padre (directa del item) también esté, por si no hay asignación explícita
        for item in items:
            if item.get('orden_produccion_id'):
                op_id = item.get('orden_produccion_id')
                all_op_ids.add(op_id)
                ops_por_item[item['id']].add(op_id)

        # 2. Si hay OPs, obtener sus datos completos y calcular la producción total asignada
        ops_data_map = {}
        total_cantidad_producida_asignada = Decimal('0') # Para la lógica de 'todas_ops_completadas'

        if all_op_ids:
            op_model = OrdenProduccionModel()
            ops_result = op_model.find_by_ids(list(all_op_ids))

            if ops_result.get('success'):
                for op in ops_result['data']:
                    ops_data_map[op['id']] = op
                    # Sumar solo si la OP está completada para la lógica de 'todas_ops_completadas'
                    if op.get('estado') == 'COMPLETADA':
                         total_cantidad_producida_asignada += Decimal(str(op.get('cantidad_producida', '0')))
                    elif op.get('estado') == 'CONSOLIDADA':
                         pass
            else:
                return {'success': False, 'error': f"Error al obtener datos de OPs vinculadas: {ops_result.get('error')}"}

        # 3. Adjuntar la lista de OPs a cada item y CALCULAR STOCK REAL
        for item in items:
            # A. Lógica de OPs (Mantenemos la de HEAD para soporte múltiple)
            item_op_ids = ops_por_item.get(item['id'], set())
            item['ordenes_produccion'] = [ops_data_map[op_id] for op_id in item_op_ids if op_id in ops_data_map]

            # B. Lógica de Stock (Mantenemos la CORRECCIÓN de dev-gonza)
            # IMPORTANTE: Filtrar por estado='RESERVADO' para que las reservas 'CANCELADO' (robadas) no sumen.
            reservas_res = self.db.table('reservas_productos')\
                .select('cantidad_reservada')\
                .eq('pedido_item_id', item['id'])\
                .eq('estado', 'RESERVADO')\
                .execute()

            cantidad_lote = 0
            if reservas_res.data:
                cantidad_lote = sum(float(r['cantidad_reservada']) for r in reservas_res.data)

            item['cantidad_lote'] = cantidad_lote
            item['cantidad_produccion'] = max(0, float(item['cantidad']) - cantidad_lote)

        # 4. Determinar si el pedido está completo basado en las cantidades
        total_cantidad_requerida = sum(Decimal(str(it.get('cantidad', '0'))) for it in items)

        # El pedido está completo si la producción asignada cubre la demanda total.
        # Nota: Esto es una simplificación, idealmente se compara item por item.
        pedido_data['todas_ops_completadas'] = total_cantidad_producida_asignada >= total_cantidad_requerida

        # 5. Obtener datos de despacho y mapear la información del vehículo/conductor
        pedido_data['despacho'] = None
        try:
            # Intentamos obtener el despacho junto con el vehículo asociado
            # Nota: En Supabase, 'vehiculo:vehiculo_id(*)' hace el join con la tabla vehiculos usando la FK vehiculo_id
            item_despacho_res = self.db.table('despacho_items').select('despachos(*, vehiculo:vehiculos(*))').eq('pedido_id', pedido_id).execute()
            
            if item_despacho_res and item_despacho_res.data:
                despacho_raw = item_despacho_res.data[0].get('despachos')
                if despacho_raw:
                    # Inicializamos el objeto despacho con los datos crudos de la tabla despachos
                    pedido_data['despacho'] = despacho_raw
                    
                    # Extraemos el objeto vehículo (si existe)
                    vehiculo = despacho_raw.get('vehiculo')
                    
                    # Mapeamos los campos del vehículo a las claves que espera la plantilla
                    # Si el despacho ya tiene estos campos (legacy), se conservan. Si no, se usan los del vehículo.
                    if vehiculo:
                        pedido_data['despacho']['nombre_transportista'] = despacho_raw.get('nombre_transportista') or vehiculo.get('nombre_conductor')
                        pedido_data['despacho']['dni_transportista'] = despacho_raw.get('dni_transportista') or vehiculo.get('dni_conductor')
                        pedido_data['despacho']['patente_vehiculo'] = despacho_raw.get('patente_vehiculo') or vehiculo.get('patente')
                        pedido_data['despacho']['telefono_transportista'] = despacho_raw.get('telefono_transportista') or vehiculo.get('telefono_conductor')
                    
                    # Aseguramos que las observaciones estén presentes
                    pedido_data['despacho']['observaciones'] = despacho_raw.get('observaciones')

        except Exception as e:
            logger.warning(f"No se pudieron obtener datos de despacho para el pedido {pedido_id}. Error: {str(e)}")

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
            if 'id' in pedido_data:
                pedido_data.pop('id')
                pedido_data.setdefault('condicion_venta', 'contado')
                pedido_data.setdefault('estado_pago', 'pendiente')

            # Eliminar la clave 'token_seguimiento' si existe, para evitar errores de BD.
            pedido_data.pop('token_seguimiento', None)

            # 1. Crear el pedido principal
            pedido_result = self.create(pedido_data)
            if not pedido_result['success']:
                raise Exception(f"Error al crear el pedido principal: {pedido_result.get('error')}")

            new_pedido = pedido_result['data']
            new_pedido_id = new_pedido['id']

            # 2. Crear los items del pedido
            try:
                # --- NUEVO: Obtener costos dinámicos e insertar ---
                # Para evitar dependencias circulares, importamos aquí
                from app.controllers.rentabilidad_controller import RentabilidadController
                rentabilidad_controller = RentabilidadController()
                from app.models.producto import ProductoModel
                producto_model = ProductoModel()

                # Pre-fetch de productos para obtener precio_unitario actual
                producto_ids = [item['producto_id'] for item in items_data]
                productos_res = producto_model.find_all(filters={'id': producto_ids})
                productos_map = {p['id']: p for p in productos_res.get('data', [])} if productos_res.get('success') else {}

                # Pre-fetch de roles para cálculo de costos (optimización)
                roles_resp = rentabilidad_controller.rol_model.find_all()
                roles_map = {r['id']: float(r.get('costo_por_hora') or 0) for r in roles_resp.get('data', [])} if roles_resp.get('success') else {}

                for item in items_data:
                    producto_id = int(item['producto_id'])
                    producto_data_actual = productos_map.get(producto_id, {})
                    
                    # Calcular costo unitario actual (snapshot)
                    costos = rentabilidad_controller._calcular_costos_unitarios_dinamicos(producto_data_actual, roles_map)
                    costo_unitario_snapshot = costos.get('costo_variable_unitario', 0.0)
                    
                    # Obtener precio unitario actual (snapshot)
                    precio_unitario_snapshot = float(producto_data_actual.get('precio_unitario', 0.0) or 0.0)

                    item_data = {
                        'pedido_id': new_pedido_id,
                        'producto_id': producto_id,
                        'cantidad': item['cantidad'],
                        'estado': item.get('estado', 'PENDIENTE'),
                        # --- COLUMNAS NUEVAS ---
                        'precio_unitario': precio_unitario_snapshot,
                        'costo_unitario': costo_unitario_snapshot
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
        """Obtiene todos los pedidos con sus items, cliente y dirección."""
        try:
            query = self.db.table(self.get_table_name()).select(
                '*, '
                'cliente:clientes(*),'
                'direccion:id_direccion_entrega(*),'
                'pedido_items:pedido_items!pedido_items_pedido_id_fkey(*, producto_nombre:productos(nombre))'
            )
            if filtros:
                # Procesar rango_fecha primero si existe
                if 'rango_fecha' in filtros:
                    rango = filtros.pop('rango_fecha') # Eliminar para no procesarlo en el bucle
                    today = date.today()
                    if rango == 'hoy':
                        query = query.eq('fecha_solicitud', today.isoformat())
                    elif rango == 'ultimos-7':
                        fecha_desde = today - timedelta(days=7)
                        query = query.gte('fecha_solicitud', fecha_desde.isoformat())
                    elif rango == 'ultimos-30':
                        fecha_desde = today - timedelta(days=30)
                        query = query.gte('fecha_solicitud', fecha_desde.isoformat())

                # Procesar otros filtros
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
            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error al obtener pedidos con items: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_one_with_items(self, pedido_id: int) -> Dict:
        """
        Obtiene un pedido con sus items, cliente (incluyendo email) y dirección de entrega.
        """
        try:
            # Consulta corregida y optimizada
            result = self.db.table(self.get_table_name()).select(
                '*, '
                'cliente:clientes(email, nombre, cuit), '
                'items:pedido_items!pedido_items_pedido_id_fkey(*, producto_nombre:productos(nombre, precio_unitario, unidad_medida)), '
                'direccion:id_direccion_entrega(*)'
            ).eq('id', pedido_id).single().execute()

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
            # --- NUEVO: Obtener costos dinámicos e insertar para items NUEVOS ---
            from app.controllers.rentabilidad_controller import RentabilidadController
            rentabilidad_controller = RentabilidadController()
            from app.models.producto import ProductoModel
            producto_model = ProductoModel()

            # Pre-fetch roles
            roles_resp = rentabilidad_controller.rol_model.find_all()
            roles_map = {r['id']: float(r.get('costo_por_hora') or 0) for r in roles_resp.get('data', [])} if roles_resp.get('success') else {}

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
                    
                    # Calcular costos snapshot para el NUEVO item
                    producto_info_res = producto_model.find_by_id(pid)
                    producto_data_actual = producto_info_res.get('data', {})
                    costos = rentabilidad_controller._calcular_costos_unitarios_dinamicos(producto_data_actual, roles_map)
                    costo_unitario_snapshot = costos.get('costo_variable_unitario', 0.0)
                    precio_unitario_snapshot = float(producto_data_actual.get('precio_unitario', 0.0) or 0.0)

                    self.db.table('pedido_items').insert({
                        'pedido_id': pedido_id, 
                        'producto_id': pid, 
                        'cantidad': cantidad_a_anadir, 
                        'estado': 'PENDIENTE',
                        'precio_unitario': precio_unitario_snapshot,
                        'costo_unitario': costo_unitario_snapshot
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
                        # Para el item reducido, recalculamos o copiamos? Mejor crear nuevo con snapshot actual
                        producto_info_res = producto_model.find_by_id(pid)
                        producto_data_actual = producto_info_res.get('data', {})
                        costos = rentabilidad_controller._calcular_costos_unitarios_dinamicos(producto_data_actual, roles_map)
                        costo_unitario_snapshot = costos.get('costo_variable_unitario', 0.0)
                        precio_unitario_snapshot = float(producto_data_actual.get('precio_unitario', 0.0) or 0.0)
                        
                        self.db.table('pedido_items').insert({
                            'pedido_id': pedido_id, 'producto_id': pid, 'cantidad': nueva_cantidad_pendiente, 'estado': 'PENDIENTE',
                            'precio_unitario': precio_unitario_snapshot,
                            'costo_unitario': costo_unitario_snapshot
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
        de todos sus items, incorporando la nueva lógica de estados.
        """
        try:
            items_result = self.db.table('pedido_items').select('estado').eq('pedido_id', pedido_id).execute()

            if not items_result.data:
                logger.warning(f"No se encontraron items para el pedido {pedido_id} al actualizar estado agregado.")
                return {'success': True, 'message': 'No items found.'}

            estados_items = {item['estado'] for item in items_result.data}
            nuevo_estado_pedido = None

            # --- NUEVA LÓGICA DE ESTADOS ---
            # 1. Si al menos un item está 'EN_PRODUCCION', el pedido está 'EN_PROCESO'.
            if 'EN_PRODUCCION' in estados_items:
                nuevo_estado_pedido = 'EN_PROCESO'
            # 2. Si TODOS los items están 'ALISTADO', el pedido pasa a 'LISTO PARA ENTREGAR'.
            elif all(estado == 'ALISTADO' for estado in estados_items):
                nuevo_estado_pedido = 'LISTO_PARA_ENTREGA'
            # 3. Si no hay items en producción y no todos están alistados, pero al menos uno lo está,
            #    se mantiene EN_PROCESO (o el estado que tuviera).
            elif 'ALISTADO' in estados_items and 'EN_PRODUCCION' not in estados_items:
                 # Esta condición puede ser más compleja. Por ahora, si hay una mezcla
                 # de PENDIENTE y ALISTADO, se podría considerar EN_PROCESO.
                 # O simplemente no cambiar el estado hasta que todo esté listo.
                 # Por simplicidad, no hacemos nada y esperamos a que todos los items avancen.
                 pass


            if nuevo_estado_pedido:
                # Obtenemos el estado actual para evitar actualizaciones redundantes
                pedido_actual_res = self.find_by_id(pedido_id, 'id')
                if pedido_actual_res.get('success') and pedido_actual_res['data'].get('estado') != nuevo_estado_pedido:
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

    def find_all_items_with_pedido_info(self, filters: Optional[Dict] = None, order_by: Optional[str] = None) -> Dict:
        """
        Obtiene todos los items de pedido que coinciden con los filtros,
        anidando la información completa del pedido padre.
        AHORA SOPORTA ORDENAMIENTO.
        """
        try:
            # Se especifica la clave foránea para resolver la ambigüedad en la relación.
            query = self.db.table('pedido_items').select('*, pedido:pedidos!pedido_items_pedido_id_fkey!inner(*)')

            if filters:
                for key, value in filters.items():
                    if isinstance(value, tuple) and len(value) == 2:
                        operator, filter_value = value
                        if operator == 'in':
                            query = query.in_(key, filter_value)
                        else:
                            query = query.eq(key, filter_value)
                    else:
                        query = query.eq(key, value)

            if order_by:
                # El formato es "tabla_relacionada.columna.direccion", ej: "pedido.created_at.asc"
                parts = order_by.split('.')
                if len(parts) == 3:
                    foreign_table = parts[0]
                    column_name = parts[1]
                    ascending = parts[2].lower() == 'asc'
                    
                    # Usamos el método .order() con el argumento `foreign_table`
                    query = query.order(column_name, desc=not ascending, foreign_table=foreign_table)

            result = query.execute()
            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error al obtener items de pedido con info de pedido: {str(e)}")
            return {'success': False, 'error': str(e)}

    def update_items(self, item_ids: List[int], data: Dict) -> Dict:
        """Actualiza una lista de items de pedido por sus IDs."""
        try:
            result = self.db.table('pedido_items').update(data).in_('id', item_ids).execute()
            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error actualizando items de pedido: {str(e)}")
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
        (CORREGIDO: Ahora incluye datos anidados de cliente y dirección)
        """
        if not pedido_ids:
            return {'success': True, 'data': []}

        try:
            # Consulta corregida para incluir relaciones que se usan en los templates
            result = self.db.table(self.get_table_name()).select(
                '*, '
                'cliente:clientes(email, nombre, cuit, razon_social), '
                'direccion:id_direccion_entrega(*)'
            ).in_('id', pedido_ids).execute()

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
            # Asumiendo que la tabla de items se llama 'pedido_items'
            result = self.db.table('pedido_items').update(data).eq('pedido_id', pedido_id).execute()

            # La operación de actualización devuelve los datos modificados
            if result.data:
                return {'success': True, 'data': result.data}
            else:
                # Esto puede ocurrir si el pedido no tenía ítems, lo cual no es un error.
                return {'success': True, 'data': [], 'message': 'No se encontraron ítems para el ID de pedido proporcionado.'}
        except Exception as e:
            logger.error(f"Error actualizando los ítems del pedido {pedido_id}: {e}")
            return {'success': False, 'error': str(e)}
    # --- FIN DEL MÉTODO NUEVO ---

    def get_pedidos_by_lote_producto(self, id_lote_producto: str) -> Dict:
        """
        Encuentra los pedidos y clientes que recibieron un lote de producto específico.
        Utiliza la tabla de asignación 'reserva_productos'.
        """
        try:
            reserva_result = self.db.table('reservas_productos').select(
                'cantidad_reservada, pedido_items!inner(pedido_id, pedidos!pedido_items_pedido_id_fkey!inner(id, nombre_cliente, codigo_pedido))'
            ).eq('lote_producto_id', id_lote_producto).execute()
            # --- FIN DE LA CORRECCIÓN ---
            if not reserva_result.data:
                return {'success': True, 'data': []}

            pedidos = []

            # Procesar TODOS los items
            for item in reserva_result.data:
                item_data = item.get('pedido_items')
                if not item_data: continue
                pedido_data = item_data.get('pedidos')
                if not pedido_data: continue

                    # Usar el codigo_pedido si existe, sino un fallback con el ID
                pedido_nombre = pedido_data.get('codigo_pedido') or f"Venta-{pedido_data.get('id')}"
                pedidos.append({
                            'id': pedido_data.get('id'),
                    'cliente_nombre': pedido_nombre, # Usamos el nombre único del pedido
                    'cantidad_vendida': item.get('cantidad_reservada', 0)
                })

            return {'success': True, 'data': pedidos}

        except Exception as e:
            logger.error(f"Error buscando pedidos por lote de producto {id_lote_producto}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def get_ingresos_en_periodo(self, fecha_inicio, fecha_fin, estados_filtro=None):
        try:
            query = self.db.table(self.get_table_name()).select('fecha_solicitud, precio_orden').gte('fecha_solicitud', fecha_inicio).lte('fecha_solicitud', fecha_fin)
            
            if estados_filtro:
                query = query.in_('estado', estados_filtro)
            else:
                query = query.eq('estado', 'COMPLETADO')
            
            result = query.execute()            
            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error obteniendo ingresos: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_top_selling_products(self, limit=5):
        try:
            result = self.db.rpc('get_top_productos_vendidos', {'limite': limit}).execute()
            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error obteniendo top productos: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_sales_by_product_in_period(self, start_date, end_date):
        """
        Calcula la cantidad total vendida de cada producto en un período de tiempo.
        Este método es más robusto al realizar la consulta en dos pasos.
        """
        try:
            # Paso 1: Obtener los IDs de los pedidos dentro del rango de fechas.
            pedidos_response = self.db.table(self.get_table_name()).select('id').gte('fecha_solicitud', start_date.isoformat()).lte('fecha_solicitud', end_date.isoformat()).execute()

            if not pedidos_response.data:
                return {'success': True, 'data': {}}

            pedido_ids = [p['id'] for p in pedidos_response.data]

            # Paso 2: Obtener los items de esos pedidos y agruparlos.
            items_response = self.db.table('pedido_items').select(
                'cantidad, productos!inner(nombre)'
            ).in_('pedido_id', pedido_ids).execute()

            if not items_response.data:
                return {'success': True, 'data': {}}

            sales_data = {}
            for item in items_response.data:
                # Asegurarse de que el producto no sea nulo
                if not item.get('productos'):
                    continue

                nombre_producto = item['productos']['nombre']
                cantidad = float(item['cantidad'])

                if nombre_producto in sales_data:
                    sales_data[nombre_producto] += cantidad
                else:
                    sales_data[nombre_producto] = cantidad

            return {'success': True, 'data': sales_data}

        except Exception as e:
            logger.error(f"Error en get_sales_by_product_in_period: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def count_by_estado_in_date_range(self, estado: str, fecha_inicio: datetime, fecha_fin: datetime) -> Dict:
        """
        Cuenta los pedidos por estado en un rango de fechas.
        """
        try:
            query = self.db.table(self.get_table_name()).select("id", count='exact')
            query = query.eq('estado', estado)
            query = query.gte('fecha_solicitud', fecha_inicio.isoformat())
            query = query.lte('fecha_solicitud', fecha_fin.isoformat())
            result = query.execute()

            return {'success': True, 'count': result.count}

        except Exception as e:
            logger.error(f"Error contando pedidos por estado y rango de fecha: {str(e)}", exc_info=True)
            return {'success': False, 'count': 0}

    def count_by_estados_in_date_range(self, estados: List[str], fecha_inicio: datetime, fecha_fin: datetime) -> Dict:
        """
        Cuenta los pedidos por una lista de estados en un rango de fechas.
        """
        try:
            query = self.db.table(self.get_table_name()).select("id", count='exact')
            query = query.in_('estado', estados)
            query = query.gte('fecha_solicitud', fecha_inicio.isoformat())
            query = query.lte('fecha_solicitud', fecha_fin.isoformat())
            result = query.execute()

            return {'success': True, 'count': result.count}
        except Exception as e:
            logger.error(f"Error contando pedidos por estados y rango de fecha: {str(e)}", exc_info=True)
            return {'success': False, 'count': 0}

    def count_completed_on_time_in_date_range(self, fecha_inicio: datetime, fecha_fin: datetime) -> Dict:
        """
        Cuenta los pedidos completados a tiempo en un rango de fechas.
        Se considera "a tiempo" si la fecha de actualización (cuando se completó) es menor o igual a la fecha requerida.
        """
        try:
            query = self.db.table(self.get_table_name()).select('updated_at, fecha_requerido')
            query = query.eq('estado', estados.OV_COMPLETADO)
            query = query.gte('fecha_solicitud', fecha_inicio.isoformat())
            query = query.lte('fecha_solicitud', fecha_fin.isoformat())
            result = query.execute()

            if not result.data:
                return {'success': True, 'count': 0}

            on_time_count = 0
            for pedido in result.data:
                if pedido.get('updated_at') and pedido.get('fecha_requerido'):
                    try:
                        completion_date = datetime.fromisoformat(pedido['updated_at']).date()
                        required_date = datetime.strptime(pedido['fecha_requerido'], '%Y-%m-%d').date()
                        if completion_date <= required_date:
                            on_time_count += 1
                    except (ValueError, TypeError):
                        # Ignorar si las fechas tienen un formato incorrecto
                        continue

            return {'success': True, 'count': on_time_count}

        except Exception as e:
            logger.error(f"Error contando pedidos completados a tiempo: {str(e)}", exc_info=True)
            return {'success': False, 'count': 0}

    def get_total_valor_pedidos_completados(self, fecha_inicio: datetime, fecha_fin: datetime) -> Dict:
        """
        Obtiene la suma del valor total de los pedidos completados en un rango de fechas.
        """
        try:
            query = self.db.table(self.get_table_name()).select('precio_orden').eq('estado', estados.OV_COMPLETADO).gte('fecha_solicitud', fecha_inicio.isoformat()).lte('fecha_solicitud', fecha_fin.isoformat())
            result = query.execute()

            if not result.data:
                return {'success': True, 'total_valor': 0}

            total_valor = sum(item.get('precio_orden', 0) for item in result.data if item.get('precio_orden') is not None)
            return {'success': True, 'total_valor': total_valor}
        except Exception as e:
            logger.error(f"Error obteniendo el valor total de pedidos completados: {str(e)}")
            return {'success': False, 'error': str(e), 'total_valor': 0}

    def get_reservas_for_item(self, item_id: int) -> List[Dict]:
        """Obtiene las reservas de lotes de producto para un item de pedido específico."""
        try:
            reservas_res = self.db.table('reservas_productos').select('*').eq('pedido_item_id', item_id).execute()
            return reservas_res.data or []
        except Exception as e:
            logger.error(f"Error obteniendo reservas para el item {item_id}: {e}")
            return []


    def obtener_anos_distintos(self) -> Dict:
        """
        Obtiene los años únicos en los que se crearon pedidos.
        Implementación en Python para evitar la dependencia de una RPC.
        """
        try:
            # Selecciona solo la columna de fecha para minimizar la transferencia de datos.
            response = self.db.table(self.get_table_name()).select('fecha_solicitud').execute()
            
            if response.data:
                # Usa un set para obtener años únicos eficientemente.
                years = {
                    datetime.fromisoformat(item['fecha_solicitud']).year 
                    for item in response.data 
                    if item.get('fecha_solicitud')
                }
                # Devuelve una lista ordenada de años.
                return {'success': True, 'data': sorted(list(years), reverse=True)}
            
            # Si no hay datos, devuelve una lista vacía.
            return {'success': True, 'data': []}

        except Exception as e:
            logger.error(f"Error obteniendo años distintos de pedidos (implementación Python): {str(e)}")
            # Fallback en caso de error: devolver el año actual.
            return {'success': True, 'data': [datetime.now().year]}

class PedidoItemModel(BaseModel):
    """Modelo para la tabla pedido_items"""

    def get_table_name(self) -> str:
        return 'pedido_items'

    def get_primary_key(self) -> str:
        return 'id'
