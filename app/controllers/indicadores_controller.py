from datetime import datetime, timedelta, date
from dateutil import parser
from app.models.orden_produccion import OrdenProduccionModel
from app.models.control_calidad_producto import ControlCalidadProductoModel
from app.models.registro_desperdicio_lote_producto_model import RegistroDesperdicioLoteProductoModel
from app.models.registro_desperdicio_model import RegistroDesperdicioModel
from app.models.registro_desperdicio_lote_insumo_model import RegistroDesperdicioLoteInsumoModel
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
from app.models.nota_credito import NotaCreditoModel
from app.models.alerta_riesgo import AlertaRiesgoModel
from app.models.reclamo_proveedor_model import ReclamoProveedorModel
from app.models.costo_fijo import CostoFijoModel
from app.controllers.reporte_produccion_controller import ReporteProduccionController
from app.controllers.reporte_stock_controller import ReporteStockController
from app.controllers.rentabilidad_controller import RentabilidadController
from decimal import Decimal
from app.utils import estados
import logging
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)

class IndicadoresController:
    def __init__(self):
        self.reporte_produccion_controller = ReporteProduccionController()
        self.reporte_stock_controller = ReporteStockController()
        self.rentabilidad_controller = RentabilidadController()
        self.orden_produccion_model = OrdenProduccionModel()
        self.control_calidad_producto_model = ControlCalidadProductoModel()
        self.registro_desperdicio_model = RegistroDesperdicioLoteProductoModel()
        self.registro_desperdicio_insumo_model = RegistroDesperdicioModel()
        self.registro_desperdicio_lote_insumo_model = RegistroDesperdicioLoteInsumoModel()
        self.costo_fijo_model = CostoFijoModel()
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
        self.nota_credito_model = NotaCreditoModel()
        self.alerta_riesgo_model = AlertaRiesgoModel()
        self.reclamo_proveedor_model = ReclamoProveedorModel()
        
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
        if semana: 
            year, week_num = map(int, semana.split('-W'))
            fecha_inicio = datetime.fromisocalendar(year, week_num, 1)
            fecha_fin = fecha_inicio + timedelta(days=6)
        elif mes: 
            year, month = map(int, mes.split('-'))
            fecha_inicio = datetime(year, month, 1)
            next_month = (fecha_inicio.replace(day=28) + timedelta(days=4))
            fecha_fin = next_month - timedelta(days=next_month.day)
        elif ano: 
            year = int(ano)
            fecha_inicio = datetime(year, 1, 1)
            fecha_fin = datetime(year, 12, 31)
        else: 
            fecha_inicio = hoy - timedelta(days=hoy.weekday())
            fecha_fin = fecha_inicio + timedelta(days=6)
        return fecha_inicio.date(), fecha_fin.date()
    
    def obtener_anos_disponibles(self):
        return self.pedido_model.obtener_anos_distintos()

    # --- CATEGORÍA: PRODUCCIÓN ---
    def obtener_datos_produccion(self, semana=None, mes=None, ano=None):
        return {}

    def obtener_kpis_produccion(self, semana=None, mes=None, ano=None, top_n=5, **kwargs):
        fecha_inicio, fecha_fin = self._parsear_periodo(semana, mes, ano)
        
        contexto = 'mes' 
        if semana: contexto = 'semana'
        elif mes: contexto = 'mes'
        elif ano: contexto = 'ano'

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
        
        evolucion_desperdicios = self._obtener_evolucion_desperdicios(fecha_inicio, fecha_fin, contexto)
        
        velocidad_produccion = self._obtener_velocidad_produccion(inicio_mes_actual, fin_mes_actual)
        top_insumos = self._obtener_top_insumos_wrapper(fecha_inicio, fecha_fin, top_n=top_n)
        
        evolucion_consumo_insumos = self._obtener_evolucion_consumo_insumos(fecha_inicio, fecha_fin, contexto)

        oee = self._calcular_oee(fecha_inicio, fecha_fin)

        return {
            "meta": {"top_n": top_n},
            "panorama_estados": panorama_estados,
            "ranking_desperdicios": ranking_desperdicios,
            "evolucion_desperdicios": evolucion_desperdicios,
            "velocidad_produccion": velocidad_produccion,
            "top_insumos": top_insumos,
            "evolucion_consumo_insumos": evolucion_consumo_insumos,
            "oee": oee if isinstance(oee, dict) else {"valor": 0, "disponibilidad": 0, "rendimiento": 0, "calidad": 0},
        }

    def _obtener_panorama_estados(self, inicio_semana):
        estados_activos = [
            'EN ESPERA', 'EN_LINEA_1', 'EN_LINEA_2', 'EN_EMPAQUETADO', 'LISTA PARA PRODUCIR', 'EN_EMPAQUETADO', 
            'EN_PROCESO', 'CONTROL_DE_CALIDAD', 'PAUSADA'
        ]
        
        res_activas = self.orden_produccion_model.find_all(filters={'estado': estados_activos})
        data_activas = res_activas.get('data', []) if res_activas.get('success') else []
        
        res_completadas = self.orden_produccion_model.find_all(filters={
            'estado': 'COMPLETADA',
            'fecha_fin_gte': inicio_semana.isoformat() 
        })
        data_completadas = res_completadas.get('data', []) if res_completadas.get('success') else []

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
        res_prod = self.registro_desperdicio_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_prod = res_prod.get('data', []) if res_prod.get('success') else []

        res_insumo = self.registro_desperdicio_insumo_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_insumo = res_insumo.get('data', []) if res_insumo.get('success') else []

        res_lote_insumo = self.registro_desperdicio_lote_insumo_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_lote_insumo = res_lote_insumo.get('data', []) if res_lote_insumo.get('success') else []
        
        conteo = Counter()
        
        for d in data_prod:
            if isinstance(d.get('motivo'), dict):
                motivo = d.get('motivo', {}).get('motivo', 'Sin motivo') 
            else:
                motivo = 'Sin motivo'
            conteo[motivo] += 1 
            
        for d in data_insumo:
            if isinstance(d.get('motivo_desperdicio'), dict):
                motivo = d.get('motivo_desperdicio', {}).get('descripcion', 'Sin motivo')
            else:
                motivo = 'Sin motivo (Producción)'
            conteo[motivo] += 1

        for d in data_lote_insumo:
            if isinstance(d.get('motivo'), dict):
                motivo = d.get('motivo', {}).get('descripcion', 'Sin motivo')
            else:
                motivo = 'Sin motivo (Insumo)'
            conteo[motivo] += 1

        top_5 = conteo.most_common(5)
        total_incidentes = len(data_prod) + len(data_insumo) + len(data_lote_insumo)
        
        if top_5:
            top_motivo = top_5[0][0]
            porcentaje = (top_5[0][1] / total_incidentes * 100) if total_incidentes > 0 else 0
            insight = f"El motivo principal de las mermas ha sido '{top_motivo}', representando el {porcentaje:.0f}% del total de incidencias registradas en el periodo."
        else:
            insight = "No se han registrado incidentes de desperdicio significativos durante este mes."

        top_5_inv = top_5[::-1]
        chart_type = 'pie' if len(top_5) <= 6 else 'bar'
        
        return {
            "categories": [x[0] for x in top_5_inv],
            "values": [x[1] for x in top_5_inv],
            "insight": insight,
            "tooltip": "Los motivos más recurrentes por cantidad de incidentes (frecuencia).",
            "chart_type": chart_type
        }

    def _obtener_evolucion_desperdicios(self, fecha_inicio, fecha_fin, contexto='mes'):
        res_prod = self.registro_desperdicio_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_prod = res_prod.get('data', []) if res_prod.get('success') else []

        res_insumo = self.registro_desperdicio_insumo_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_insumo = res_insumo.get('data', []) if res_insumo.get('success') else []

        res_lote_insumo = self.registro_desperdicio_lote_insumo_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_lote_insumo = res_lote_insumo.get('data', []) if res_lote_insumo.get('success') else []
        
        data_agregada = defaultdict(int)
        labels_ordenados = []
        
        bucket_format = "%Y-%m-%d"
        delta = timedelta(days=1)
        
        if contexto == 'ano':
            bucket_format = "%Y-%m"
            current = fecha_inicio.replace(day=1)
            while current <= fecha_fin:
                key = current.strftime(bucket_format)
                labels_ordenados.append(key)
                data_agregada[key] = 0
                next_month = current.replace(day=28) + timedelta(days=4)
                current = next_month - timedelta(days=next_month.day - 1)
        else:
            current = fecha_inicio
            while current <= fecha_fin:
                key = current.strftime(bucket_format)
                labels_ordenados.append(key)
                data_agregada[key] = 0
                current += delta

        def procesar_lista(lista_datos, fecha_key):
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
                if key in data_agregada:
                    data_agregada[key] += 1
                elif contexto == 'ano': 
                     if key in data_agregada: 
                         data_agregada[key] += 1

        procesar_lista(data_prod, 'created_at')
        procesar_lista(data_insumo, 'fecha_registro')
        procesar_lista(data_lote_insumo, 'created_at')

        valores = [data_agregada[k] for k in labels_ordenados]
        
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
            
        insight = f"La tendencia de incidentes se muestra {trend_text} comparada con el promedio del periodo ({promedio:.1f} incidentes/periodo)."

        return {
            "categories": labels_display,
            "values": valores,
            "insight": insight,
            "tooltip": "Muestra la cantidad de reportes de desperdicio (tanto de producto como de insumos) registrados en cada periodo temporal."
        }

    def _obtener_velocidad_produccion(self, fecha_inicio, fecha_fin):
        res = self.reporte_produccion_controller.obtener_tiempo_ciclo_horas(fecha_inicio, fecha_fin)
        
        data = res.get('data', {}) if res.get('success') else {}
        promedio_horas = data.get('valor', 0.0)
        cantidad_ordenes = data.get('ordenes', 0)
        
        insight = f"Se completaron {cantidad_ordenes} órdenes en el periodo, con un tiempo promedio de ejecución estable."
        
        return {
            "valor": round(promedio_horas, 1),
            "unidad": "Horas",
            "insight": insight,
            "tooltip": "Tiempo promedio que toma completar una orden desde su inicio real hasta su fin."
        }

    def _obtener_top_insumos_wrapper(self, fecha_inicio, fecha_fin, top_n=5):
        res = self.reporte_produccion_controller.obtener_top_insumos(top_n) 
        data = res.get('data', {}) if res.get('success') else {}
        
        sorted_items = sorted(data.items(), key=lambda item: item[1], reverse=True)
        
        labels = [x[0] for x in sorted_items]
        values = [x[1] for x in sorted_items]
        
        top_nombre = labels[0] if labels else "N/A"
        insight = f"El insumo más utilizado es {top_nombre}."
        
        return {
            "labels": labels,
            "data": values,
            "insight": insight,
            "tooltip": "Insumos con mayor cantidad reservada en órdenes de producción en el periodo seleccionado."
        }

    def _obtener_evolucion_consumo_insumos(self, fecha_inicio, fecha_fin, contexto='mensual'):
        periodo_map = {'mes': 'mensual', 'semana': 'semanal', 'ano': 'mensual'} 
        periodo = periodo_map.get(contexto, 'mensual')
        
        res = self.reporte_produccion_controller.obtener_consumo_insumos_por_tiempo(fecha_inicio, fecha_fin, periodo)
        data = res.get('data', {}) if res.get('success') else {'labels': [], 'data': []}
        
        insight = "El consumo de insumos se mantiene consistente."
        if data['data'] and len(data['data']) > 1:
             if data['data'][-1] > data['data'][0]:
                 insight = "El consumo de insumos muestra una tendencia al alza."
        
        return {
            "categories": data.get('labels', []),
            "values": data.get('data', []),
            "insight": insight,
            "tooltip": "Cantidad total de insumos reservados (consumidos) a lo largo del tiempo."
        }

    # --- CATEGORÍA: CALIDAD ---
    def obtener_datos_calidad(self, semana=None, mes=None, ano=None):
        fecha_inicio, fecha_fin = self._parsear_periodo(semana, mes, ano)
        
        contexto = 'mes'
        if semana: contexto = 'semana'
        elif mes: contexto = 'mes'
        elif ano: contexto = 'ano'

        rechazo_interno = self._calcular_tasa_rechazo_interno(fecha_inicio, fecha_fin)
        reclamos_clientes = self._calcular_tasa_reclamos_clientes(fecha_inicio, fecha_fin)
        rechazo_proveedores = self._calcular_tasa_rechazo_proveedores(fecha_inicio, fecha_fin)
        
        alertas_activas_res = self.alerta_riesgo_model.find_all(filters={'estado': 'Pendiente'})
        alertas_activas_count = len(alertas_activas_res.get('data', [])) if alertas_activas_res.get('success') else 0

        desperdicios_res = self.registro_desperdicio_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        desperdicios_count = len(desperdicios_res.get('data', [])) if desperdicios_res.get('success') else 0
        desperdicios_insumos_res = self.registro_desperdicio_insumo_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        desperdicios_count += len(desperdicios_insumos_res.get('data', [])) if desperdicios_insumos_res.get('success') else 0
        desperdicios_lote_insumos_res = self.registro_desperdicio_lote_insumo_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        desperdicios_count += len(desperdicios_lote_insumos_res.get('data', [])) if desperdicios_lote_insumos_res.get('success') else 0

        evolucion_reclamos = self._obtener_evolucion_reclamos_detalle(fecha_inicio, fecha_fin, contexto)
        distribucion_alertas = self._obtener_distribucion_alertas(fecha_inicio, fecha_fin)
        resultados_calidad = self._obtener_resultados_calidad(fecha_inicio, fecha_fin)
        motivos_alerta = self._obtener_motivos_alerta(fecha_inicio, fecha_fin)
        evolucion_desperdicios = self._obtener_evolucion_desperdicios(fecha_inicio, fecha_fin, contexto)
        top_items_desperdicio = self._obtener_top_items_con_desperdicio(fecha_inicio, fecha_fin)
        origen_desperdicios = self._obtener_origen_desperdicios(fecha_inicio, fecha_fin)

        return {
            "tasa_rechazo_interno": rechazo_interno if isinstance(rechazo_interno, dict) else {"valor": 0, "rechazadas": 0, "inspeccionadas": 0},
            "tasa_reclamos_clientes": reclamos_clientes if isinstance(reclamos_clientes, dict) else {"valor": 0, "reclamos": 0, "pedidos_entregados": 0},
            "tasa_rechazo_proveedores": rechazo_proveedores if isinstance(rechazo_proveedores, dict) else {"valor": 0, "rechazados": 0, "recibidos": 0},
            "alertas_activas": alertas_activas_count,
            "incidentes_desperdicio": desperdicios_count,
            "evolucion_reclamos_clientes": evolucion_reclamos['clientes'],
            "evolucion_reclamos_proveedores": evolucion_reclamos['proveedores'],
            "distribucion_alertas": distribucion_alertas,
            "resultados_calidad": resultados_calidad,
            "motivos_alerta": motivos_alerta,
            "evolucion_desperdicios": evolucion_desperdicios,
            "top_items_desperdicio": top_items_desperdicio,
            "origen_desperdicios": origen_desperdicios
        }

    def _obtener_evolucion_reclamos_detalle(self, fecha_inicio, fecha_fin, contexto):
        reclamos_cli_res = self.reclamo_model.find_all(filters={
            'created_at_gte': fecha_inicio.isoformat(),
            'created_at_lte': fecha_fin.isoformat()
        })
        data_cli = reclamos_cli_res.get('data', []) if reclamos_cli_res.get('success') else []

        reclamos_prov_res = self.reclamo_proveedor_model.find_all(filters={
            'created_at_gte': fecha_inicio.isoformat(),
            'created_at_lte': fecha_fin.isoformat()
        })
        data_prov = reclamos_prov_res.get('data', []) if reclamos_prov_res.get('success') else []

        data_agregada = defaultdict(lambda: {'cli': 0, 'prov': 0})
        labels_ordenados = []
        
        bucket_format = "%Y-%m-%d"
        delta = timedelta(days=1)
        
        if contexto == 'ano':
            bucket_format = "%Y-%m"
            current = fecha_inicio.replace(day=1)
            while current <= fecha_fin:
                key = current.strftime(bucket_format)
                labels_ordenados.append(key)
                data_agregada[key] 
                next_month = current.replace(day=28) + timedelta(days=4)
                current = next_month - timedelta(days=next_month.day - 1)
        else:
            current = fecha_inicio
            while current <= fecha_fin:
                key = current.strftime(bucket_format)
                labels_ordenados.append(key)
                data_agregada[key] 
                current += delta

        def procesar(data, tipo):
            for d in data:
                f_str = d.get('created_at')
                if not f_str: continue
                try:
                    dt = datetime.fromisoformat(f_str)
                    key = dt.strftime(bucket_format)
                    if key in data_agregada:
                        data_agregada[key][tipo] += 1
                    elif contexto == 'ano': 
                        if key in data_agregada:
                             data_agregada[key][tipo] += 1
                except: pass
        
        procesar(data_cli, 'cli')
        procesar(data_prov, 'prov')

        vals_cli = [data_agregada[k]['cli'] for k in labels_ordenados]
        vals_prov = [data_agregada[k]['prov'] for k in labels_ordenados]

        labels_display = []
        for k in labels_ordenados:
             if contexto == 'ano':
                 dt = datetime.strptime(k, "%Y-%m")
                 labels_display.append(dt.strftime("%b"))
             else:
                 dt = datetime.strptime(k, "%Y-%m-%d")
                 labels_display.append(dt.strftime("%d/%m"))

        tot_cli = sum(vals_cli)
        trend_cli = "estable"
        if len(vals_cli) > 1:
            if vals_cli[-1] > vals_cli[0]: trend_cli = "al alza"
            elif vals_cli[-1] < vals_cli[0]: trend_cli = "a la baja"
        insight_cli = f"Se registraron {tot_cli} reclamos de clientes. La tendencia es {trend_cli}."

        tot_prov = sum(vals_prov)
        insight_prov = f"Se registraron {tot_prov} reclamos a proveedores."

        return {
            "clientes": {
                "categories": labels_display,
                "series": [{"name": "Reclamos Clientes", "data": vals_cli}],
                "insight": insight_cli,
                "tooltip": "Evolución de reclamos recibidos de clientes."
            },
            "proveedores": {
                "categories": labels_display,
                "series": [{"name": "Reclamos Proveedores", "data": vals_prov}],
                "insight": insight_prov,
                "tooltip": "Evolución de reclamos emitidos a proveedores."
            }
        }

    def _obtener_distribucion_alertas(self, fecha_inicio, fecha_fin):
        res = self.alerta_riesgo_model.find_all(filters={
            'fecha_creacion_gte': fecha_inicio.isoformat(),
            'fecha_creacion_lte': fecha_fin.isoformat()
        })
        data = res.get('data', []) if res.get('success') else []
        
        conteo = Counter([d.get('origen_tipo_entidad', 'Desconocido') for d in data])
        nombres_map = {
            'lote_insumo': 'Insumos',
            'lote_producto': 'Productos',
            'pedido': 'Pedidos',
            'orden_produccion': 'Producción'
        }
        
        formatted = [{"name": nombres_map.get(k, k).capitalize(), "value": v} for k, v in conteo.items()]
        
        insight = "No se han generado alertas de riesgo en este periodo."
        if data:
            top = conteo.most_common(1)[0]
            nom = nombres_map.get(top[0], top[0])
            insight = f"La mayor fuente de riesgos proviene de '{nom}' ({top[1]} alertas)."

        return {
            "data": formatted,
            "insight": insight,
            "tooltip": "Desglose de alertas de riesgo según el origen (Insumo, Producto, Pedido, etc.)."
        }

    def _obtener_resultados_calidad(self, fecha_inicio, fecha_fin):
        try:
            res_ins = self.control_calidad_insumo_model.db.table('control_calidad_insumos').select('decision_final').gte('fecha_inspeccion', fecha_inicio.isoformat()).lte('fecha_inspeccion', fecha_fin.isoformat()).execute()
            data_ins = res_ins.data if res_ins.data else []
        except Exception as e:
            logger.error(f"Error obteniendo resultados calidad insumos: {e}")
            data_ins = []

        try:
            res_prod = self.control_calidad_producto_model.db.table('control_calidad_productos').select('decision_final').gte('fecha_inspeccion', fecha_inicio.isoformat()).lte('fecha_inspeccion', fecha_fin.isoformat()).execute()
            data_prod = res_prod.data if res_prod.data else []
        except Exception as e:
            logger.error(f"Error obteniendo resultados calidad productos: {e}")
            data_prod = []
        
        c_ins = Counter([d.get('decision_final', 'PENDIENTE') for d in data_ins])
        c_prod = Counter([d.get('decision_final', 'PENDIENTE') for d in data_prod])
        
        series = {
            'Aprobado': [],
            'Rechazado': [],
            'Cuarentena': []
        }
        categories = ['Insumos', 'Productos']
        
        def get_val(counter, key_list):
            return sum(counter.get(k, 0) for k in key_list)

        series['Aprobado'] = [get_val(c_ins, ['APROBADO', 'Aprobado']), get_val(c_prod, ['APROBADO', 'Aprobado'])]
        series['Rechazado'] = [get_val(c_ins, ['RECHAZADO', 'Rechazado']), get_val(c_prod, ['RECHAZADO', 'Rechazado'])]
        series['Cuarentena'] = [get_val(c_ins, ['CUARENTENA', 'EN_CUARENTENA', 'En Cuarentena']), get_val(c_prod, ['CUARENTENA', 'EN_CUARENTENA'])]

        total_ins = sum(c_ins.values())
        total_prod = sum(c_prod.values())
        
        rechazo_ins = series['Rechazado'][0]
        rechazo_prod = series['Rechazado'][1]
        
        insight = "Calidad estable."
        if total_ins > 0 or total_prod > 0:
            t_rechazo = rechazo_ins + rechazo_prod
            t_total = total_ins + total_prod
            pct = (t_rechazo / t_total * 100)
            insight = f"Tasa global de rechazo: {pct:.1f}% ({t_rechazo} inspecciones fallidas de {t_total})."

        return {
            "categories": categories,
            "series": [
                {"name": "Aprobado", "data": series['Aprobado'], "color": "#198754"}, 
                {"name": "Rechazado", "data": series['Rechazado'], "color": "#dc3545"}, 
                {"name": "Cuarentena", "data": series['Cuarentena'], "color": "#ffc107"} 
            ],
            "insight": insight,
            "tooltip": "Resultados de las inspecciones de calidad realizadas en el periodo."
        }

    def _obtener_motivos_alerta(self, fecha_inicio, fecha_fin):
        res = self.alerta_riesgo_model.find_all(filters={
            'fecha_creacion_gte': fecha_inicio.isoformat(),
            'fecha_creacion_lte': fecha_fin.isoformat()
        })
        data = res.get('data', []) if res.get('success') else []
        
        conteo = Counter([d.get('motivo', 'Sin motivo') for d in data])
        top_5 = conteo.most_common(5)
        
        insight = "Sin alertas registradas."
        if top_5:
            insight = f"El motivo más frecuente es '{top_5[0][0]}'."

        return {
            "categories": [x[0] for x in top_5],
            "values": [x[1] for x in top_5],
            "insight": insight,
            "tooltip": "Ranking de los motivos declarados al crear alertas de riesgo."
        }

    def _obtener_top_items_con_desperdicio(self, fecha_inicio, fecha_fin):
        conteo_items = Counter()

        # 1. Desperdicios de Lotes de Producto (Ya terminados)
        res_prod = self.registro_desperdicio_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_prod = res_prod.get('data', []) if res_prod.get('success') else []
        
        if data_prod:
            lote_ids = []
            for d in data_prod:
                lid = d.get('lote_producto_id') or d.get('lote_id')
                if lid: lote_ids.append(lid)
            
            lote_ids = list(set(lote_ids))
            lote_map = {}

            if lote_ids:
                lote_ids_str = [str(id_) for id_ in lote_ids]
                try:
                    lotes_res = self.lote_producto_model.db.table('lotes_productos')\
                        .select('id_lote, producto:productos(nombre)')\
                        .in_('id_lote', lote_ids_str)\
                        .execute()
                    
                    if lotes_res.data:
                        for item in lotes_res.data:
                            lote_map[str(item['id_lote'])] = item.get('producto', {}).get('nombre', 'Producto Desconocido')
                            lote_map[int(item['id_lote'])] = item.get('producto', {}).get('nombre', 'Producto Desconocido')
                except Exception as e:
                    logger.error(f"Error fetching product details for waste: {e}")

            for d in data_prod:
                l_id = d.get('lote_producto_id') or d.get('lote_id')
                if l_id:
                    name = lote_map.get(l_id) or lote_map.get(str(l_id)) or f"Producto ID {l_id}"
                    conteo_items[f"{name}"] += 1

        # 2. Desperdicios en Ordenes de Producción (Productos en proceso)
        res_ins = self.registro_desperdicio_insumo_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_ins = res_ins.get('data', []) if res_ins.get('success') else []

        # 3. Desperdicios de Lotes de Insumos (O en OP)
        res_lote_ins = self.registro_desperdicio_lote_insumo_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_lote_ins = res_lote_ins.get('data', []) if res_lote_ins.get('success') else []
        
        # Combinar datos de insumos (tabla registro_desperdicio y registro_desperdicio_lote_insumo)
        combined_insumo_data = data_ins + data_lote_ins

        if combined_insumo_data:
            op_ids_to_fetch = set()
            lote_insumo_ids = set()

            for d in combined_insumo_data:
                op_id = d.get('orden_produccion_id')
                if op_id:
                    op_ids_to_fetch.add(op_id)
                
                lid = d.get('lote_insumo_id') or d.get('lote_inventario_id') or d.get('lote_id')
                if lid:
                    lote_insumo_ids.add(lid)

            op_map = {}
            if op_ids_to_fetch:
                try:
                    ops_res = self.orden_produccion_model.db.table('ordenes_produccion')\
                        .select('id, producto:productos(nombre)')\
                        .in_('id', list(op_ids_to_fetch))\
                        .execute()
                    
                    if ops_res.data:
                        for item in ops_res.data:
                            p_name = item.get('producto', {}).get('nombre', 'Producto Desconocido')
                            op_map[item['id']] = f"{p_name} (En Producción)"
                except Exception as e:
                    logger.error(f"Error fetching OP details for waste: {e}")

            insumo_map = {}
            if lote_insumo_ids:
                lote_ids_str = [str(id_) for id_ in lote_insumo_ids]
                try:
                    insumos_res = self.insumo_inventario_model.db.table('insumos_inventario')\
                        .select('id_lote, insumo:insumos_catalogo(nombre)')\
                        .in_('id_lote', lote_ids_str)\
                        .execute()
                    
                    if insumos_res.data:
                        for item in insumos_res.data:
                            insumo_map[str(item['id_lote'])] = item.get('insumo', {}).get('nombre', 'Insumo Desconocido')
                except Exception as e:
                    logger.error(f"Error fetching insumo details for waste: {e}")

            for d in combined_insumo_data:
                op_id = d.get('orden_produccion_id')
                l_id = d.get('lote_insumo_id') or d.get('lote_inventario_id') or d.get('lote_id')
                
                if op_id and op_id in op_map:
                    conteo_items[op_map[op_id]] += 1
                elif l_id:
                    name = insumo_map.get(str(l_id)) or f"Insumo ID {str(l_id)[:8]}..."
                    conteo_items[f"{name}"] += 1
                elif op_id: 
                     conteo_items[f"Orden Producción #{op_id}"] += 1

        top_items = conteo_items.most_common(10)
        
        insight = "No se registraron desperdicios específicos."
        if top_items:
            top_name = top_items[0][0]
            insight = f"El ítem con más reportes de desperdicio es '{top_name}'."

        return {
            "categories": [x[0] for x in top_items],
            "values": [x[1] for x in top_items],
            "insight": insight,
            "tooltip": "Ranking de productos e insumos según la cantidad de reportes de desperdicio registrados."
        }

    def _obtener_origen_desperdicios(self, fecha_inicio, fecha_fin):
        # 1. Productos en Ordenes de Producción
        res_op_prod = self.registro_desperdicio_insumo_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_op_prod = res_op_prod.get('data', []) if res_op_prod.get('success') else []
        count_op_prod = len(data_op_prod)

        # 2. Insumos (Pueden ser de OP o de Lote directo)
        res_insumo = self.registro_desperdicio_lote_insumo_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_insumo = res_insumo.get('data', []) if res_insumo.get('success') else []
        
        count_op_insumo = 0
        count_lote_insumo = 0
        
        for d in data_insumo:
            if d.get('orden_produccion_id'):
                count_op_insumo += 1
            else:
                count_lote_insumo += 1

        # 3. Lotes de Productos (Ya terminados)
        res_lote_prod = self.registro_desperdicio_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_lote_prod = res_lote_prod.get('data', []) if res_lote_prod.get('success') else []
        count_lote_prod = len(data_lote_prod)

        # Agregación
        ordenes_produccion = count_op_prod + count_op_insumo
        lotes_insumos = count_lote_insumo
        lotes_productos = count_lote_prod
        
        total = ordenes_produccion + lotes_insumos + lotes_productos
        
        data = [
            {"name": "Ordenes de Producción", "value": ordenes_produccion},
            {"name": "Lotes de Insumos", "value": lotes_insumos},
            {"name": "Lotes de Productos", "value": lotes_productos}
        ]
        
        insight = "No se han registrado desperdicios."
        if total > 0:
            top = max(data, key=lambda x: x['value'])
            pct = (top['value'] / total * 100)
            insight = f"La mayor cantidad de desperdicios proviene de '{top['name']}' ({pct:.0f}%)."
            
        return {
            "data": data,
            "insight": insight,
            "tooltip": "Distribución del origen de los desperdicios registrados."
        }

    # --- CATEGORÍA: COMERCIAL ---
    def obtener_datos_comercial(self, semana=None, mes=None, ano=None):
        fecha_inicio, fecha_fin = self._parsear_periodo(semana, mes, ano)

        kpis_data = self._obtener_kpis_comerciales(fecha_inicio, fecha_fin)

        contexto = 'mes'
        if semana: contexto = 'semana'
        elif mes: contexto = 'mes'
        elif ano: contexto = 'ano'

        evolucion_ventas = self._obtener_evolucion_ventas_comparativa(fecha_inicio, fecha_fin, contexto)
        distribucion_estados = self._obtener_distribucion_estados_pedidos(fecha_inicio, fecha_fin)
        top_clientes = self._obtener_top_clientes_kpi(fecha_inicio, fecha_fin)
        motivos_nc = self._obtener_motivos_notas_credito(fecha_inicio, fecha_fin)

        return {"kpis_comerciales": kpis_data,
            "evolucion_ventas": evolucion_ventas,
            "distribucion_estados": distribucion_estados,
            "top_clientes": top_clientes,
            "motivos_notas_credito": motivos_nc
        }

    def _obtener_kpis_comerciales(self, fecha_inicio, fecha_fin):
        estados_totales = [
            estados.OV_PENDIENTE, estados.OV_EN_PROCESO, estados.OV_LISTO_PARA_ENTREGA,
            estados.OV_COMPLETADO, estados.OV_CANCELADA, estados.OV_EN_TRANSITO, estados.OV_ITEM_ALISTADO
        ]
        total_pedidos_res = self.pedido_model.count_by_estados_in_date_range(estados_totales, fecha_inicio, fecha_fin)
        completados_res = self.pedido_model.count_by_estado_in_date_range(estados.OV_COMPLETADO, fecha_inicio, fecha_fin)
        
        total_pedidos = total_pedidos_res.get('count', 0)
        num_pedidos_completados = completados_res.get('count', 0)
        
        cumplimiento_pedidos = (num_pedidos_completados / total_pedidos) * 100 if total_pedidos > 0 else 0

        estados_activos = [
            estados.OV_PENDIENTE, estados.OV_EN_PROCESO, estados.OV_LISTO_PARA_ENTREGA,
            estados.OV_COMPLETADO, estados.OV_EN_TRANSITO, estados.OV_ITEM_ALISTADO
        ]
        
        ingresos_res = self.pedido_model.get_ingresos_en_periodo(
            fecha_inicio.isoformat(), 
            fecha_fin.isoformat(), 
            estados_filtro=estados_activos
        )
        data_p = ingresos_res.get('data', []) if ingresos_res.get('success') else []
        
        total_valor = sum(float(p['precio_orden'] or 0) for p in data_p)
        num_pedidos_validos = len(data_p)
            
        valor_promedio = total_valor / num_pedidos_validos if num_pedidos_validos > 0 else 0.0

        return {
            "cumplimiento_pedidos": {"valor": round(cumplimiento_pedidos, 2), "completados": num_pedidos_completados, "total": total_pedidos},
            "valor_promedio_pedido": {"valor": round(valor_promedio, 2), "num_pedidos": num_pedidos_validos},
            "ingresos_totales": {"valor": round(total_valor, 2), "num_pedidos": num_pedidos_validos}        
            }

    def _obtener_evolucion_ventas_comparativa(self, fecha_inicio, fecha_fin, contexto):
        estados_ventas = [
            estados.OV_COMPLETADO, 
            estados.OV_PENDIENTE, 
            estados.OV_EN_PROCESO, 
            estados.OV_LISTO_PARA_ENTREGA,
            estados.OV_ITEM_ALISTADO, 
            estados.OV_EN_TRANSITO
        ]
        
        pedidos_actuales = self.pedido_model.get_ingresos_en_periodo(fecha_inicio, fecha_fin, estados_filtro=estados_ventas)
        data_actual = pedidos_actuales.get('data', []) if pedidos_actuales.get('success') else []
        
        delta_periodo = fecha_fin - fecha_inicio
        fecha_fin_prev = fecha_inicio - timedelta(days=1)
        fecha_inicio_prev = fecha_fin_prev - delta_periodo
        pedidos_previos = self.pedido_model.get_ingresos_en_periodo(fecha_inicio_prev, fecha_fin_prev, estados_filtro=estados_ventas)
        data_previo = pedidos_previos.get('data', []) if pedidos_previos.get('success') else []
        
        def agregar_data(dataset, inicio):
            agregado = defaultdict(float)
            labels = []
            end = inicio + delta_periodo
            
            if contexto == 'ano':
                fmt = "%Y-%m"
                curr = inicio.replace(day=1)
                while curr <= end:
                    labels.append(curr.strftime(fmt))
                    curr = (curr.replace(day=28) + timedelta(days=4)).replace(day=1)
            else:
                fmt = "%Y-%m-%d"
                curr = inicio
                while curr <= end:
                    labels.append(curr.strftime(fmt))
                    curr += timedelta(days=1)
            
            for p in dataset:
                f_str = p.get('fecha_solicitud')
                if not f_str: continue
                dt = datetime.fromisoformat(f_str).date()
                key = dt.strftime(fmt)
                agregado[key] += float(p.get('precio_orden', 0))
            
            return [agregado[l] for l in labels], labels

        vals_actual, keys_actual = agregar_data(data_actual, fecha_inicio)
        vals_previo, keys_previo = agregar_data(data_previo, fecha_inicio_prev)
        
        max_len = max(len(vals_actual), len(vals_previo))
        vals_actual += [0] * (max_len - len(vals_actual))
        vals_previo += [0] * (max_len - len(vals_previo))

        labels_display = []
        for k in keys_actual:
            dt = datetime.strptime(k, "%Y-%m" if contexto == 'ano' else "%Y-%m-%d")
            labels_display.append(dt.strftime("%b" if contexto == 'ano' else "%d/%m"))

        total_actual = sum(vals_actual)
        total_previo = sum(vals_previo)
        diff = total_actual - total_previo
        pct = (diff / total_previo * 100) if total_previo > 0 else 100 if total_actual > 0 else 0
        trend = "crecimiento" if diff >= 0 else "decrecimiento"
        insight = f"Los ingresos muestran un {trend} del {abs(pct):.1f}% respecto al periodo anterior."

        return {
            "categories": labels_display,
            "series": [
                {"name": "Periodo Actual", "data": vals_actual},
                {"name": "Periodo Anterior", "data": vals_previo}
            ],
            "insight": insight,
            "tooltip": "Comparativa de ingresos por ventas confirmadas entre el periodo seleccionado y el anterior inmediato."
        }

    def _obtener_distribucion_estados_pedidos(self, fecha_inicio, fecha_fin):
        query = self.pedido_model.find_all(filters={
            'fecha_solicitud_gte': fecha_inicio.isoformat(),
            'fecha_solicitud_lte': fecha_fin.isoformat()
        })
        data = query.get('data', []) if query.get('success') else []
        
        conteo = Counter([d.get('estado', 'DESCONOCIDO') for d in data])
        formatted_data = [{"name": k.replace('_', ' '), "value": v} for k, v in conteo.items()]
        
        total = sum(conteo.values())
        completados = conteo.get('COMPLETADO', 0)
        pct = (completados / total * 100) if total > 0 else 0
        insight = f"El {pct:.1f}% de los pedidos generados en este periodo ya han sido completados."

        return {
            "data": formatted_data,
            "insight": insight,
            "tooltip": "Distribución de estados de todos los pedidos creados dentro del rango de fechas seleccionado."
        }

    def _obtener_top_clientes_kpi(self, fecha_inicio, fecha_fin):
        estados_validos = [estados.OV_COMPLETADO, estados.OV_PENDIENTE, estados.OV_EN_PROCESO, estados.OV_LISTO_PARA_ENTREGA]
        
        res = self.pedido_model.find_all(filters={
            'fecha_solicitud_gte': fecha_inicio.isoformat(),
            'fecha_solicitud_lte': fecha_fin.isoformat(),
            'estado': estados_validos
        })
        data = res.get('data', []) if res.get('success') else []
        
        clientes_spend = defaultdict(float)
        clientes_names = {} 
        
        full_data_res = self.pedido_model.get_all_with_items(filtros={
            'fecha_desde': fecha_inicio.strftime('%Y-%m-%d'),
            'fecha_hasta': fecha_fin.strftime('%Y-%m-%d')
        })
        full_data = full_data_res.get('data', []) if full_data_res.get('success') else []
        
        for p in full_data:
            if p.get('estado') == 'CANCELADO': continue
            cid = p.get('id_cliente')
            if not cid: continue
            
            cname = p.get('cliente', {}).get('nombre') or f"Cliente {cid}"
            val = float(p.get('precio_orden', 0) or 0)
            if val == 0:
                for item in p.get('pedido_items', []):
                    qty = float(item.get('cantidad') or 0)
                    prod = item.get('producto_nombre') 
                    price = float(prod.get('precio_unitario') or 0) if isinstance(prod, dict) else 0
                    val += qty * price
            
            clientes_spend[cname] += val
            
        top_5 = sorted(clientes_spend.items(), key=lambda x: x[1], reverse=True)[:5]
        
        insight = "No hay datos suficientes."
        if top_5:
            total_spend = sum(clientes_spend.values())
            top_c = top_5[0][0]
            pct = (top_5[0][1] / total_spend * 100) if total_spend > 0 else 0
            insight = f"El cliente '{top_c}' representa el {pct:.1f}% del volumen de ventas del periodo."
            
        return {
            "categories": [x[0] for x in top_5],
            "values": [x[1] for x in top_5],
            "insight": insight,
            "tooltip": "Ranking de clientes basado en la suma total de pedidos (excluyendo cancelados)."
        }

    def _obtener_motivos_notas_credito(self, fecha_inicio, fecha_fin):
        res = self.nota_credito_model.find_all(filters={
            'created_at_gte': fecha_inicio.isoformat(),
            'created_at_lte': fecha_fin.isoformat()
        })
        data = res.get('data', []) if res.get('success') else []
        
        conteo = Counter([d.get('motivo', 'Sin motivo') for d in data])
        top_motivos = conteo.most_common(5)
        
        chart_type = 'pie'
        if len(conteo) > 5: chart_type = 'bar'
        
        formatted_data = [{"name": k, "value": v} for k, v in top_motivos]
        if chart_type == 'bar': 
            formatted_data = {
                "categories": [x[0] for x in top_motivos],
                "values": [x[1] for x in top_motivos]
            }
            
        insight = "No se han generado notas de crédito en este periodo."
        if data:
            insight = f"Se han generado {len(data)} notas de crédito en total."
            
        return {
            "data": formatted_data,
            "chart_type": chart_type,
            "insight": insight,
            "tooltip": "Clasificación de Notas de Crédito por motivo registrado."
        }

    # --- CATEGORÍA: FINANCIERA ---
    def obtener_datos_financieros(self, semana=None, mes=None, ano=None):
        fecha_inicio, fecha_fin = self._parsear_periodo(semana, mes, ano)
        fecha_inicio_str = fecha_inicio.strftime('%Y-%m-%d')
        fecha_fin_str = fecha_fin.strftime('%Y-%m-%d')
        
        contexto = 'mes'
        if semana: contexto = 'semana'
        elif mes: contexto = 'mes'
        elif ano: contexto = 'ano'
        
        estados_ventas = [
            estados.OV_COMPLETADO, estados.OV_LISTO_PARA_ENTREGA, estados.OV_EN_TRANSITO,
            estados.OV_EN_PROCESO, estados.OV_ITEM_ALISTADO, estados.OV_PLANIFICADA
        ]
        ventas_res = self.pedido_model.get_ingresos_en_periodo(fecha_inicio_str, fecha_fin_str, estados_filtro=estados_ventas)
        data_ventas = ventas_res.get('data', []) if ventas_res.get('success') else []
        ventas_totales = sum(float(p.get('precio_orden') or 0) for p in data_ventas)

        flujo_caja_real = 0.0
        ids_pago_parcial = []
        
        for p in data_ventas:
            estado_pago = p.get('estado_pago', '').lower()
            precio = float(p.get('precio_orden') or 0)
            
            if estado_pago == 'pagado':
                flujo_caja_real += precio
            elif estado_pago == 'pagado parcialmente':
                ids_pago_parcial.append(p['id'])
                
        from app.models.pago import PagoModel
        pago_model = PagoModel()
        
        if ids_pago_parcial:
            try:
                pagos_parciales_res = pago_model.db.table('pagos').select('monto')\
                    .in_('id_pedido', ids_pago_parcial)\
                    .eq('estado', 'verificado')\
                    .execute()
                data_parciales = pagos_parciales_res.data if pagos_parciales_res.data else []
                flujo_caja_real += sum(float(pg.get('monto') or 0) for pg in data_parciales)
            except Exception as e:
                logger.error(f"Error consultando pagos parciales: {e}")

        ingreso_pendiente = ventas_totales - flujo_caja_real
        if ingreso_pendiente < 0: ingreso_pendiente = 0

        ordenes_res = self.orden_produccion_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        costo_total = 0.0
        dias_periodo = max((fecha_fin - fecha_inicio).days, 1)
        
        costos_fijos_res = self.costo_fijo_model.find_all(filters={'activo': True})
        monto_mensual_fijos = sum(float(c.get('monto_mensual', 0)) for c in costos_fijos_res.get('data', [])) if costos_fijos_res.get('success') else 0.0
        gastos_fijos_periodo = (monto_mensual_fijos / 30) * dias_periodo

        if ordenes_res.get('success'):
            ordenes_data = ordenes_res.get('data', [])
            producto_ids_en_ordenes = [op['producto_id'] for op in ordenes_data if op.get('producto_id')]
            costos_cache = self._preparar_cache_costos_por_productos(list(set(producto_ids_en_ordenes)))
            
            costo_mp = sum(self._get_costo_producto(op['producto_id'], costos_cache) * float(op.get('cantidad_producida', 0)) for op in ordenes_data if op.get('producto_id'))
            horas_prod = sum((datetime.fromisoformat(op['fecha_fin']) - datetime.fromisoformat(op['fecha_inicio'])).total_seconds() / 3600 for op in ordenes_data if op.get('fecha_fin') and op.get('fecha_inicio'))
            costo_mo = horas_prod * 15 
            costo_total = costo_mp + costo_mo + gastos_fijos_periodo

        beneficio_bruto = ventas_totales - costo_total
        margen_beneficio = (beneficio_bruto / ventas_totales) * 100 if ventas_totales > 0 else 0
        
        kpis = {
            "ventas_totales": {"valor": round(ventas_totales, 2), "etiqueta": "Ventas Totales (Pendiente)"},
            "flujo_caja_real": {"valor": round(flujo_caja_real, 2), "etiqueta": "Flujo de Caja (Recibido)"},
            "ingreso_pendiente": {"valor": round(ingreso_pendiente, 2), "etiqueta": "Cuentas por Cobrar"},
            "costo_total": {"valor": round(costo_total, 2), "etiqueta": "Egresos Totales (Est.)"},
            "beneficio_bruto": {"valor": round(beneficio_bruto, 2), "etiqueta": "Resultado Operativo"},
            "facturacion_total": {"valor": round(ventas_totales, 2), "etiqueta": "Ventas Totales"}
        }

        evolucion_ingresos = self._obtener_evolucion_financiera_comparativa(fecha_inicio, fecha_fin, contexto)
        descomposicion = self._obtener_descomposicion_costos_con_detalle(fecha_inicio, fecha_fin, gastos_fijos_periodo)
        ingresos_vs_egresos = self._obtener_evolucion_ingresos_vs_egresos(fecha_inicio, fecha_fin, contexto, monto_mensual_fijos)
        evolucion_costos_fijos = self._obtener_evolucion_costos_fijos(fecha_inicio, fecha_fin, contexto, monto_mensual_fijos)

        try:
            rentabilidad_raw = self.rentabilidad_controller.obtener_datos_matriz_rentabilidad(fecha_inicio_str, fecha_fin_str)
            if isinstance(rentabilidad_raw, tuple):
                rentabilidad_res = rentabilidad_raw[0]
            else:
                rentabilidad_res = rentabilidad_raw
                
            bcg_matrix = rentabilidad_res.get('data', {}) if rentabilidad_res.get('success') else {}
        except Exception as e:
            logger.error(f"Error obteniendo matriz rentabilidad: {e}")
            bcg_matrix = {}

        return {
            "kpis_financieros": kpis,
            "evolucion_ingresos": evolucion_ingresos,
            "descomposicion_costos": descomposicion,
            "ingresos_vs_egresos": ingresos_vs_egresos,
            "evolucion_costos_fijos": evolucion_costos_fijos,
            "bcg_matrix": bcg_matrix
        }

    def _fill_time_series_gaps(self, data_dict, start_date, end_date, frequency='day'):
        labels = []
        values = []
        
        current = start_date
        if frequency == 'month':
            current = current.replace(day=1)
            end_align = end_date.replace(day=1)
            
            while current <= end_align:
                key = current.strftime('%Y-%m')
                labels.append(key)
                values.append(data_dict.get(key, 0.0))
                next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
                current = next_month
        else: 
            while current <= end_date:
                key = current.strftime('%Y-%m-%d')
                labels.append(key)
                values.append(data_dict.get(key, 0.0))
                current += timedelta(days=1)
                
        return labels, values

    def _obtener_evolucion_financiera_comparativa(self, fecha_inicio, fecha_fin, contexto):
        freq = 'month' if contexto == 'ano' else 'day'
        bucket_fmt = '%Y-%m' if freq == 'month' else '%Y-%m-%d'

        estados_ventas = [
            estados.OV_COMPLETADO, estados.OV_LISTO_PARA_ENTREGA, estados.OV_EN_TRANSITO,
            estados.OV_EN_PROCESO, estados.OV_ITEM_ALISTADO, estados.OV_PLANIFICADA
        ]
        
        ventas_res = self.pedido_model.get_ingresos_en_periodo(fecha_inicio.strftime('%Y-%m-%d'), fecha_fin.strftime('%Y-%m-%d'), estados_filtro=estados_ventas)
        data_ventas = ventas_res.get('data', []) if ventas_res.get('success') else []

        ventas_map = defaultdict(float)
        caja_map = defaultdict(float)
        
        ids_parciales = []
        mapa_fechas_parciales = {} 

        for p in data_ventas:
            if not p.get('fecha_solicitud'): continue
            dt = datetime.fromisoformat(p['fecha_solicitud'])
            key = dt.strftime(bucket_fmt)
            
            precio = float(p.get('precio_orden') or 0)
            ventas_map[key] += precio
            
            estado_pago = p.get('estado_pago', '').lower()
            if estado_pago == 'pagado':
                caja_map[key] += precio
            elif estado_pago == 'pagado parcialmente':
                ids_parciales.append(p['id'])
                mapa_fechas_parciales[p['id']] = key

        if ids_parciales:
            from app.models.pago import PagoModel
            pago_model = PagoModel()
            try:
                pagos_res = pago_model.db.table('pagos').select('id_pedido, monto')\
                    .in_('id_pedido', ids_parciales)\
                    .eq('estado', 'verificado')\
                    .execute()
                if pagos_res.data:
                    for pg in pagos_res.data:
                        pid = pg['id_pedido']
                        if pid in mapa_fechas_parciales:
                            key = mapa_fechas_parciales[pid]
                            caja_map[key] += float(pg['monto'])
            except Exception as e:
                logger.error(f"Error sumando parciales en grafica: {e}")

        filled_labels, filled_ventas = self._fill_time_series_gaps(dict(ventas_map), fecha_inicio, fecha_fin, freq)
        _, filled_caja = self._fill_time_series_gaps(dict(caja_map), fecha_inicio, fecha_fin, freq)

        display_labels = []
        for l in filled_labels:
            if freq == 'month':
                dt = datetime.strptime(l, "%Y-%m")
                display_labels.append(dt.strftime("%b"))
            else:
                dt = datetime.strptime(l, "%Y-%m-%d")
                display_labels.append(dt.strftime("%d/%m"))

        insight = "Flujos alineados."
        total_ventas = sum(filled_ventas)
        total_caja = sum(filled_caja)
        if total_ventas > total_caja * 1.2:
            insight = "Las ventas superan significativamente al flujo de caja real (Crédito)."
        elif total_caja > total_ventas:
            insight = "El flujo de caja supera a las ventas del periodo (Cobros atrasados)."

        return {
            "categories": display_labels,
            "series": [
                {"name": "Ventas (Devengado)", "data": filled_ventas},
                {"name": "Flujo Caja (Percibido)", "data": filled_caja}
            ],
            "insight": insight,
            "tooltip": "Comparativa entre lo facturado (Ventas) y lo realmente cobrado (Flujo de Caja)."
        }

    def _obtener_descomposicion_costos_con_detalle(self, fecha_inicio, fecha_fin, gastos_fijos_total):
        ordenes_res = self.orden_produccion_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        data_ordenes = ordenes_res.get('data', []) if ordenes_res.get('success') else []
        
        producto_ids = [op['producto_id'] for op in data_ordenes if op.get('producto_id')]
        costos_cache = self._preparar_cache_costos_por_productos(list(set(producto_ids)))

        costo_mp = 0.0
        horas_prod = 0.0
        
        for op in data_ordenes:
            if pid := op.get('producto_id'):
                u_cost = self._get_costo_producto(pid, costos_cache)
                costo_mp += u_cost * float(op.get('cantidad_producida', 0))
            if op.get('fecha_inicio') and op.get('fecha_fin'):
                horas_prod += (datetime.fromisoformat(op['fecha_fin']) - datetime.fromisoformat(op['fecha_inicio'])).total_seconds() / 3600

        costo_mo = horas_prod * 15.0 
        
        costos_fijos_res = self.costo_fijo_model.find_all(filters={'activo': True})
        detalle_fijos = []
        total_mensual_fijos = 0.0
        
        if costos_fijos_res.get('success'):
            for cf in costos_fijos_res.get('data', []):
                monto = float(cf.get('monto_mensual', 0))
                total_mensual_fijos += monto
                detalle_fijos.append({"name": cf.get('nombre_costo', 'Varios'), "value": monto})

        dias = max((fecha_fin - fecha_inicio).days, 1)
        factor = dias / 30.0
        
        detalle_fijos_ajustado = [{"name": d["name"], "value": round(d["value"] * factor, 2)} for d in detalle_fijos]

        main_data = [
            {"name": "Materia Prima", "value": round(costo_mp, 2)},
            {"name": "Mano de Obra", "value": round(costo_mo, 2)},
            {"name": "Costos Fijos", "value": round(gastos_fijos_total, 2), "drilldown": True} 
        ]
        
        total = costo_mp + costo_mo + gastos_fijos_total
        pct_fijos = (gastos_fijos_total / total * 100) if total > 0 else 0
        insight = f"Los costos fijos representan el {pct_fijos:.1f}% de los egresos básicos totales."

        return {
            "data": main_data,
            "drilldown_data": detalle_fijos_ajustado,
            "insight": insight,
            "tooltip": "Desglose de los principales egresos. Haga clic en 'Costos Fijos' para ver su composición."
        }

    def _obtener_evolucion_ingresos_vs_egresos(self, fecha_inicio, fecha_fin, contexto, monto_mensual_fijos):
        periodo_req = 'mensual' if contexto == 'ano' else 'diario'
        res_cvg = self.obtener_costo_vs_ganancia(fecha_inicio.strftime('%Y-%m-%d'), fecha_fin.strftime('%Y-%m-%d'), periodo=periodo_req)
        
        raw_labels = res_cvg.get('labels', [])
        ingresos_map = dict(zip(raw_labels, res_cvg.get('ingresos', [])))
        costos_var_map = dict(zip(raw_labels, res_cvg.get('costos', [])))
        
        freq = 'month' if contexto == 'ano' else 'day'
        
        filled_labels, filled_ingresos = self._fill_time_series_gaps(ingresos_map, fecha_inicio, fecha_fin, freq)
        _, filled_costos_var = self._fill_time_series_gaps(costos_var_map, fecha_inicio, fecha_fin, freq)
        
        fixed_cost_per_bucket = monto_mensual_fijos
        if freq == 'day':
            fixed_cost_per_bucket = monto_mensual_fijos / 30.0
        
        filled_egresos = []
        for cv in filled_costos_var:
            filled_egresos.append(round(cv + fixed_cost_per_bucket, 2))
            
        total_ing = sum(filled_ingresos)
        total_egr = sum(filled_egresos)
        diff = total_ing - total_egr
        insight = "Los egresos superan a los ingresos en este periodo."
        if diff > 0:
            insight = "El balance es positivo, con ingresos superando a los egresos básicos."

        display_labels = []
        for l in filled_labels:
            if freq == 'month':
                dt = datetime.strptime(l, "%Y-%m")
                display_labels.append(dt.strftime("%b"))
            else:
                dt = datetime.strptime(l, "%Y-%m-%d")
                display_labels.append(dt.strftime("%d/%m"))

        return {
            "categories": display_labels,
            "series": [
                {"name": "Ingresos", "data": filled_ingresos},
                {"name": "Egresos Básicos", "data": filled_egresos}
            ],
            "insight": insight,
            "tooltip": "Comparativa de Ingresos vs Egresos Básicos (Variable + Fijos). Nota: Los egresos son aproximados."
        }

    def _obtener_evolucion_costos_fijos(self, fecha_inicio, fecha_fin, contexto, monto_actual):
        freq = 'month' if contexto == 'ano' else 'day'
        bucket_fmt = '%Y-%m' if freq == 'month' else '%Y-%m-%d'

        data_map = defaultdict(float)
        
        try:
            costos_res = self.costo_fijo_model.find_all()
            costos = costos_res.get('data', []) if costos_res.get('success') else []
            
            historial_res = self.costo_fijo_model.db.table('historial_costos_fijos').select('*').execute()
            all_historial = historial_res.data if historial_res.data else []
            
            historial_map = defaultdict(list)
            for h in all_historial:
                historial_map[h['costo_fijo_id']].append(h)
            
            for cid in historial_map:
                historial_map[cid].sort(key=lambda x: x['fecha_cambio'])

            fechas_bucket = []
            current = fecha_inicio
            if freq == 'month':
                current = current.replace(day=1)
                end_align = fecha_fin.replace(day=1)
                while current <= end_align:
                    fechas_bucket.append(current)
                    next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
                    current = next_month
            else:
                while current <= fecha_fin:
                    fechas_bucket.append(current)
                    current += timedelta(days=1)

            for date_point in fechas_bucket:
                key = date_point.strftime(bucket_fmt)
                
                total_dia = 0.0
                
                for costo in costos:
                    cid = costo['id']
                    cambios = historial_map.get(cid, [])
                    
                    try:
                        valor_vigente = float(costo.get('monto_mensual') or 0.0) 
                    except:
                        valor_vigente = 0.0
                    
                    point_dt = datetime.combine(date_point, datetime.min.time())
                    
                    if cambios:
                        try:
                            primer_cambio_dt = datetime.fromisoformat(cambios[0]['fecha_cambio'].replace('Z', '+00:00')).replace(tzinfo=None)
                            
                            if point_dt < primer_cambio_dt:
                                valor_vigente = float(cambios[0].get('monto_anterior') or 0.0)
                            else:
                                for cambio in cambios:
                                    cambio_dt = datetime.fromisoformat(cambio['fecha_cambio'].replace('Z', '+00:00')).replace(tzinfo=None)
                                    if cambio_dt <= point_dt:
                                        valor_vigente = float(cambio.get('monto_nuevo') or 0.0)
                                    else:
                                        break
                        except Exception as e:
                            logger.error(f"Error procesando historial de costo {cid}: {e}")
                    
                    if valor_vigente > 1_000_000_000_000: 
                        logger.warning(f"Valor de costo fijo {cid} anormalmente alto detectado y omitido: {valor_vigente}")
                        valor_vigente = 0.0

                    total_dia += valor_vigente

                val_final = total_dia if freq == 'month' else (total_dia / 30.0)
                data_map[key] = val_final

        except Exception as e:
            logger.error(f"Error calculando historial costos fijos para gráfico: {e}")
            val_per_unit = monto_actual if freq == 'month' else (monto_actual / 30.0)
            return self._obtener_evolucion_costos_fijos_fallback(fecha_inicio, fecha_fin, freq, val_per_unit)

        labels = sorted(data_map.keys())
        values = [round(data_map[k], 2) for k in labels]
        
        display_labels = []
        for l in labels:
            if freq == 'month':
                dt = datetime.strptime(l, "%Y-%m")
                display_labels.append(dt.strftime("%b"))
            else:
                dt = datetime.strptime(l, "%Y-%m-%d")
                display_labels.append(dt.strftime("%d/%m"))

        insight = "Los costos fijos se mantienen estables."
        if len(values) > 1:
            first = values[0]
            last = values[-1]
            if last > first * 1.05:
                insight = "Se observa un aumento en la estructura de costos fijos."
            elif last < first * 0.95:
                insight = "Los costos fijos han disminuido en el periodo."

        return {
            "categories": display_labels,
            "values": values,
            "insight": insight,
            "tooltip": "Evolución histórica calculada basada en los registros de cambio de valor."
        }

    def _obtener_evolucion_costos_fijos_fallback(self, fecha_inicio, fecha_fin, freq, val_per_unit):
        labels = []
        values = []
        current = fecha_inicio
        
        if freq == 'month':
            current = current.replace(day=1)
            end_align = fecha_fin.replace(day=1)
            while current <= end_align:
                labels.append(current.strftime("%b"))
                values.append(round(val_per_unit, 2))
                current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        else:
            while current <= fecha_fin:
                labels.append(current.strftime("%d/%m"))
                values.append(round(val_per_unit, 2))
                current += timedelta(days=1)

        return {
            "categories": labels,
            "values": values,
            "insight": "Proyección basada en valores actuales (sin historial disponible).",
            "tooltip": "Evolución proyectada del total de costos fijos."
        }
        
    # --- CATEGORÍA: INVENTARIO ---
    def obtener_datos_inventario(self, semana=None, mes=None, ano=None, top_n=5, **kwargs): 
        top_n = top_n if top_n else 5
        
        insumos_criticos_res = self.reporte_stock_controller.obtener_insumos_stock_critico()
        insumos_criticos_list = insumos_criticos_res.get('data', []) if insumos_criticos_res.get('success') else []
        insumos_criticos_count = len(insumos_criticos_list)

        productos_cero_res = self.reporte_stock_controller.obtener_productos_sin_stock()
        productos_cero_list = productos_cero_res.get('data', []) if productos_cero_res.get('success') else []
        productos_cero_count = len(productos_cero_list)

        insumos_venc_res = self.reporte_stock_controller.obtener_lotes_insumos_a_vencer(dias_horizonte=30)
        insumos_venc_list = insumos_venc_res.get('data', []) if insumos_venc_res.get('success') else []
        insumos_venc_count = len(insumos_venc_list)
        
        productos_venc_res = self.reporte_stock_controller.obtener_lotes_productos_a_vencer(dias_horizonte=30)
        productos_venc_list = productos_venc_res.get('data', []) if productos_venc_res.get('success') else []
        productos_venc_count = len(productos_venc_list)

        kpis_inventario = {
            "insumos_criticos": insumos_criticos_count,
            "productos_cero": productos_cero_count,
            "productos_proximos_vencimiento": productos_venc_count,
            "insumos_proximos_vencimiento": insumos_venc_count
        }

        antiguedad_insumos = self.obtener_antiguedad_stock('insumo')
        antiguedad_productos = self.obtener_antiguedad_stock('producto')

        valor_insumos_res = self.reporte_stock_controller.obtener_valor_stock_insumos(top_n=top_n)
        valor_insumos_data = valor_insumos_res.get('data', {}) if valor_insumos_res.get('success') else {}
        valor_insumos_chart = {
            "labels": list(valor_insumos_data.keys()), 
            "data": list(valor_insumos_data.values())
        }
        
        valor_productos_res = self.reporte_stock_controller.obtener_valor_stock_productos(top_n=top_n)
        valor_productos_data = valor_productos_res.get('data', {}) if valor_productos_res.get('success') else {}
        valor_productos_chart = {
            "labels": list(valor_productos_data.keys()),
            "data": list(valor_productos_data.values())
        }

        comp_insumos_res = self.reporte_stock_controller.obtener_composicion_stock_insumos()
        comp_insumos_data = comp_insumos_res.get('data', {}) if comp_insumos_res.get('success') else {}
        comp_insumos_chart = {
            "labels": list(comp_insumos_data.keys()),
            "data": list(comp_insumos_data.values())
        }

        dist_estado_res = self.reporte_stock_controller.obtener_distribucion_stock_por_estado_producto()
        dist_estado_data = dist_estado_res.get('data', {}) if dist_estado_res.get('success') else {}
        dist_estado_chart = {
            "labels": list(dist_estado_data.keys()),
            "data": list(dist_estado_data.values())
        }

        cobertura_res = self.reporte_stock_controller.obtener_cobertura_stock(dias_periodo=30)
        cobertura_data_raw = cobertura_res.get('data', {}) if cobertura_res.get('success') else {}
        cobertura_chart = {
            "labels": list(cobertura_data_raw.keys())[:10],
            "data": list(cobertura_data_raw.values())[:10]
        }
        low_coverage = [k for k, v in cobertura_data_raw.items() if v < 7]
        if low_coverage:
            insight_cobertura = f"Existen {len(low_coverage)} productos con cobertura crítica (menos de 7 días). Se sugiere revisar el plan de producción."
        else:
            insight_cobertura = "La mayoría de los productos tienen una cobertura saludable superior a una semana."
        cobertura_chart['insight'] = insight_cobertura

        total_val_ins = sum(valor_insumos_data.values())
        if valor_insumos_chart['labels']:
            top_ins = valor_insumos_chart['labels'][0]
            pct_ins = (valor_insumos_chart['data'][0] / total_val_ins * 100) if total_val_ins else 0
            valor_insumos_chart['insight'] = f"'{top_ins}' concentra el {pct_ins:.1f}% del valor total del inventario de insumos."
        else:
            valor_insumos_chart['insight'] = "No hay datos de valorización."

        total_val_prod = sum(valor_productos_data.values())
        if valor_productos_chart['labels']:
            top_prod = valor_productos_chart['labels'][0]
            pct_prod = (valor_productos_chart['data'][0] / total_val_prod * 100) if total_val_prod else 0
            valor_productos_chart['insight'] = f"El producto '{top_prod}' representa el {pct_prod:.1f}% del valor del stock terminado."
        else:
            valor_productos_chart['insight'] = "No hay datos de valorización."

        comp_labels = comp_insumos_chart['labels']
        comp_vals = comp_insumos_chart['data']
        if comp_labels:
            max_idx = comp_vals.index(max(comp_vals))
            comp_insumos_chart['insight'] = f"La categoría '{comp_labels[max_idx]}' es la predominante en volumen de almacenamiento."
        else:
            comp_insumos_chart['insight'] = "Sin datos de composición."

        dist_labels = dist_estado_chart['labels']
        dist_vals = dist_estado_chart['data']
        if dist_labels:
            max_idx = dist_vals.index(max(dist_vals))
            dist_estado_chart['insight'] = f"La mayor parte del stock se encuentra en estado '{dist_labels[max_idx]}'."
        else:
            dist_estado_chart['insight'] = "Sin datos de estado."

        usage_res = self.reporte_produccion_controller.obtener_top_insumos(top_n=1000)
        usage_map = usage_res.get('data', {}) if usage_res.get('success') else {}

        for insumo in insumos_criticos_list:
            nombre = insumo.get('nombre')
            insumo['usage_score'] = usage_map.get(nombre, 0)
        
        insumos_criticos_list.sort(key=lambda x: (x.get('usage_score', 0), -x.get('stock_actual', 0)), reverse=True)

        stock_critico_chart = {
            "labels": [x['nombre'] for x in insumos_criticos_list[:top_n]],
            "actual": [max(0, x['stock_actual']) for x in insumos_criticos_list[:top_n]], # <-- FIXED: Prevent negative stock
            "minimo": [x['stock_min'] for x in insumos_criticos_list[:top_n]]
        }
        if insumos_criticos_count > 0:
            stock_critico_chart['insight'] = f"Se han detectado {insumos_criticos_count} insumos por debajo de su stock mínimo de seguridad."
        else:
            stock_critico_chart['insight'] = "Todos los insumos mantienen niveles de stock saludables."
        
        today = date.today()
        
        def get_days_left(date_str):
            try:
                d = datetime.fromisoformat(str(date_str)).date() if 'T' in str(date_str) else datetime.strptime(str(date_str), '%Y-%m-%d').date()
                return (d - today).days
            except: return 0

        insumos_venc_processed = sorted([
            {'nombre': x.get('nombre_insumo') or x.get('insumo_nombre') or x.get('insumos_catalogo', {}).get('nombre') or x.get('nombre', 'N/A'), 'dias': get_days_left(x.get('f_vencimiento') or x.get('fecha_vencimiento'))}
            for x in insumos_venc_list
        ], key=lambda k: k['dias'])[:top_n]

        productos_venc_processed = sorted([
            {'nombre': x.get('producto', {}).get('nombre') or x.get('producto_nombre') or x.get('nombre', 'N/A'), 'dias': get_days_left(x.get('fecha_vencimiento'))}
            for x in productos_venc_list
        ], key=lambda k: k['dias'])[:top_n]

        insumos_venc_chart = {
            "labels": [x['nombre'] for x in insumos_venc_processed],
            "data": [x['dias'] for x in insumos_venc_processed]
        }
        if insumos_venc_list:
            min_days = min([x['dias'] for x in insumos_venc_processed]) if insumos_venc_processed else 0
            insumos_venc_chart['insight'] = f"Se detectaron {len(insumos_venc_list)} lotes próximos a vencer. El más urgente vence en {min_days} días."
        else:
            insumos_venc_chart['insight'] = "No hay alertas de vencimiento inminente en insumos."
        
        productos_venc_chart = {
            "labels": [x['nombre'] for x in productos_venc_processed],
            "data": [x['dias'] for x in productos_venc_processed]
        }
        if productos_venc_list:
            min_days = min([x['dias'] for x in productos_venc_processed]) if productos_venc_processed else 0
            productos_venc_chart['insight'] = f"Se detectaron {len(productos_venc_list)} lotes de producto terminados próximos a vencer."
        else:
            productos_venc_chart['insight'] = "El stock de productos terminados tiene fechas de vencimiento lejanas."

        return {
            "meta": {"top_n": top_n},
            "kpis_inventario": kpis_inventario,
            "antiguedad_stock_insumos": antiguedad_insumos,
            "antiguedad_stock_productos": antiguedad_productos,
            "valor_stock_insumos_chart": valor_insumos_chart,
            "valor_stock_productos_chart": valor_productos_chart,
            "composicion_stock_insumos_chart": comp_insumos_chart,
            "distribucion_estado_productos_chart": dist_estado_chart,
            "cobertura_chart": cobertura_chart,
            "stock_critico_chart": stock_critico_chart,
            "insumos_vencimiento_chart": insumos_venc_chart,
            "productos_vencimiento_chart": productos_venc_chart
        }
        
    # --- MÉTODOS DE CÁLCULO OPTIMIZADOS ---

    def _preparar_cache_operaciones(self, receta_ids: list):
        if not receta_ids: return {}
        operaciones_res = self.receta_model.get_operaciones_by_receta_ids(list(set(receta_ids)))
        if not operaciones_res.get('success'): return {}
        
        cache = defaultdict(list)
        for op in operaciones_res.get('data', []):
            cache[op['receta_id']].append(op)
        return cache

    def _calcular_carga_op_con_cache(self, op_data: dict, cache_operaciones: dict) -> Decimal:
        carga_total, receta_id, cantidad = Decimal(0), op_data.get('receta_id'), Decimal(op_data.get('cantidad_planificada', 0))
        if not receta_id or cantidad <= 0 or receta_id not in cache_operaciones:
            return carga_total

        for op_step in cache_operaciones[receta_id]:
            t_prep = Decimal(op_step.get('tiempo_preparacion', 0))
            t_ejec_unit = Decimal(op_step.get('tiempo_ejecucion_unitario', 0))
            carga_total += t_prep + (t_ejec_unit * cantidad)
        return carga_total
    
    def _calcular_carga_op(self, orden_produccion_data):
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

    def _calcular_oee(self, fecha_inicio, fecha_fin):
        ordenes_res = self.orden_produccion_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        ordenes_en_periodo = ordenes_res.get('data', [])
        if not ordenes_en_periodo:
            return {"valor": 0, "disponibilidad": 0, "rendimiento": 0, "calidad": 0}

        tiempo_produccion_real = sum(
            (datetime.fromisoformat(op['fecha_fin']) - datetime.fromisoformat(op['fecha_inicio'])).total_seconds()
            for op in ordenes_en_periodo if op.get('fecha_fin') and op.get('fecha_inicio')
        )

        paros_operario_res = self.registro_paro_model.find_all(filters={
            'fecha_inicio_gte': fecha_inicio.isoformat(), 
            'fecha_inicio_lte': fecha_fin.isoformat()
        })
        tiempo_paradas_operario = 0
        if paros_operario_res.get('success'):
            for paro in paros_operario_res.get('data', []):
                if paro.get('fecha_fin') and paro.get('fecha_inicio'):
                    tiempo_paradas_operario += (datetime.fromisoformat(paro['fecha_fin']) - datetime.fromisoformat(paro['fecha_inicio'])).total_seconds()
        
        bloqueos_linea_res = self.bloqueo_capacidad_model.find_all(filters={
            'fecha_gte': fecha_inicio.isoformat(), 
            'fecha_lte': fecha_fin.isoformat()
        })
        tiempo_paradas_linea_minutos = 0
        if bloqueos_linea_res.get('success'):
            tiempo_paradas_linea_minutos = sum(b.get('minutos_bloqueados', 0) for b in bloqueos_linea_res.get('data', []))
        
        tiempo_paradas_total = tiempo_paradas_operario + (tiempo_paradas_linea_minutos * 60)

        tiempo_operativo = tiempo_produccion_real - tiempo_paradas_total

        receta_ids = [op['receta_id'] for op in ordenes_en_periodo if op.get('receta_id')]
        cache_operaciones = self._preparar_cache_operaciones(receta_ids)
        tiempo_produccion_planificado = sum(
            self._calcular_carga_op_con_cache(op, cache_operaciones) for op in ordenes_en_periodo
        ) * 60 

        disponibilidad = tiempo_operativo / tiempo_produccion_real if tiempo_produccion_real > 0 else 0

        rendimiento = float(tiempo_produccion_planificado) / tiempo_operativo if tiempo_operativo > 0 else 0

        produccion_real = sum(float(op.get('cantidad_producida', 0)) for op in ordenes_en_periodo)
        
        # --- CÁLCULO DE CALIDAD ---
        cantidad_rechazada = 0
        cantidad_desperdicio = 0
        op_ids = [op['id'] for op in ordenes_en_periodo]
        
        if op_ids:
            try:
                # 1. Calcular Desperdicios (Mermas) de estas OPs
                # self.registro_desperdicio_insumo_model mapea a mes_kanban.registros_desperdicio
                # Usamos schema explícito para asegurar que consultamos la tabla correcta
                desperdicios_res = self.registro_desperdicio_insumo_model.db.schema('mes_kanban').table('registros_desperdicio')\
                    .select('cantidad')\
                    .in_('orden_produccion_id', op_ids)\
                    .execute()
                
                if desperdicios_res.data:
                    cantidad_desperdicio = sum(float(d.get('cantidad', 0)) for d in desperdicios_res.data)

                # 2. Calcular Rechazos de Calidad (Lotes Completos Rechazados/Cuarentena)
                # Primero obtener los lotes asociados a estas OPs que fueron rechazados
                # Buscamos en control_calidad_productos los registros con decision negativa
                rechazos_cc_res = self.control_calidad_producto_model.db.table('control_calidad_productos')\
                    .select('lote_producto_id')\
                    .in_('orden_produccion_id', op_ids)\
                    .in_('decision_final', ['RECHAZADO', 'CUARENTENA', 'NO APTO'])\
                    .execute()
                
                lotes_rechazados_ids = [r['lote_producto_id'] for r in rechazos_cc_res.data] if rechazos_cc_res.data else []
                
                if lotes_rechazados_ids:
                    # Sumar la cantidad inicial de estos lotes
                    lotes_res = self.lote_producto_model.db.table('lotes_productos')\
                        .select('cantidad_inicial')\
                        .in_('id_lote', lotes_rechazados_ids)\
                        .execute()
                    
                    if lotes_res.data:
                        cantidad_rechazada = sum(float(l.get('cantidad_inicial', 0)) for l in lotes_res.data)

            except Exception as e:
                logger.error(f"Error calculando calidad OEE: {e}")

        # Calidad = Unidades Buenas / Total Producido
        # Unidades Buenas = Total Producido - (Desperdicios + Rechazos)
        unidades_malas = cantidad_rechazada + cantidad_desperdicio
        unidades_buenas = max(produccion_real - unidades_malas, 0)
        
        calidad = unidades_buenas / produccion_real if produccion_real > 0 else 0

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
            filtros = {
                'fecha_meta_desde': fecha_inicio.isoformat(),
                'fecha_meta_hasta': fecha_fin.isoformat()
            }
            ordenes_planificadas_res = self.orden_produccion_model.get_all_enriched(filtros=filtros)
            ordenes_planificadas = ordenes_planificadas_res.get('data', [])
            total_ordenes_planificadas = len(ordenes_planificadas)
            ordenes_completadas_a_tiempo = 0

            for i, orden in enumerate(ordenes_planificadas):
                estado = orden.get('estado')
                fecha_fin_str = orden.get('fecha_fin')
                
                fecha_meta_str = orden.get('fecha_meta') 
                
                if estado == estados.OP_COMPLETADA and fecha_fin_str and fecha_meta_str:
                    fecha_fin_dt = datetime.fromisoformat(fecha_fin_str).date()
                    fecha_meta_dt = datetime.fromisoformat(fecha_meta_str).date()
                    if fecha_fin_dt <= fecha_meta_dt:
                        ordenes_completadas_a_tiempo += 1
            
            cumplimiento = (ordenes_completadas_a_tiempo / total_ordenes_planificadas) * 100 if total_ordenes_planificadas > 0 else 0
            return {"valor": round(cumplimiento, 2), "completadas_a_tiempo": ordenes_completadas_a_tiempo, "planificadas": total_ordenes_planificadas}
    
    def _calcular_tasa_desperdicio(self, fecha_inicio, fecha_fin):
        desperdicios_data_res = self.registro_desperdicio_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        desperdicios_data = desperdicios_data_res.get('data', [])
        cantidad_desperdicio = sum([d.get('cantidad', 0) for d in desperdicios_data])
        
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
        lotes_aprobados_res = self.control_calidad_insumo_model.count_by_decision_in_date_range('APROBADO', fecha_inicio, fecha_fin)
        
        lotes_rechazados = lotes_rechazados_res.get('count', 0)
        lotes_aprobados = lotes_aprobados_res.get('count', 0)
        lotes_inspeccionados = lotes_rechazados + lotes_aprobados

        tasa = (lotes_rechazados / lotes_inspeccionados) * 100 if lotes_inspeccionados > 0 else 0
        return {"valor": round(tasa, 2), "rechazados": lotes_rechazados, "recibidos": lotes_inspeccionados}

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

        date_format = '%Y-%m'
        if periodo in ['semanal', 'diario']:
            date_format = '%Y-%m-%d'
        if periodo == 'mensual':
            date_format = '%Y-%m-%d'

        if isinstance(ingresos_res.get('data'), dict):
            return ingresos_res['data']
        else:
            processed_data = defaultdict(float)
            for ingreso in ingresos_res.get('data', []):
                 if not ingreso.get('fecha_solicitud'): continue
                 fecha_dt = datetime.fromisoformat(ingreso['fecha_solicitud'])
                 key = fecha_dt.strftime(date_format)
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

        date_format = '%Y-%m'
        if periodo in ['semanal', 'diario', 'mensual']:
            date_format = '%Y-%m-%d'

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
            key = fecha_op.strftime(date_format)
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
        
        costo_mo = horas_prod * 15 
        gastos_fijos = (5000 / 30) * (fecha_fin - fecha_inicio).days 

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
        categorias = {
            "0-30 días": {"count": 0, "quantity": 0.0},
            "31-60 días": {"count": 0, "quantity": 0.0},
            "61-90 días": {"count": 0, "quantity": 0.0},
            "+90 días": {"count": 0, "quantity": 0.0},
            "Sin fecha": {"count": 0, "quantity": 0.0}
        }
        
        def asignar_categoria(dias, cantidad):
            key = "+90 días"
            if 0 <= dias <= 30: key = "0-30 días"
            elif 31 <= dias <= 60: key = "31-60 días"
            elif 61 <= dias <= 90: key = "61-90 días"
            
            categorias[key]["count"] += 1
            categorias[key]["quantity"] += cantidad

        def procesar_lote(lote, fecha_key):
            cantidad = float(lote.get('cantidad', 0))
            fecha_str = lote.get(fecha_key)
            
            if not fecha_str:
                categorias["Sin fecha"]["count"] += 1
                categorias["Sin fecha"]["quantity"] += cantidad
                return

            try:
                # FIX: Check for format before parsing to avoid error
                if isinstance(fecha_str, str):
                    if 'T' in fecha_str:
                        dt = datetime.fromisoformat(fecha_str).date()
                    else:
                        dt = datetime.strptime(fecha_str[:10], '%Y-%m-%d').date()
                elif isinstance(fecha_str, (date, datetime)):
                    dt = fecha_str if isinstance(fecha_str, date) else fecha_str.date()
                else:
                    raise ValueError("Formato desconocido")

                antiguedad = (hoy - dt).days
                asignar_categoria(antiguedad, cantidad)
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parseando fecha '{fecha_str}': {e}")
                categorias["Sin fecha"]["count"] += 1
                categorias["Sin fecha"]["quantity"] += cantidad

        if tipo == 'insumo':
            lotes_res = self.insumo_inventario_model.get_all_lotes_for_view()
            if lotes_res.get('success'):
                for lote in lotes_res.get('data', []):
                    # InsumoInventarioModel maps created_at to fecha_ingreso
                    procesar_lote(lote, 'fecha_ingreso')

        else: 
            lotes_res = self.lote_producto_model.get_all_lotes_for_antiquity_view()
            if lotes_res.get('success'):
                for lote in lotes_res.get('data', []):
                    fecha_key = 'fecha_produccion' if lote.get('fecha_produccion') else 'fecha_fabricacion'
                    procesar_lote(lote, fecha_key)
            
        if categorias["Sin fecha"]["count"] == 0:
            del categorias["Sin fecha"]

        labels = list(categorias.keys())
        data_counts = [categorias[k]["count"] for k in labels]
        data_quantities = [categorias[k]["quantity"] for k in labels]
        
        total_lotes = sum(data_counts)
        if total_lotes > 0:
            top_category = max(categorias, key=lambda k: categorias[k]['count'])
            pct = (categorias[top_category]['count'] / total_lotes) * 100
            
            if top_category == "0-30 días":
                insight = f"El stock es mayormente reciente, con un {pct:.0f}% de los lotes ingresados en el último mes."
            elif top_category == "+90 días":
                insight = f"Atención: El {pct:.0f}% de los lotes tiene una antigüedad superior a 3 meses."
            else:
                insight = f"La mayor concentración de lotes ({pct:.0f}%) se encuentra en el rango de {top_category}."
        else:
            insight = "No hay lotes en inventario para analizar su antigüedad."

        return {
            "labels": labels,
            "data": data_counts,
            "quantities": data_quantities,
            "insight": insight
        }