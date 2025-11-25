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

    def obtener_eficiencia_consumo_insumos(self, fecha_inicio_str=None, fecha_fin_str=None):
        try:
            # 1. Determinar el rango de fechas
            fecha_fin = datetime.now() if not fecha_fin_str else datetime.fromisoformat(fecha_fin_str)
            fecha_inicio = fecha_fin - timedelta(days=30) if not fecha_inicio_str else datetime.fromisoformat(fecha_inicio_str)

            # 2. Obtener todas las órdenes de producción completadas en el rango con datos de producto
            ops_response = self.orden_produccion_model.find_all_with_producto_in_date_range(fecha_inicio, fecha_fin, estado='COMPLETADA')
            if not ops_response.get('success'):
                return {'success': False, 'error': 'No se pudieron obtener órdenes de producción.'}
            
            ops = ops_response.get('data', [])
            if not ops:
                return {'success': True, 'data': {'data_agregada': [], 'data_detalle': {}}}

            op_ids = [op['id'] for op in ops]

            # 3. Obtener todos los desperdicios de insumos para esas OPs
            desperdicios_response = self.registro_desperdicio_lote_insumo_model.get_by_op_ids(op_ids)
            desperdicios_data = desperdicios_response.get('data', [])
            
            # Mapear desperdicios por OP y por Insumo para fácil acceso
            desperdicios_map = defaultdict(lambda: defaultdict(float))
            for d in desperdicios_data:
                desperdicios_map[d['orden_produccion_id']][d['insumo_id']] += float(d.get('cantidad', 0))

            # 4. Obtener todas las recetas e ingredientes de una vez
            recetas_response = self.receta_ingrediente_model.get_all_with_insumo_details()
            ingredientes_map = defaultdict(list)
            if recetas_response.get('success'):
                for ing in recetas_response.get('data', []):
                    ingredientes_map[ing['receta_id']].append(ing)

            # 5. Procesar los datos
            consumo_por_producto = defaultdict(lambda: {'planificado': 0.0, 'real': 0.0})
            detalle_por_producto = defaultdict(list)

            for op in ops:
                receta_id = op.get('receta_id')
                if not receta_id:
                    continue
                
                cantidad_producida = float(op.get('cantidad_producida', 0))
                producto_nombre = op.get('producto_nombre', 'Desconocido')

                consumo_op_planificado = 0.0
                consumo_op_real = 0.0
                
                ingredientes = ingredientes_map.get(receta_id, [])
                for ing in ingredientes:
                    cantidad_receta = float(ing.get('cantidad', 0))
                    insumo_id = ing.get('insumo_id')
                    
                    # Consumo planificado (teórico) para la producción real
                    consumo_teorico = cantidad_producida * cantidad_receta
                    
                    # Consumo real = teórico + desperdicio
                    desperdicio = desperdicios_map[op['id']][insumo_id]
                    consumo_real_insumo = consumo_teorico + desperdicio
                    
                    consumo_op_planificado += consumo_teorico
                    consumo_op_real += consumo_real_insumo

                # Acumular para el gráfico agregado
                consumo_por_producto[producto_nombre]['planificado'] += consumo_op_planificado
                consumo_por_producto[producto_nombre]['real'] += consumo_op_real
                
                # Guardar para la tabla de detalle
                detalle_por_producto[producto_nombre].append({
                    'orden_id': op.get('id'),
                    'documento_op': op.get('documento_op', f"OP-{op.get('id')}")[:10],
                    'fecha_fin': op.get('fecha_fin'),
                    'cantidad_planificada': op.get('cantidad_planificada'),
                    'cantidad_producida': cantidad_producida,
                    'consumo_planificado': round(consumo_op_planificado, 2),
                    'consumo_real': round(consumo_op_real, 2)
                })

            # Formatear la salida para el gráfico principal
            data_agregada = [
                {
                    'producto': prod,
                    'planificado': round(valores['planificado'], 2),
                    'real': round(valores['real'], 2)
                }
                for prod, valores in consumo_por_producto.items()
            ]

            return {
                'success': True,
                'data': {
                    'data_agregada': data_agregada,
                    'data_detalle': dict(detalle_por_producto)
                }
            }

        except Exception as e:
            logger.error(f"Error en obtener_eficiencia_consumo_insumos: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def obtener_costos_produccion_plan_vs_real(self, periodo='semanal'):
        # Esta función ya no es necesaria y la dejo comentada para limpieza.
        return {'success': True, 'data': {}}
