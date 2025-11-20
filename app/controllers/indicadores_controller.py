from datetime import datetime, timedelta, date
from app.models.orden_produccion import OrdenProduccionModel
from app.models.control_calidad_producto import ControlCalidadProductoModel
from app.models.registro_desperdicio_lote_producto_model import RegistroDesperdicioLoteProductoModel
from app.models.registro_desperdicio_model import RegistroDesperdicioModel
from app.models.receta import RecetaModel
from app.models.registro_paro_model import RegistroParoModel
from app.models.bloqueo_capacidad_model import BloqueoCapacidadModel
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
# Faltaba importar defaultdict
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)

class IndicadoresController:
    def __init__(self):
        self.orden_produccion_model = OrdenProduccionModel()
        self.control_calidad_producto_model = ControlCalidadProductoModel()
        self.registro_desperdicio_model = RegistroDesperdicioLoteProductoModel()
        self.registro_desperdicio_insumo_model = RegistroDesperdicioModel()
        self.receta_model = RecetaModel()
        self.registro_paro_model = RegistroParoModel()
        self.bloqueo_capacidad_model = BloqueoCapacidadModel()
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

    def _parsear_periodo(self, semana=None, mes=None, ano=None):
        hoy = datetime.now()
        if semana: # formato "2024-W48"
            year, week_num = map(int, semana.split('-W'))
            fecha_inicio = datetime.fromisocalendar(year, week_num, 1)
            fecha_fin = fecha_inicio + timedelta(days=6)
        elif mes: # formato "2024-11"
            year, month = map(int, mes.split('-'))
            fecha_inicio = datetime(year, month, 1)
            next_month = (fecha_inicio.replace(day=28) + timedelta(days=4))
            fecha_fin = next_month - timedelta(days=next_month.day)
        elif ano: # formato "2024"
            year = int(ano)
            fecha_inicio = datetime(year, 1, 1)
            fecha_fin = datetime(year, 12, 31)
        else: # Por defecto, semana actual
            fecha_inicio = hoy - timedelta(days=hoy.weekday())
            fecha_fin = fecha_inicio + timedelta(days=6)
        return fecha_inicio.date(), fecha_fin.date()
    
    def obtener_anos_disponibles(self):
        """Obtiene los años únicos en los que se registraron pedidos."""
        return self.pedido_model.obtener_anos_distintos()

    # --- CATEGORÍA: PRODUCCIÓN ---
    def obtener_datos_produccion(self, semana=None, mes=None, ano=None):
        """
        Esta función está reservada para KPIs puramente de producción.
        La lógica de inventario que estaba aquí fue movida a su propia categoría.
        """
        return {}

    def obtener_kpis_produccion(self, semana=None, mes=None, ano=None):
        fecha_inicio, fecha_fin = self._parsear_periodo(semana, mes, ano)
        
        # Determinar contexto para la evolución
        contexto = 'mes' # Default
        if semana: contexto = 'semana'
        elif mes: contexto = 'mes'
        elif ano: contexto = 'ano'

        # --- Métodos de apoyo para fechas fijas ---
        hoy_dt = datetime.now()
        inicio_semana_dt = hoy_dt - timedelta(days=hoy_dt.weekday())
        inicio_semana_actual = inicio_semana_dt.date()
        
        inicio_mes_dt = hoy_dt.replace(day=1)
        inicio_mes_actual = inicio_mes_dt.date()
        
        next_month = inicio_mes_dt.replace(day=28) + timedelta(days=4)
        fin_mes_dt = next_month - timedelta(days=next_month.day)
        fin_mes_actual = fin_mes_dt.date()

        panorama_estados = self._obtener_panorama_estados(inicio_semana_actual)
        ranking_desperdicios = self._obtener_ranking_desperdicios(inicio_mes_actual, fin_mes_actual)
        
        # Pasar el contexto y rango dinámico a la evolución
        evolucion_desperdicios = self._obtener_evolucion_desperdicios(fecha_inicio, fecha_fin, contexto)
        
        velocidad_produccion = self._obtener_velocidad_produccion(inicio_mes_actual, fin_mes_actual)
        oee = self._calcular_oee(fecha_inicio, fecha_fin)
        cumplimiento_plan = self._calcular_cumplimiento_plan(fecha_inicio, fecha_fin)

        return {
            "panorama_estados": panorama_estados,
            "ranking_desperdicios": ranking_desperdicios,
            "evolucion_desperdicios": evolucion_desperdicios,
            "velocidad_produccion": velocidad_produccion,
            "oee": oee if isinstance(oee, dict) else {"valor": 0, "disponibilidad": 0, "rendimiento": 0, "calidad": 0},
            "cumplimiento_plan": cumplimiento_plan
        }

    # --- IMPLEMENTACIÓN NUEVOS MÉTODOS PRIVADOS ---

    def _obtener_panorama_estados(self, inicio_semana):
        """
        Obtiene el conteo de órdenes por estado.
        Criterio: Todas las activas (independiente de fecha) + Completadas esta semana.
        """
        estados_activos = [
            'EN ESPERA', 'EN_LINEA_1', 'EN_LINEA_2', 'EN_EMPAQUETADO', 'LISTA PARA PRODUCIR', 'EN_EMPAQUETADO', 
            'EN_PROCESO', 'CONTROL_DE_CALIDAD', 'PAUSADA'
        ]
        
        # 1. Activas
        res_activas = self.orden_produccion_model.find_all(filters={'estado': estados_activos})
        data_activas = res_activas.get('data', []) if res_activas.get('success') else []
        
        # 2. Completadas esta semana
        res_completadas = self.orden_produccion_model.find_all(filters={
            'estado': 'COMPLETADA',
            'fecha_fin_gte': inicio_semana.isoformat() 
        })
        data_completadas = res_completadas.get('data', []) if res_completadas.get('success') else []

        # Consolidar y contar
        conteo_estados = Counter()
        conteo_lineas = Counter()
        total = 0
        
        ids_procesados = set()

        for op in data_activas + data_completadas:
            if op['id'] in ids_procesados: continue
            ids_procesados.add(op['id'])
            
            estado_raw = op.get('estado', 'Desconocido')
            estado_fmt = estado_raw.replace('_', ' ')
            conteo_estados[estado_fmt] += 1
            
            # Conteo para líneas
            if estado_raw == 'EN_LINEA_1':
                conteo_lineas['Línea 1'] += 1
            elif estado_raw == 'EN_LINEA_2':
                conteo_lineas['Línea 2'] += 1
                
            total += 1

        en_proceso = conteo_estados.get('EN PROCESO', 0) + conteo_estados.get('EN LINEA 1', 0) + conteo_estados.get('EN LINEA 2', 0)
        insight = f"Actualmente hay {en_proceso} órdenes en piso de producción y un total de {total} órdenes activas o finalizadas recientemente."
        
        return {
            "states_data": [{"name": k, "value": v} for k, v in conteo_estados.items()],
            "lines_data": [{"name": k, "value": v} for k, v in conteo_lineas.items()],
            "total": total,
            "insight": insight,
            "tooltip": "Distribución de órdenes activas (En Espera, Líneas, Calidad) y completadas esta semana."
        }

    def _obtener_ranking_desperdicios(self, fecha_inicio, fecha_fin):
        """
        Top 5 motivos de desperdicio más frecuentes en el periodo (count).
        Combina desperdicios de productos y desperdicios de insumos.
        """
        # 1. Desperdicio de Productos
        res_prod = self.registro_desperdicio_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_prod = res_prod.get('data', []) if res_prod.get('success') else []

        # 2. Desperdicio de Insumos (Nuevo)
        res_insumo = self.registro_desperdicio_insumo_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_insumo = res_insumo.get('data', []) if res_insumo.get('success') else []
        
        conteo = Counter()
        
        # Procesar Productos
        for d in data_prod:
            # Motivo en 'motivo' dict o string
            if isinstance(d.get('motivo'), dict):
                motivo = d.get('motivo', {}).get('motivo', 'Sin motivo') 
            else:
                motivo = 'Sin motivo'
            conteo[motivo] += 1 
            
        # Procesar Insumos (campo 'motivo_desperdicio' -> 'descripcion')
        for d in data_insumo:
            if isinstance(d.get('motivo_desperdicio'), dict):
                motivo = d.get('motivo_desperdicio', {}).get('descripcion', 'Sin motivo')
            else:
                 # Fallback si no hay join o estructura diferente
                motivo = 'Sin motivo (Insumo)'
            conteo[motivo] += 1

        top_5 = conteo.most_common(5)
        total_incidentes = len(data_prod) + len(data_insumo)
        
        if top_5:
            top_motivo = top_5[0][0]
            porcentaje = (top_5[0][1] / total_incidentes * 100) if total_incidentes > 0 else 0
            insight = f"El motivo principal de las mermas ha sido '{top_motivo}', representando el {porcentaje:.0f}% del total de incidencias registradas en el periodo."
        else:
            insight = "No se han registrado incidentes de desperdicio significativos durante este mes."

        top_5_inv = top_5[::-1]

        # --- Lógica Dinámica (Pie vs Bar) ---
        chart_type = 'pie' if len(top_5) <= 6 else 'bar'
        
        return {
            "categories": [x[0] for x in top_5_inv],
            "values": [x[1] for x in top_5_inv],
            "insight": insight,
            "tooltip": "Los motivos más recurrentes por cantidad de incidentes (frecuencia).",
            "chart_type": chart_type
        }

    def _obtener_evolucion_desperdicios(self, fecha_inicio, fecha_fin, contexto='mes'):
        """
        Evolución dinámica basada en el costo ($) del desperdicio en el periodo seleccionado.
        """
        # Ampliar rango para asegurar datos en bordes si es necesario
        res_prod = self.registro_desperdicio_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_prod = res_prod.get('data', []) if res_prod.get('success') else []

        res_insumo = self.registro_desperdicio_insumo_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_insumo = res_insumo.get('data', []) if res_insumo.get('success') else []
        
        # --- Obtener Costos para Valorización ---
        
        # 1. Costos de Lotes de Producto
        lote_prod_ids = list(set(d['lote_producto_id'] for d in data_prod if d.get('lote_producto_id')))
        mapa_costos_producto = {}
        if lote_prod_ids:
            lotes_res = self.lote_producto_model.find_all(filters={'id_lote': lote_prod_ids})
            lotes_data = lotes_res.get('data', []) if lotes_res.get('success') else []
            
            # Obtener Recetas para calcular costo estándar
            prod_ids_para_costo = list(set(l['producto_id'] for l in lotes_data if l.get('producto_id')))
            costos_receta_cache = {} # producto_id -> costo
            
            # Obtener Precios de Productos
            precios_producto_cache = {} # producto_id -> precio_unitario
            if prod_ids_para_costo:
                 productos_res = self.producto_model.find_all(filters={'id': prod_ids_para_costo})
                 if productos_res.get('success'):
                     for p in productos_res.get('data', []):
                         precios_producto_cache[p['id']] = float(p.get('precio_unitario') or 0)

            # Pre-calcular costos de receta
            for pid in prod_ids_para_costo:
                costos_receta_cache[pid] = self.receta_model.get_costo_produccion(pid)
            
            for lote in lotes_data:
                # Prioridad: Costo estimado en lote > Precio Producto > Costo estándar de receta
                costo = float(lote.get('costo_unitario_estimado') or 0)
                producto_id = lote.get('producto_id')

                if costo == 0 and producto_id:
                     # Intentar usar precio de venta del producto como aproximación si no hay costo
                     if producto_id in precios_producto_cache and precios_producto_cache[producto_id] > 0:
                         costo = precios_producto_cache[producto_id]
                     # Fallback a costo de receta
                     elif producto_id in costos_receta_cache:
                         costo = float(costos_receta_cache[producto_id])
                         
                mapa_costos_producto[lote['id_lote']] = costo

        # 2. Costos de Insumos
        insumo_ids = list(set(d['insumo_id'] for d in data_insumo if d.get('insumo_id')))
        mapa_costos_insumo = {}
        if insumo_ids:
            insumos_res = self.insumo_model.find_all(filters={'id_insumo': insumo_ids})
            insumos_data = insumos_res.get('data', []) if insumos_res.get('success') else []
            for ins in insumos_data:
                mapa_costos_insumo[ins['id_insumo']] = float(ins.get('precio_unitario') or 0)


        data_agregada = defaultdict(float)
        labels_ordenados = []
        
        # Definir formato de buckets
        bucket_format = "%Y-%m-%d"
        label_format = "%d/%m"
        delta = timedelta(days=1)
        
        if contexto == 'ano':
            bucket_format = "%Y-%m"
            label_format = "%b %Y" # Ene 2024
            # Iterar por meses
            current = fecha_inicio.replace(day=1)
            while current <= fecha_fin:
                key = current.strftime(bucket_format)
                labels_ordenados.append(key)
                data_agregada[key] = 0.0
                # Avanzar mes
                next_month = current.replace(day=28) + timedelta(days=4)
                current = next_month - timedelta(days=next_month.day - 1)
        else:
            # Iterar por días (semana o mes)
            current = fecha_inicio
            while current <= fecha_fin: 
                key = current.strftime(bucket_format)
                labels_ordenados.append(key)
                data_agregada[key] = 0.0
                current += delta

        def procesar_lista(lista_datos, fecha_key, tipo='producto'):
            for d in lista_datos:
                fecha_raw = d.get(fecha_key)
                if not fecha_raw: continue
                try:
                    dt = datetime.fromisoformat(fecha_raw)
                except ValueError:
                    try:
                        dt = datetime.strptime(fecha_raw[:10], "%Y-%m-%d")
                    except:
                        continue
                
                key = dt.strftime(bucket_format)
                
                # Calcular Costo del registro
                cantidad = float(d.get('cantidad') or 0)
                costo_unitario = 0.0
                
                if tipo == 'producto':
                    lote_id = d.get('lote_producto_id')
                    costo_unitario = mapa_costos_producto.get(lote_id, 0.0)
                else: # insumo
                    insumo_id = d.get('insumo_id')
                    costo_unitario = mapa_costos_insumo.get(insumo_id, 0.0)
                
                valor_desperdicio = cantidad * costo_unitario

                if key in data_agregada:
                    data_agregada[key] += valor_desperdicio
                elif contexto == 'ano': 
                     if key in data_agregada: 
                         data_agregada[key] += valor_desperdicio

        procesar_lista(data_prod, 'created_at', 'producto')
        procesar_lista(data_insumo, 'fecha_registro', 'insumo')

        valores = [round(data_agregada[k], 2) for k in labels_ordenados]
        
        # Formatear etiquetas para el frontend
        labels_display = []
        for k in labels_ordenados:
             if contexto == 'ano':
                 dt = datetime.strptime(k, "%Y-%m")
                 labels_display.append(dt.strftime("%b")) 
             else:
                 dt = datetime.strptime(k, "%Y-%m-%d")
                 labels_display.append(dt.strftime("%d/%m"))

        promedio = sum(valores) / len(valores) if valores else 0
        ultimo_valor = valores[-1] if valores else 0
        trend_text = "estable"
        if ultimo_valor > promedio * 1.1: trend_text = "al alza"
        elif ultimo_valor < promedio * 0.9: trend_text = "a la baja"
            
        insight = f"El costo del desperdicio se muestra {trend_text} comparado con el promedio del periodo (${promedio:,.2f} / periodo)."

        return {
            "categories": labels_display,
            "values": valores,
            "insight": insight,
            "tooltip": "Valor monetario total ($) de los desperdicios de insumos y productos registrados."
        }

    def _obtener_velocidad_produccion(self, fecha_inicio, fecha_fin):
        """
        Tiempo promedio de ciclo (Cycle Time) para órdenes completadas en el periodo.
        """
        res = self.orden_produccion_model.find_all(filters={
            'estado': 'COMPLETADA',
            'fecha_fin_gte': fecha_inicio.isoformat(),
            'fecha_fin_lte': fecha_fin.isoformat()
        })
        data = res.get('data', []) if res.get('success') else []
        
        tiempos = []
        for op in data:
            if op.get('fecha_inicio') and op.get('fecha_fin'):
                inicio = datetime.fromisoformat(op['fecha_inicio'])
                fin = datetime.fromisoformat(op['fecha_fin'])
                delta_horas = (fin - inicio).total_seconds() / 3600
                tiempos.append(delta_horas)
                
        promedio = sum(tiempos) / len(tiempos) if tiempos else 0
        
        insight = f"Se completaron {len(tiempos)} órdenes este mes, con un tiempo promedio de ejecución estable."
        
        return {
            "valor": round(promedio, 1),
            "unidad": "Horas",
            "insight": insight,
            "tooltip": "Tiempo promedio que toma completar una orden desde su inicio real hasta su fin."
        }

    # --- CATEGORÍA: CALIDAD ---
    def obtener_datos_calidad(self, semana=None, mes=None, ano=None):
        fecha_inicio, fecha_fin = self._parsear_periodo(semana, mes, ano)
        
        rechazo_interno = self._calcular_tasa_rechazo_interno(fecha_inicio, fecha_fin)
        reclamos_clientes = self._calcular_tasa_reclamos_clientes(fecha_inicio, fecha_fin)
        rechazo_proveedores = self._calcular_tasa_rechazo_proveedores(fecha_inicio, fecha_fin)
        
        # Se retorna una estructura defensiva que coincide con el frontend
        return {
            "tasa_rechazo_interno": rechazo_interno if isinstance(rechazo_interno, dict) else {"valor": 0, "rechazadas": 0, "inspeccionadas": 0},
            "tasa_reclamos_clientes": reclamos_clientes if isinstance(reclamos_clientes, dict) else {"valor": 0, "reclamos": 0, "pedidos_entregados": 0},
            "tasa_rechazo_proveedores": rechazo_proveedores if isinstance(rechazo_proveedores, dict) else {"valor": 0, "rechazados": 0, "recibidos": 0},
        }

    # --- CATEGORÍA: COMERCIAL ---
    def obtener_datos_comercial(self, semana=None, mes=None, ano=None):
        fecha_inicio, fecha_fin = self._parsear_periodo(semana, mes, ano)
        fecha_inicio_str = fecha_inicio.strftime('%Y-%m-%d')
        fecha_fin_str = fecha_fin.strftime('%Y-%m-%d')
        
        # --- 1. CÁLCULO DE KPIs PARA TARJETAS ---
        kpis_data = self._obtener_kpis_comerciales(fecha_inicio, fecha_fin)

        # --- 2. CÁLCULO DE DATOS PARA GRÁFICOS ---
        top_productos = self.obtener_top_productos_vendidos(fecha_inicio_str, fecha_fin_str)
        top_clientes = self.obtener_top_clientes(fecha_inicio_str, fecha_fin_str)

        # --- 3. COMBINAR AMBAS ESTRUCTURAS ---
        # Aseguramos que la estructura de KPIs sea la que espera el template
        return {
            "kpis_comerciales": {
                "cumplimiento_pedidos": kpis_data.get("cumplimiento_pedidos", {"valor": 0, "completados": 0, "total": 0}),
                "valor_promedio_pedido": kpis_data.get("valor_promedio_pedido", {"valor": 0, "num_pedidos": 0})
            },
            "top_productos_vendidos": top_productos if isinstance(top_productos, dict) else {"labels": [], "data": []},
            "top_clientes": top_clientes if isinstance(top_clientes, dict) else {"labels": [], "data": []},
        }

    # --- CATEGORÍA: FINANCIERA ---
    def obtener_datos_financieros(self, semana=None, mes=None, ano=None):
        fecha_inicio, fecha_fin = self._parsear_periodo(semana, mes, ano)
        fecha_inicio_str = fecha_inicio.strftime('%Y-%m-%d')
        fecha_fin_str = fecha_fin.strftime('%Y-%m-%d')
        
        # --- 1. CÁLCULO DE KPIs PARA TARJETAS ---
        total_valor_res = self.pedido_model.get_total_valor_pedidos_completados(fecha_inicio, fecha_fin)
        facturacion_total = total_valor_res.get('total_valor', 0.0) if total_valor_res.get('success') else 0.0

        ordenes_res = self.orden_produccion_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        costo_total = 0.0
        if ordenes_res.get('success'):
            ordenes_data = ordenes_res.get('data', [])
            producto_ids_en_ordenes = [op['producto_id'] for op in ordenes_data if op.get('producto_id')]
            costos_cache = self._preparar_cache_costos_por_productos(list(set(producto_ids_en_ordenes)))
            
            costo_mp = sum(self._get_costo_producto(op['producto_id'], costos_cache) * float(op.get('cantidad_producida', 0)) for op in ordenes_data if op.get('producto_id'))
            horas_prod = sum((datetime.fromisoformat(op['fecha_fin']) - datetime.fromisoformat(op['fecha_inicio'])).total_seconds() / 3600 for op in ordenes_data if op.get('fecha_fin') and op.get('fecha_inicio'))
            costo_mo = horas_prod * 15
            dias_periodo = max((fecha_fin - fecha_inicio).days, 1)
            gastos_fijos = (5000 / 30) * dias_periodo
            costo_total = costo_mp + costo_mo + gastos_fijos

        beneficio_bruto = facturacion_total - costo_total
        margen_beneficio = (beneficio_bruto / facturacion_total) * 100 if facturacion_total > 0 else 0
        
        kpis = {
            "facturacion_total": {"valor": round(facturacion_total, 2), "etiqueta": "Facturación Total"},
            "costo_total": {"valor": round(costo_total, 2), "etiqueta": "Costo de Ventas"},
            "beneficio_bruto": {"valor": round(beneficio_bruto, 2), "etiqueta": "Beneficio Bruto"},
            "margen_beneficio": {"valor": round(margen_beneficio, 2), "etiqueta": "Margen de Beneficio (%)"}
        }

        # --- 2. CÁLCULO DE DATOS PARA GRÁFICOS ---
        facturacion = self.obtener_facturacion_por_periodo(fecha_inicio_str, fecha_fin_str)
        costo_ganancia = self.obtener_costo_vs_ganancia(fecha_inicio_str, fecha_fin_str)
        rentabilidad = self.obtener_rentabilidad_productos(fecha_inicio_str, fecha_fin_str)
        descomposicion = self.obtener_descomposicion_costos(fecha_inicio_str, fecha_fin_str)

        # --- 3. COMBINAR AMBAS ESTRUCTURAS ---
        return {
            "kpis_financieros": kpis,
            "facturacion_periodo": facturacion if isinstance(facturacion, dict) else {"labels": [], "data": []},
            "costo_vs_ganancia": costo_ganancia if isinstance(costo_ganancia, dict) else {"labels": [], "ingresos": [], "costos": []},
            "rentabilidad_productos": rentabilidad if isinstance(rentabilidad, dict) else {"labels": [], "costos": [], "ingresos": [], "rentabilidad_neta": []},
            "descomposicion_costos": descomposicion if isinstance(descomposicion, dict) else {"labels": [], "data": []},
        }
        
    # --- CATEGORÍA: INVENTARIO ---
    def obtener_datos_inventario(self, semana=None, mes=None, ano=None): # Periodo se ignora aquí
        # Para la rotación, usamos un período fijo (ej. último año) para que sea consistente
        hoy = datetime.now()
        fecha_inicio = hoy - timedelta(days=365)
        fecha_fin = hoy
        
        rotacion = self._calcular_rotacion_inventario(fecha_inicio, fecha_fin)
        cobertura = self._calcular_cobertura_stock()
        antiguedad_insumos = self.obtener_antiguedad_stock('insumo')
        antiguedad_productos = self.obtener_antiguedad_stock('producto')

        kpis_inventario = {
            "rotacion_inventario": rotacion if isinstance(rotacion, dict) else {"valor": 0, "cogs": 0, "inventario_valorizado": 0}
        }

        # Se retorna una estructura defensiva que coincide con el frontend
        return {
            "kpis_inventario": kpis_inventario,
            "cobertura_stock": cobertura if isinstance(cobertura, dict) else {"valor": 0, "insumo_nombre": "N/A", "stock": 0, "consumo_diario": 0},
            "antiguedad_stock_insumos": antiguedad_insumos if isinstance(antiguedad_insumos, dict) else {"labels": [], "data": []},
            "antiguedad_stock_productos": antiguedad_productos if isinstance(antiguedad_productos, dict) else {"labels": [], "data": []},
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
    
    # --- MÉTODO _calcular_carga_op FALTANTE ---
    # Asumo que existe o deberías agregarlo si _calcular_oee lo necesita
    def _calcular_carga_op(self, orden_produccion_data):
        # Esta es una implementación de EJEMPLO. 
        # Deberías tener la lógica real de esta función.
        # Basado en la optimización, probablemente ya no uses este método
        # y deberías quitar la llamada en _calcular_oee.
        receta_id = orden_produccion_data.get('receta_id')
        cantidad = Decimal(orden_produccion_data.get('cantidad_planificada', 0))
        if not receta_id:
            return Decimal(0)
        
        operaciones_res = self.receta_model.get_operaciones(receta_id)
        if not operaciones_res.get('success'):
            return Decimal(0)
            
        carga_total = Decimal(0)
        for op_step in operaciones_res.get('data', []):
            t_prep = Decimal(op_step.get('tiempo_preparacion', 0))
            t_ejec_unit = Decimal(op_step.get('tiempo_ejecucion_unitario', 0))
            carga_total += t_prep + (t_ejec_unit * cantidad)
        return carga_total
    # --- FIN MÉTODO FALTANTE ---


    def _calcular_oee(self, fecha_inicio, fecha_fin):
        ordenes_res = self.orden_produccion_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        ordenes_en_periodo = ordenes_res.get('data', [])
        if not ordenes_en_periodo:
            return {"valor": 0, "disponibilidad": 0, "rendimiento": 0, "calidad": 0}

        # 1. Tiempo de Producción Real (Tiempo de Carga)
        tiempo_produccion_real = sum(
            (datetime.fromisoformat(op['fecha_fin']) - datetime.fromisoformat(op['fecha_inicio'])).total_seconds()
            for op in ordenes_en_periodo if op.get('fecha_fin') and op.get('fecha_inicio')
        )

        # 2. Tiempo de Paradas
        # Paradas de operario
        paros_operario_res = self.registro_paro_model.find_all(filters={
            'fecha_inicio_gte': fecha_inicio.isoformat(), 
            'fecha_inicio_lte': fecha_fin.isoformat()
        })
        tiempo_paradas_operario = 0
        if paros_operario_res.get('success'):
            for paro in paros_operario_res.get('data', []):
                if paro.get('fecha_fin') and paro.get('fecha_inicio'):
                    tiempo_paradas_operario += (datetime.fromisoformat(paro['fecha_fin']) - datetime.fromisoformat(paro['fecha_inicio'])).total_seconds()
        
        # Bloqueos de línea/capacidad
        bloqueos_linea_res = self.bloqueo_capacidad_model.find_all(filters={
            'fecha_gte': fecha_inicio.isoformat(), 
            'fecha_lte': fecha_fin.isoformat()
        })
        tiempo_paradas_linea_minutos = 0
        if bloqueos_linea_res.get('success'):
            tiempo_paradas_linea_minutos = sum(b.get('minutos_bloqueados', 0) for b in bloqueos_linea_res.get('data', []))
        
        tiempo_paradas_total = tiempo_paradas_operario + (tiempo_paradas_linea_minutos * 60)

        # 3. Tiempo Operativo
        tiempo_operativo = tiempo_produccion_real - tiempo_paradas_total

        # 4. Tiempo Estándar (Ideal)
        receta_ids = [op['receta_id'] for op in ordenes_en_periodo if op.get('receta_id')]
        cache_operaciones = self._preparar_cache_operaciones(receta_ids)
        tiempo_produccion_planificado = sum(
            self._calcular_carga_op_con_cache(op, cache_operaciones) for op in ordenes_en_periodo
        ) * 60  # a segundos

        # 5. Cálculo de Componentes OEE
        # Disponibilidad = Tiempo Operando / Tiempo Total Disponible
        disponibilidad = tiempo_operativo / tiempo_produccion_real if tiempo_produccion_real > 0 else 0

        # Rendimiento = Tiempo Teórico / Tiempo que estuvo operando
        rendimiento = float(tiempo_produccion_planificado) / tiempo_operativo if tiempo_operativo > 0 else 0

        # Calidad = Unidades Buenas / Total de Unidades Producidas
        produccion_real = sum(op.get('cantidad_producida', 0) for op in ordenes_en_periodo)
        unidades_buenas_res = self.control_calidad_producto_model.get_total_unidades_aprobadas_en_periodo(fecha_inicio, fecha_fin)
        unidades_buenas = unidades_buenas_res.get('total_unidades', 0) if unidades_buenas_res.get('success') else 0
        
        calidad = unidades_buenas / produccion_real if produccion_real > 0 else 0

        # 6. Cálculo Final OEE
        oee = disponibilidad * rendimiento * calidad * 100
        
        return {
            "valor": round(oee, 2),
            "disponibilidad": round(disponibilidad, 2),
            "rendimiento": round(rendimiento, 2),
            "calidad": round(calidad, 2)
        }
        
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

        costos_calculados = {}
        if all_insumo_ids:
            costos_res = self.insumo_inventario_model.get_costos_promedio_ponderado_bulk(list(all_insumo_ids))
            if costos_res and costos_res.get('success'):
                costos_calculados = costos_res.get('data', {})

        insumos_sin_costo = all_insumo_ids - set(costos_calculados.keys())
        if insumos_sin_costo:
            fallback_res = self.insumo_model.find_all(filters={'id_insumo': list(insumos_sin_costo)})
            if fallback_res and fallback_res.get('success'):
                for insumo in fallback_res.get('data', []):
                    costos_calculados[insumo['id_insumo']] = float(insumo.get('precio_unitario', 0.0))
                    logging.info(f"Usando precio de catálogo como fallback para costo de insumo: {insumo['id_insumo']}")

        return costos_calculados

    def _get_costo_producto(self, producto_id, costos_insumos_cache=None):
        return self.receta_model.get_costo_produccion(producto_id, costos_insumos=costos_insumos_cache)

    def _calcular_cumplimiento_plan(self, fecha_inicio, fecha_fin):
            # CORRECCIÓN: Filtrar por fecha_meta para obtener las órdenes que debían completarse en el período.
            filtros = {
                'fecha_meta_desde': fecha_inicio.isoformat(),
                'fecha_meta_hasta': fecha_fin.isoformat()
            }
            ordenes_planificadas_res = self.orden_produccion_model.get_all_enriched(filtros=filtros)
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

    # --- CORRECCIÓN 2: Función completada ---
    def _calcular_tasa_rechazo_proveedores(self, fecha_inicio, fecha_fin):
        lotes_rechazados_res = self.control_calidad_insumo_model.count_by_decision_in_date_range('RECHAZADO', fecha_inicio, fecha_fin)
        lotes_recibidos_res = self.orden_compra_model.count_by_estado_in_date_range(estados.OC_RECEPCION_COMPLETA, fecha_inicio, fecha_fin)
        
        lotes_rechazados = lotes_rechazados_res.get('count', 0)
        lotes_recibidos = lotes_recibidos_res.get('count', 0)

        tasa = (lotes_rechazados / lotes_recibidos) * 100 if lotes_recibidos > 0 else 0
        return {"valor": round(tasa, 2), "rechazados": lotes_rechazados, "recibidos": lotes_recibidos}


    def _obtener_kpis_comerciales(self, fecha_inicio, fecha_fin):
        # 1. Cumplimiento de Pedidos
        # CORRECCIÓN: Usar el método correcto 'count_by_estados_in_date_range' para el total
        estados_totales = [
            estados.OV_PENDIENTE, estados.OV_EN_PROCESO, estados.OV_LISTO_PARA_ENTREGA,
            estados.OV_COMPLETADO, estados.OV_CANCELADA
        ]
        total_pedidos_res = self.pedido_model.count_by_estados_in_date_range(estados_totales, fecha_inicio, fecha_fin)
        completados_res = self.pedido_model.count_by_estado_in_date_range(estados.OV_COMPLETADO, fecha_inicio, fecha_fin)
        
        total_pedidos = total_pedidos_res.get('count', 0)
        num_pedidos_completados = completados_res.get('count', 0)
        
        cumplimiento_pedidos = (num_pedidos_completados / total_pedidos) * 100 if total_pedidos > 0 else 0

        # 2. Valor Promedio de Pedido
        total_valor_res = self.pedido_model.get_total_valor_pedidos_completados(fecha_inicio, fecha_fin)
        total_valor = total_valor_res.get('total_valor', 0.0)
        
        valor_promedio = total_valor / num_pedidos_completados if num_pedidos_completados > 0 else 0.0

        return {
            "cumplimiento_pedidos": {"valor": round(cumplimiento_pedidos, 2), "completados": num_pedidos_completados, "total": total_pedidos},
            "valor_promedio_pedido": {"valor": round(valor_promedio, 2), "num_pedidos": num_pedidos_completados}
        }

    def _calcular_rotacion_inventario(self, fecha_inicio, fecha_fin):
        try:
            cogs_res = self.reserva_insumo_model.get_consumo_total_valorizado_en_periodo(fecha_inicio, fecha_fin)
            stock_valorizado_res = self.insumo_inventario_model.get_stock_total_valorizado()

            if cogs_res['success'] and stock_valorizado_res['success']:
                cogs = cogs_res.get('total_consumido_valorizado', 0)
                inventario_promedio = stock_valorizado_res.get('total_valorizado', 0)
                
                rotacion = cogs / inventario_promedio if inventario_promedio else 0
                return {"valor": round(rotacion, 2), "cogs": cogs, "inventario_valorizado": inventario_promedio}
            return {"valor": 0, "cogs": 0, "inventario_valorizado": 0}
        except Exception:
            return {"valor": 0, "cogs": 0, "inventario_valorizado": 0}

    def _calcular_cobertura_stock(self):
        try:
            insumos_res = self.insumo_model.find_all()
            if not (insumos_res['success'] and insumos_res['data']):
                return {"valor": 0, "insumo_nombre": "N/A", "stock": 0, "consumo_diario": 0}

            total_stock_valorizado = 0
            total_consumo_diario_valorizado = 0

            for insumo in insumos_res['data']:
                id_insumo = insumo['id_insumo']
                precio_unitario = insumo.get('precio_unitario', 0)

                stock_res = self.insumo_inventario_model.get_stock_actual_por_insumo(id_insumo)
                consumo_res = self.reserva_insumo_model.get_consumo_promedio_diario_por_insumo(id_insumo)

                if stock_res['success'] and consumo_res['success']:
                    stock_actual = stock_res.get('stock_actual', 0)
                    consumo_diario = consumo_res.get('consumo_promedio_diario', 0)
                    total_stock_valorizado += stock_actual * precio_unitario
                    total_consumo_diario_valorizado += consumo_diario * precio_unitario
            
            cobertura_promedio = (total_stock_valorizado / total_consumo_diario_valorizado 
                                  if total_consumo_diario_valorizado > 0 else float('inf'))

            return {
                "valor": round(cobertura_promedio, 2) if cobertura_promedio != float('inf') else 'inf',
                "insumo_nombre": "Todos los insumos",
                "stock": round(total_stock_valorizado, 2),
                "consumo_diario": round(total_consumo_diario_valorizado, 2)
            }
        except Exception:
            return {"valor": 0, "insumo_nombre": "N/A", "stock": 0, "consumo_diario": 0}
        
    # --- MÉTODOS PÚBLICOS PARA GRÁFICOS ---

    def obtener_top_productos_vendidos(self, fecha_inicio_str, fecha_fin_str, top_n=5):
        fecha_inicio, fecha_fin = self._parsear_fechas(fecha_inicio_str, fecha_fin_str)
        sales_res = self.pedido_model.get_sales_by_product_in_period(fecha_inicio, fecha_fin)
        if not sales_res.get('success'): return {"labels": [], "data": []}

        sorted_products = sorted(sales_res.get('data', {}).items(), key=lambda item: item[1], reverse=True)
        top_products = sorted_products[:top_n]
        return {"labels": [p[0] for p in top_products], "data": [p[1] for p in top_products]}

    def obtener_facturacion_por_periodo(self, fecha_inicio_str, fecha_fin_str, periodo='mensual'):
        fecha_inicio, fecha_fin = self._parsear_fechas(fecha_inicio_str, fecha_fin_str, 365)
        ingresos_res = self.pedido_model.get_ingresos_en_periodo(fecha_inicio, fecha_fin)
        if not ingresos_res.get('success'): return {"labels": [], "data": []}

        try:
            total_valor_res = self.pedido_model.get_total_valor_pedidos_completados(fecha_inicio, fecha_fin)
            num_pedidos_res = self.pedido_model.count_by_estado_in_date_range(estados.OV_COMPLETADO, fecha_inicio, fecha_fin)
        except Exception as e:
            logger.error(f"Error calculando valor promedio: {e}")

        if isinstance(ingresos_res.get('data'), dict):
            return ingresos_res['data']
        else:
            processed_data = defaultdict(float)
            for ingreso in ingresos_res.get('data', []):
                 fecha_dt = datetime.fromisoformat(ingreso['fecha_solicitud'])
                 key = fecha_dt.strftime('%Y-%m') 
                 processed_data[key] += float(ingreso['precio_orden'])
            
            labels = sorted(processed_data.keys())
            data = [processed_data[key] for key in labels]
            return {"labels": labels, "data": data}

    def obtener_rentabilidad_productos(self, fecha_inicio_str, fecha_fin_str):
        from app.models.insumo_inventario import InsumoInventarioModel
        insumo_inventario_model = InsumoInventarioModel()
        empty_return = {"labels": [], "costos": [], "ingresos": [], "rentabilidad_neta": []}

        productos_res = self.producto_model.find_all()
        if not productos_res.get('success'): return empty_return
        productos_data = productos_res.get('data', [])
        producto_ids = [p['id'] for p in productos_data]

        recetas_res = self.receta_model.find_all(filters={'producto_id': ('in', producto_ids), 'activa': True})
        if not recetas_res.get('success'): return empty_return
        
        recetas_por_producto_id = {receta['producto_id']: receta for receta in recetas_res.get('data', [])}
        receta_ids = [r['id'] for r in recetas_por_producto_id.values()]

        ingredientes_res = self.receta_model.get_ingredientes_by_receta_ids(receta_ids)
        if not ingredientes_res.get('success'): return empty_return
        
        ingredientes_por_receta_id = defaultdict(list)
        all_insumo_ids = set()
        for ing in ingredientes_res.get('data', []):
            ingredientes_por_receta_id[ing['receta_id']].append(ing)
            if insumo_data := ing.get('insumos_catalogo'):
                all_insumo_ids.add(insumo_data['id_insumo'])

        costos_insumos_res = insumo_inventario_model.get_costos_promedio_ponderado_bulk(list(all_insumo_ids))
        costos_insumos = costos_insumos_res.get('data', {}) if costos_insumos_res.get('success') else {}

        # Fallback para insumos sin costo pre-calculado
        insumos_sin_costo = all_insumo_ids - set(costos_insumos.keys())
        if insumos_sin_costo:
            fallback_res = self.insumo_model.find_all(filters={'id_insumo': list(insumos_sin_costo)})
            if fallback_res and fallback_res.get('success'):
                for insumo in fallback_res.get('data', []):
                    costos_insumos[insumo['id_insumo']] = float(insumo.get('precio_unitario', 0.0))
                    logging.info(f"Usando precio de catálogo como fallback para rentabilidad: {insumo['id_insumo']}")

        rentabilidad = {"labels": [], "costos": [], "ingresos": [], "rentabilidad_neta": []}
        for p in productos_data:
            costo_total = 0.0
            receta = recetas_por_producto_id.get(p['id'])
            if receta:
                ingredientes = ingredientes_por_receta_id.get(receta['id'], [])
                for ing in ingredientes:
                    insumo_id = ing.get('insumos_catalogo', {}).get('id_insumo')
                    cantidad = float(ing.get('cantidad', 0))
                    costo_unitario = costos_insumos.get(insumo_id, 0.0)
                    costo_total += cantidad * costo_unitario

            precio = float(p.get('precio_unitario', 0.0))
            rentabilidad['labels'].append(p['nombre'])
            rentabilidad['costos'].append(round(costo_total, 2))
            rentabilidad['ingresos'].append(round(precio, 2))
            rentabilidad['rentabilidad_neta'].append(round(precio - costo_total, 2))
            
        return rentabilidad

    def obtener_costo_vs_ganancia(self, fecha_inicio_str, fecha_fin_str, periodo='mensual'):
        fecha_inicio, fecha_fin = self._parsear_fechas(fecha_inicio_str, fecha_fin_str, 365)
        facturacion_res = self.obtener_facturacion_por_periodo(fecha_inicio_str, fecha_fin_str, periodo)
        empty_return = {"labels": [], "ingresos": [], "costos": []}
        if not facturacion_res or facturacion_res.get('error'): return empty_return
        
        ordenes_res = self.orden_produccion_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        if not ordenes_res.get('success'): return empty_return
        
        ordenes_data = ordenes_res.get('data', [])
        
        receta_ids_en_ordenes = [op['receta_id'] for op in ordenes_data if op.get('receta_id') and op.get('producto_id')]
        producto_ids_en_ordenes = [op['producto_id'] for op in ordenes_data if op.get('receta_id') and op.get('producto_id')]
        
        costos_cache = self._preparar_cache_costos_por_productos(list(set(producto_ids_en_ordenes)))

        costos_por_periodo = defaultdict(float)
        for op in ordenes_data:
            producto_id = op.get('producto_id')
            if not producto_id: 
                continue
                
            costo_unitario = self._get_costo_producto(producto_id, costos_cache)
            costo_op = costo_unitario * float(op.get('cantidad_producida', 0))
            
            fecha_op_str = op.get('fecha_inicio')
            if not fecha_op_str:
                continue

            fecha_op = datetime.fromisoformat(fecha_op_str).date()
            key = fecha_op.strftime('%Y-%m') if periodo == 'mensual' else fecha_op.strftime('%Y-W%U') if periodo == 'semanal' else fecha_op.strftime('%Y-%m-%d')
            costos_por_periodo[key] += costo_op

        labels = sorted(list(set(facturacion_res['labels']) | set(costos_por_periodo.keys())))
        ingresos_map = dict(zip(facturacion_res['labels'], facturacion_res['data']))
        return {"labels": labels, "ingresos": [ingresos_map.get(l, 0) for l in labels], "costos": [costos_por_periodo.get(l, 0) for l in labels]}

    def obtener_descomposicion_costos(self, fecha_inicio_str, fecha_fin_str):
        fecha_inicio, fecha_fin = self._parsear_fechas(fecha_inicio_str, fecha_fin_str)
        ordenes_res = self.orden_produccion_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        if not ordenes_res.get('success'): return {"labels": [], "data": []}
        
        ordenes_data = ordenes_res.get('data', [])
        
        producto_ids_en_ordenes = [op['producto_id'] for op in ordenes_data if op.get('producto_id')]
        costos_cache = self._preparar_cache_costos_por_productos(list(set(producto_ids_en_ordenes)))

        costo_mp = 0
        for op in ordenes_data:
            producto_id = op.get('producto_id')
            if producto_id:
                costo_unitario = self._get_costo_producto(producto_id, costos_cache)
                costo_mp += costo_unitario * float(op.get('cantidad_producida', 0))

        horas_prod = sum((datetime.fromisoformat(op['fecha_fin']) - datetime.fromisoformat(op['fecha_inicio'])).total_seconds() / 3600 for op in ordenes_data if op.get('fecha_fin') and op.get('fecha_inicio'))
        
        costo_mo = horas_prod * 15 # COSTO_HORA_HOMBRE
        gastos_fijos = (5000 / 30) * (fecha_fin - fecha_inicio).days # GASTOS_FIJOS_MENSUALES

        return {"labels": ["Materia Prima", "Mano de Obra (Est.)", "Gastos Fijos (Est.)"], "data": [round(costo_mp, 2), round(costo_mo, 2), round(gastos_fijos, 2)]}

    def obtener_top_clientes(self, fecha_inicio_str, fecha_fin_str, top_n=5, criterio='valor'):
        fecha_inicio, fecha_fin = self._parsear_fechas(fecha_inicio_str, fecha_fin_str, 365)
        pedidos_res = self.pedido_model.get_all_with_items(filtros={'fecha_desde': fecha_inicio.strftime('%Y-%m-%d'), 'fecha_hasta': fecha_fin.strftime('%Y-%m-%d'), 'estado': 'COMPLETADO'})
        if not pedidos_res.get('success'): return {"labels": [], "data": []}

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
        if not desperdicios_res.get('success'): return {"labels": [], "data": [], "line_data": []}

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
        empty_return = {"labels": list(categorias.keys()), "data": [0] * len(categorias)}

        if tipo == 'insumo':
            lotes_res = self.insumo_inventario_model.get_all_lotes_for_view()
            if not lotes_res.get('success'): return empty_return
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
            if not lotes_res.get('success'): return empty_return
            lotes_data = lotes_res.get('data', [])
            
            for lote in lotes_data:
                if not (fecha_str := lote.get('fecha_fabricacion')): continue
                antiguedad = (hoy - datetime.fromisoformat(fecha_str).date()).days
                
                valor = float(lote.get('costo_unitario_estimado') or 0.0) * float(lote.get('cantidad_actual', 0)) 
                
                if 0 <= antiguedad <= 30: categorias["0-30 días"] += valor
                elif 31 <= antiguedad <= 60: categorias["31-60 días"] += valor
                elif 61 <= antiguedad <= 90: categorias["61-90 días"] += valor
                else: categorias["+90 días"] += valor
            
        return {"labels": list(categorias.keys()), "data": list(categorias.values())}