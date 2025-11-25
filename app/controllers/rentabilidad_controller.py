from datetime import datetime, timedelta
import logging
from app.controllers.base_controller import BaseController
from app.models.producto import ProductoModel
from app.models.receta import RecetaModel
from app.models.pedido import PedidoModel, PedidoItemModel
from app.models.insumo import InsumoModel
from app.models.costo_fijo import CostoFijoModel
from app.models.operacion_receta_model import OperacionRecetaModel
from app.models.operacion_receta_rol_model import OperacionRecetaRolModel
from app.models.rol import RoleModel
from app.models.zona import ZonaModel
from app.models.historial_costos_producto import HistorialCostosProductoModel
from app.models.pago import PagoModel  # [MODIFICADO] Importar modelo de pagos
from app.controllers.receta_controller import RecetaController
from typing import Dict, List
import calendar
from collections import defaultdict  # [MODIFICADO] Para agrupar pagos

logger = logging.getLogger(__name__)

class RentabilidadController(BaseController):
    """
    Controlador para la lógica de negocio del análisis de rentabilidad.
    """

    def __init__(self):
        super().__init__()
        self.producto_model = ProductoModel()
        self.receta_model = RecetaModel()
        self.pedido_model = PedidoModel()
        self.insumo_model = InsumoModel()
        self.pedido_item_model = PedidoItemModel()
        self.costo_fijo_model = CostoFijoModel()
        self.operacion_receta_model = OperacionRecetaModel()
        self.operacion_receta_rol_model = OperacionRecetaRolModel()
        self.rol_model = RoleModel()
        self.zona_model = ZonaModel()
        self.historial_costos_model = HistorialCostosProductoModel()
        # Instanciamos RecetaController para reutilizar la lógica de costo de materia prima
        self.receta_controller = RecetaController()
        self.pago_model = PagoModel()  # [MODIFICADO] Instanciar PagoModel

    def _should_include_order(self, pedido: Dict) -> bool:
        """
        Determine if an order should be included in the main realized profitability calculation.
        Rule (Option A): 
        - Include if payment condition is 'contado'.
        - OR if status is 'COMPLETADO'.
        """
        condicion_venta = pedido.get('condicion_venta', '').lower()
        estado = pedido.get('estado', '')
        
        is_contado = condicion_venta == 'contado'
        is_completed = estado == 'COMPLETADO'
        
        return is_contado or is_completed

    def _obtener_costo_historico(self, producto_id: int, fecha_pedido_iso: str) -> float:
        """
        Obtiene el costo total histórico de un producto para una fecha dada.
        Intenta encontrar el registro más cercano a la fecha del pedido.
        """
        try:
            # 1. Intentar buscar registros anteriores o iguales a la fecha (el precio vigente en ese momento)
            # Asegurar formato ISO
            if 'T' in fecha_pedido_iso:
                 fecha_limite = fecha_pedido_iso
            else:
                 fecha_limite = f"{fecha_pedido_iso}T23:59:59"

            historial_res = self.historial_costos_model.db.table('historial_costos_productos')\
                .select('costo_total')\
                .eq('producto_id', producto_id)\
                .lte('fecha_registro', fecha_limite)\
                .order('fecha_registro', desc=True)\
                .limit(1)\
                .execute()
            
            if historial_res.data:
                return float(historial_res.data[0]['costo_total'] or 0)
            
            # 2. Si no hay registros previos, buscar el PRIMER registro histórico disponible (puede ser posterior pero cercano)
            # Esto ayuda si el historial se empezó a guardar después de los primeros pedidos
            future_res = self.historial_costos_model.db.table('historial_costos_productos')\
                .select('costo_total')\
                .eq('producto_id', producto_id)\
                .gt('fecha_registro', fecha_limite)\
                .order('fecha_registro', desc=False)\
                .limit(1)\
                .execute()
                
            if future_res.data:
                return float(future_res.data[0]['costo_total'] or 0)

            return 0.0

        except Exception as e:
            logger.error(f"Error obteniendo costo histórico para prod {producto_id} fecha {fecha_pedido_iso}: {e}")
            return 0.0

    def obtener_datos_matriz_rentabilidad(self, fecha_inicio: str = None, fecha_fin: str = None) -> tuple:
        """
        Calcula la rentabilidad basándose en los cobros reales (flujo de caja verificado)
        para determinar la facturación realizada vs la pendiente.
        """
        # 1. Calcular duración del período para prorrateo de costos fijos
        months_duration = 1.0
        if fecha_inicio and fecha_fin:
            try:
                dt_inicio = datetime.fromisoformat(fecha_inicio)
                dt_fin = datetime.fromisoformat(fecha_fin)
                delta = dt_fin - dt_inicio
                months_duration = max(delta.days / 30.0, 1.0)
            except ValueError:
                months_duration = 1.0
        else:
            try:
                first_order_res = self.pedido_model.db.table('pedidos').select('fecha_solicitud').order('fecha_solicitud', desc=False).limit(1).execute()
                if first_order_res.data:
                    dt_inicio = datetime.fromisoformat(first_order_res.data[0]['fecha_solicitud'])
                    dt_fin = datetime.now()
                    delta = dt_fin - dt_inicio
                    months_duration = max(delta.days / 30.0, 1.0)
            except Exception as e:
                logger.error(f"Error calculando duración histórica: {e}")
                months_duration = 1.0

        # 2. Obtener todos los productos activos para iterar.
        productos_result = self.producto_model.find_all({'activo': True})
        if not productos_result.get('success'):
            return self.error_response("Error al obtener productos.", 500)
        productos_data = productos_result.get('data', [])
        
        # Pre-fetch de roles para cálculo de costos fallback
        roles_resp = self.rol_model.find_all()
        roles_map = {}
        if roles_resp.get('success'):
            for r in roles_resp.get('data', []):
                roles_map[r['id']] = float(r.get('costo_por_hora') or 0)

        # Calcular costos unitarios ACTUALES para fallback
        productos_info_actual = {}
        for p in productos_data:
            costos_dinamicos = self._calcular_costos_unitarios_dinamicos(p, roles_map)
            productos_info_actual[p['id']] = {
                'producto': p,
                'costos_actuales': costos_dinamicos
            }

        # 3. Obtener los pedidos e ITEMS dentro del rango de fechas.
        items_filtrados = []
        try:
            # Use safe select
            try:
                query = self.pedido_item_model.db.table('pedido_items')\
                    .select('*, pedido:pedidos!pedido_items_pedido_id_fkey!inner(id, fecha_solicitud, condicion_venta, estado, precio_orden, id_direccion_entrega)')
                
                # Filter cancelled orders at DB level
                query = query.neq('pedido.estado', 'CANCELADO')

                if fecha_inicio and fecha_fin:
                    query = query.gte('pedido.fecha_solicitud', fecha_inicio).lte('pedido.fecha_solicitud', fecha_fin)
                
                items_res = query.execute()
                items_filtrados = items_res.data if items_res.data else []
            except Exception as e:
                logger.warning(f"Query failed, retrying safe select: {e}")
                # Fallback query
                query = self.pedido_item_model.db.table('pedido_items')\
                    .select('cantidad, producto_id, pedido_id, pedido:pedidos!pedido_items_pedido_id_fkey!inner(id, fecha_solicitud, condicion_venta, estado, precio_orden, id_direccion_entrega)')
                
                query = query.neq('pedido.estado', 'CANCELADO')

                if fecha_inicio and fecha_fin:
                    query = query.gte('pedido.fecha_solicitud', fecha_inicio).lte('pedido.fecha_solicitud', fecha_fin)
                
                items_res = query.execute()
                items_filtrados = items_res.data if items_res.data else []
                
        except Exception as e:
            logger.error(f"Error al obtener datos de rentabilidad: {e}", exc_info=True)
            return self.error_response("Error al obtener datos.", 500)

        # --- [MODIFICADO] Obtener Pagos Reales para los pedidos filtrados ---
        pedido_ids = set()
        for item in items_filtrados:
            if item.get('pedido'):
                pedido_ids.add(item['pedido']['id'])
        
        pagos_map = defaultdict(float)
        if pedido_ids:
            try:
                pagos_res = self.pago_model.db.table('pagos')\
                    .select('id_pedido, monto')\
                    .in_('id_pedido', list(pedido_ids))\
                    .eq('estado', 'verificado')\
                    .execute()
                
                if pagos_res.data:
                    for pago in pagos_res.data:
                        pagos_map[pago['id_pedido']] += float(pago['monto'] or 0)
            except Exception as e:
                logger.error(f"Error obteniendo pagos para rentabilidad: {e}")

        # 4. Calcular métricas agregando item por item
        datos_por_producto = {pid: {'volumen': 0, 'facturacion': 0.0, 'costo_variable': 0.0} for pid in productos_info_actual.keys()}

        total_facturacion_global = 0.0
        total_costo_variable_global = 0.0
        total_volumen_ventas = 0
        total_margen_porcentual_acumulado = 0.0
        
        total_proximo_a_facturar = 0.0 # Acumulador para Ingresos Proyectados
        
        realized_order_ids = set() 
        order_subtotals = {} 
        order_objects_map = {} 

        # Iterar sobre cada item vendido
        for item in items_filtrados:
            producto_id = item.get('producto_id')
            if producto_id not in datos_por_producto:
                continue 

            pedido = item.get('pedido', {})
            pid = pedido.get('id')
            
            if pid and pid not in order_objects_map:
                order_objects_map[pid] = pedido

            cantidad = float(item.get('cantidad', 0))
            
            # --- PRECIO VENTA ---
            precio_unitario_real = float(item.get('precio_unitario') or 0)
            if not precio_unitario_real:
                 precio_unitario_real = float(productos_info_actual[producto_id]['producto'].get('precio_unitario', 0) or 0)
            
            # --- COSTO VARIABLE ---
            costo_unitario_real = productos_info_actual[producto_id]['costos_actuales']['costo_variable_unitario']

            facturacion_total_item = cantidad * precio_unitario_real
            costo_total_item = cantidad * costo_unitario_real
            
            # --- [LOGICA CORREGIDA] Cálculo de Realizado vs Pendiente ---
            precio_orden_total = float(pedido.get('precio_orden') or 0)
            total_pagado_orden = pagos_map.get(pid, 0.0)
            
            # Ratio de pago (0.0 a 1.0)
            ratio_pagado = 0.0
            if precio_orden_total > 0:
                ratio_pagado = total_pagado_orden / precio_orden_total
                if ratio_pagado > 1.0: ratio_pagado = 1.0 
            elif total_pagado_orden > 0:
                ratio_pagado = 1.0
            
            # Distribuimos valores
            facturacion_realizada = facturacion_total_item * ratio_pagado
            costo_realizado = costo_total_item * ratio_pagado
            
            facturacion_pendiente = facturacion_total_item - facturacion_realizada
            
            # Acumulamos en "Realizado"
            datos_por_producto[producto_id]['volumen'] += cantidad 
            datos_por_producto[producto_id]['facturacion'] += facturacion_realizada
            datos_por_producto[producto_id]['costo_variable'] += costo_realizado

            total_facturacion_global += facturacion_realizada
            total_costo_variable_global += costo_realizado
            total_volumen_ventas += cantidad
            
            # Acumulamos pendiente
            total_proximo_a_facturar += facturacion_pendiente
            
            if ratio_pagado > 0:
                realized_order_ids.add(pid)
                if pid not in order_subtotals:
                    order_subtotals[pid] = 0.0
                order_subtotals[pid] += facturacion_realizada

        # Construir array final
        datos_matriz = []
        for pid, stats in datos_por_producto.items():
            info = productos_info_actual[pid]
            volumen = stats['volumen']
            facturacion = stats['facturacion']
            costo_total = stats['costo_variable']
            margen_total = facturacion - costo_total
            
            precio_promedio = facturacion / volumen if volumen > 0 else float(info['producto'].get('precio_unitario') or 0)
            costo_promedio = costo_total / volumen if volumen > 0 else info['costos_actuales']['costo_variable_unitario']
            margen_unitario_promedio = precio_promedio - costo_promedio
            margen_porcentual = (margen_total / facturacion * 100) if facturacion > 0 else 0
            
            if volumen > 0 and facturacion > 0:
                total_margen_porcentual_acumulado += margen_porcentual

            datos_matriz.append({
                'id': pid,
                'nombre': info['producto'].get('nombre'),
                'volumen_ventas': volumen,
                'precio_venta': round(precio_promedio, 2),
                'costo_variable_unitario': round(costo_promedio, 2),
                'margen_contribucion_unitario': round(margen_unitario_promedio, 2),
                'margen_porcentual': round(margen_porcentual, 2),
                'facturacion_total': round(facturacion, 2),
                'costo_variable_total': round(costo_total, 2),
                'margen_contribucion_total': round(margen_total, 2),
                'detalles_costo': info['costos_actuales']
            })

        # 5. Calcular Costos Fijos
        resultados_costos_fijos = self._calcular_costo_fijo_mensual_iterativo(fecha_inicio, fecha_fin)
        total_costos_fijos_global = resultados_costos_fijos['total']
        total_directos = resultados_costos_fijos['directos']
        total_indirectos = resultados_costos_fijos['indirectos']

        if total_costos_fijos_global <= 0.0:
             try:
                costos_fijos_resp = self.costo_fijo_model.find_all(filters={'activo': True})
                costos_activos = [c for c in costos_fijos_resp.get('data', []) if c.get('activo') is True]
                if costos_activos:
                    total_mensual = 0.0
                    for c in costos_activos:
                        monto = float(c.get('monto_mensual') or 0)
                        total_mensual += monto
                        if c.get('tipo') == 'Directo':
                            total_directos += monto * months_duration
                        else:
                            total_indirectos += monto * months_duration
                    total_costos_fijos_global = total_mensual * months_duration
             except Exception as e: 
                logger.error(f"Fallback Fixed Cost Calc Error: {e}")

        # 6. Calcular Costos de Envío (Solo para ordenes realizadas)
        total_costos_envio_global = 0.0
        pedidos_para_envio = [order_objects_map[pid] for pid in realized_order_ids if pid in order_objects_map]
        
        # Método: Calcular envío y aplicar ratio de pago global para esas órdenes
        if pedidos_para_envio:
             costo_envio_teorico = self._calcular_costos_envio(pedidos_para_envio)
             
             fact_teorica_envio = sum(float(p.get('precio_orden') or 0) for p in pedidos_para_envio)
             fact_real_envio = sum(pagos_map.get(p['id'], 0) for p in pedidos_para_envio)
             
             ratio_global_envio = (fact_real_envio / fact_teorica_envio) if fact_teorica_envio > 0 else 0
             total_costos_envio_global = costo_envio_teorico * ratio_global_envio

        margen_contribucion_global = total_facturacion_global - total_costo_variable_global
        rentabilidad_neta_global = margen_contribucion_global - total_costos_fijos_global - total_costos_envio_global
        rentabilidad_porcentual_global = (rentabilidad_neta_global / total_facturacion_global * 100) if total_facturacion_global > 0 else 0
        
        # 7. Punto de Equilibrio
        punto_equilibrio = 0.0
        if total_facturacion_global > 0 and margen_contribucion_global > 0:
            ratio_margen = margen_contribucion_global / total_facturacion_global
            if ratio_margen > 0:
                punto_equilibrio = total_costos_fijos_global / ratio_margen

        productos_con_ventas_count = len([p for p in datos_matriz if p['facturacion_total'] > 0])
        promedio_ventas = total_volumen_ventas / productos_con_ventas_count if productos_con_ventas_count > 0 else 0
        promedio_margen = total_margen_porcentual_acumulado / productos_con_ventas_count if productos_con_ventas_count > 0 else 0

        totales_globales = {
            'facturacion_total': round(total_facturacion_global, 2),
            'costo_variable_total': round(total_costo_variable_global, 2),
            'margen_contribucion_total': round(margen_contribucion_global, 2),
            'costos_fijos_total': round(total_costos_fijos_global, 2),
            'costos_fijos_directos': round(total_directos, 2),
            'costos_fijos_indirectos': round(total_indirectos, 2),
            'costos_envio_total': round(total_costos_envio_global, 2),
            'rentabilidad_neta': round(rentabilidad_neta_global, 2),
            'rentabilidad_porcentual': round(rentabilidad_porcentual_global, 2),
            'proximo_a_facturar': round(total_proximo_a_facturar, 2),
            'punto_equilibrio': round(punto_equilibrio, 2)
        }
        
        promedios_matriz = {
            'volumen_ventas': round(promedio_ventas, 2),
            'margen_ganancia': round(promedio_margen, 2)
        }

        return self.success_response(data={'productos': datos_matriz, 'totales_globales': totales_globales, 'promedios': promedios_matriz})

    def _calcular_costo_fijo_mensual_iterativo(self, fecha_inicio_str: str, fecha_fin_str: str) -> Dict:
        """
        Calcula el costo fijo para el periodo.
        """
        resultado = {'total': 0.0, 'directos': 0.0, 'indirectos': 0.0}
        now = datetime.now()

        def parse_date_naive(date_str):
            if not date_str: return None
            try:
                s = str(date_str).strip()
                try:
                    dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
                except ValueError:
                    if ' ' in s:
                        s = s.replace(' ', 'T')
                    if '+' in s and '.' in s: 
                        s = s.split('+')[0]
                    dt = datetime.fromisoformat(s)
                return dt.replace(tzinfo=None)
            except Exception as e:
                logger.warning(f"Error parseando fecha '{date_str}': {e}")
                return None

        start_date = parse_date_naive(fecha_inicio_str) or (now - timedelta(days=30))
        end_date = parse_date_naive(fecha_fin_str)
        if not end_date:
            end_date = now
        elif len(str(fecha_fin_str)) == 10:
            end_date = end_date.replace(hour=23, minute=59, second=59)

        try:
            costos_res = self.costo_fijo_model.find_all(filters={'activo': True})
            if not costos_res.get('success'):
                return resultado
            costos_activos = [c for c in costos_res.get('data', []) if c.get('activo') is True]
            
            historial_res = self.costo_fijo_model.db.table('historial_costos_fijos').select('*').execute()
            all_history = historial_res.data if historial_res.data else []
            
            history_by_cost = {}
            for h in all_history:
                try:
                    cid = int(h['costo_fijo_id'])
                    dt_val = parse_date_naive(h.get('fecha_cambio'))
                    if dt_val:
                        h['fecha_cambio_dt'] = dt_val
                        if cid not in history_by_cost: 
                            history_by_cost[cid] = []
                        history_by_cost[cid].append(h)
                except Exception:
                    continue
            
            for cid in history_by_cost:
                history_by_cost[cid].sort(key=lambda x: x['fecha_cambio_dt'])

            dias_duracion = (end_date - start_date).total_seconds() / 86400
            
            if dias_duracion <= 35:
                for costo in costos_activos:
                    monto = float(costo.get('monto_mensual') or 0)
                    resultado['total'] += monto
                    if costo.get('tipo') == 'Directo':
                        resultado['directos'] += monto
                    else:
                        resultado['indirectos'] += monto
                return resultado

            months_to_process = []
            current = start_date.replace(day=1)
            
            while current.year < end_date.year or (current.year == end_date.year and current.month <= end_date.month):
                months_to_process.append((current.year, current.month))
                next_month = current.month + 1
                next_year = current.year
                if next_month > 12:
                    next_month = 1
                    next_year += 1
                current = current.replace(year=next_year, month=next_month, day=1)
                if current.year > end_date.year + 1: break 

            now_year = now.year
            now_month = now.month

            for year, month in months_to_process:
                last_day = calendar.monthrange(year, month)[1]
                month_end_dt = datetime(year, month, last_day, 23, 59, 59)
                is_current_month = (year == now_year and month == now_month)

                for costo in costos_activos:
                    cid = int(costo['id'])
                    historial_especifico = history_by_cost.get(cid, [])

                    tiene_historial_previo = any(h['fecha_cambio_dt'] <= month_end_dt for h in historial_especifico)
                    if not tiene_historial_previo:
                         if not self._existia_en_fecha(costo, month_end_dt):
                            continue

                    monto_mensual = 0.0
                    if is_current_month:
                        monto_mensual = float(costo.get('monto_mensual') or 0)
                    else:
                        monto_mensual = self._obtener_monto_vigente_dt(costo, month_end_dt, historial_especifico)
                    
                    resultado['total'] += monto_mensual
                    if costo.get('tipo') == 'Directo':
                        resultado['directos'] += monto_mensual
                    else:
                        resultado['indirectos'] += monto_mensual

        except Exception as e:
            logger.error(f"Error CRITICO en cálculo costos fijos: {e}", exc_info=True)
            return resultado

        return resultado

    def _existia_en_fecha(self, costo: Dict, fecha_limite_dt: datetime) -> bool:
        created_at_str = costo.get('created_at') or costo.get('fecha_creacion')
        if not created_at_str:
            return True
        try:
            s = str(created_at_str).strip()
            if ' ' in s: s = s.replace(' ', 'T')
            if '+' in s: s = s.split('+')[0]
            if 'Z' in s: s = s.replace('Z', '')
            created_at_dt = datetime.fromisoformat(s)
            if fecha_limite_dt < created_at_dt:
                return False
            return True
        except Exception:
            return True

    def _obtener_monto_vigente_dt(self, costo, fecha_limite_dt, historial):
        monto_actual_modelo = float(costo.get('monto_mensual') or 0)
        if not historial:
            return monto_actual_modelo

        registro_previo = None
        for h in historial:
            if h['fecha_cambio_dt'] <= fecha_limite_dt:
                registro_previo = h
            else:
                break
        
        if registro_previo:
            return float(registro_previo['monto_nuevo'])
        
        primer_cambio_futuro = None
        for h in historial:
            if h['fecha_cambio_dt'] > fecha_limite_dt:
                primer_cambio_futuro = h
                break
        
        if primer_cambio_futuro:
            val_anterior = float(primer_cambio_futuro['monto_anterior'])
            if val_anterior == 0.0:
                return float(primer_cambio_futuro['monto_nuevo'])
            return val_anterior

        return monto_actual_modelo

    def _calcular_costos_envio(self, pedidos_data: List[Dict]) -> float:
        total_costo = 0.0
        if not pedidos_data:
            return total_costo

        try:
            zonas_res = self.zona_model.find_all()
            zonas = zonas_res.get('data', []) if zonas_res.get('success') else []
            
            ids_to_fetch = []
            for p in pedidos_data:
                if p.get('id_direccion_entrega') and not p.get('direccion'):
                    ids_to_fetch.append(p['id_direccion_entrega'])
            
            extra_dirs_map = {}
            if ids_to_fetch:
                try:
                    direcciones_res = self.pedido_model.db.table('usuario_direccion').select('id, codigo_postal').in_('id', list(set(ids_to_fetch))).execute()
                    extra_dirs_map = {d['id']: d for d in direcciones_res.data} if direcciones_res.data else {}
                except Exception as e:
                    logger.warning(f"Error fetching extra addresses: {e}")

            for pedido in pedidos_data:
                cp_str = None
                direccion_obj = pedido.get('direccion')
                if direccion_obj and isinstance(direccion_obj, dict):
                    cp_str = direccion_obj.get('codigo_postal')
                
                if not cp_str:
                    dir_id = pedido.get('id_direccion_entrega')
                    if dir_id and dir_id in extra_dirs_map:
                         cp_str = extra_dirs_map[dir_id].get('codigo_postal')
                
                if not cp_str:
                    continue
                
                try:
                    import re
                    cp_limpio = re.sub(r'\D', '', str(cp_str))
                    if not cp_limpio:
                        continue
                        
                    cp = int(cp_limpio)
                    precio_zona = 0.0
                    
                    for zona in zonas:
                        z_ini = int(zona.get('codigo_postal_inicio') or 0)
                        z_fin = int(zona.get('codigo_postal_fin') or 99999)
                        
                        if z_ini <= cp <= z_fin:
                            precio_zona = float(zona.get('precio', 0))
                            break
                    
                    total_costo += precio_zona
                except (ValueError, TypeError):
                    continue

        except Exception as e:
            logger.error(f"Error calculando costos de envío: {e}", exc_info=True)
        
        return total_costo

    def _calcular_costos_unitarios_dinamicos(self, producto: Dict, roles_map: Dict[int, float]) -> Dict:
        producto_id = producto.get('id')
        costo_materia_prima = 0.0
        costo_mano_obra = 0.0
        
        try:
            receta_resp = self.receta_model.find_all(filters={'producto_id': producto_id})
            receta = None
            if receta_resp.get('success') and receta_resp.get('data'):
                receta = receta_resp['data'][0] 
            
            if receta:
                receta_id = receta['id']
                
                costo_mp_resp = self.receta_controller.calcular_costo_total_receta(receta_id)
                if costo_mp_resp and costo_mp_resp.get('success'):
                    costo_materia_prima = float(costo_mp_resp['data'].get('costo_total', 0))

                operaciones_resp = self.operacion_receta_model.find_by_receta_id(receta_id)
                if operaciones_resp.get('success'):
                    for op in operaciones_resp.get('data', []):
                        t_prep = float(op.get('tiempo_preparacion') or 0)
                        t_ejec = float(op.get('tiempo_ejecucion_unitario') or 0)
                        
                        tiempo_minutos = t_prep + t_ejec
                        tiempo_horas = tiempo_minutos / 60.0
                        
                        roles_op_resp = self.operacion_receta_rol_model.find_by_operacion_id(op['id'])
                        if roles_op_resp.get('success'):
                            for rol_asignado in roles_op_resp.get('data', []):
                                rol_id = rol_asignado.get('rol_id')
                                costo_hora_rol = roles_map.get(rol_id, 0.0)
                                costo_mano_obra += tiempo_horas * costo_hora_rol

        except Exception as e:
            logger.error(f"Error calculando costos dinámicos para producto {producto_id}: {e}", exc_info=True)

        costo_variable_unitario = costo_materia_prima + costo_mano_obra
        
        return {
            'costo_materia_prima': round(costo_materia_prima, 2),
            'costo_mano_obra': round(costo_mano_obra, 2),
            'costo_variable_unitario': round(costo_variable_unitario, 2)
        }

    def obtener_evolucion_producto(self, producto_id: int) -> tuple:
        producto_result = self.producto_model.find_by_id(producto_id)
        if not producto_result.get('success') or not producto_result.get('data'):
            return self.error_response("Producto no encontrado", 404)
        producto_data = producto_result.get('data')
        
        roles_resp = self.rol_model.find_all()
        roles_map = {r['id']: float(r.get('costo_por_hora') or 0) for r in roles_resp.get('data', [])} if roles_resp.get('success') else {}
        costos_actuales = self._calcular_costos_unitarios_dinamicos(producto_data, roles_map)
        costo_fallback = costos_actuales['costo_variable_unitario']

        fecha_fin = datetime.now()
        fecha_inicio = fecha_fin - timedelta(days=365)
        
        try:
            try:
                items_result = self.pedido_item_model.db.table('pedido_items').select(
                    'cantidad, precio_unitario, costo_unitario, pedido:pedidos!pedido_items_pedido_id_fkey!inner(fecha_solicitud, condicion_venta, estado)'
                ).eq('producto_id', producto_id).gte('pedido.fecha_solicitud', fecha_inicio.isoformat()).neq('pedido.estado', 'CANCELADO').execute()
            except Exception as e:
                logger.warning(f"Query failed in evolution, falling back: {e}")
                items_result = self.pedido_item_model.db.table('pedido_items').select(
                    'cantidad, pedido:pedidos!pedido_items_pedido_id_fkey!inner(fecha_solicitud, condicion_venta, estado)'
                ).eq('producto_id', producto_id).gte('pedido.fecha_solicitud', fecha_inicio.isoformat()).neq('pedido.estado', 'CANCELADO').execute()
            
        except Exception as e:
            logger.error(f"Error al obtener evolucion para producto ID {producto_id}: {e}", exc_info=True)
            return self.error_response("Error al obtener evolucion del producto.", 500)

        from collections import defaultdict
        ventas_por_mes = defaultdict(lambda: {'unidades': 0, 'facturacion': 0, 'ganancia': 0})
        
        if hasattr(items_result, 'data'):
            for item in items_result.data:
                pedido = item.get('pedido')
                if not pedido or not pedido.get('fecha_solicitud'):
                    continue
                
                if not self._should_include_order(pedido):
                    continue

                fecha_str = pedido['fecha_solicitud']
                mes_key = datetime.fromisoformat(fecha_str).strftime('%Y-%m')
                cantidad = float(item.get('cantidad', 0))
                
                precio = float(item.get('precio_unitario') or 0)
                if not precio:
                    precio = float(producto_data.get('precio_unitario', 0) or 0)
                
                costo = costo_fallback

                margen_unitario = precio - costo
                
                ventas_por_mes[mes_key]['unidades'] += cantidad
                ventas_por_mes[mes_key]['facturacion'] += cantidad * precio
                ventas_por_mes[mes_key]['ganancia'] += cantidad * margen_unitario

        evolucion = []
        for i in range(12):
            mes_actual = fecha_fin - timedelta(days=i * 30)
            mes_key = mes_actual.strftime('%Y-%m')
            
            datos_mes = ventas_por_mes.get(mes_key, {'unidades': 0, 'facturacion': 0, 'ganancia': 0})
            
            margen_porcentual = (datos_mes['ganancia'] / datos_mes['facturacion']) * 100 if datos_mes['facturacion'] > 0 else 0
            evolucion.append({
                "mes": mes_key,
                "unidades_vendidas": datos_mes['unidades'],
                "margen_ganancia_porcentual": round(margen_porcentual, 2)
            })

        evolucion.sort(key=lambda x: x['mes'])
        return self.success_response(data=evolucion)

    def _calcular_costo_producto(self, producto: Dict) -> Dict:
        try:
            roles_resp = self.rol_model.find_all()
            roles_map = {r['id']: float(r.get('costo_por_hora') or 0) for r in roles_resp.get('data', [])} if roles_resp.get('success') else {}
            costos = self._calcular_costos_unitarios_dinamicos(producto, roles_map)
            
            return {
                'costo_materia_prima': costos['costo_materia_prima'],
                'costo_mano_obra': costos['costo_mano_obra'],
                'costo_fijos': 0.0,
                'costo_total': costos['costo_variable_unitario']
            }
        except:
            return {'costo_materia_prima': 0, 'costo_mano_obra': 0, 'costo_fijos': 0, 'costo_total': 0}

    def calcular_crecimiento_ventas(self, periodo: str, metrica: str) -> tuple:
        hoy = datetime.now()
        if periodo == 'mes':
            fecha_fin_actual = hoy
            fecha_inicio_actual = hoy - timedelta(days=30)
            fecha_fin_anterior = fecha_inicio_actual - timedelta(days=1)
            fecha_inicio_anterior = fecha_fin_anterior - timedelta(days=30)
        elif periodo == 'trimestre':
            fecha_fin_actual = hoy
            fecha_inicio_actual = hoy - timedelta(days=90)
            fecha_fin_anterior = fecha_inicio_actual - timedelta(days=1)
            fecha_inicio_anterior = fecha_fin_anterior - timedelta(days=90)
        else: # año
            fecha_fin_actual = hoy
            fecha_inicio_actual = hoy - timedelta(days=365)
            fecha_fin_anterior = fecha_inicio_actual - timedelta(days=1)
            fecha_inicio_anterior = fecha_fin_anterior - timedelta(days=365)

        total_actual = self._obtener_total_ventas_periodo(fecha_inicio_actual, fecha_fin_actual, metrica)
        total_anterior = self._obtener_total_ventas_periodo(fecha_inicio_anterior, fecha_fin_anterior, metrica)

        if total_anterior == 0:
            crecimiento = 100.0 if total_actual > 0 else 0.0
        else:
            crecimiento = ((total_actual - total_anterior) / total_anterior) * 100

        return self.success_response(data={'crecimiento': round(crecimiento, 2), 'periodo_actual': total_actual, 'periodo_anterior': total_anterior})

    def _obtener_total_ventas_periodo(self, fecha_inicio: datetime, fecha_fin: datetime, metrica: str) -> float:
        pedidos_result = self.pedido_model.get_all_with_items(filtros={
            'fecha_desde': fecha_inicio.strftime('%Y-%m-%d'),
            'fecha_hasta': fecha_fin.strftime('%Y-%m-%d')
        })
        
        total = 0.0
        if pedidos_result.get('success') and pedidos_result.get('data'):
            for pedido in pedidos_result['data']:
                if metrica == 'facturacion':
                    total += pedido.get('total', 0.0) or 0.0
                else: # unidades
                    for item in pedido.get('pedido_items', []):
                        total += item.get('cantidad', 0)
        return total

    def obtener_detalles_producto(self, producto_id: int) -> tuple:
        """
        Devuelve detalles de un producto: historial de ventas, historial de precios,
        clientes principales Y AHORA LISTA DE PEDIDOS DETALLADA.
        """
        producto_result = self.producto_model.find_by_id(producto_id)
        if not producto_result.get('success') or not producto_result.get('data'):
            return self.error_response("Producto no encontrado", 404)
        
        producto_data = producto_result['data']
        producto_nombre = producto_data.get('nombre', 'Producto Desconocido')

        # Fallback de costos actuales
        roles_resp = self.rol_model.find_all()
        roles_map = {r['id']: float(r.get('costo_por_hora') or 0) for r in roles_resp.get('data', [])} if roles_resp.get('success') else {}
        costos_actuales = self._calcular_costos_unitarios_dinamicos(producto_data, roles_map)
        costo_fallback = costos_actuales['costo_variable_unitario']

        items_result = None
        try:
            try:
                # Eliminar codigo_pedido de la consulta
                items_result = self.producto_model.db.table('pedido_items').select(
                    'cantidad, precio_unitario, costo_unitario, pedido:pedidos!pedido_items_pedido_id_fkey!inner(id, fecha_solicitud, nombre_cliente, condicion_venta, estado)'
                ).eq('producto_id', producto_id).neq('pedido.estado', 'CANCELADO').execute()
            except Exception as e:
                logger.warning(f"Failed detailed query (missing cols?), fallback to basic: {e}")
                items_result = self.producto_model.db.table('pedido_items').select(
                    'cantidad, pedido:pedidos!pedido_items_pedido_id_fkey!inner(id, fecha_solicitud, nombre_cliente, condicion_venta, estado)'
                ).eq('producto_id', producto_id).neq('pedido.estado', 'CANCELADO').execute()

            if not items_result.data:
                return self.success_response(data={
                    'nombre_producto': producto_nombre,
                    'historial_ventas': [], 'historial_precios': [], 'clientes_principales': [],
                    'pedidos_relacionados': [], # Nueva lista
                    'costos': self._calcular_costo_producto(producto_data)
                })
        except Exception as e:
            logger.error(f"Error al consultar detalles para producto ID {producto_id}: {e}", exc_info=True)
            return self.error_response("Error al obtener detalles del producto.", 500)

        historial_ventas, historial_precios, clientes = [], {}, {}
        pedidos_relacionados = [] # Nueva lista

        precio_actual_prod = float(producto_data.get('precio_unitario', 0.0) or 0.0)

        for item in items_result.data:
            pedido = item.get('pedido')
            if not pedido:
                continue
            
            if not self._should_include_order(pedido):
                continue

            cantidad = float(item.get('cantidad', 0))
            
            precio_real = float(item.get('precio_unitario') or 0)
            if not precio_real:
                precio_real = precio_actual_prod
            
            fecha = pedido.get('fecha_solicitud')
            
            costo_real = costo_fallback
            
            subtotal = cantidad * precio_real
            ganancia = subtotal - (cantidad * costo_real)
            
            cliente_nombre = pedido.get('nombre_cliente', 'N/A')
            pedido_id = pedido.get('id')
            codigo_pedido = f"#{pedido_id}"

            historial_ventas.append({'fecha': fecha, 'cantidad': cantidad, 'cliente': cliente_nombre, 'subtotal': subtotal})
            
            if fecha:
                fecha_corta = fecha.split('T')[0]
                if fecha_corta not in historial_precios:
                     historial_precios[fecha_corta] = round(precio_real, 2)

            if cliente_nombre not in clientes:
                clientes[cliente_nombre] = {'facturacion': 0, 'unidades': 0}
            clientes[cliente_nombre]['facturacion'] += subtotal
            clientes[cliente_nombre]['unidades'] += cantidad
            
            pedidos_relacionados.append({
                'id': pedido_id,
                'codigo': codigo_pedido,
                'fecha': fecha.split('T')[0] if fecha else 'N/A',
                'cliente': cliente_nombre,
                'cantidad': cantidad,
                'precio_unitario': round(precio_real, 2),
                'costo_unitario': round(costo_real, 2),
                'total_venta': round(subtotal, 2),
                'ganancia': round(ganancia, 2)
            })

        clientes_principales = sorted(clientes.items(), key=lambda x: x[1]['facturacion'], reverse=True)
        historial_precios_ordenado = sorted(historial_precios.items(), key=lambda x: x[0])
        costos_info = self._calcular_costo_producto(producto_data)
        
        pedidos_relacionados.sort(key=lambda x: x['fecha'], reverse=True)

        return self.success_response(data={
            'nombre_producto': producto_nombre,
            'historial_ventas': sorted(historial_ventas, key=lambda x: x['fecha'], reverse=True),
            'historial_precios': historial_precios_ordenado,
            'clientes_principales': clientes_principales,
            'pedidos_relacionados': pedidos_relacionados,
            'costos': costos_info
        })