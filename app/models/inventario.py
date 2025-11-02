from app.models.base_model import BaseModel
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
import logging

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
                query = query.in_('estado', ['disponible', 'reservado'])

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
        Solución robusta que consulta la tabla y enriquece los datos manualmente.
        """
        try:
            # 1. Construir la consulta base sobre la tabla de lotes
            query = self.db.table(self.get_table_name()).select('*')

            # 2. Aplicar filtros dinámicamente
            if filtros:
                for key, value in filtros.items():
                    if value:
                        # Usar 'ilike' para búsquedas de texto flexibles y 'eq' para el resto
                        if key in ['documento_ingreso'] and isinstance(value, str):
                            query = query.ilike(key, f'%{value}%')
                        else:
                            query = query.eq(key, value)
            
            # 3. Ejecutar la consulta de lotes
            result = query.order('f_ingreso', desc=True).execute()
            
            if not result.data:
                return {'success': True, 'data': []}

            lotes = result.data

            # 4. Obtener los IDs de insumos y proveedores para enriquecer los datos
            insumo_ids = list(set(lote['id_insumo'] for lote in lotes if lote.get('id_insumo')))
            
            # 5. Consultar los nombres de los insumos en una sola llamada
            insumos_data = {}
            if insumo_ids:
                insumos_resp = self.db.table('insumos_catalogo').select('id_insumo, nombre').in_('id_insumo', insumo_ids).execute()
                if insumos_resp.data:
                    insumos_data = {insumo['id_insumo']: insumo['nombre'] for insumo in insumos_resp.data}

            # 6. Combinar los datos
            for lote in lotes:
                lote['insumo_nombre'] = insumos_data.get(lote.get('id_insumo'), 'Insumo no encontrado')
            
            return {'success': True, 'data': lotes}

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
        Calcula el stock actual para todos los insumos sumando los lotes de inventario
        y lo actualiza en la tabla insumos_catalogo.
        """
        try:
            # 1. Obtener todos los insumos del catálogo
            catalogo_resp = self.db.table('insumos_catalogo').select('id_insumo', 'stock_actual').execute()
            if not hasattr(catalogo_resp, 'data'):
                raise Exception("No se pudo obtener el catálogo de insumos.")
            
            insumos_catalogo = {item['id_insumo']: item for item in catalogo_resp.data}

            # 2. Calcular el stock agregado desde el inventario
            inventario_resp = self.db.table(self.get_table_name()).select('id_insumo', 'cantidad_actual').in_('estado', ['disponible', 'reservado']).execute()
            if not hasattr(inventario_resp, 'data'):
                raise Exception("No se pudo obtener el inventario de insumos.")

            stock_calculado = {}
            for lote in inventario_resp.data:
                insumo_id = lote['id_insumo']
                cantidad = lote.get('cantidad_actual') or 0
                stock_calculado[insumo_id] = stock_calculado.get(insumo_id, 0) + cantidad

            # 3. Preparar los datos para la actualización
            updates = []
            for insumo_id, insumo_data in insumos_catalogo.items():
                stock_nuevo = stock_calculado.get(insumo_id, 0)
                stock_viejo = insumo_data.get('stock_actual') or 0

                # Solo actualizar si el stock ha cambiado
                if stock_nuevo != stock_viejo:
                    updates.append({'id_insumo': insumo_id, 'stock_actual': stock_nuevo})
            
            # 4. Ejecutar las actualizaciones de forma iterativa si hay cambios
            if updates:
                logger.info(f"Actualizando stock para {len(updates)} insumos.")
                for item in updates:
                    insumo_id = item['id_insumo']
                    new_stock = item['stock_actual']
                    (self.db.table('insumos_catalogo')
                     .update({'stock_actual': new_stock})
                     .eq('id_insumo', insumo_id)
                     .execute())
            else:
                logger.info("No se requirieron actualizaciones de stock.")

            return {'success': True}

        except Exception as e:
            logger.error(f"Error al ejecutar el recálculo de stock general: {str(e)}")
            return {'success': False, 'error': str(e)}

    def recalcular_stock_para_insumo(self, insumo_id: str) -> Dict:
        """
        Calcula y actualiza el stock_actual para un único insumo basado en la suma
        de sus lotes de inventario en estado 'disponible' o 'reservado'.
        """
        try:
            # 1. Obtener todos los lotes relevantes para el insumo
            lotes_resp = self.db.table(self.get_table_name()).select('cantidad_actual').eq('id_insumo', insumo_id).in_('estado', ['disponible', 'reservado']).execute()
            
            if not hasattr(lotes_resp, 'data'):
                # Si hasattr falla, es probable que lotes_resp no sea un objeto esperado.
                error_msg = f"Respuesta inesperada de la base de datos al buscar lotes para el insumo {insumo_id}."
                logger.error(error_msg)
                return {'success': False, 'error': error_msg}

            # 2. Calcular el nuevo stock sumando las cantidades
            nuevo_stock = sum(lote.get('cantidad_actual', 0) for lote in lotes_resp.data)

            # 3. Actualizar el stock en la tabla 'insumos_catalogo'
            update_resp = (self.db.table('insumos_catalogo')
                           .update({'stock_actual': nuevo_stock})
                           .eq('id_insumo', insumo_id)
                           .execute())

            if not hasattr(update_resp, 'data'):
                 error_msg = f"Respuesta inesperada de la base de datos al actualizar el stock para el insumo {insumo_id}."
                 logger.error(error_msg)
                 return {'success': False, 'error': error_msg}


            logger.info(f"Stock para el insumo {insumo_id} recalculado y actualizado a: {nuevo_stock}")
            return {'success': True}

        except Exception as e:
            logger.error(f"Error al recalcular el stock para el insumo {insumo_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
        
    def get_trazabilidad_ascendente(self, id_lote_insumo: str) -> Dict:
        """
        Obtiene la trazabilidad "hacia arriba" de un lote de insumo.
        Encuentra OPs, Lotes de Producto y Pedidos de Venta asociados.
        
        @param id_lote_insumo: El ID del lote de la tabla 'insumos_inventario'.
        """
        try:
            # 1. Buscar en qué OPs se usó este lote de insumo
            
            # --- CORRECCIÓN AQUÍ: Se cambió 'cantidad_utilizada' por 'cantidad_reservada' ---
            reservas_insumo_result = self.db.table('reservas_insumos').select(
                'cantidad_reservada, orden_produccion:ordenes_produccion(id, codigo, estado)'
            ).eq('lote_inventario_id', id_lote_insumo).execute()
            # --- FIN DE LA CORRECCIÓN 1 ---

            if not reservas_insumo_result.data:
                logger.info(f"Trazabilidad: Lote {id_lote_insumo} no encontrado en 'reservas_insumos'.")
                return {'success': True, 'data': {'ops': [], 'productos': [], 'pedidos': []}}

            op_data = {}
            op_ids = []
            
            # Agrupar por OP
            for reserva in reservas_insumo_result.data:
                op = reserva.get('orden_produccion')
                if not op: continue
                
                op_id = op['id']
                if op_id not in op_data:
                    op_data[op_id] = {
                        'id': op_id,
                        'codigo_op': op.get('codigo'), 
                        'estado': op.get('estado'),
                        'cantidad_insumo_utilizada': 0,
                        'productos_fabricados': [],
                        'pedidos_asociados': []
                    }
                    op_ids.append(op_id)
                
                # --- CORRECCIÓN AQUÍ: Se cambió 'cantidad_utilizada' por 'cantidad_reservada' ---
                op_data[op_id]['cantidad_insumo_utilizada'] += reserva.get('cantidad_reservada', 0)
                # --- FIN DE LA CORRECCIÓN 2 ---

            if not op_ids:
                 return {'success': True, 'data': {'ops': list(op_data.values()), 'productos': [], 'pedidos': []}}

            # 2. Buscar qué lotes de producto generaron esas OPs
            lotes_producto_result = self.db.table('lotes_productos').select(
                'id_lote, orden_produccion_id, cantidad_inicial, producto:productos(id, nombre)'
            ).in_('orden_produccion_id', op_ids).execute()

            producto_data = {}
            lote_producto_ids = []

            for lote_prod in lotes_producto_result.data:
                prod = lote_prod.get('producto')
                if not prod: continue
                
                lote_prod_id = lote_prod['id_lote_producto']
                op_id = lote_prod['orden_produccion_id']
                
                prod_info = {
                    'id': prod['id'],
                    'nombre': prod.get('nombre'),
                    'codigo': prod.get('codigo'), 
                    'id_lote_producto': lote_prod_id,
                    'cantidad_producida': lote_prod.get('cantidad_producida')
                }
                
                if lote_prod_id not in producto_data:
                    producto_data[lote_prod_id] = prod_info
                    lote_producto_ids.append(lote_prod_id)
                
                if op_id in op_data:
                    op_data[op_id]['productos_fabricados'].append(prod_info)

            # 3. Buscar qué pedidos usaron esos lotes de producto
            if not lote_producto_ids:
                return {'success': True, 'data': {'ops': list(op_data.values()), 'productos': list(producto_data.values()), 'pedidos': []}}

            reservas_producto_result = self.db.table('reservas_productos').select(
                'lote_producto_id, cantidad_reservada, item:pedido_items(id, pedido:pedidos!pedido_items_pedido_id_fkey(id, nombre_cliente))'
            ).in_('lote_producto_id', lote_producto_ids).execute()

            pedido_data = {}

            for reserva_prod in reservas_producto_result.data:
                item = reserva_prod.get('item')
                if not item: continue
                pedido = item.get('pedido')
                if not pedido: continue

                pedido_id = pedido['id']
                lote_prod_id = reserva_prod['lote_producto_id']
                
                pedido_info = {
                    'id': pedido_id,
                    'nombre_cliente': pedido.get('nombre_cliente'),
                    'codigo_pedido': pedido.get('codigo_pedido') or f"Venta-{pedido_id}",
                    'cantidad_asignada': reserva_prod.get('cantidad_reservada', 0)
                }

                if pedido_id not in pedido_data:
                    pedido_data[pedido_id] = pedido_info
                else:
                    pedido_data[pedido_id]['cantidad_asignada'] += reserva_prod.get('cantidad_reservada', 0)
                
                for op in op_data.values():
                    for prod in op['productos_fabricados']:
                        if prod['id_lote_producto'] == lote_prod_id:
                            if not any(p['id'] == pedido_id for p in op['pedidos_asociados']):
                                op['pedidos_asociados'].append(pedido_info)

            final_data = {
                'ops': list(op_data.values()),
                'productos': list(producto_data.values()),
                'pedidos': list(pedido_data.values())
            }

            return {'success': True, 'data': final_data}
        
        except Exception as e:
            logger.error(f"Error obteniendo trazabilidad ascendente para lote {id_lote_insumo}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}