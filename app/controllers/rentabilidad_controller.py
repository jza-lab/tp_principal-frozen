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
from app.controllers.receta_controller import RecetaController
from typing import Dict, List

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
        # Instanciamos RecetaController para reutilizar la lógica de costo de materia prima
        self.receta_controller = RecetaController()

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

    def obtener_datos_matriz_rentabilidad(self, fecha_inicio: str = None, fecha_fin: str = None) -> tuple:
        """
        Orquesta el cálculo de métricas para todos los productos, con un rango de fechas opcional.
        Calcula costos variables dinámicos y resta costos fijos globales y costos de envío del total facturado.
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
            # Use safe select (removed codigo_pedido which caused issues)
            # Also fetch condicion_venta and estado from pedido for filtering
            try:
                query = self.pedido_item_model.db.table('pedido_items')\
                    .select('*, pedido:pedidos!pedido_items_pedido_id_fkey!inner(fecha_solicitud, condicion_venta, estado)')
                
                # Filter cancelled orders at DB level
                query = query.neq('pedido.estado', 'CANCELADO')

                if fecha_inicio and fecha_fin:
                    query = query.gte('pedido.fecha_solicitud', fecha_inicio).lte('pedido.fecha_solicitud', fecha_fin)
                
                items_res = query.execute()
                items_filtrados = items_res.data if items_res.data else []
            except Exception as e:
                logger.warning(f"Query failed (possibly missing columns), retrying safe select: {e}")
                # Fallback query with standard columns only
                query = self.pedido_item_model.db.table('pedido_items')\
                    .select('cantidad, producto_id, pedido_id, pedido:pedidos!pedido_items_pedido_id_fkey!inner(fecha_solicitud, condicion_venta, estado)')
                
                query = query.neq('pedido.estado', 'CANCELADO')

                if fecha_inicio and fecha_fin:
                    query = query.gte('pedido.fecha_solicitud', fecha_inicio).lte('pedido.fecha_solicitud', fecha_fin)
                
                items_res = query.execute()
                items_filtrados = items_res.data if items_res.data else []

            # Para envíos, obtenemos lista única de pedidos (filtered later)
            # We will filter this list later based on realized vs projected
            all_order_ids = list(set([i['pedido_id'] for i in items_filtrados]))
            pedidos_data_for_shipping = [] 
            if all_order_ids:
                pedidos_res = self.pedido_model.find_by_id_list(all_order_ids)
                # This list contains ALL orders (realized + projected), we need to filter it for shipping cost calculation of realized orders only
                all_pedidos_data = pedidos_res.get('data', [])
                
        except Exception as e:
            logger.error(f"Error al obtener datos de rentabilidad: {e}", exc_info=True)
            return self.error_response("Error al obtener datos.", 500)

        # 4. Calcular métricas agregando item por item
        datos_por_producto = {pid: {'volumen': 0, 'facturacion': 0.0, 'costo_variable': 0.0} for pid in productos_info_actual.keys()}

        total_facturacion_global = 0.0
        total_costo_variable_global = 0.0
        total_volumen_ventas = 0
        total_margen_porcentual_acumulado = 0.0
        
        total_proximo_a_facturar = 0.0 # New accumulator for Projected Revenue
        realized_order_ids = set() # Track IDs for shipping calculation

        # Iterar sobre cada item vendido
        for item in items_filtrados:
            producto_id = item.get('producto_id')
            if producto_id not in datos_por_producto:
                continue 

            pedido = item.get('pedido', {})
            
            cantidad = float(item.get('cantidad', 0))
            
            # --- PRECIO VENTA (Safe Access) ---
            precio_unitario_real = item.get('precio_unitario')
            if precio_unitario_real is None:
                 precio_unitario_real = float(productos_info_actual[producto_id]['producto'].get('precio_unitario', 0) or 0)
            else:
                 precio_unitario_real = float(precio_unitario_real)
            
            # --- COSTO VARIABLE (Safe Access) ---
            costo_unitario_real = item.get('costo_unitario')
            if costo_unitario_real is None:
                 costo_unitario_real = productos_info_actual[producto_id]['costos_actuales']['costo_variable_unitario']
            else:
                 costo_unitario_real = float(costo_unitario_real)

            facturacion_item = cantidad * precio_unitario_real
            
            # --- FILTERING LOGIC ---
            if self._should_include_order(pedido):
                # Include in Realized Profitability
                costo_item = cantidad * costo_unitario_real
                
                datos_por_producto[producto_id]['volumen'] += cantidad
                datos_por_producto[producto_id]['facturacion'] += facturacion_item
                datos_por_producto[producto_id]['costo_variable'] += costo_item

                total_facturacion_global += facturacion_item
                total_costo_variable_global += costo_item
                total_volumen_ventas += cantidad
                
                realized_order_ids.add(item['pedido_id'])
            else:
                # Include in Projected Revenue
                total_proximo_a_facturar += facturacion_item

        # Filter shipping data to include only realized orders
        pedidos_data_for_shipping = [p for p in all_pedidos_data if p['id'] in realized_order_ids]

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
            
            if volumen > 0:
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

        # 5-8. Calcular Costos Fijos, Envío, Rentabilidad Neta, Promedios
        resultados_costos_fijos = self._calcular_costo_fijo_historico_total(fecha_inicio, fecha_fin)
        total_costos_fijos_global = resultados_costos_fijos['total']
        total_directos = resultados_costos_fijos['directos']
        total_indirectos = resultados_costos_fijos['indirectos']

        if total_costos_fijos_global == 0.0:
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
             except Exception: pass

        total_costos_envio_global = self._calcular_costos_envio(pedidos_data_for_shipping)
        margen_contribucion_global = total_facturacion_global - total_costo_variable_global
        rentabilidad_neta_global = margen_contribucion_global - total_costos_fijos_global - total_costos_envio_global
        rentabilidad_porcentual_global = (rentabilidad_neta_global / total_facturacion_global * 100) if total_facturacion_global > 0 else 0
        
        productos_con_ventas_count = len([p for p in datos_matriz if p['volumen_ventas'] > 0])
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
            # New KPI
            'proximo_a_facturar': round(total_proximo_a_facturar, 2)
        }
        
        promedios_matriz = {
            'volumen_ventas': round(promedio_ventas, 2),
            'margen_ganancia': round(promedio_margen, 2)
        }

        return self.success_response(data={'productos': datos_matriz, 'totales_globales': totales_globales, 'promedios': promedios_matriz})

    # ... (helper methods unchanged) ...
    def _calcular_costo_fijo_historico_total(self, fecha_inicio_str: str, fecha_fin_str: str) -> Dict:
        """
        Calcula el costo fijo total acumulado en un rango de fechas.
        """
        resultado = {'total': 0.0, 'directos': 0.0, 'indirectos': 0.0}
        
        if not fecha_inicio_str:
            start_date = datetime.now() - timedelta(days=30) 
        else:
            start_date = datetime.fromisoformat(fecha_inicio_str)
            
        if not fecha_fin_str:
            end_date = datetime.now()
        else:
            end_date = datetime.fromisoformat(fecha_fin_str)

        try:
            costos_res = self.costo_fijo_model.find_all(filters={'activo': True})
            if not costos_res.get('success'):
                return resultado
            
            costos_activos = [c for c in costos_res.get('data', []) if c.get('activo') is True]

            for costo in costos_activos:
                costo_id = costo['id']
                es_directo = costo.get('tipo') == 'Directo'
                
                historial_res = self.costo_fijo_model.db.table('historial_costos_fijos')\
                    .select('*').eq('costo_fijo_id', costo_id).order('fecha_cambio', desc=False).execute()
                
                cambios = historial_res.data if historial_res.data else []
                timeline = []
                
                if not cambios:
                    timeline.append((datetime.min, float(costo['monto_mensual'])))
                else:
                    primer_cambio = cambios[0]
                    valor_inicial = float(primer_cambio['monto_anterior'])
                    timeline.append((datetime.min, valor_inicial))
                    
                    for cambio in cambios:
                        fecha = datetime.fromisoformat(cambio['fecha_cambio'].replace('Z', '+00:00')).replace(tzinfo=None)
                        valor = float(cambio['monto_nuevo'])
                        timeline.append((fecha, valor))
                
                costo_acumulado_item = 0.0
                ts_start = start_date.timestamp()
                ts_end = end_date.timestamp()
                
                for i in range(len(timeline)):
                    period_start_date = timeline[i][0]
                    if period_start_date == datetime.min:
                        ts_period_start = 0
                    else:
                        ts_period_start = period_start_date.timestamp()
                        
                    value = timeline[i][1]
                    
                    if i + 1 < len(timeline):
                        period_end_date = timeline[i+1][0]
                        ts_period_end = period_end_date.timestamp()
                    else:
                        ts_period_end = datetime(3000, 1, 1).timestamp()
                    
                    overlap_start = max(ts_start, ts_period_start)
                    overlap_end = min(ts_end, ts_period_end)
                    
                    if overlap_end > overlap_start:
                        seconds = overlap_end - overlap_start
                        days = seconds / (24 * 3600)
                        costo_acumulado_item += (days / 30.0) * value
                
                resultado['total'] += costo_acumulado_item
                if es_directo:
                    resultado['directos'] += costo_acumulado_item
                else:
                    resultado['indirectos'] += costo_acumulado_item

        except Exception as e:
            logger.error(f"Error en cálculo histórico de costos fijos: {e}", exc_info=True)
            return resultado
            
        return resultado

    def _calcular_costos_envio(self, pedidos_data: List[Dict]) -> float:
        """
        Calcula el costo total de envíos basado en las direcciones de entrega de los pedidos.
        """
        total_costo = 0.0
        if not pedidos_data:
            return total_costo

        try:
            zonas_res = self.zona_model.find_all()
            zonas = zonas_res.get('data', []) if zonas_res.get('success') else []
            
            direccion_ids = [p['id_direccion_entrega'] for p in pedidos_data if p.get('id_direccion_entrega')]
            
            if not direccion_ids:
                return 0.0

            direcciones_res = self.pedido_model.db.table('usuario_direccion').select('id, codigo_postal').in_('id', direccion_ids).execute()
            direcciones_map = {d['id']: d.get('codigo_postal') for d in direcciones_res.data} if direcciones_res.data else {}

            for pedido in pedidos_data:
                dir_id = pedido.get('id_direccion_entrega')
                if not dir_id:
                    continue
                
                cp_str = direcciones_map.get(dir_id)
                if not cp_str:
                    continue
                
                try:
                    cp = int(cp_str)
                    precio_zona = 0.0
                    for zona in zonas:
                        if zona.get('codigo_postal_inicio') <= cp <= zona.get('codigo_postal_fin'):
                            precio_zona = float(zona.get('precio', 0))
                            break
                    total_costo += precio_zona
                except (ValueError, TypeError):
                    continue

        except Exception as e:
            logger.error(f"Error calculando costos de envío: {e}", exc_info=True)
        
        return total_costo

    def _calcular_costos_unitarios_dinamicos(self, producto: Dict, roles_map: Dict[int, float]) -> Dict:
        """
        Calcula el costo unitario variable (Materia Prima + Mano de Obra) dinámicamente.
        """
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
                        tiempo_minutos = float(op.get('tiempo_ejecucion_unitario') or 0)
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
        """
        Devuelve la evolución de ventas y margen para un producto en los últimos 12 meses.
        Only include Realized Sales.
        """
        producto_result = self.producto_model.find_by_id(producto_id)
        if not producto_result.get('success') or not producto_result.get('data'):
            return self.error_response("Producto no encontrado", 404)
        producto_data = producto_result.get('data')
        
        # Calcular costos dinámicos actuales para fallback
        roles_resp = self.rol_model.find_all()
        roles_map = {r['id']: float(r.get('costo_por_hora') or 0) for r in roles_resp.get('data', [])} if roles_resp.get('success') else {}
        costos_actuales = self._calcular_costos_unitarios_dinamicos(producto_data, roles_map)
        costo_fallback = costos_actuales['costo_variable_unitario']

        fecha_fin = datetime.now()
        fecha_inicio = fecha_fin - timedelta(days=365)
        
        try:
            # --- FIX: Fallback query logic here too ---
            try:
                # Eliminar codigo_pedido
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
                
                # --- FILTERING LOGIC (Same as Main) ---
                if not self._should_include_order(pedido):
                    continue

                fecha_str = pedido['fecha_solicitud']
                mes_key = datetime.fromisoformat(fecha_str).strftime('%Y-%m')
                cantidad = float(item.get('cantidad', 0))
                
                # Usar precio/costo histórico o fallback
                precio = float(item.get('precio_unitario')) if item.get('precio_unitario') is not None else float(producto_data.get('precio_unitario', 0) or 0)
                costo = float(item.get('costo_unitario')) if item.get('costo_unitario') is not None else costo_fallback

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
            # --- FIX: Try-catch for missing columns ---
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
            
            # --- FILTERING LOGIC (Same as Main) ---
            if not self._should_include_order(pedido):
                continue

            # --- VALORES REALES vs FALLBACK (handled by .get() logic) ---
            cantidad = float(item.get('cantidad', 0))
            precio_real = float(item.get('precio_unitario')) if item.get('precio_unitario') is not None else precio_actual_prod
            costo_real = float(item.get('costo_unitario')) if item.get('costo_unitario') is not None else costo_fallback
            
            subtotal = cantidad * precio_real
            ganancia = subtotal - (cantidad * costo_real)
            
            fecha = pedido.get('fecha_solicitud')
            cliente_nombre = pedido.get('nombre_cliente', 'N/A')
            pedido_id = pedido.get('id')
            codigo_pedido = f"#{pedido_id}"

            # Historial Ventas (Gráfico)
            historial_ventas.append({'fecha': fecha, 'cantidad': cantidad, 'cliente': cliente_nombre, 'subtotal': subtotal})
            
            # Historial Precios (Gráfico)
            if fecha:
                fecha_corta = fecha.split('T')[0]
                if fecha_corta not in historial_precios:
                     historial_precios[fecha_corta] = round(precio_real, 2)

            # Clientes
            if cliente_nombre not in clientes:
                clientes[cliente_nombre] = {'facturacion': 0, 'unidades': 0}
            clientes[cliente_nombre]['facturacion'] += subtotal
            clientes[cliente_nombre]['unidades'] += cantidad
            
            # Pedidos Relacionados (Tabla)
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
        
        # Ordenar pedidos por fecha desc
        pedidos_relacionados.sort(key=lambda x: x['fecha'], reverse=True)

        return self.success_response(data={
            'nombre_producto': producto_nombre,
            'historial_ventas': sorted(historial_ventas, key=lambda x: x['fecha'], reverse=True),
            'historial_precios': historial_precios_ordenado,
            'clientes_principales': clientes_principales,
            'pedidos_relacionados': pedidos_relacionados,
            'costos': costos_info
        })
