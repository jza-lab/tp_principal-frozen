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

    def obtener_datos_matriz_rentabilidad(self, fecha_inicio: str = None, fecha_fin: str = None) -> tuple:
        """
        Orquesta el cálculo de métricas para todos los productos, con un rango de fechas opcional.
        Calcula costos variables dinámicos y resta costos fijos globales y costos de envío del total facturado.
        """
        # 1. Calcular duración del período para prorrateo de costos fijos (fallback si no hay histórico)
        months_duration = 1.0
        if fecha_inicio and fecha_fin:
            try:
                dt_inicio = datetime.fromisoformat(fecha_inicio)
                dt_fin = datetime.fromisoformat(fecha_fin)
                delta = dt_fin - dt_inicio
                # Consideramos 30 días como un mes estándar
                months_duration = max(delta.days / 30.0, 1.0)
            except ValueError:
                months_duration = 1.0
        else:
            # Si es histórico ("Todo"), calculamos desde el primer pedido hasta hoy
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

        # 2. Obtener todos los productos activos.
        productos_result = self.producto_model.find_all({'activo': True})
        if not productos_result.get('success'):
            return self.error_response("Error al obtener productos.", 500)
        
        productos_data = productos_result.get('data', [])
        
        # Pre-fetch roles y sus costos para optimizar
        roles_resp = self.rol_model.find_all()
        roles_map = {}
        if roles_resp.get('success'):
            for r in roles_resp.get('data', []):
                roles_map[r['id']] = float(r.get('costo_por_hora') or 0)

        # Calcular costos unitarios dinámicos para cada producto
        productos_con_costo = {}
        for p in productos_data:
            costos_dinamicos = self._calcular_costos_unitarios_dinamicos(p, roles_map)
            productos_con_costo[p['id']] = {
                'producto': p,
                'costos': costos_dinamicos
            }

        # 3. Obtener los IDs de los pedidos dentro del rango de fechas.
        pedidos_en_rango_ids = None
        pedidos_data_for_shipping = []
        
        if fecha_inicio and fecha_fin:
            try:
                pedidos_query = self.pedido_model.db.table('pedidos').select('id, id_direccion_entrega').gte('fecha_solicitud', fecha_inicio).lte('fecha_solicitud', fecha_fin)
                pedidos_result = pedidos_query.execute()
                if hasattr(pedidos_result, 'data'):
                    pedidos_en_rango_ids = [p['id'] for p in pedidos_result.data]
                    pedidos_data_for_shipping = pedidos_result.data
                else:
                    pedidos_en_rango_ids = []
            except Exception as e:
                logger.error(f"Error al obtener pedidos en rango de fechas: {e}", exc_info=True)
                return self.error_response("Error al filtrar pedidos por fecha.", 500)
        else:
             # Histórico
             try:
                pedidos_query = self.pedido_model.db.table('pedidos').select('id, id_direccion_entrega')
                pedidos_result = pedidos_query.execute()
                pedidos_en_rango_ids = None 
                pedidos_data_for_shipping = pedidos_result.data if hasattr(pedidos_result, 'data') else []
             except Exception as e:
                 logger.error(f"Error al obtener pedidos históricos: {e}")

        # 4. Calcular métricas de ventas y agregados globales
        datos_matriz = []
        
        total_facturacion_global = 0.0
        total_costo_variable_global = 0.0
        total_volumen_ventas = 0
        total_margen_porcentual_acumulado = 0.0

        for producto_id, info in productos_con_costo.items():
            producto = info['producto']
            costos = info['costos']
            producto_nombre = producto.get('nombre')
            
            items_query = self.pedido_item_model.db.table('pedido_items').select('cantidad').eq('producto_id', producto_id)
            if pedidos_en_rango_ids is not None:
                if not pedidos_en_rango_ids:
                    items_result = None # No hay pedidos
                else:
                    items_result = items_query.in_('pedido_id', pedidos_en_rango_ids).execute()
            else:
                items_result = items_query.execute()

            volumen_ventas = 0
            if items_result and hasattr(items_result, 'data'):
                volumen_ventas = sum(item.get('cantidad', 0) for item in items_result.data)
            
            precio_venta = float(producto.get('precio_unitario') or 0)
            costo_variable_unitario = costos['costo_variable_unitario']
            
            facturacion_producto = volumen_ventas * precio_venta
            costo_variable_total_producto = volumen_ventas * costo_variable_unitario
            margen_contribucion_producto = facturacion_producto - costo_variable_total_producto
            
            margen_contribucion_unitario = precio_venta - costo_variable_unitario
            margen_porcentual = (margen_contribucion_unitario / precio_venta * 100) if precio_venta > 0 else 0

            # Acumulados globales
            total_facturacion_global += facturacion_producto
            total_costo_variable_global += costo_variable_total_producto
            total_volumen_ventas += volumen_ventas
            if volumen_ventas > 0:
                total_margen_porcentual_acumulado += margen_porcentual

            datos_matriz.append({
                'id': producto_id,
                'nombre': producto_nombre,
                'volumen_ventas': volumen_ventas,
                'precio_venta': round(precio_venta, 2),
                'costo_variable_unitario': round(costo_variable_unitario, 2),
                'margen_contribucion_unitario': round(margen_contribucion_unitario, 2),
                'margen_porcentual': round(margen_porcentual, 2),
                'facturacion_total': round(facturacion_producto, 2),
                'costo_variable_total': round(costo_variable_total_producto, 2),
                'margen_contribucion_total': round(margen_contribucion_producto, 2),
                'detalles_costo': costos
            })

        # 5. Calcular Costos Fijos Globales (Directos + Indirectos para Rentabilidad Global)
        # Intentamos usar el cálculo histórico preciso primero
        total_costos_fijos_global = self._calcular_costo_fijo_historico_total(fecha_inicio, fecha_fin)
        
        # Variables para desglose (solo se calculan en fallback por simplicidad, o se podrían estimar)
        total_directos = 0.0
        total_indirectos = 0.0

        # Si el cálculo histórico devuelve 0 (por ejemplo, sin datos históricos), 
        # usamos el fallback del multiplicador simple si hay costos activos
        if total_costos_fijos_global == 0.0:
             try:
                costos_fijos_resp = self.costo_fijo_model.find_all(filters={'activo': True})
                costos_activos = [c for c in costos_fijos_resp.get('data', []) if c.get('activo') is True]

                if costos_activos:
                    total_mensual = 0.0
                    for c in costos_activos:
                        monto = float(c.get('monto_mensual') or 0)
                        tipo = c.get('tipo', 'Indirecto') # Default a indirecto si no existe
                        total_mensual += monto
                        
                        if tipo == 'Directo':
                            total_directos += monto * months_duration
                        else:
                            total_indirectos += monto * months_duration

                    total_costos_fijos_global = total_mensual * months_duration
             except Exception as e:
                 logger.error(f"Error en fallback de costos fijos: {e}")
        else:
             # Si tenemos cálculo histórico, intentamos una aproximación del desglose
             # (esto es imperfecto sin re-calcular el histórico por tipo, pero aceptable para visualización)
             try:
                costos_fijos_resp = self.costo_fijo_model.find_all(filters={'activo': True})
                active_direct = sum(float(c['monto_mensual']) for c in costos_fijos_resp.get('data', []) if c.get('activo') is True and c.get('tipo') == 'Directo')
                active_total = sum(float(c['monto_mensual']) for c in costos_fijos_resp.get('data', []) if c.get('activo') is True)
                
                ratio_direct = (active_direct / active_total) if active_total > 0 else 0
                total_directos = total_costos_fijos_global * ratio_direct
                total_indirectos = total_costos_fijos_global - total_directos
             except:
                pass

        # 6. Calcular Costos de Envío Globales
        total_costos_envio_global = self._calcular_costos_envio(pedidos_data_for_shipping)

        # 7. Calcular Rentabilidad Neta Global
        margen_contribucion_global = total_facturacion_global - total_costo_variable_global
        rentabilidad_neta_global = margen_contribucion_global - total_costos_fijos_global - total_costos_envio_global
        
        rentabilidad_porcentual_global = (rentabilidad_neta_global / total_facturacion_global * 100) if total_facturacion_global > 0 else 0
        
        # 8. Calcular Promedios para la Matriz (Cuadrantes)
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
            'rentabilidad_porcentual': round(rentabilidad_porcentual_global, 2)
        }
        
        promedios_matriz = {
            'volumen_ventas': round(promedio_ventas, 2),
            'margen_ganancia': round(promedio_margen, 2)
        }

        respuesta = {
            'productos': datos_matriz,
            'totales_globales': totales_globales,
            'promedios': promedios_matriz
        }
        
        return self.success_response(data=respuesta)

    def _calcular_costo_fijo_historico_total(self, fecha_inicio_str: str, fecha_fin_str: str) -> float:
        """
        Calcula el costo fijo total acumulado en un rango de fechas, considerando el historial de cambios.
        """
        total_acumulado = 0.0
        
        # Definir el rango de fechas
        if not fecha_inicio_str:
            # Si no hay inicio, buscar la fecha del primer costo creado o primer pedido (fallback a 30 días)
            start_date = datetime.now() - timedelta(days=30) 
        else:
            start_date = datetime.fromisoformat(fecha_inicio_str)
            
        if not fecha_fin_str:
            end_date = datetime.now()
        else:
            end_date = datetime.fromisoformat(fecha_fin_str)

        try:
            # 1. Obtener solo los costos fijos ACTIVOS actualmente
            # El usuario solicitó explícitamente excluir los inhabilitados del cálculo.
            costos_res = self.costo_fijo_model.find_all(filters={'activo': True})
            if not costos_res.get('success'):
                return 0.0
            
            # Verificación adicional en Python para garantizar que solo se usen activos
            # NOTA: Aquí revertimos a TODOS los costos (Directos + Indirectos) para el análisis global
            costos_activos = [c for c in costos_res.get('data', []) if c.get('activo') is True]

            for costo in costos_activos:
                costo_id = costo['id']
                # Obtener historial ordenado por fecha
                historial_res = self.costo_fijo_model.db.table('historial_costos_fijos')\
                    .select('*').eq('costo_fijo_id', costo_id).order('fecha_cambio', desc=False).execute()
                
                cambios = historial_res.data if historial_res.data else []
                
                # Construir línea de tiempo
                # Timeline es una lista de (fecha_inicio, valor)
                timeline = []
                
                # Valor inicial: asumimos que antes del primer cambio era el 'monto_anterior' del primer cambio,
                # o el valor actual si no hay cambios.
                if not cambios:
                    timeline.append((datetime.min, float(costo['monto_mensual'])))
                else:
                    # El valor antes del primer cambio registrado
                    primer_cambio = cambios[0]
                    # fecha_primer_cambio = datetime.fromisoformat(primer_cambio['fecha_cambio'].replace('Z', '+00:00')).replace(tzinfo=None)
                    valor_inicial = float(primer_cambio['monto_anterior'])
                    timeline.append((datetime.min, valor_inicial))
                    
                    for cambio in cambios:
                        fecha = datetime.fromisoformat(cambio['fecha_cambio'].replace('Z', '+00:00')).replace(tzinfo=None)
                        valor = float(cambio['monto_nuevo'])
                        timeline.append((fecha, valor))
                
                # Integrar sobre el periodo [start_date, end_date]
                costo_acumulado_item = 0.0
                
                # Convertir a timestamps para facilitar comparación
                ts_start = start_date.timestamp()
                ts_end = end_date.timestamp()
                
                # Asegurar que el loop cubre el rango
                for i in range(len(timeline)):
                    period_start_date = timeline[i][0]
                    # Si es min date (dummy), usar una fecha muy antigua o ajustar al start_date
                    if period_start_date == datetime.min:
                        ts_period_start = 0
                    else:
                        ts_period_start = period_start_date.timestamp()
                        
                    value = timeline[i][1]
                    
                    # Determinar fin de este segmento
                    if i + 1 < len(timeline):
                        period_end_date = timeline[i+1][0]
                        ts_period_end = period_end_date.timestamp()
                    else:
                        # Usamos un timestamp futuro seguro en lugar de max para evitar OverflowError
                        # Año 3000 es suficiente
                        ts_period_end = datetime(3000, 1, 1).timestamp()
                    
                    # Intersección con [ts_start, ts_end]
                    overlap_start = max(ts_start, ts_period_start)
                    overlap_end = min(ts_end, ts_period_end)
                    
                    if overlap_end > overlap_start:
                        # Calcular días
                        seconds = overlap_end - overlap_start
                        days = seconds / (24 * 3600)
                        # Prorrateo mensual (30 días)
                        costo_acumulado_item += (days / 30.0) * value
                
                total_acumulado += costo_acumulado_item

        except Exception as e:
            logger.error(f"Error en cálculo histórico de costos fijos: {e}", exc_info=True)
            return 0.0
            
        return total_acumulado

    def _calcular_costos_envio(self, pedidos_data: List[Dict]) -> float:
        """
        Calcula el costo total de envíos basado en las direcciones de entrega de los pedidos.
        Utiliza las zonas y sus precios por código postal.
        """
        total_costo = 0.0
        if not pedidos_data:
            return total_costo

        try:
            # Obtener todas las zonas para búsqueda en memoria (más eficiente que N queries)
            zonas_res = self.zona_model.find_all()
            zonas = zonas_res.get('data', []) if zonas_res.get('success') else []
            
            # Mapa de dirección -> CP para minimizar queries a usuario_direccion
            direccion_ids = [p['id_direccion_entrega'] for p in pedidos_data if p.get('id_direccion_entrega')]
            
            if not direccion_ids:
                return 0.0

            # Consultar direcciones en lote
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
                    # Buscar zona correspondiente
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
            # 1. Obtener Receta Activa
            # Asumimos que hay una receta activa vinculada, o buscamos la más reciente.
            # La relación producto-receta suele ser 1 a 1 en el modelo actual o inversa.
            # RecetaModel tiene producto_id.
            receta_resp = self.receta_model.find_all(filters={'producto_id': producto_id})
            receta = None
            if receta_resp.get('success') and receta_resp.get('data'):
                # Tomamos la primera receta encontrada (idealmente debería ser la activa)
                receta = receta_resp['data'][0] 
            
            if receta:
                receta_id = receta['id']
                
                # 2. Costo Materia Prima (Ingredientes)
                costo_mp_resp = self.receta_controller.calcular_costo_total_receta(receta_id)
                if costo_mp_resp and costo_mp_resp.get('success'):
                    costo_materia_prima = float(costo_mp_resp['data'].get('costo_total', 0))

                # 3. Costo Mano de Obra (Operaciones * Roles)
                operaciones_resp = self.operacion_receta_model.find_by_receta_id(receta_id)
                if operaciones_resp.get('success'):
                    for op in operaciones_resp.get('data', []):
                        tiempo_minutos = float(op.get('tiempo_ejecucion_unitario') or 0)
                        tiempo_horas = tiempo_minutos / 60.0
                        
                        # Obtener roles asignados a esta operación
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
        Nota: En esta versión simplificada, el margen histórico se calcula con el costo ACTUAL dinámico.
        Para un histórico preciso se necesitaría guardar snapshots de costos, pero esto cumple el requerimiento actual.
        """
        # 1. Obtener datos del producto
        producto_result = self.producto_model.find_by_id(producto_id)
        if not producto_result.get('success') or not producto_result.get('data'):
            return self.error_response("Producto no encontrado", 404)
        
        producto_data = producto_result.get('data')
        
        # Calcular costos dinámicos actuales
        roles_resp = self.rol_model.find_all()
        roles_map = {r['id']: float(r.get('costo_por_hora') or 0) for r in roles_resp.get('data', [])} if roles_resp.get('success') else {}
        
        costos = self._calcular_costos_unitarios_dinamicos(producto_data, roles_map)
        costo_variable_unitario = costos['costo_variable_unitario']
        precio_venta_unitario = float(producto_data.get('precio_unitario') or 0)
        margen_contribucion_unitario = precio_venta_unitario - costo_variable_unitario

        # 2. Obtener ventas del último año
        fecha_fin = datetime.now()
        fecha_inicio = fecha_fin - timedelta(days=365)
        
        try:
            pedidos_resp = self.pedido_model.db.table('pedidos').select('id').gte(
                'fecha_solicitud', fecha_inicio.isoformat()
            ).lte('fecha_solicitud', fecha_fin.isoformat()).execute()
            
            if not hasattr(pedidos_resp, 'data'):
                return self.success_response(data=[]) 
            
            pedido_ids_en_rango = [p['id'] for p in pedidos_resp.data]
            if not pedido_ids_en_rango:
                return self.success_response(data=[])

            items_result = self.pedido_item_model.db.table('pedido_items').select(
                'cantidad, pedido:pedidos!pedido_items_pedido_id_fkey!inner(fecha_solicitud)'
            ).eq('producto_id', producto_id).in_('pedido_id', pedido_ids_en_rango).execute()
            
        except Exception as e:
            logger.error(f"Error al obtener evolucion para producto ID {producto_id}: {e}", exc_info=True)
            return self.error_response("Error al obtener evolucion del producto.", 500)

        # 3. Agregar datos por mes
        from collections import defaultdict
        ventas_por_mes = defaultdict(lambda: {'unidades': 0, 'facturacion': 0, 'ganancia': 0})
        
        if hasattr(items_result, 'data'):
            for item in items_result.data:
                if not item.get('pedido') or not item['pedido'].get('fecha_solicitud'):
                    continue
                
                fecha_str = item['pedido']['fecha_solicitud']
                mes_key = datetime.fromisoformat(fecha_str).strftime('%Y-%m')
                cantidad = item.get('cantidad', 0)
                
                ventas_por_mes[mes_key]['unidades'] += cantidad
                ventas_por_mes[mes_key]['facturacion'] += cantidad * precio_venta_unitario
                ventas_por_mes[mes_key]['ganancia'] += cantidad * margen_contribucion_unitario

        # 4. Formatear la respuesta
        evolucion = []
        for i in range(12):
            mes_actual = fecha_fin - timedelta(days=i * 30)
            mes_key = mes_actual.strftime('%Y-%m')
            
            datos_mes = ventas_por_mes.get(mes_key, {'unidades': 0, 'facturacion': 0, 'ganancia': 0})
            
            margen_porcentual = (datos_mes['ganancia'] / datos_mes['facturacion']) * 100 if datos_mes['facturacion'] > 0 else 0
            evolucion.append({
                "mes": mes_key,
                "unidades_vendidas": datos_mes['unidades'],
                "margen_ganancia_porcentual": round(margen_porcentual, 2) # Ahora es Margen Contribución %
            })

        evolucion.sort(key=lambda x: x['mes'])
        return self.success_response(data=evolucion)

    def _calcular_costo_producto(self, producto: Dict) -> Dict:
        """
        Método legacy mantenido para compatibilidad con views antiguas que lo usen,
        pero redirigido a la lógica dinámica si es posible, o devolviendo lo almacenado.
        Para este caso, usamos la lógica dinámica instanciando dependencias al vuelo si es necesario.
        """
        # Esta función se usaba para mostrar detalles estáticos.
        # Vamos a intentar usar la dinámica.
        try:
            roles_resp = self.rol_model.find_all()
            roles_map = {r['id']: float(r.get('costo_por_hora') or 0) for r in roles_resp.get('data', [])} if roles_resp.get('success') else {}
            costos = self._calcular_costos_unitarios_dinamicos(producto, roles_map)
            
            return {
                'costo_materia_prima': costos['costo_materia_prima'],
                'costo_mano_obra': costos['costo_mano_obra'],
                'costo_fijos': 0.0, # Ya no se asigna unitariamente
                'costo_total': costos['costo_variable_unitario']
            }
        except:
            return {'costo_materia_prima': 0, 'costo_mano_obra': 0, 'costo_fijos': 0, 'costo_total': 0}

    def calcular_crecimiento_ventas(self, periodo: str, metrica: str) -> tuple:
        """
        Calcula el crecimiento en ventas comparando dos períodos.
        """
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
        """Función auxiliar para obtener el total de ventas en un rango de fechas."""
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
        Devuelve detalles de un producto: historial de ventas, historial de precios (inferido) y clientes principales.
        """
        producto_result = self.producto_model.find_by_id(producto_id)
        if not producto_result.get('success') or not producto_result.get('data'):
            return self.error_response("Producto no encontrado", 404)
        
        producto_data = producto_result['data']
        producto_nombre = producto_data.get('nombre', 'Producto Desconocido')

        try:
            items_result = self.producto_model.db.table('pedido_items').select(
                'cantidad, pedido:pedidos!pedido_items_pedido_id_fkey!inner(fecha_solicitud, nombre_cliente)'
            ).eq('producto_id', producto_id).execute()

            if not items_result.data:
                return self.success_response(data={
                    'nombre_producto': producto_nombre,
                    'historial_ventas': [], 'historial_precios': [], 'clientes_principales': [],
                    'costos': self._calcular_costo_producto(producto_data)
                })
        except Exception as e:
            logger.error(f"Error al consultar detalles para producto ID {producto_id}: {e}", exc_info=True)
            return self.error_response("Error al obtener detalles del producto.", 500)

        historial_ventas, historial_precios, clientes = [], {}, {}
        precio_unitario_actual = producto_data.get('precio_unitario', 0.0) or 0.0

        for item in items_result.data:
            if not item.get('pedido'):
                continue
            
            cantidad = item.get('cantidad', 0)
            subtotal = cantidad * precio_unitario_actual
            fecha = item['pedido'].get('fecha_solicitud')
            cliente_nombre = item['pedido'].get('nombre_cliente', 'N/A')

            historial_ventas.append({'fecha': fecha, 'cantidad': cantidad, 'cliente': cliente_nombre, 'subtotal': subtotal})
            
            if fecha:
                fecha_corta = fecha.split('T')[0]
                if fecha_corta not in historial_precios:
                     historial_precios[fecha_corta] = round(precio_unitario_actual, 2)

            if cliente_nombre not in clientes:
                clientes[cliente_nombre] = {'facturacion': 0, 'unidades': 0}
            clientes[cliente_nombre]['facturacion'] += subtotal
            clientes[cliente_nombre]['unidades'] += cantidad

        clientes_principales = sorted(clientes.items(), key=lambda x: x[1]['facturacion'], reverse=True)
        historial_precios_ordenado = sorted(historial_precios.items(), key=lambda x: x[0])
        costos_info = self._calcular_costo_producto(producto_data)

        return self.success_response(data={
            'nombre_producto': producto_nombre,
            'historial_ventas': sorted(historial_ventas, key=lambda x: x['fecha'], reverse=True),
            'historial_precios': historial_precios_ordenado,
            'clientes_principales': clientes_principales,
            'costos': costos_info
        })
