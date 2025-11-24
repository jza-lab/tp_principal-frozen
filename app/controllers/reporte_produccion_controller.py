from app.models.orden_produccion import OrdenProduccionModel
from app.models.reserva_insumo import ReservaInsumoModel
from app.models.insumo import InsumoModel
from app.models.producto import ProductoModel
from app.models.receta_ingrediente import RecetaIngredienteModel
from app.models.registro_desperdicio_model import RegistroDesperdicioModel
from datetime import datetime, timedelta
from collections import defaultdict

class ReporteProduccionController:
    def __init__(self):
        self.orden_produccion_model = OrdenProduccionModel()
        self.reserva_insumo_model = ReservaInsumoModel()
        self.insumo_model = InsumoModel()
        self.producto_model = ProductoModel()
        self.receta_ingrediente_model = RecetaIngredienteModel()
        self.registro_desperdicio_model = RegistroDesperdicioModel()

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
        Calcula la eficiencia de consumo de insumos comparando lo planificado vs lo real.
        Real = Planificado + Desperdicio.
        Retorna datos para el gráfico y una narrativa.
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
            
            # 2. Buscar desperdicios en el rango de fechas de estas OPs
            fechas_inicio = [op['fecha_inicio'] for op in ops if op.get('fecha_inicio')]
            fechas_fin = [op['fecha_fin'] for op in ops if op.get('fecha_fin')]
            
            desperdicios = []
            if fechas_inicio and fechas_fin:
                min_fecha = min(fechas_inicio)
                max_fecha = max(fechas_fin)
                if isinstance(min_fecha, str): min_fecha = datetime.fromisoformat(min_fecha)
                if isinstance(max_fecha, str): max_fecha = datetime.fromisoformat(max_fecha)
                
                waste_res = self.registro_desperdicio_model.get_all_in_date_range(min_fecha, max_fecha)
                if waste_res.get('success'):
                    desperdicios = waste_res.get('data', [])

            waste_by_insumo = defaultdict(float)
            waste_reasons = defaultdict(lambda: defaultdict(int)) 

            for w in desperdicios:
                insumo_id = w.get('insumo_id')
                if insumo_id:
                    cantidad = float(w.get('cantidad', 0))
                    waste_by_insumo[insumo_id] += cantidad
                    motivo = w.get('motivo_desperdicio', {}).get('descripcion', 'Sin motivo')
                    waste_reasons[insumo_id][motivo] += 1

            # 3. Calcular Planificado por Insumo y Producto
            data_map = defaultdict(lambda: defaultdict(lambda: {'planificado': 0, 'real': 0, 'insumo_id': None}))
            products_set = set()

            for op in ops:
                if not op.get('receta_id'): continue
                
                prod_nombre = op.get('producto_nombre', 'Producto Desconocido') 
                if 'producto_nombre' not in op:
                    if op.get('producto_id'):
                        prod = self.producto_model.find_by_id(op['producto_id'])
                        if prod.get('success'):
                             prod_nombre = prod['data'].get('nombre')
                
                products_set.add(prod_nombre)

                if product_id and str(op.get('producto_id')) != str(product_id) and prod_nombre != product_id: 
                    continue

                qty_op = float(op.get('cantidad_planificada', 0))
                
                ingredientes_res = self.receta_ingrediente_model.find_by_receta_id_with_insumo(op['receta_id'])
                ingredientes = ingredientes_res.get('data', [])
                
                for ing in ingredientes:
                    insumo_data = ing.get('insumo', {})
                    insumo_nombre = insumo_data.get('nombre', 'Insumo Desconocido')
                    insumo_id = ing.get('insumo_id')
                    cantidad_unitaria = float(ing.get('cantidad', 0))
                    
                    total_planificado = qty_op * cantidad_unitaria
                    
                    entry = data_map[prod_nombre][insumo_nombre]
                    entry['planificado'] += total_planificado
                    entry['insumo_id'] = insumo_id

            # 4. Asignar desperdicio a los insumos planificados
            total_planned_by_insumo = defaultdict(float)
            for prod, insumos in data_map.items():
                for ins_nom, datos in insumos.items():
                    total_planned_by_insumo[datos['insumo_id']] += datos['planificado']
            
            for prod, insumos in data_map.items():
                for ins_nom, datos in insumos.items():
                    planned = datos['planificado']
                    ins_id = datos['insumo_id']
                    
                    waste_amount = 0
                    if ins_id in waste_by_insumo and total_planned_by_insumo[ins_id] > 0:
                        ratio = planned / total_planned_by_insumo[ins_id]
                        waste_amount = waste_by_insumo[ins_id] * ratio
                    
                    datos['real'] = planned + waste_amount

            # 5. Formatear datos para el gráfico
            chart_data = []
            
            for prod, insumos in data_map.items():
                for ins_nom, datos in insumos.items():
                    plan = datos['planificado']
                    real = datos['real']
                    
                    if plan == 0: continue
                    
                    # Avoid near-zero floating point errors
                    if abs(real - plan) < 0.0001:
                        real = plan
                        desviacion_pct = 0.0
                    else:
                        desviacion_pct = ((real - plan) / plan) * 100
                    
                    chart_data.append({
                        'producto': prod,
                        'insumo': ins_nom,
                        'planificado': round(plan, 2),
                        'real': round(real, 2),
                        'desviacion': round(desviacion_pct, 2),
                        'diff_absoluta': abs(real - plan)
                    })
            
            chart_data.sort(key=lambda x: x['diff_absoluta'], reverse=True)
            
            if not product_id:
                chart_data = chart_data[:top_n]
            
            # 6. Generar Narrativa
            narrative = ""
            if chart_data:
                top_item = chart_data[0]
                
                if top_item['desviacion'] == 0.0:
                    narrative = "Excelente gestión. No se registraron desperdicios ni desviaciones significativas en los insumos analizados para el periodo."
                else:
                    insumo_critico_id = None
                    # Re-search ID needed for reasons (inefficient but safe)
                    for prod, insumos in data_map.items():
                        if top_item['insumo'] in insumos:
                            insumo_critico_id = insumos[top_item['insumo']]['insumo_id']
                            break
                    
                    reasons_text = ""
                    if insumo_critico_id and insumo_critico_id in waste_reasons:
                        top_reason = max(waste_reasons[insumo_critico_id].items(), key=lambda x: x[1])
                        reasons_text = f" La causa más frecuente de desperdicio reportada fue '{top_reason[0]}'."
                    
                    narrative = (
                        f"El insumo con mayor desviación es **{top_item['insumo']}** utilizado en **{top_item['producto']}**, "
                        f"con un excedente del **{top_item['desviacion']}%** sobre lo planificado. "
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
        Planificado = Cantidad OP * Costo Receta (aprox sum ingrediente * costo).
        Real = Planificado + (Desperdicio * Costo Insumo).
        """
        try:
            # 1. Obtener OPs Completadas
            filters = {'estado': 'COMPLETADA'}
            # Limitar a un rango razonable (e.g., último año o según periodo)
            # Aquí simplificamos trayendo las últimas 100 o filtrando por fecha si se pasara argumento.
            # Asumimos 'últimos 6 meses' por defecto para el gráfico.
            fecha_limite = datetime.now() - timedelta(days=180)
            filters['fecha_fin_gte'] = fecha_limite.isoformat()
            
            op_response = self.orden_produccion_model.find_all(filters)
            ops = op_response.get('data', [])
            
            if not ops:
                return {'success': True, 'data': {}}

            # 2. Obtener Desperdicios en el mismo rango
            waste_res = self.registro_desperdicio_model.get_all_in_date_range(fecha_limite, datetime.now())
            desperdicios = waste_res.get('data', []) if waste_res.get('success') else []

            # Mapa de costos de insumos (Optimización: cargar todos los insumos una vez)
            # InsumoModel no tiene un get_all_costs fácil, usaremos un cache simple si es posible
            # O iterar. Para hacerlo bien, asumiremos un costo promedio si no tenemos acceso directo rapido.
            # Mejor opción: Consultar insumos y crear mapa {id: costo}
            insumos_res = self.insumo_model.find_all()
            costos_insumos = {}
            if insumos_res.get('success'):
                for ins in insumos_res.get('data', []):
                    # Asumimos campo 'costo' o 'precio'. Si no existe, 0.
                    costos_insumos[ins['id']] = float(ins.get('costo', 0) or ins.get('precio', 0))

            # 3. Calcular Costos Agrupados por Tiempo
            costos_por_tiempo = defaultdict(lambda: {'planificado': 0.0, 'real': 0.0})

            # A. Costos Planificados (OPs)
            for op in ops:
                fecha_fin = op.get('fecha_fin')
                if not fecha_fin: continue
                
                try:
                    dt = datetime.fromisoformat(fecha_fin)
                    if periodo == 'semanal':
                        key = dt.strftime('%Y-W%U')
                    elif periodo == 'mensual':
                        key = dt.strftime('%Y-%m')
                    else: # diario
                        key = dt.strftime('%Y-%m-%d')
                    
                    # Costo Planificado de esta OP
                    # Idealmente: Receta.get_costo(). Si no, calcular sum(ing * cost).
                    receta_id = op.get('receta_id')
                    qty_op = float(op.get('cantidad_planificada', 0))
                    
                    # Calcular costo receta al vuelo (podría ser lento, caching recomendado)
                    # Simplificación: Usar un costo estimado promedio si es muy pesado, 
                    # pero intentaremos calcularlo bien.
                    ingredientes_res = self.receta_ingrediente_model.find_by_receta_id_with_insumo(receta_id)
                    costo_receta_unitario = 0
                    for ing in ingredientes_res.get('data', []):
                        ins_id = ing.get('insumo_id')
                        cant_ing = float(ing.get('cantidad', 0))
                        costo_u = costos_insumos.get(ins_id, 0)
                        costo_receta_unitario += cant_ing * costo_u
                    
                    total_plan_op = qty_op * costo_receta_unitario
                    
                    costos_por_tiempo[key]['planificado'] += total_plan_op
                    # El real empieza igual al planificado (base), luego sumamos desperdicio
                    costos_por_tiempo[key]['real'] += total_plan_op

                except ValueError:
                    continue

            # B. Sumar Costos de Desperdicio al Real
            for w in desperdicios:
                fecha_reg = w.get('fecha_registro') or w.get('created_at')
                if not fecha_reg: continue
                
                try:
                    dt = datetime.fromisoformat(fecha_reg)
                    if periodo == 'semanal':
                        key = dt.strftime('%Y-W%U')
                    elif periodo == 'mensual':
                        key = dt.strftime('%Y-%m')
                    else:
                        key = dt.strftime('%Y-%m-%d')
                    
                    ins_id = w.get('insumo_id')
                    cant = float(w.get('cantidad', 0))
                    costo_u = costos_insumos.get(ins_id, 0)
                    costo_waste = cant * costo_u
                    
                    # Sumar solo si la fecha cae en una clave existente (o crearla si queremos mostrar todo desperdicio)
                    # Si solo mostramos produccion, el desperdicio sin produccion quizas no deba salir, 
                    # pero para ser honestos, es costo real. Lo agregamos.
                    costos_por_tiempo[key]['real'] += costo_waste
                    
                except ValueError:
                    continue

            # Ordenar
            sorted_keys = sorted(costos_por_tiempo.keys())
            result_data = {
                'labels': sorted_keys,
                'planificado': [round(costos_por_tiempo[k]['planificado'], 2) for k in sorted_keys],
                'real': [round(costos_por_tiempo[k]['real'], 2) for k in sorted_keys]
            }
            
            return {'success': True, 'data': result_data}

        except Exception as e:
            return {'success': False, 'error': str(e)}
