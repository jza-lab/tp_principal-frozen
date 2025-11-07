from app.models.base_model import BaseModel
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

class InventarioModel(BaseModel):
    """Modelo para la tabla insumos_inventario"""

    def get_table_name(self) -> str:
        return 'insumos_inventario'
    
    # --- Métodos de utilidad para la base de datos ---
    
    def _sanitize_dates_for_db(self, data: Dict) -> Dict:
        """
        Convierte objetos date/datetime de Python a strings ISO 8601
        antes de enviarlos a Supabase, lo cual es necesario para evitar
        errores de serialización en el método update genérico.
        """
        sanitized_data = data.copy()
        for key, value in sanitized_data.items():
            # Si el valor es una instancia de date o datetime (pero no un string ya formateado)
            if isinstance(value, (date, datetime)) and not isinstance(value, str):
                try:
                    # ✅ Conversión a string ISO, la clave de la corrección
                    sanitized_data[key] = value.isoformat()
                except AttributeError:
                    sanitized_data[key] = str(value)
        return sanitized_data
    
    # --- Métodos de consulta y manipulación de datos ---

    def find_by_insumo(self, id_insumo: str, solo_disponibles: bool = True) -> Dict:
        """Obtener todos los lotes de un insumo"""
        try:
            query = (self.db.table(self.table_name)
                     .select('*, insumos_catalogo(nombre, unidad_medida, categoria)')
                     .eq('id_insumo', id_insumo))

            if solo_disponibles:
                query = query.ilike('estado', 'disponible')

            result = query.order('f_vencimiento').execute()

            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error obteniendo lotes por insumo: {str(e)}")
            return {'success': False, 'error': str(e)}
        
    def get_stock_critico(self):
        try:
            result = self.db.rpc('get_insumos_stock_critico', {}).execute()
            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error obteniendo stock crítico: {str(e)}")
            return {'success': False, 'error': str(e)}


    # ✅ SOBRESCRIBE: Sobrescribimos el método 'update' para asegurar la sanitización de datos.
    # Esto asegura que f_vencimiento se convierta a string antes de la DB.
    def update(self, id_value: str, data: Dict, key_name: str) -> Dict:
        """
        Envuelve la llamada al método update de BaseModel para aplicar la sanitización
        de datos (especialmente fechas) antes de la operación de base de datos.
        """
        # Sanitizar los datos (la corrección clave)
        sanitized_data = self._sanitize_dates_for_db(data)
        
        # Llamada al método update de BaseModel (usando super() para llamar a la implementación base)
        return super().update(id_value, sanitized_data, key_name)


    def actualizar_cantidad(self, id_lote: str, nueva_cantidad: float, motivo: str = '') -> Dict:
        """Actualizar cantidad de un lote específico"""
        try:
            # Obtener lote actual
            lote_result = self.find_by_id(id_lote, 'id_lote')
            if not lote_result['success']:
                return lote_result

            lote_actual = lote_result['data']

            # Validaciones
            if nueva_cantidad > lote_actual['cantidad_inicial']:
                return {'success': False, 'error': 'La cantidad no puede ser mayor a la inicial'}

            if nueva_cantidad < 0:
                return {'success': False, 'error': 'La cantidad no puede ser negativa'}

            # Determinar nuevo estado
            if nueva_cantidad == 0:
                nuevo_estado = 'agotado'
            elif nueva_cantidad == lote_actual['cantidad_inicial']:
                nuevo_estado = 'disponible'
            else:
                nuevo_estado = lote_actual.get('estado', 'disponible')

            # Preparar datos de actualización
            update_data = {
                'cantidad_actual': nueva_cantidad,
                'estado': nuevo_estado
            }

            # Agregar motivo a observaciones si se proporciona
            if motivo:
                observaciones_actuales = lote_actual.get('observaciones', '')
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                nueva_observacion = f"[{timestamp}] {motivo}"

                if observaciones_actuales:
                    update_data['observaciones'] = f"{observaciones_actuales} | {nueva_observacion}"
                else:
                    update_data['observaciones'] = nueva_observacion

            # Actualizar. Llama a self.update, que ahora incluye sanitización.
            result = self.update(id_lote, update_data, 'id_lote')

            if result['success']:
                logger.info(f"Cantidad actualizada - Lote: {id_lote}, Nueva cantidad: {nueva_cantidad}")

            return result

        except Exception as e:
            logger.error(f"Error actualizando cantidad: {str(e)}")
            return {'success': False, 'error': str(e)}

    def obtener_por_vencimiento(self, dias_adelante: int = 7) -> Dict:
        """Obtener lotes que vencen en X días"""
        try:
            fecha_limite = (date.today() + timedelta(days=dias_adelante)).isoformat()
            fecha_hoy = date.today().isoformat()

            result = (self.db.table(self.table_name)
                     .select('*, insumos_catalogo(nombre, es_critico)')
                     .gte('f_vencimiento', fecha_hoy)
                     .lte('f_vencimiento', fecha_limite)
                     .eq('estado', 'disponible')
                     .order('f_vencimiento')
                     .execute())

            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error obteniendo por vencimiento: {str(e)}")
            return {'success': False, 'error': str(e)}

    def obtener_stock_consolidado(self, filtros: Optional[Dict] = None) -> Dict:
        """Obtener stock consolidado por insumo consultando insumos_catalogo directamente."""
        try:
            # Consultamos todos los insumos activos que tienen definido un stock mínimo.
            query = self.db.table('insumos_catalogo').select('*').eq('activo', True).neq('stock_min', 0)
            
            result = query.order('nombre').execute()
            
            if not result.data:
                return {'success': True, 'data': []}

            final_data = []
            filtros = filtros or {}

            target_estado = filtros.get('estado_stock', None)
            
            
            for insumo in result.data:
                if insumo is None:
                    continue
                
                stock_actual = insumo.get('stock_actual', 0.0) or 0
                stock_min = insumo.get('stock_min', 0) or 0

                
                # Calcular el estado del stock
                if stock_min > 0 and stock_actual < stock_min:
                    insumo['estado_stock'] = 'BAJO'
                else:
                    insumo['estado_stock'] = 'OK'
                    
                # Aplicar el filtro de estado si fue solicitado (solo para 'BAJO' o 'OK')
                if target_estado is None or insumo['estado_stock'] == target_estado:
                    final_data.append(insumo)

            return {'success': True, 'data': final_data}

        except Exception as e:
            logger.error(f"Error obteniendo stock consolidado (FIXED): {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_all_lotes_for_view(self, filtros: Optional[Dict] = None) -> Dict:
        """
        Obtiene todos los lotes con detalles del insumo y proveedor para la vista de listado.
        """
        try:
            # 1. Construir la consulta base pidiendo explícitamente los datos relacionados.
            query = self.db.table(self.get_table_name()).select(
                '*, insumo:insumos_catalogo(nombre), proveedor:proveedores(nombre)'
            )

            # 2. Aplicar filtros dinámicamente
            if filtros:
                for key, value in filtros.items():
                    if value:
                        if key in ['documento_ingreso'] and isinstance(value, str):
                            query = query.ilike(key, f'%{value}%')
                        else:
                            query = query.eq(key, value)
            
            # 3. Ejecutar la consulta de lotes
            result = query.order('f_ingreso', desc=True).execute()
            
            if not result.data:
                return {'success': True, 'data': []}

            # 4. Aplanar los datos para que la plantilla los pueda usar fácilmente.
            for lote in result.data:
                if lote.get('insumo'):
                    lote['insumo_nombre'] = lote['insumo'].get('nombre', 'Insumo no encontrado')
                else:
                    lote['insumo_nombre'] = 'Insumo no especificado'
                
                if lote.get('proveedor'):
                    lote['proveedor_nombre'] = lote['proveedor'].get('nombre', 'Proveedor sin nombre')
                else:
                    lote['proveedor_nombre'] = 'Proveedor no especificado'

            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error obteniendo lotes para la vista (robusto): {e}")
            return {'success': False, 'error': str(e)}

    def get_lote_detail_for_view(self, id_lote: str) -> Dict:
        """
        Obtiene un único lote con todos los detalles de insumo y proveedor.
        Este método es el equivalente de 'find_by_id' pero enriquecido.
        """
        try:
            query = self.db.table(self.get_table_name()).select(
                '*, insumo:insumos_catalogo(nombre, categoria, unidad_medida), proveedor:proveedores(nombre)'
            ).eq('id_lote', id_lote) 

            result = query.execute()

            if not result.data:
                return {'success': True, 'data': None}

            lote = result.data[0]

            # Aplanar los datos del primer lote
            if lote.get('insumo'):
                lote['insumo_nombre'] = lote['insumo']['nombre']
                lote['insumo_categoria'] = lote['insumo']['categoria']
                lote['insumo_unidad_medida'] = lote['insumo']['unidad_medida']
            else:
                lote['insumo_nombre'] = 'Insumo no encontrado'

            if lote.get('proveedor'):
                lote['proveedor_nombre'] = lote['proveedor']['nombre']
            else:
                lote['proveedor_nombre'] = 'N/A'

            return {'success': True, 'data': lote}

        except Exception as e:
            logger.error(f"Error obteniendo detalle de lote: {e}")
            return {'success': False, 'error': str(e)}

    def calcular_y_actualizar_stock_general(self) -> Dict:
        """
        Calcula y actualiza el stock 'disponible' (actual) para todos los insumos,
        considerando las reservas.
        """
        try:
            logger.info("Iniciando recálculo de stock general para todos los insumos.")
            # 1. Obtener el stock físico total por insumo desde la tabla de lotes (inventario)
            stock_fisico_res = self.db.table(self.get_table_name()).select("id_insumo, cantidad_actual").execute()
            if not hasattr(stock_fisico_res, 'data'):
                raise Exception("No se pudo obtener el stock físico de los lotes.")

            stock_fisico_map = {}
            for lote in stock_fisico_res.data:
                insumo_id = lote.get('id_insumo')
                if insumo_id:
                    stock_fisico_map[insumo_id] = stock_fisico_map.get(insumo_id, 0.0) + float(lote.get('cantidad_actual', 0))

            # 2. Obtener el total de reservas activas por insumo
            reservas_res = self.db.table('reservas_insumos').select("insumo_id, cantidad_reservada").execute()
            if not hasattr(reservas_res, 'data'):
                raise Exception("No se pudo obtener las reservas de insumos.")

            reservas_map = {}
            for reserva in reservas_res.data:
                insumo_id = reserva.get('insumo_id')
                if insumo_id:
                    reservas_map[insumo_id] = reservas_map.get(insumo_id, 0.0) + float(reserva.get('cantidad_reservada', 0))

            # 3. Preparar la actualización masiva (upsert)
            updates = []
            todos_los_insumos_ids = set(stock_fisico_map.keys()) | set(reservas_map.keys())

            for insumo_id in todos_los_insumos_ids:
                fisico = stock_fisico_map.get(insumo_id, 0.0)
                reservado = reservas_map.get(insumo_id, 0.0)
                disponible = fisico - reservado
                
                updates.append({
                    'id_insumo': insumo_id,
                    'stock_actual': disponible,
                    'stock_total': fisico # stock_total representa el físico
                })
            
            # 4. Ejecutar la actualización masiva si hay algo que actualizar
            if updates:
                (self.db.table('insumos_catalogo')
                    .upsert(updates, on_conflict='id_insumo')
                    .execute())
                logger.info(f"Stock general actualizado para {len(updates)} insumos.")

            # 5. Poner en cero el stock de insumos que NO tienen lotes ni reservas
            insumos_en_catalogo_res = self.db.table('insumos_catalogo').select('id_insumo').execute()
            insumos_en_catalogo_ids = {item['id_insumo'] for item in insumos_en_catalogo_res.data}
            
            insumos_a_cero = list(insumos_en_catalogo_ids - todos_los_insumos_ids)
            
            if insumos_a_cero:
                (self.db.table('insumos_catalogo')
                    .update({'stock_actual': 0, 'stock_total': 0})
                    .in_('id_insumo', insumos_a_cero)
                    .execute())
                logger.info(f"{len(insumos_a_cero)} insumos sin lotes ni reservas fueron puestos a cero.")

            return {'success': True, 'message': 'Stock general recalculado exitosamente.'}

        except Exception as e:
            logger.error(f"Error masivo al recalcular stock general: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def get_trazabilidad_ascendente(self, id_lote_insumo) -> Dict:
        """
        Obtiene la trazabilidad ascendente de un lote de insumo.
        Este método llama a una función de base de datos (RPC) 
        y luego procesa los resultados para construir un árbol de dependencias.
        """
        try:
            # 1. Llamar a la función RPC de la base de datos
            
            # --- INICIO DE LA CORRECCIÓN 1: Usar el nombre de función correcto ---
            # El setup.sql 
            # también define 'get_trazabilidad_ascendente' (línea 1832).
            # Probamos usar esa en lugar de la que no encontraba.
            result = self.db.rpc(
                'get_trazabilidad_ascendente',  # <-- Nombre corregido (sin 'insumo_')
                {'p_id_lote_insumo': str(id_lote_insumo)}
            ).execute()
            # --- FIN DE LA CORRECCIÓN 1 ---
            
            if not result.data:
                logger.warning(f"No se encontró trazabilidad ascendente para {id_lote_insumo}")
                return {'success': True, 'data': {'ops': [], 'productos': [], 'pedidos': []}}

            # 2. Procesar los datos crudos del RPC
            op_data = {}
            producto_data = {}
            insumo_data = {}
            
            for row in result.data:
                id_op = row.get('id_op')
                if id_op not in op_data:
                    op_data[id_op] = {
                        'id': id_op,
                        'codigo_orden_produccion': row.get('codigo_op'),
                        'productos_fabricados': [],
                        'pedidos_asociados': [] 
                    }
                
                id_lote_prod = row.get('id_lote_producto')
                if id_lote_prod not in producto_data:
                    producto_data[id_lote_prod] = {
                        'id_lote_producto': id_lote_prod,
                        'codigo_lote_producto': row.get('codigo_lote_producto'),
                        'nombre_producto': row.get('nombre_producto'),
                        'id_op': id_op,
                        'insumos_utilizados': []
                    }
                
                # El 'id_consumo_insumo' puede no ser único si la función RPC 
                # no lo maneja, pero lo usamos como key de 'insumo_data'
                # Asumimos que la fila 'row' es única por consumo.
                # Si 'id_consumo_insumo' es None, esto podría agrupar mal.
                # Vamos a usar una tupla (lote_prod, lote_insumo) si id_consumo no existe
                id_lote_insumo_row = row.get('id_lote_insumo')
                id_consumo_key = row.get('id_consumo_insumo') or f"{id_lote_prod}-{id_lote_insumo_row}"

                if id_consumo_key not in insumo_data:
                    insumo_info = {
                        'id_consumo_insumo': row.get('id_consumo_insumo'),
                        'id_lote_insumo': id_lote_insumo_row,
                        'codigo_lote_insumo': row.get('codigo_lote_insumo'),
                        'nombre_insumo': row.get('nombre_insumo'),
                        'cantidad_utilizada': float(row.get('cantidad_utilizada', 0) or 0)
                    }
                    insumo_data[id_consumo_key] = insumo_info
                    producto_data[id_lote_prod]['insumos_utilizados'].append(insumo_info)

            # Re-asignar productos a OPs
            for prod in producto_data.values():
                if prod['id_op'] in op_data:
                    op_data[prod['id_op']]['productos_fabricados'].append(prod)

            # 3. Buscar Pedidos asociados a los lotes de producto fabricados
            lotes_producto_ids = list(producto_data.keys())
            if not lotes_producto_ids:
                return {'success': True, 'data': {'ops': list(op_data.values()), 'productos': [], 'pedidos': []}}

            reservas_productos_resp = self.db.table('reservas_productos').select('*').in_('lote_producto_id', lotes_producto_ids).execute()
            reservas_productos = reservas_productos_resp.data
            
            pedido_ids = list(set(r['id_pedido'] for r in reservas_productos if r.get('id_pedido')))
            
            pedidos_info_map = {} # { id_pedido: {'id': ..., 'codigo_pedido': ..., 'nombre_cliente': ...} }
            if pedido_ids:
                pedidos_resp = self.db.table('pedidos').select('id_pedido, codigo_pedido, id_cliente').in_('id_pedido', pedido_ids).execute()
                
                cliente_ids = list(set(p['id_cliente'] for p in pedidos_resp.data if p.get('id_cliente')))
                clientes_data = {}
                if cliente_ids:
                    clientes_resp = self.db.table('clientes').select('id_cliente, nombre, apellido').in_('id_cliente', cliente_ids).execute()
                    for c in clientes_resp.data:
                        clientes_data[c['id_cliente']] = f"{c.get('nombre', '')} {c.get('apellido', '')}".strip()

                for p in pedidos_resp.data:
                    pedidos_info_map[p['id_pedido']] = {
                        'id': p['id_pedido'],
                        'codigo_pedido': p.get('codigo_pedido') or f"Venta-{p['id_pedido']}",
                        'nombre_cliente': clientes_data.get(p.get('id_cliente'), 'N/A')
                    }

            # 4. Procesar y asociar Pedidos
            lote_a_pedido_cantidad = {} # { (lote_prod_id, pedido_id): cantidad_total }
            
            for reserva_prod in reservas_productos:
                pedido_id = reserva_prod.get('id_pedido')
                lote_prod_id = reserva_prod.get('lote_producto_id')
                
                if not pedido_id or not lote_prod_id or pedido_id not in pedidos_info_map:
                    continue
                
                # --- INICIO DE LA CORRECCIÓN 2: Sumar ambas cantidades ---
                # (Esta corrección la mantenemos)
                cantidad_reservada = float(reserva_prod.get('cantidad_reservada', 0) or 0)
                cantidad_consumida = float(reserva_prod.get('cantidad_consumida', 0) or 0)
                cantidad_total_asignada = cantidad_reservada + cantidad_consumida
                # --- FIN DE LA CORRECCIÓN 2 ---

                if cantidad_total_asignada == 0:
                   continue

                key = (lote_prod_id, pedido_id)
                lote_a_pedido_cantidad[key] = lote_a_pedido_cantidad.get(key, 0.0) + cantidad_total_asignada
            
            pedidos_final_map = {} # { pedido_id: { 'id': ..., 'codigo_pedido': ..., 'cantidad_asignada': ... } }

            for (lote_prod_id, pedido_id), cantidad_total in lote_a_pedido_cantidad.items():
                
                id_op = producto_data.get(lote_prod_id, {}).get('id_op')
                if not id_op or id_op not in op_data:
                    continue

                if pedido_id not in pedidos_final_map:
                    pedidos_final_map[pedido_id] = {
                        **pedidos_info_map[pedido_id],
                        'cantidad_asignada': 0.0
                    }
                
                pedidos_final_map[pedido_id]['cantidad_asignada'] += cantidad_total
                
                op_pedidos_list = op_data[id_op]['pedidos_asociados']
                pedido_encontrado = next((p for p in op_pedidos_list if p['id'] == pedido_id), None)
                
                if not pedido_encontrado:
                    op_pedidos_list.append({
                        **pedidos_info_map[pedido_id],
                        'cantidad_asignada': cantidad_total
                    })
                else:
                    pedido_encontrado['cantidad_asignada'] += cantidad_total
            
            final_data = {
                'ops': list(op_data.values()),
                'productos': list(producto_data.values()),
                'pedidos': list(pedidos_final_map.values())
            }

            return {'success': True, 'data': final_data}
        
        except Exception as e:
            logger.error(f"Error obteniendo trazabilidad ascendente para lote {id_lote_insumo}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}