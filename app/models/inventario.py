from app.models.base_model import BaseModel
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import date, datetime, timedelta
import logging
from uuid import UUID
import math  # <-- CORRECCIÓN 1: Importar math

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
                     .select('*, insumos_catalogo(nombre, es_critico, unidad_medida)')
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

    def get_all_lotes_for_view(self, filtros: Optional[Dict] = None):
        """
        Obtiene todos los lotes de INSUMOS con datos enriquecidos.
        Calcula 'cantidad_reservada' sumando la tabla 'reserva_insumos'.
        """
        try:
            # 1. Consulta base de lotes
            query = self.db.table(self.get_table_name()).select(
                '*, insumo:insumos_catalogo(nombre, unidad_medida), proveedor:proveedores(nombre)'
            )

            if filtros:
                for key, value in filtros.items():
                    # Manejo de filtros especiales (ej: ilike)
                    if isinstance(value, tuple) and len(value) == 2:
                        op, val = value
                        if op == 'ilike': query = query.ilike(key, f'%{val}%')
                        elif op == 'in': query = query.in_(key, val)
                        else: query = query.eq(key, val) # Fallback
                    else:
                        query = query.eq(key, value)

            lotes_result = query.order('created_at', desc=True).execute()

            if not hasattr(lotes_result, 'data'):
                 return {'success': True, 'data': []}

            lotes_data = lotes_result.data

            # --- NUEVO: Obtener reservas activas de insumos ---
            # Buscamos en la tabla 'reserva_insumos' (o 'reservas_insumos' según tu DB)
            # Asumo 'reserva_insumos' basado en tus controladores anteriores.
            reservas_result = self.db.table('reservas_insumos').select(
                'lote_inventario_id, cantidad_reservada'
            ).eq('estado', 'RESERVADO').execute()

            reservas_map = {}
            if hasattr(reservas_result, 'data'):
                for reserva in reservas_result.data:
                    # Nota: Verifica si en tu DB es 'lote_inventario_id' o 'lote_id'
                    lote_id = reserva.get('lote_inventario_id')
                    cantidad = float(reserva.get('cantidad_reservada', 0))
                    reservas_map[lote_id] = reservas_map.get(lote_id, 0.0) + cantidad
            # --------------------------------------------------

            # 3. Enriquecer los datos
            enriched_data = []
            for lote in lotes_data:
                # Aplanar datos anidados
                if lote.get('insumo'):
                    lote['insumo_nombre'] = lote['insumo']['nombre']
                    lote['insumo_unidad_medida'] = lote['insumo']['unidad_medida']
                else:
                    lote['insumo_nombre'] = 'Desconocido'
                    lote['insumo_unidad_medida'] = ''

                if lote.get('proveedor'):
                    lote['proveedor_nombre'] = lote['proveedor']['nombre']
                else:
                    lote['proveedor_nombre'] = 'N/A'

                # Limpiar objetos
                lote.pop('insumo', None)
                lote.pop('proveedor', None)

                # --- ASIGNAR CANTIDAD RESERVADA ---
                lote_id = lote.get('id_lote')
                lote['cantidad_reservada'] = reservas_map.get(lote_id, 0.0)
                # ----------------------------------

                # Corrección visual de estado 'VENCIDO' (si aplica)
                if lote.get('f_vencimiento'):
                    try:
                        # Asegurar formato fecha
                        venc_str = lote['f_vencimiento']
                        venc = datetime.fromisoformat(venc_str).date() if 'T' in venc_str else date.fromisoformat(venc_str)
                        if venc <= date.today() and lote.get('estado') not in ['agotado', 'retirado']:
                             lote['estado_visual'] = 'VENCIDO' # Usamos un campo visual para no tocar el real
                    except: pass

                enriched_data.append(lote)

            return {'success': True, 'data': enriched_data}

        except Exception as e:
            logger.error(f"Error obteniendo lotes de insumos: {e}", exc_info=True)
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
        considerando las reservas. Es robusto frente a lotes "huérfanos".
        """
        try:
            logger.info("Iniciando recálculo de stock general para todos los insumos.")

            # 0. Obtener IDs de insumos que SÍ existen en el catálogo. Esto es CRÍTICO
            # para evitar que un lote "huérfano" (de un insumo borrado) intente
            # crear un nuevo registro de insumo incompleto, causando un error de not-null.
            insumos_existentes_res = self.db.table('insumos_catalogo').select("id_insumo").execute()
            if not hasattr(insumos_existentes_res, 'data'):
                raise Exception("No se pudo obtener la lista de insumos existentes del catálogo.")
            insumos_existentes_ids = {item['id_insumo'] for item in insumos_existentes_res.data}

            # 1. Obtener el stock físico total por insumo desde la tabla de lotes (inventario)
            #    sumando únicamente los lotes que representan stock físico real.
            estados_fisicos = ['disponible', 'reservado', 'cuarentena', 'EN REVISION']
            stock_fisico_res = (self.db.table(self.get_table_name())
                                .select("id_insumo, cantidad_actual")
                                .in_('estado', estados_fisicos)
                                .execute())
            if not hasattr(stock_fisico_res, 'data'):
                raise Exception("No se pudo obtener el stock físico de los lotes.")

            stock_fisico_map = {}
            for lote in stock_fisico_res.data:
                insumo_id = lote.get('id_insumo')
                # Solo procesar lotes de insumos que sabemos que existen
                if insumo_id and insumo_id in insumos_existentes_ids:
                    stock_fisico_map[insumo_id] = stock_fisico_map.get(insumo_id, 0.0) + float(lote.get('cantidad_actual', 0))

            # 2. Obtener el total de reservas activas por insumo
            reservas_res = (self.db.table('reservas_insumos')
                                .select("insumo_id, cantidad_reservada")
                                .eq('estado', 'RESERVADO')
                                .execute())
            if not hasattr(reservas_res, 'data'):
                raise Exception("No se pudo obtener las reservas de insumos.")

            reservas_map = {}
            for reserva in reservas_res.data:
                insumo_id = reserva.get('insumo_id')
                # Solo procesar reservas de insumos que sabemos que existen
                if insumo_id and insumo_id in insumos_existentes_ids:
                    reservas_map[insumo_id] = reservas_map.get(insumo_id, 0.0) + float(reserva.get('cantidad_reservada', 0))

            # 3. Preparar la actualización masiva (ahora solo con insumos válidos)
            updates = []
            todos_los_insumos_con_movimiento = set(stock_fisico_map.keys()) | set(reservas_map.keys())

            for insumo_id in todos_los_insumos_con_movimiento:
                fisico = stock_fisico_map.get(insumo_id, 0.0)
                reservado = reservas_map.get(insumo_id, 0.0)

                # --- INICIO DE LA CORRECCIÓN 2 ---
                disponible_calculado = fisico - reservado

                # Si el número es 'casi cero', forzarlo a 0.0
                if math.isclose(disponible_calculado, 0, abs_tol=1e-9):
                    disponible = 0.0
                else:
                    # Opcional: redondear a 4 decimales por seguridad
                    disponible = round(disponible_calculado, 4)
                # --- FIN DE LA CORRECCIÓN 2 ---

                updates.append({
                    'id_insumo': insumo_id,
                    'stock_actual': disponible, # <-- Se guarda el valor corregido
                    'stock_total': fisico # stock_total representa el físico
                })

            # 4. Ejecutar las actualizaciones de forma individual para máxima seguridad.
            # Este enfoque es más lento pero evita el comportamiento impredecible de `upsert`
            # que estaba causando el error de 'not-null constraint'. La estabilidad es prioritaria.
            if updates:
                updated_count = 0
                for update_data in updates:
                    try:
                        insumo_id = update_data.pop('id_insumo')
                        payload = {
                            'stock_actual': update_data['stock_actual'],
                            'stock_total': update_data['stock_total']
                        }
                        (self.db.table('insumos_catalogo')
                            .update(payload)
                            .eq('id_insumo', insumo_id)
                            .execute())
                        updated_count += 1
                    except Exception as e:
                        logger.error(f"Error actualizando stock individualmente para el insumo {insumo_id}: {e}")
                logger.info(f"Stock general actualizado para {updated_count} insumos.")

            # 5. Poner en cero el stock de insumos que existen pero NO tienen lotes ni reservas
            insumos_a_cero = list(insumos_existentes_ids - todos_los_insumos_con_movimiento)

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

    def get_all_stock_disponible_map(self) -> Dict:
        """
        Obtiene el stock disponible de TODOS los insumos en una sola consulta
        y lo devuelve como un mapa {insumo_id: stock_disponible}.
        """
        try:
            # Asumiendo que tienes una función o vista en Supabase que hace esto.
            # Si no, esta es la consulta SQL que necesitas crear:
            # SELECT insumo_id, SUM(stock_disponible) as stock_disponible
            # FROM stock_insumos_lote
            # WHERE estado = 'DISPONIBLE'
            # GROUP BY insumo_id

            # Usando Supabase RPC (Remote Procedure Call)
            # Debes crear una función en tu DB llamada 'get_stock_total_disponible'
            result = self.db.rpc('get_stock_total_disponible').execute()

            stock_map = {item['insumo_id']: Decimal(item['stock_disponible']) for item in result.data}
            return {'success': True, 'data': stock_map}

        except Exception as e:
            logger.error(f"Error en get_all_stock_disponible_map: {e}", exc_info=True)
            return {'success': False, 'error': str(e), 'data': {}}