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
from decimal import Decimal
from app.utils import estados
import logging

logger = logging.getLogger(__name__)

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

    def obtener_kpis_inventario(self, fecha_inicio_str, fecha_fin_str):
        if fecha_inicio_str:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        else:
            fecha_inicio = datetime.now() - timedelta(days=30)

        if fecha_fin_str:
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
        else:
            fecha_fin = datetime.now()
            
        kpis = {}
        
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
        tasa_desperdicio = self._calcular_tasa_desperdicio(fecha_inicio, fecha_fin)

        return {
            "oee": oee,
            "cumplimiento_plan": cumplimiento_plan,
            "tasa_desperdicio": tasa_desperdicio,
            "fecha_inicio": fecha_inicio.strftime('%Y-%m-%d'),
            "fecha_fin": fecha_fin.strftime('%Y-%m-%d')
        }

    def _calcular_carga_op(self, op_data: dict) -> Decimal:
        carga_total = Decimal(0)
        receta_id = op_data.get('receta_id')
        cantidad = Decimal(op_data.get('cantidad_planificada', 0))
        
        if not receta_id or cantidad <= 0:
            return carga_total

        operaciones_res = self.receta_model.obtener_operaciones_receta(receta_id)
        if not operaciones_res.get('success') or not operaciones_res.get('data'):
            return carga_total

        for op_step in operaciones_res['data']:
            t_prep = Decimal(op_step.get('tiempo_preparacion', 0))
            t_ejec_unit = Decimal(op_step.get('tiempo_ejecucion_unitario', 0))
            carga_total += t_prep + (t_ejec_unit * cantidad)
        return carga_total

    def _calcular_oee(self, fecha_inicio, fecha_fin):
        ordenes_en_periodo_res = self.orden_produccion_model.get_all_in_date_range(fecha_inicio, fecha_fin)
        ordenes_en_periodo = ordenes_en_periodo_res.get('data', [])
        
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
        rechazados_res = self.control_calidad_producto_model.count_by_decision_in_date_range('RECHAZADO', fecha_inicio, fecha_fin)
        aprobados_res = self.control_calidad_producto_model.count_by_decision_in_date_range('APROBADO', fecha_inicio, fecha_fin)
        
        unidades_rechazadas = rechazados_res.get('count', 0)
        unidades_aprobadas = aprobados_res.get('count', 0)
        unidades_inspeccionadas = unidades_rechazadas + unidades_aprobadas

        tasa = (unidades_rechazadas / unidades_inspeccionadas) * 100 if unidades_inspeccionadas > 0 else 0
        return {"valor": round(tasa, 2), "rechazadas": unidades_rechazadas, "inspeccionadas": unidades_inspeccionadas}

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

        lotes_rechazados = lotes_rechazados_res.get('count', 0)
        lotes_recibidos = lotes_recibidos_res.get('count', 0)
        
        tasa = (lotes_rechazados / lotes_recibidos) * 100 if lotes_recibidos > 0 else 0
        return {"valor": round(tasa, 2), "rechazados": lotes_rechazados, "recibidos": lotes_recibidos}

    def obtener_kpis_comercial(self, fecha_inicio, fecha_fin):
        kpis = {}
        
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

            if total_valor_res['success'] and num_pedidos_res['success']:
                total_valor = total_valor_res['total_valor']
                num_pedidos = num_pedidos_res['count']
                valor_promedio = total_valor / num_pedidos if num_pedidos > 0 else 0
                kpis['valor_promedio_pedido'] = {"valor": round(valor_promedio, 2), "total_valor": total_valor, "num_pedidos": num_pedidos}
            else:
                 kpis['valor_promedio_pedido'] = {"valor": 0, "total_valor": 0, "num_pedidos": 0}
        except Exception as e:
            kpis['valor_promedio_pedido'] = {"valor": 0, "total_valor": 0, "num_pedidos": 0}
            
        return kpis