from datetime import datetime, timedelta
from app.models.orden_produccion import OrdenProduccionModel
from app.models.control_calidad_producto import ControlCalidadProductoModel
from app.models.registro_desperdicio_lote_producto_model import RegistroDesperdicioLoteProductoModel
from app.models.receta import RecetaModel
from app.models.reclamo import ReclamoModel
from app.models.pedido import PedidoModel
from app.models.control_calidad_insumo import ControlCalidadInsumoModel
from app.models.orden_compra_model import OrdenCompraModel
from app.models.insumo_inventario import InsumoInventarioModel
from app.models.reserva_insumo import ReservaInsumoModel
from app.models.insumo import InsumoModel
from app.models.lote_producto import LoteProductoModel
from app.models.producto import ProductoModel
from decimal import Decimal
from app.utils import estados
import logging
logger = logging.getLogger(__name__)
from collections import defaultdict
logging.basicConfig(level=logging.INFO)

class IndicadoresController:
    def __init__(self):
        self.orden_produccion_model = OrdenProduccionModel()
        self.control_calidad_producto_model = ControlCalidadProductoModel()
        self.registro_desperdicio_model = RegistroDesperdicioLoteProductoModel()
        self.receta_model = RecetaModel()
        self.reclamo_model = ReclamoModel()
        self.pedido_model = PedidoModel()
        self.control_calidad_insumo_model = ControlCalidadInsumoModel()
        self.orden_compra_model = OrdenCompraModel()
        self.insumo_inventario_model = InsumoInventarioModel()
        self.reserva_insumo_model = ReservaInsumoModel()
        self.insumo_model = InsumoModel()
        self.lote_producto_model = LoteProductoModel()
        self.producto_model = ProductoModel()

    def _parsear_fechas(self, fecha_inicio_str, fecha_fin_str, default_days=30):
        if fecha_inicio_str:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        else:
            fecha_inicio = datetime.now() - timedelta(days=default_days)

        if fecha_fin_str:
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
        else:
            fecha_fin = datetime.now()
        return fecha_inicio, fecha_fin

    # --- CATEGORÍA: PRODUCCIÓN ---
    def obtener_datos_produccion(self, fecha_inicio_str, fecha_fin_str):
        fecha_inicio, fecha_fin = self._parsear_fechas(fecha_inicio_str, fecha_fin_str)
        
        # 1. Rotación de Inventario (mensual)
        try:
            cogs_res = self.reserva_insumo_model.get_consumo_total_valorizado_en_periodo(fecha_inicio, fecha_fin)
            stock_valorizado_res = self.insumo_inventario_model.get_stock_total_valorizado()

            if cogs_res['success'] and stock_valorizado_res['success']:
                cogs = cogs_res['total_consumido_valorizado']
                inventario_promedio = stock_valorizado_res['total_valorizado'] # Simplificación: usamos el valor actual
                
                rotacion = cogs / inventario_promedio if inventario_promedio else 0
                kpis['rotacion_inventario'] = {"valor": round(rotacion, 2), "cogs": cogs, "inventario_valorizado": inventario_promedio}
            else:
                kpis['rotacion_inventario'] = {"valor": 0, "cogs": 0, "inventario_valorizado": 0}
        except Exception as e:
            kpis['rotacion_inventario'] = {"valor": 0, "cogs": 0, "inventario_valorizado": 0}

        # 2. Cobertura de Stock (promedio de todos los insumos)
        try:
            insumos_res = self.insumo_model.find_all()
            if insumos_res['success'] and insumos_res['data']:
                coberturas = []
                total_stock_valorizado = 0
                total_consumo_diario_valorizado = 0

                for insumo in insumos_res['data']:
                    id_insumo = insumo['id_insumo']
                    precio_unitario = insumo.get('precio_unitario', 0)

                    stock_res = self.insumo_inventario_model.get_stock_actual_por_insumo(id_insumo)
                    consumo_res = self.reserva_insumo_model.get_consumo_promedio_diario_por_insumo(id_insumo)

                    if stock_res['success'] and consumo_res['success']:
                        stock_actual = stock_res['stock_actual']
                        consumo_diario = consumo_res['consumo_promedio_diario']

                        total_stock_valorizado += stock_actual * precio_unitario
                        total_consumo_diario_valorizado += consumo_diario * precio_unitario
                        
                        if consumo_diario > 0:
                            coberturas.append(stock_actual / consumo_diario)

                if total_consumo_diario_valorizado > 0:
                    cobertura_promedio = total_stock_valorizado / total_consumo_diario_valorizado
                else:
                    cobertura_promedio = float('inf')

                kpis['cobertura_stock'] = {
                    "valor": round(cobertura_promedio, 2) if cobertura_promedio != float('inf') else 'inf',
                    "insumo_nombre": "Todos los insumos",
                    "stock": round(total_stock_valorizado, 2),
                    "consumo_diario": round(total_consumo_diario_valorizado, 2)
                }
            else:
                kpis['cobertura_stock'] = {"valor": 0, "insumo_nombre": "N/A", "stock": 0, "consumo_diario": 0}
        except Exception as e:
            kpis['cobertura_stock'] = {"valor": 0, "insumo_nombre": "N/A", "stock": 0, "consumo_diario": 0}
            
        return kpis
        
    def obtener_kpis_produccion(self, fecha_inicio_str, fecha_fin_str):
        if fecha_inicio_str:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        else:
            fecha_inicio = datetime.now() - timedelta(days=30)

        if fecha_fin_str:
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
        else:
            fecha_fin = datetime.now()

        oee = self._calcular_oee(fecha_inicio, fecha_fin)
        cumplimiento_plan = self._calcular_cumplimiento_plan(fecha_inicio, fecha_fin)
        causas_desperdicio = self.obtener_causas_desperdicio_pareto(fecha_inicio_str, fecha_fin_str)

        return { "oee": oee, "cumplimiento_plan": cumplimiento_plan, "causas_desperdicio_pareto": causas_desperdicio }

    # --- CATEGORÍA: CALIDAD ---
    def obtener_datos_calidad(self, fecha_inicio_str, fecha_fin_str):
        fecha_inicio, fecha_fin = self._parsear_fechas(fecha_inicio_str, fecha_fin_str)
        
        return {
            "tasa_rechazo_interno": self._calcular_tasa_rechazo_interno(fecha_inicio, fecha_fin),
            "tasa_reclamos_clientes": self._calcular_tasa_reclamos_clientes(fecha_inicio, fecha_fin),
            "tasa_rechazo_proveedores": self._calcular_tasa_rechazo_proveedores(fecha_inicio, fecha_fin),
        }

    # --- CATEGORÍA: COMERCIAL ---
    def obtener_datos_comercial(self, fecha_inicio_str, fecha_fin_str):
        fecha_inicio, fecha_fin = self._parsear_fechas(fecha_inicio_str, fecha_fin_str, default_days=365)
        return {
            "kpis_comerciales": self._obtener_kpis_comerciales(fecha_inicio, fecha_fin),
            "top_productos_vendidos": self.obtener_top_productos_vendidos(fecha_inicio_str, fecha_fin_str),
            "top_clientes": self.obtener_top_clientes(fecha_inicio_str, fecha_fin_str),
        }

    # --- CATEGORÍA: FINANCIERA ---
    def obtener_datos_financieros(self, fecha_inicio_str, fecha_fin_str):
        return {
            "facturacion_periodo": self.obtener_facturacion_por_periodo(fecha_inicio_str, fecha_fin_str),
            "costo_vs_ganancia": self.obtener_costo_vs_ganancia(fecha_inicio_str, fecha_fin_str),
            "rentabilidad_productos": self.obtener_rentabilidad_productos(fecha_inicio_str, fecha_fin_str),
            "descomposicion_costos": self.obtener_descomposicion_costos(fecha_inicio_str, fecha_fin_str),
        }
        
    # --- CATEGORÍA: INVENTARIO ---
    def obtener_datos_inventario(self, fecha_inicio_str, fecha_fin_str):
        fecha_inicio, fecha_fin = self._parsear_fechas(fecha_inicio_str, fecha_fin_str)
        return {
            "kpis_inventario": self._obtener_kpis_inventario(fecha_inicio, fecha_fin),
            "antiguedad_stock_insumos": self.obtener_antiguedad_stock('insumo'),
            "antiguedad_stock_productos": self.obtener_antiguedad_stock('producto'),
        }
        
    # --- MÉTODOS DE CÁLCULO OPTIMIZADOS ---

    def _preparar_cache_operaciones(self, receta_ids: list):
        """Pre-carga todas las operaciones para una lista de IDs de recetas en una sola consulta."""
        if not receta_ids: return {}
        operaciones_res = self.receta_model.get_operaciones_by_receta_ids(list(set(receta_ids)))
        if not operaciones_res.get('success'): return {}
        
        cache = defaultdict(list)
        for op in operaciones_res.get('data', []):
            cache[op['receta_id']].append(op)
        return cache

    def _calcular_carga_op_con_cache(self, op_data: dict, cache_operaciones: dict) -> Decimal:
        """Calcula la carga de una OP usando la caché de operaciones pre-cargada."""
        carga_total, receta_id, cantidad = Decimal(0), op_data.get('receta_id'), Decimal(op_data.get('cantidad_planificada', 0))
        if not receta_id or cantidad <= 0 or receta_id not in cache_operaciones:
            return carga_total

        for op_step in cache_operaciones[receta_id]:
            t_prep = Decimal(op_step.get('tiempo_preparacion', 0))
            t_ejec_unit = Decimal(op_step.get('tiempo_ejecucion_unitario', 0))
            carga_total += t_prep + (t_ejec_unit * cantidad)
        return carga_total

    def _calcular_oee(self, fecha_inicio, fecha_fin):
        ordenes_res = self.orden_produccion_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        ordenes_en_periodo = ordenes_res.get('data', [])
        if not ordenes_en_periodo: return {"valor": 0, "disponibilidad": 0, "rendimiento": 0, "calidad": 0}

        # Optimización: Pre-cargar todas las operaciones de las recetas necesarias.
        receta_ids = [op['receta_id'] for op in ordenes_en_periodo if op.get('receta_id')]
        cache_operaciones = self._preparar_cache_operaciones(receta_ids)

        # Usar la caché para calcular el tiempo planificado sin consultas N+1.
        tiempo_planificado = sum(self._calcular_carga_op_con_cache(op, cache_operaciones) for op in ordenes_en_periodo) * 60
        
        tiempo_produccion_planificado = sum([self._calcular_carga_op(op) for op in ordenes_en_periodo]) * 60 # a segundos
        tiempo_produccion_real = sum([(datetime.fromisoformat(op['fecha_fin']) - datetime.fromisoformat(op['fecha_inicio'])).total_seconds() for op in ordenes_en_periodo if op.get('fecha_fin') and op.get('fecha_inicio')])

        # Logging para depuración
        logger.info(f"Cálculo de OEE para el período {fecha_inicio} a {fecha_fin}")
        logger.info(f"Órdenes en período: {len(ordenes_en_periodo)}")
        logger.info(f"Tiempo de Producción Planificado (segundos): {tiempo_produccion_planificado}")
        logger.info(f"Tiempo de Producción Real (segundos): {tiempo_produccion_real}")

        disponibilidad = float(tiempo_produccion_real) / float(tiempo_produccion_planificado) if tiempo_produccion_planificado > 0 else 0

        produccion_real = sum([op.get('cantidad_producida', 0) for op in ordenes_en_periodo])
        produccion_teorica = sum([op.get('cantidad_planificada', 0) for op in ordenes_en_periodo])
        rendimiento = produccion_real / produccion_teorica if produccion_teorica > 0 else 0

        unidades_buenas_res = self.control_calidad_producto_model.get_total_unidades_aprobadas_en_periodo(fecha_inicio, fecha_fin)
        unidades_buenas = 0
        if unidades_buenas_res['success']:
            unidades_buenas = unidades_buenas_res['total_unidades']
            
        calidad = unidades_buenas / produccion_real if produccion_real > 0 else 0

        oee = disponibilidad * rendimiento * calidad * 100
        return {"valor": round(oee, 2), "disponibilidad": round(disponibilidad, 2), "rendimiento": round(rendimiento, 2), "calidad": round(calidad, 2)}
        
    def _preparar_cache_costos_por_productos(self, producto_ids: list):
        if not producto_ids: return {}
        producto_ids_unicos = list(set(producto_ids))
        
        recetas_res = self.receta_model.find_all(filters={'producto_id': producto_ids_unicos, 'activa': True})
        if not recetas_res.get('success') or not recetas_res.get('data'):
            logging.warning(f"No se encontraron recetas para IDs: {producto_ids_unicos}. Error: {recetas_res.get('error')}")
            return {}

        receta_ids = [receta['id'] for receta in recetas_res.get('data', [])]
        if not receta_ids: return {}

        all_insumo_ids = set()
        ingredientes_res = self.receta_model.get_ingredientes_by_receta_ids(receta_ids)
        if ingredientes_res.get('success') and ingredientes_res.get('data'):
            for ing in ingredientes_res['data']:
                if (insumo_data := ing.get('insumos_catalogo')) and insumo_data.get('id_insumo'):
                    all_insumo_ids.add(insumo_data['id_insumo'])

        costos_insumos = {}
        if all_insumo_ids:
            if costos_res := self.insumo_inventario_model.get_costos_promedio_ponderado_bulk(list(all_insumo_ids)):
                 if costos_res.get('success'):
                    costos_insumos = costos_res.get('data', {})
        return costos_insumos

    def _get_costo_producto(self, producto_id, costos_insumos_cache=None):
        return self.receta_model.get_costo_produccion(producto_id, costos_insumos=costos_insumos_cache)

    def _calcular_cumplimiento_plan(self, fecha_inicio, fecha_fin):
            ordenes_planificadas_res = self.orden_produccion_model.get_all_in_date_range(fecha_inicio, fecha_fin)
            ordenes_planificadas = ordenes_planificadas_res.get('data', [])
            total_ordenes_planificadas = len(ordenes_planificadas)
            ordenes_completadas_a_tiempo = 0

            print("--- DEBUG: Verificando Cumplimiento del Plan de Producción ---")
            for i, orden in enumerate(ordenes_planificadas):
                estado = orden.get('estado')
                fecha_fin_str = orden.get('fecha_fin')
                
                # --- CORRECCIÓN: Usando 'fecha_meta' como indicaste ---
                fecha_meta_str = orden.get('fecha_meta') 
                
                # Usamos 'id_orden_produccion' que es más probable que exista en el dict
                print(f"Orden #{i+1}: ID={orden.get('id_orden_produccion', 'N/A')}, Estado='{estado}', Fecha Fin='{fecha_fin_str}', Fecha Meta='{fecha_meta_str}'")

                # --- CORRECCIÓN: Usando la variable 'estados.OP_COMPLETADA' (más seguro) y 'fecha_meta_str' ---
                if estado == estados.OP_COMPLETADA and fecha_fin_str and fecha_meta_str:
                    fecha_fin_dt = datetime.fromisoformat(fecha_fin_str).date()
                    fecha_meta_dt = datetime.fromisoformat(fecha_meta_str).date() # Corregido
                    print(f"  -> Comparando: {fecha_fin_dt} <= {fecha_meta_dt}   -->   {fecha_fin_dt <= fecha_meta_dt}")
                    if fecha_fin_dt <= fecha_meta_dt:
                        ordenes_completadas_a_tiempo += 1
                else:
                    print("  -> No cumple condiciones para ser 'completada a tiempo'.")
            
            print(f"--- Fin DEBUG: Total Planificadas={total_ordenes_planificadas}, Completadas a Tiempo={ordenes_completadas_a_tiempo} ---")
            
            cumplimiento = (ordenes_completadas_a_tiempo / total_ordenes_planificadas) * 100 if total_ordenes_planificadas > 0 else 0
            return {"valor": round(cumplimiento, 2), "completadas_a_tiempo": ordenes_completadas_a_tiempo, "planificadas": total_ordenes_planificadas}
    
    def _calcular_tasa_desperdicio(self, fecha_inicio, fecha_fin):
        desperdicios_data_res = self.registro_desperdicio_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        desperdicios_data = desperdicios_data_res.get('data', [])
        cantidad_desperdicio = sum([d.get('cantidad', 0) for d in desperdicios_data])
        
        # Lógica mejorada para calcular el material utilizado a partir de las reservas consumidas
        consumo_res = self.reserva_insumo_model.get_consumo_total_en_periodo(fecha_inicio, fecha_fin)
        cantidad_material_utilizado = 0
        if consumo_res['success']:
            cantidad_material_utilizado = consumo_res['total_consumido']

        tasa = (cantidad_desperdicio / cantidad_material_utilizado) * 100 if cantidad_material_utilizado > 0 else 0
        return {"valor": round(tasa, 2), "desperdicio": cantidad_desperdicio, "total_utilizado": cantidad_material_utilizado}

    def obtener_kpis_calidad(self, fecha_inicio, fecha_fin):
        tasa_rechazo_interno = self._calcular_tasa_rechazo_interno(fecha_inicio, fecha_fin)
        tasa_reclamos_clientes = self._calcular_tasa_reclamos_clientes(fecha_inicio, fecha_fin)
        tasa_rechazo_proveedores = self._calcular_tasa_rechazo_proveedores(fecha_inicio, fecha_fin)

        return {
            "tasa_rechazo_interno": tasa_rechazo_interno,
            "tasa_reclamos_clientes": tasa_reclamos_clientes,
            "tasa_rechazo_proveedores": tasa_rechazo_proveedores,
        }

    def _calcular_tasa_rechazo_interno(self, fecha_inicio, fecha_fin):
        rechazados = self.control_calidad_producto_model.count_by_decision_in_date_range('RECHAZADO', fecha_inicio, fecha_fin).get('count', 0)
        aprobados = self.control_calidad_producto_model.count_by_decision_in_date_range('APROBADO', fecha_inicio, fecha_fin).get('count', 0)
        inspeccionadas = rechazados + aprobados
        tasa = (rechazados / inspeccionadas) * 100 if inspeccionadas > 0 else 0
        return {"valor": round(tasa, 2), "rechazadas": rechazados, "inspeccionadas": inspeccionadas}

    def _calcular_tasa_reclamos_clientes(self, fecha_inicio, fecha_fin):
        reclamos_res = self.reclamo_model.count_in_date_range(fecha_inicio, fecha_fin)
        pedidos_entregados_res = self.pedido_model.count_by_estado_in_date_range(estados.OV_COMPLETADO, fecha_inicio, fecha_fin)

        num_reclamos = reclamos_res.get('count', 0)
        total_pedidos_entregados = pedidos_entregados_res.get('count', 0)

        tasa = (num_reclamos / total_pedidos_entregados) * 100 if total_pedidos_entregados > 0 else 0
        return {"valor": round(tasa, 2), "reclamos": num_reclamos, "pedidos_entregados": total_pedidos_entregados}

    def _calcular_tasa_rechazo_proveedores(self, fecha_inicio, fecha_fin):
        lotes_rechazados_res = self.control_calidad_insumo_model.count_by_decision_in_date_range('RECHAZADO', fecha_inicio, fecha_fin)
        lotes_recibidos_res = self.orden_compra_model.count_by_estado_in_date_range(estados.OC_RECEPCION_COMPLETA, fecha_inicio, fecha_fin)

    def _obtener_kpis_comerciales(self, fecha_inicio, fecha_fin):
        completados = self.pedido_model.count_by_estado_in_date_range('COMPLETADO', fecha_inicio, fecha_fin).get('count', 0)
        total = self.pedido_model.count_by_estados_in_date_range(['COMPLETADO', 'CANCELADO', 'COMPLETADO_TARDE'], fecha_inicio, fecha_fin).get('count', 0)
        tasa_cumplimiento = (completados / total) * 100 if total > 0 else 0

        total_valor = self.pedido_model.get_total_valor_pedidos_completados(fecha_inicio, fecha_fin).get('total_valor', 0)
        valor_promedio = total_valor / completados if completados > 0 else 0

        return {
            "cumplimiento_pedidos": {"valor": round(tasa_cumplimiento, 2), "completados": completados, "total": total},
            "valor_promedio_pedido": {"valor": round(valor_promedio, 2), "total_valor": total_valor, "num_pedidos": completados}
        }
        
    def _obtener_kpis_inventario(self, fecha_inicio, fecha_fin):
        cogs = self.reserva_insumo_model.get_consumo_total_valorizado_en_periodo(fecha_inicio, fecha_fin).get('total_consumido_valorizado', 0)
        stock_valorizado = self.insumo_inventario_model.get_stock_total_valorizado().get('total_valorizado', 0)
        rotacion = cogs / stock_valorizado if stock_valorizado else 0
        return {"rotacion_inventario": {"valor": round(rotacion, 2), "cogs": cogs, "inventario_valorizado": stock_valorizado}}

    # --- MÉTODOS PÚBLICOS PARA GRÁFICOS ---

    def obtener_top_productos_vendidos(self, fecha_inicio_str, fecha_fin_str, top_n=5):
        fecha_inicio, fecha_fin = self._parsear_fechas(fecha_inicio_str, fecha_fin_str)
        sales_res = self.pedido_model.get_sales_by_product_in_period(fecha_inicio, fecha_fin)
        if not sales_res.get('success'): return {"error": "Failed to retrieve sales data"}

        sorted_products = sorted(sales_res.get('data', {}).items(), key=lambda item: item[1], reverse=True)
        top_products = sorted_products[:top_n]
        return {"labels": [p[0] for p in top_products], "data": [p[1] for p in top_products]}

    def obtener_facturacion_por_periodo(self, fecha_inicio_str, fecha_fin_str, periodo='mensual'):
        fecha_inicio, fecha_fin = self._parsear_fechas(fecha_inicio_str, fecha_fin_str, 365)
        ingresos_res = self.pedido_model.get_ingresos_en_periodo(fecha_inicio, fecha_fin)
        if not ingresos_res.get('success'): return {"error": "Failed to retrieve income data"}
        
        # 1. Tasa de Cumplimiento de Pedidos (On-Time Full-Fillment)
        try:
            pedidos_completados_a_tiempo_res = self.pedido_model.count_completed_on_time_in_date_range(fecha_inicio, fecha_fin)
            todos_los_pedidos_res = self.pedido_model.count_by_estados_in_date_range([estados.OV_COMPLETADO, estados.OV_CANCELADA], fecha_inicio, fecha_fin)

            if pedidos_completados_a_tiempo_res['success'] and todos_los_pedidos_res['success']:
                completados_a_tiempo = pedidos_completados_a_tiempo_res['count']
                total_pedidos = todos_los_pedidos_res['count']
                tasa = (completados_a_tiempo / total_pedidos) * 100 if total_pedidos > 0 else 0
                kpis['cumplimiento_pedidos'] = {"valor": round(tasa, 2), "completados": completados_a_tiempo, "total": total_pedidos}
            else:
                kpis['cumplimiento_pedidos'] = {"valor": 0, "completados": 0, "total": 0}
        except Exception as e:
            kpis['cumplimiento_pedidos'] = {"valor": 0, "completados": 0, "total": 0}

        # 2. Valor Promedio de Pedido
        try:
            total_valor_res = self.pedido_model.get_total_valor_pedidos_completados(fecha_inicio, fecha_fin)
            num_pedidos_res = self.pedido_model.count_by_estado_in_date_range(estados.OV_COMPLETADO, fecha_inicio, fecha_fin)

        productos_data = productos_res.get('data', [])
        costos_insumos_cache = self._preparar_cache_costos_por_productos([p['id'] for p in productos_data])

        rentabilidad = {"labels": [], "costos": [], "ingresos": [], "rentabilidad_neta": []}
        for p in productos_data:
            costo = self._get_costo_producto(p['id'], costos_insumos_cache)
            precio = float(p.get('precio_unitario', 0.0))
            rentabilidad['labels'].append(p['nombre'])
            rentabilidad['costos'].append(round(costo, 2))
            rentabilidad['ingresos'].append(round(precio, 2))
            rentabilidad['rentabilidad_neta'].append(round(precio - costo, 2))
        return rentabilidad

    def obtener_costo_vs_ganancia(self, fecha_inicio_str, fecha_fin_str, periodo='mensual'):
        fecha_inicio, fecha_fin = self._parsear_fechas(fecha_inicio_str, fecha_fin_str, 365)
        facturacion_res = self.obtener_facturacion_por_periodo(fecha_inicio_str, fecha_fin_str, periodo)
        if facturacion_res.get('error'): return facturacion_res
        
        ordenes_res = self.orden_produccion_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        if not ordenes_res.get('success'): return {"error": "Could not get production orders."}
        
        ordenes_data = ordenes_res.get('data', [])
        costos_cache = self._preparar_cache_costos_por_productos([op['producto_id'] for op in ordenes_data if 'producto_id' in op])

        costos_por_periodo = defaultdict(float)
        for op in ordenes_data:
            if 'producto_id' not in op: continue
            costo_op = self._get_costo_producto(op['producto_id'], costos_cache) * float(op.get('cantidad_producida', 0))
            fecha_op = datetime.fromisoformat(op['fecha_inicio']).date()
            key = fecha_op.strftime('%Y-%m') if periodo == 'mensual' else fecha_op.strftime('%Y-W%U') if periodo == 'semanal' else fecha_op.strftime('%Y-%m-%d')
            costos_por_periodo[key] += costo_op

        labels = sorted(list(set(facturacion_res['labels']) | set(costos_por_periodo.keys())))
        ingresos_map = dict(zip(facturacion_res['labels'], facturacion_res['data']))
        return {"labels": labels, "ingresos": [ingresos_map.get(l, 0) for l in labels], "costos": [costos_por_periodo.get(l, 0) for l in labels]}

    def obtener_descomposicion_costos(self, fecha_inicio_str, fecha_fin_str):
        fecha_inicio, fecha_fin = self._parsear_fechas(fecha_inicio_str, fecha_fin_str)
        ordenes_res = self.orden_produccion_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        if not ordenes_res.get('success'): return {"error": "Could not get production orders."}
        
        ordenes_data = ordenes_res.get('data', [])
        costos_cache = self._preparar_cache_costos_por_productos([op['producto_id'] for op in ordenes_data if 'producto_id' in op])

        costo_mp = sum(self._get_costo_producto(op['producto_id'], costos_cache) * float(op.get('cantidad_producida', 0)) for op in ordenes_data if 'producto_id' in op)
        horas_prod = sum((datetime.fromisoformat(op['fecha_fin']) - datetime.fromisoformat(op['fecha_inicio'])).total_seconds() / 3600 for op in ordenes_data if op.get('fecha_fin') and op.get('fecha_inicio'))
        
        costo_mo = horas_prod * 15 # COSTO_HORA_HOMBRE
        gastos_fijos = (5000 / 30) * (fecha_fin - fecha_inicio).days # GASTOS_FIJOS_MENSUALES

        return {"labels": ["Materia Prima", "Mano de Obra (Est.)", "Gastos Fijos (Est.)"], "data": [round(costo_mp, 2), round(costo_mo, 2), round(gastos_fijos, 2)]}

    def obtener_top_clientes(self, fecha_inicio_str, fecha_fin_str, top_n=5, criterio='valor'):
        fecha_inicio, fecha_fin = self._parsear_fechas(fecha_inicio_str, fecha_fin_str, 365)
        pedidos_res = self.pedido_model.get_all_with_items(filtros={'fecha_desde': fecha_inicio.strftime('%Y-%m-%d'), 'fecha_hasta': fecha_fin.strftime('%Y-%m-%d'), 'estado': 'COMPLETADO'})
        if not pedidos_res.get('success'): return {"error": "Could not get orders."}

        clientes_data = defaultdict(lambda: {'valor': 0, 'cantidad': 0, 'nombre': 'N/A'})
        for pedido in pedidos_res.get('data', []):
            if not (cid := pedido.get('id_cliente')): continue
            c_nombre = pedido.get('cliente', {}).get('nombre') or f"Cliente ID {cid}"
            clientes_data[cid]['valor'] += float(pedido.get('monto_total', 0))
            clientes_data[cid]['cantidad'] += 1
            clientes_data[cid]['nombre'] = c_nombre
        
        sorted_clientes = sorted(clientes_data.values(), key=lambda x: x[criterio], reverse=True)
        top = sorted_clientes[:top_n]
        return {"labels": [c['nombre'] for c in top], "data": [c[criterio] for c in top]}

    def obtener_causas_desperdicio_pareto(self, fecha_inicio_str, fecha_fin_str):
        fecha_inicio, fecha_fin = self._parsear_fechas(fecha_inicio_str, fecha_fin_str)
        desperdicios_res = self.registro_desperdicio_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        if not desperdicios_res.get('success'): return {"error": "Could not get waste records."}

        causas = defaultdict(float)
        for d in desperdicios_res.get('data', []):
            motivo = d.get('motivo', {}).get('motivo', 'Desconocido') if isinstance(d.get('motivo'), dict) else 'Desconocido'
            causas[motivo] += float(d.get('cantidad', 0))

        sorted_causas = sorted(causas.items(), key=lambda x: x[1], reverse=True)
        labels, data = [c[0] for c in sorted_causas], [c[1] for c in sorted_causas]
        
        total = sum(data)
        acum_porc = []
        acum = 0
        for val in data:
            acum += val
            acum_porc.append((acum / total) * 100 if total > 0 else 0)

        return {"labels": labels, "data": data, "line_data": [round(p, 2) for p in acum_porc]}

    def obtener_antiguedad_stock(self, tipo='insumo'):
        hoy = datetime.now().date()
        categorias = {"0-30 días": 0.0, "31-60 días": 0.0, "61-90 días": 0.0, "+90 días": 0.0}

        if tipo == 'insumo':
            lotes_res = self.insumo_inventario_model.get_all_lotes_for_view()
            if not lotes_res.get('success'): return {"error": "Could not get raw material lots."}
            for lote in lotes_res.get('data', []):
                if not (fecha_str := lote.get('fecha_ingreso')): continue
                antiguedad = (hoy - datetime.fromisoformat(fecha_str).date()).days
                valor = float(lote.get('precio_unitario') or 0.0) * float(lote.get('cantidad', 0))
                if 0 <= antiguedad <= 30: categorias["0-30 días"] += valor
                elif 31 <= antiguedad <= 60: categorias["31-60 días"] += valor
                elif 61 <= antiguedad <= 90: categorias["61-90 días"] += valor
                else: categorias["+90 días"] += valor
        else: # producto
            lotes_res = self.lote_producto_model.get_all_lotes_for_antiquity_view()
            if not lotes_res.get('success'): return {"error": "Could not get product lots."}
            lotes_data = lotes_res.get('data', [])
            
        return kpis
