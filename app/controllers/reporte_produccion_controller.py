from app.models.orden_produccion import OrdenProduccionModel
from app.models.reserva_insumo import ReservaInsumoModel
from app.models.insumo import InsumoModel
from app.models.producto import ProductoModel
from app.models.receta_ingrediente import RecetaIngredienteModel
from app.models.registro_desperdicio_model import RegistroDesperdicioModel
from app.models.registro_desperdicio_lote_insumo_model import RegistroDesperdicioLoteInsumoModel
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class ReporteProduccionController:
    def __init__(self):
        self.orden_produccion_model = OrdenProduccionModel()
        self.reserva_insumo_model = ReservaInsumoModel()
        self.insumo_model = InsumoModel()
        self.producto_model = ProductoModel()
        self.receta_ingrediente_model = RecetaIngredienteModel()
        self.registro_desperdicio_model = RegistroDesperdicioModel()
        self.registro_desperdicio_lote_insumo_model = RegistroDesperdicioLoteInsumoModel()

    def obtener_ordenes_por_estado(self):
        """
        Calcula el número de órdenes de producción por cada estado.
        OPTIMIZADO: Solo selecciona la columna 'estado'.
        """
        try:
            # Consulta directa y ligera para evitar timeouts con payloads grandes
            response = self.orden_produccion_model.db.table(
                self.orden_produccion_model.get_table_name()
            ).select('estado').execute()

            ordenes = response.data if response.data else []
            if not ordenes:
                return {'success': True, 'data': {}}

            # Contar los estados
            from collections import Counter
            conteo_estados = Counter(orden['estado'] for orden in ordenes)

            return {'success': True, 'data': dict(conteo_estados)}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def obtener_composicion_produccion(self):
        """
        Calcula la cantidad total a producir por cada producto.
        OPTIMIZADO: Solo selecciona 'cantidad_planificada' y el nombre del producto.
        """
        try:
            # Consulta optimizada: solo campos necesarios
            response = self.orden_produccion_model.db.table(
                self.orden_produccion_model.get_table_name()
            ).select(
                'cantidad_planificada, productos(nombre)'
            ).execute()

            ordenes = response.data if response.data else []
            if not ordenes:
                return {'success': True, 'data': {}}

            composicion = {}
            for orden in ordenes:
                # Extraer nombre del producto anidado
                producto_info = orden.get('productos')
                nombre_producto = producto_info.get('nombre') if producto_info else 'Desconocido'
                
                cantidad = orden.get('cantidad_planificada', 0)
                
                if nombre_producto in composicion:
                    composicion[nombre_producto] += cantidad
                else:
                    composicion[nombre_producto] = cantidad
            
            return {'success': True, 'data': composicion}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def obtener_top_insumos(self, top_n=5, fecha_inicio=None, fecha_fin=None):
        """
        Obtiene los N insumos más utilizados.
        """
        try:
            # Nota: Si esta consulta también es pesada, debería optimizarse para traer solo campos necesarios.
            # Por ahora, mantenemos la lógica pero vigilando.
            response = self.reserva_insumo_model.get_all_with_details()
            
            if not response.get('success'):
                return {'success': False, 'error': 'No se pudieron obtener las reservas de insumos.'}

            reservas = response.get('data', [])
            
            if fecha_inicio and fecha_fin:
                reservas_filtradas = []
                if isinstance(fecha_inicio, str):
                     fecha_inicio = datetime.fromisoformat(fecha_inicio)
                if isinstance(fecha_fin, str):
                     fecha_fin = datetime.fromisoformat(fecha_fin)
                     
                for r in reservas:
                    op_fecha_str = r.get('orden_produccion_fecha_inicio') or r.get('created_at')
                    if op_fecha_str:
                        try:
                            op_date = datetime.fromisoformat(op_fecha_str)
                            if fecha_inicio <= op_date <= fecha_fin:
                                reservas_filtradas.append(r)
                        except ValueError:
                            continue
                
                reservas = reservas_filtradas
            
            if not reservas:
                return {'success': True, 'data': {}}

            conteo_insumos = {}
            for reserva in reservas:
                nombre_insumo = reserva.get('insumo_nombre', 'Desconocido')
                cantidad = reserva.get('cantidad_reservada', 0)
                if nombre_insumo in conteo_insumos:
                    conteo_insumos[nombre_insumo] += cantidad
                else:
                    conteo_insumos[nombre_insumo] = cantidad

            from collections import Counter
            contador = Counter(conteo_insumos)
            top_insumos = dict(contador.most_common(top_n))

            return {'success': True, 'data': top_insumos}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def calcular_tiempo_ciclo_segundos(self, fecha_inicio=None, fecha_fin=None):
        """
        Retorna (promedio_segundos, cantidad_ordenes_validas).
        OPTIMIZADO: Solo selecciona fechas.
        """
        try:
            query = self.orden_produccion_model.db.table(
                self.orden_produccion_model.get_table_name()
            ).select('fecha_inicio, fecha_fin').eq('estado', 'COMPLETADA')

            if fecha_inicio:
                query = query.gte('fecha_fin', fecha_inicio.isoformat())
            if fecha_fin:
                query = query.lte('fecha_fin', fecha_fin.isoformat())

            response = query.execute()
            ordenes = response.data if response.data else []

            if not ordenes:
                return 0, 0

            total_diferencia = timedelta()
            ordenes_validas = 0

            for orden in ordenes:
                fecha_inicio_str = orden.get('fecha_inicio')
                fecha_fin_str = orden.get('fecha_fin')

                if fecha_inicio_str and fecha_fin_str:
                    try:
                        fi = datetime.fromisoformat(fecha_inicio_str)
                        ff = datetime.fromisoformat(fecha_fin_str)
                        total_diferencia += ff - fi
                        ordenes_validas += 1
                    except ValueError:
                        continue
            
            if ordenes_validas == 0:
                return 0, 0
            
            promedio_segundos = total_diferencia.total_seconds() / ordenes_validas
            return promedio_segundos, ordenes_validas
            
        except Exception:
            return 0, 0

    def obtener_tiempo_ciclo_promedio(self, fecha_inicio=None, fecha_fin=None):
        """
        Calcula el tiempo promedio desde el inicio hasta el fin de las órdenes completadas.
        """
        try:
            promedio_segundos, ordenes_validas = self.calcular_tiempo_ciclo_segundos(fecha_inicio, fecha_fin)
            
            if ordenes_validas == 0:
                return {'success': True, 'data': {'dias': 0, 'horas': 0, 'minutos': 0}}

            dias = int(promedio_segundos // 86400)
            rem_segundos = promedio_segundos % 86400
            horas = int(rem_segundos // 3600)
            rem_segundos %= 3600
            minutos = int(rem_segundos // 60)

            return {'success': True, 'data': {'dias': dias, 'horas': horas, 'minutos': minutos}}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def obtener_tiempo_ciclo_horas(self, fecha_inicio=None, fecha_fin=None):
        """
        Calcula el tiempo promedio de ciclo en HORAS (float).
        """
        try:
            promedio_segundos, ordenes_validas = self.calcular_tiempo_ciclo_segundos(fecha_inicio, fecha_fin)
            
            promedio_horas = promedio_segundos / 3600
            return {'success': True, 'data': {'valor': promedio_horas, 'ordenes': ordenes_validas}}
            
        except Exception as e:
             return {'success': False, 'error': str(e)}

    def obtener_consumo_insumos_por_tiempo(self, fecha_inicio, fecha_fin, periodo='mensual'):
        """
        Calcula la evolución del consumo de insumos a lo largo del tiempo.
        """
        try:
            response = self.reserva_insumo_model.get_all_with_details_in_date_range(fecha_inicio, fecha_fin)
            
            if not response.get('success'):
                 return {'success': False, 'error': 'No se pudieron obtener los consumos.'}
            
            reservas = response.get('data', [])
            data_agregada = {}
            
            for r in reservas:
                fecha_str = r.get('created_at')
                cantidad = r.get('cantidad_reservada', 0)
                
                if not fecha_str: continue
                
                try:
                    dt = datetime.fromisoformat(fecha_str)
                    if periodo == 'mensual':
                        key = dt.strftime('%Y-%m')
                    elif periodo == 'semanal':
                        key = dt.strftime('%Y-W%U')
                    else:
                        key = dt.strftime('%Y-%m-%d')
                        
                    data_agregada[key] = data_agregada.get(key, 0) + float(cantidad)
                except ValueError:
                    continue

            labels = sorted(data_agregada.keys())
            values = [data_agregada[k] for k in labels]
            
            return {
                'success': True, 
                'data': {
                    'labels': labels,
                    'data': values
                }
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def obtener_produccion_por_tiempo(self, periodo='semanal'):
        """
        Agrupa las órdenes de producción completadas por semana o mes.
        OPTIMIZADO: Solo selecciona 'fecha_fin' de las órdenes completadas.
        """
        try:
            response = self.orden_produccion_model.db.table(
                self.orden_produccion_model.get_table_name()
            ).select('fecha_fin').eq('estado', 'COMPLETADA').execute()

            ordenes = response.data if response.data else []
            if not ordenes:
                return {'success': True, 'data': {}}

            produccion_por_tiempo = {}
            for orden in ordenes:
                fecha_fin_str = orden.get('fecha_fin')
                if fecha_fin_str:
                    try:
                        fecha_fin = datetime.fromisoformat(fecha_fin_str)
                        if periodo == 'semanal':
                            llave = fecha_fin.strftime('%Y-%U')
                        else: # mensual
                            llave = fecha_fin.strftime('%Y-%m')
                        
                        if llave in produccion_por_tiempo:
                            produccion_por_tiempo[llave] += 1
                        else:
                            produccion_por_tiempo[llave] = 1
                    except ValueError:
                        continue
            
            sorted_produccion = dict(sorted(produccion_por_tiempo.items()))

            return {'success': True, 'data': sorted_produccion}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def obtener_eficiencia_consumo_insumos(self, top_n=15, product_id=None):
        """
        Calcula la eficiencia de consumo de insumos centrada en la eficiencia real.
        Estándar (Planificado para Output) = Cantidad Real Producida * Cantidad Receta.
        Real = Estándar + Desperdicios (RegistroDesperdicioLoteInsumoModel con OP ID).
        """
        try:
            # 1. Obtener OPs recientes completadas
            op_response = self.orden_produccion_model.find_all(
                filters={'estado': 'COMPLETADA'}, 
                order_by='fecha_fin.desc',
                limit=50
            )
            
            if not op_response.get('success'):
                return {'success': False, 'error': 'No se pudieron obtener órdenes.'}
            
            ops = op_response.get('data', [])
            if not ops:
                return {'success': True, 'data': {'chart': [], 'narrative': 'No hay datos de producción recientes.', 'products': []}}

            op_ids = [op['id'] for op in ops]
            
            # 2. Obtener desperdicios de insumos vinculados a estas OPs
            # Usamos el nuevo modelo RegistroDesperdicioLoteInsumoModel
            desperdicios = []
            if op_ids:
                waste_res = self.registro_desperdicio_lote_insumo_model.db.table('registros_desperdicio_lote_insumo')\
                    .select('*, motivo:motivos_desperdicio(descripcion)')\
                    .in_('orden_produccion_id', op_ids)\
                    .execute()
                
                if waste_res.data:
                    desperdicios = waste_res.data

            # Agrupar desperdicios por OP y por Insumo
            waste_map = defaultdict(lambda: defaultdict(float)) # op_id -> insumo_id -> cantidad
            waste_reasons = defaultdict(lambda: defaultdict(int)) # insumo_id -> motivo -> count

            # Mapa auxiliar para obtener insumo_id desde lote_insumo_id si fuera necesario
            # Asumimos que podemos obtener el insumo a través del registro o inferirlo de la OP,
            # pero el registro de desperdicio suele tener lote_insumo_id.
            # Necesitamos saber qué "insumo_id" (catalogo) corresponde a ese lote para agrupar con la receta.
            # Haremos una consulta para resolver lote_insumo_id -> insumo_id
            
            lote_ids = list(set([w['lote_insumo_id'] for w in desperdicios if w.get('lote_insumo_id')]))
            lote_to_insumo_map = {}
            if lote_ids:
                lotes_res = self.insumo_inventario_model.db.table('insumos_inventario')\
                    .select('id_lote, id_insumo')\
                    .in_('id_lote', [str(lid) for lid in lote_ids])\
                    .execute()
                if lotes_res.data:
                    for l in lotes_res.data:
                        lote_to_insumo_map[l['id_lote']] = l['id_insumo']
                        lote_to_insumo_map[str(l['id_lote'])] = l['id_insumo']

            for w in desperdicios:
                op_id = w.get('orden_produccion_id')
                lid = w.get('lote_insumo_id')
                insumo_id = lote_to_insumo_map.get(lid) or lote_to_insumo_map.get(str(lid))
                
                if op_id and insumo_id:
                    cantidad = float(w.get('cantidad', 0))
                    waste_map[op_id][insumo_id] += cantidad
                    
                    motivo_desc = 'Sin motivo'
                    if w.get('motivo'):
                        motivo_desc = w.get('motivo', {}).get('descripcion', 'Sin motivo')
                    waste_reasons[insumo_id][motivo_desc] += 1

            # 3. Calcular Estándar vs Real por Insumo y Producto
            data_map = defaultdict(lambda: defaultdict(lambda: {'estandar': 0, 'real': 0, 'insumo_id': None}))
            products_set = set()

            for op in ops:
                if not op.get('receta_id'): continue
                op_id = op['id']
                
                prod_nombre = op.get('producto_nombre', 'Producto Desconocido') 
                if 'producto_nombre' not in op and op.get('producto_id'):
                    prod = self.producto_model.find_by_id(op['producto_id'])
                    if prod.get('success'):
                         prod_nombre = prod['data'].get('nombre')
                
                products_set.add(prod_nombre)

                if product_id and str(op.get('producto_id')) != str(product_id) and prod_nombre != product_id: 
                    continue

                qty_op_prod = float(op.get('cantidad_producida', 0)) # Cantidad Real Producida
                
                ingredientes_res = self.receta_ingrediente_model.find_by_receta_id_with_insumo(op['receta_id'])
                ingredientes = ingredientes_res.get('data', [])
                
                for ing in ingredientes:
                    insumo_data = ing.get('insumo', {})
                    insumo_nombre = insumo_data.get('nombre', 'Insumo Desconocido')
                    insumo_id = ing.get('insumo_id')
                    cantidad_unitaria_receta = float(ing.get('cantidad', 0))
                    
                    # Consumo Estándar (Lo que se debió usar para la producción real)
                    consumo_estandar = qty_op_prod * cantidad_unitaria_receta
                    
                    # Consumo Real = Estándar + Desperdicio registrado para esta OP/Insumo
                    desperdicio_op = waste_map[op_id][insumo_id]
                    consumo_real = consumo_estandar + desperdicio_op
                    
                    entry = data_map[prod_nombre][insumo_nombre]
                    entry['estandar'] += consumo_estandar
                    entry['real'] += consumo_real
                    entry['insumo_id'] = insumo_id

            # 5. Formatear datos para el gráfico
            chart_data = []
            
            for prod, insumos in data_map.items():
                for ins_nom, datos in insumos.items():
                    std = datos['estandar']
                    real = datos['real']
                    
                    if std == 0 and real == 0: continue
                    
                    # Desviación: (Real - Estándar) / Estándar
                    # Positiva = Ineficiencia (Usé más de lo necesario)
                    # Negativa = Ahorro (Raro si Real >= Estándar, pero posible si hubo merma negativa o corrección)
                    # Como Real = Std + Waste, Real siempre >= Std (salvo errores de datos), por lo que desviación >= 0
                    
                    if std > 0:
                        desviacion_pct = ((real - std) / std) * 100
                    else:
                        desviacion_pct = 100.0 # Todo fue desperdicio si no había estándar
                    
                    chart_data.append({
                        'producto': prod,
                        'insumo': ins_nom,
                        'planificado': round(std, 2), # Mapeado a 'planificado' para compatibilidad frontend, pero es 'Estándar'
                        'real': round(real, 2),
                        'desviacion': round(desviacion_pct, 2),
                        'diff_absoluta': abs(real - std)
                    })
            
            chart_data.sort(key=lambda x: x['diff_absoluta'], reverse=True)
            
            if not product_id:
                chart_data = chart_data[:top_n]
            
            # 6. Generar Narrativa
            narrative = ""
            if chart_data:
                top_item = chart_data[0]
                
                if top_item['desviacion'] <= 0.1:
                    narrative = "Excelente eficiencia. El consumo de insumos se ajusta a los estándares de producción."
                else:
                    insumo_critico_id = None
                    for prod, insumos in data_map.items():
                        if top_item['insumo'] in insumos:
                            insumo_critico_id = insumos[top_item['insumo']]['insumo_id']
                            break
                    
                    reasons_text = ""
                    if insumo_critico_id and insumo_critico_id in waste_reasons:
                        # Find top reason
                        sorted_reasons = sorted(waste_reasons[insumo_critico_id].items(), key=lambda x: x[1], reverse=True)
                        if sorted_reasons:
                            top_reason = sorted_reasons[0]
                            reasons_text = f" La principal causa de pérdida reportada fue '{top_reason[0]}'."
                    
                    narrative = (
                        f"Se detectó una ineficiencia en el uso de **{top_item['insumo']}** para **{top_item['producto']}**, "
                        f"consumiendo un **{top_item['desviacion']}%** más de lo estipulado por receta. "
                        f"{reasons_text}"
                    )
            else:
                narrative = "No hay datos suficientes para el análisis."

            return {
                'success': True, 
                'data': {
                    'chart': chart_data,
                    'narrative': narrative,
                    'products': sorted(list(products_set))
                }
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def obtener_costos_produccion_plan_vs_real(self, periodo='semanal'):
        """
        Compara el costo planificado vs real de producción agrupado por tiempo.
        Planificado = Cantidad OP * Costo Receta.
        Real = Cantidad Producida * Costo Receta + Desperdicio.
        Rellena huecos de fechas con 0 para continuidad.
        """
        try:
            # 1. Definir rango de fechas y formato
            hoy = datetime.now()
            
            if periodo == 'anual':
                # Últimos 12 meses
                fecha_inicio = (hoy.replace(day=1) - timedelta(days=365)).replace(day=1)
                delta_step = 'month'
                fmt_key = '%Y-%m'
            elif periodo == 'mensual':
                # Últimos 6 meses (o un rango razonable para ver meses)
                fecha_inicio = (hoy.replace(day=1) - timedelta(days=180)).replace(day=1)
                delta_step = 'month'
                fmt_key = '%Y-%m'
            else: # semanal (por defecto)
                # Últimas 12 semanas
                fecha_inicio = hoy - timedelta(weeks=12)
                # Ajustar al lunes de esa semana
                fecha_inicio = fecha_inicio - timedelta(days=fecha_inicio.weekday())
                delta_step = 'week'
                fmt_key = '%Y-W%U'
            
            filters = {'estado': 'COMPLETADA'}
            filters['fecha_fin_gte'] = fecha_inicio.isoformat()
            
            op_response = self.orden_produccion_model.find_all(filters)
            ops = op_response.get('data', [])
            
            # 2. Generar mapa continuo de fechas inicializado en 0
            costos_por_tiempo = {}
            current_date = fecha_inicio
            while current_date <= hoy:
                key = current_date.strftime(fmt_key)
                costos_por_tiempo[key] = {'planificado': 0.0, 'real': 0.0}
                
                if delta_step == 'month':
                    # Avanzar al próximo mes
                    next_month = (current_date.replace(day=28) + timedelta(days=4)).replace(day=1)
                    current_date = next_month
                elif delta_step == 'week':
                    current_date += timedelta(weeks=1)
                else:
                    current_date += timedelta(days=1)

            # 3. Obtener Desperdicios en el mismo rango
            waste_res = self.registro_desperdicio_model.get_all_in_date_range(fecha_inicio, hoy)
            desperdicios = waste_res.get('data', []) if waste_res.get('success') else []

            # Mapa de costos de insumos
            insumos_res = self.insumo_model.find_all()
            costos_insumos = {}
            if insumos_res.get('success'):
                for ins in insumos_res.get('data', []):
                    costos_insumos[ins['id']] = float(ins.get('costo', 0) or ins.get('precio', 0) or ins.get('precio_unitario', 0))

            # 4. Calcular Costos Agrupados por Tiempo
            # A. Costos Planificados y Reales (Base Producida)
            for op in ops:
                fecha_fin = op.get('fecha_fin')
                if not fecha_fin: continue
                
                try:
                    dt = datetime.fromisoformat(fecha_fin)
                    key = dt.strftime(fmt_key)
                    
                    if key not in costos_por_tiempo: continue 

                    receta_id = op.get('receta_id')
                    qty_op_plan = float(op.get('cantidad_planificada', 0))
                    qty_op_prod = float(op.get('cantidad_producida', 0))
                    
                    # Calcular costo receta
                    ingredientes_res = self.receta_ingrediente_model.find_by_receta_id_with_insumo(receta_id)
                    costo_receta_unitario = 0
                    for ing in ingredientes_res.get('data', []):
                        ins_id = ing.get('insumo_id')
                        cant_ing = float(ing.get('cantidad', 0))
                        costo_u = costos_insumos.get(ins_id, 0)
                        costo_receta_unitario += cant_ing * costo_u
                    
                    total_plan_op = qty_op_plan * costo_receta_unitario
                    total_real_op_base = qty_op_prod * costo_receta_unitario
                    
                    costos_por_tiempo[key]['planificado'] += total_plan_op
                    costos_por_tiempo[key]['real'] += total_real_op_base

                except ValueError:
                    continue

            # B. Sumar Costos de Desperdicio al Real
            for w in desperdicios:
                fecha_reg = w.get('fecha_registro') or w.get('created_at')
                if not fecha_reg: continue
                
                try:
                    dt = datetime.fromisoformat(fecha_reg)
                    key = dt.strftime(fmt_key)
                    
                    if key in costos_por_tiempo:
                        ins_id = w.get('insumo_id')
                        cant = float(w.get('cantidad', 0))
                        costo_u = costos_insumos.get(ins_id, 0)
                        costo_waste = cant * costo_u
                        
                        costos_por_tiempo[key]['real'] += costo_waste
                    
                except ValueError:
                    continue

            # Ordenar
            sorted_keys = sorted(costos_por_tiempo.keys())
            
            # Formatear etiquetas para el gráfico
            labels_display = []
            for k in sorted_keys:
                if delta_step == 'month':
                    # Ej: 2023-11 -> Nov 2023
                    d = datetime.strptime(k, '%Y-%m')
                    labels_display.append(d.strftime('%b %Y'))
                elif delta_step == 'week':
                    # Ej: 2023-W45 -> Sem 45
                    labels_display.append(f"Sem {k.split('-W')[1]}")
                else:
                    labels_display.append(k)

            result_data = {
                'labels': labels_display, # Etiquetas legibles
                'raw_labels': sorted_keys, # Etiquetas crudas por si acaso
                'planificado': [round(costos_por_tiempo[k]['planificado'], 2) for k in sorted_keys],
                'real': [round(costos_por_tiempo[k]['real'], 2) for k in sorted_keys]
            }
            
            return {'success': True, 'data': result_data}

        except Exception as e:
            return {'success': False, 'error': str(e)}
