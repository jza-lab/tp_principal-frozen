from app.models.orden_produccion import OrdenProduccionModel
from app.models.reserva_insumo import ReservaInsumoModel
from app.models.insumo import InsumoModel
from app.models.producto import ProductoModel
from datetime import datetime, timedelta

class ReporteProduccionController:
    def __init__(self):
        self.orden_produccion_model = OrdenProduccionModel()
        self.reserva_insumo_model = ReservaInsumoModel()
        self.insumo_model = InsumoModel()
        self.producto_model = ProductoModel()

    def obtener_ordenes_por_estado(self):
        """
        Calcula el número de órdenes de producción por cada estado.
        """
        try:
            response = self.orden_produccion_model.get_all_enriched()
            if not response.get('success'):
                return {'success': False, 'error': 'No se pudieron obtener las órdenes de producción.'}

            ordenes = response.get('data', [])
            if not ordenes:
                return {'success': True, 'data': {}}

            # Contar los estados
            from collections import Counter
            conteo_estados = Counter(orden['estado'] for orden in ordenes)

            return {'success': True, 'data': dict(conteo_estados)}

        except Exception as e:
            # Idealmente, aquí se registraría el error en un log
            return {'success': False, 'error': str(e)}

    def obtener_composicion_produccion(self):
        """
        Calcula la cantidad total a producir por cada producto.
        """
        try:
            response = self.orden_produccion_model.get_all_enriched()
            if not response.get('success'):
                return {'success': False, 'error': 'No se pudieron obtener las órdenes de producción.'}

            ordenes = response.get('data', [])
            if not ordenes:
                return {'success': True, 'data': {}}

            composicion = {}
            for orden in ordenes:
                nombre_producto = orden.get('producto_nombre', 'Desconocido')
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
        Si se pasan fechas, filtra por la fecha de inicio de la orden de producción asociada,
        para reflejar mejor el uso real en el periodo.
        """
        try:
            # Obtenemos TODAS las reservas con detalles (incluyendo OP)
            # Nota: Si el volumen de datos es muy grande, esto debería optimizarse con una query más específica.
            response = self.reserva_insumo_model.get_all_with_details()
            
            if not response.get('success'):
                return {'success': False, 'error': 'No se pudieron obtener las reservas de insumos.'}

            reservas = response.get('data', [])
            
            # Filtrado en memoria por fecha de la Orden de Producción
            # Usamos fecha_fin (finalización) para alinear con la producción completada, 
            # o fecha_inicio para la producción iniciada.
            # Para insumos, fecha_inicio de la OP es un buen proxy de cuando se "usan".
            
            if fecha_inicio and fecha_fin:
                reservas_filtradas = []
                # Convertir a datetime para comparar si son strings
                if isinstance(fecha_inicio, str):
                     fecha_inicio = datetime.fromisoformat(fecha_inicio)
                if isinstance(fecha_fin, str):
                     fecha_fin = datetime.fromisoformat(fecha_fin)
                     
                # Asegurar que son dates para comparacion simple (o datetime completo)
                # Asumimos que vienen como date o datetime
                
                for r in reservas:
                    # Priorizamos filtrar por la fecha de la OP
                    op_fecha_str = r.get('orden_produccion_fecha_inicio') or r.get('created_at')
                    if op_fecha_str:
                        try:
                            # Manejar formato ISO
                            op_date = datetime.fromisoformat(op_fecha_str)
                            # Comparar
                            if fecha_inicio <= op_date <= fecha_fin:
                                reservas_filtradas.append(r)
                        except ValueError:
                            continue
                
                reservas = reservas_filtradas
            
            if not reservas:
                return {'success': True, 'data': {}}

            # Contar la cantidad reservada por cada insumo
            conteo_insumos = {}
            for reserva in reservas:
                nombre_insumo = reserva.get('insumo_nombre', 'Desconocido')
                cantidad = reserva.get('cantidad_reservada', 0)
                if nombre_insumo in conteo_insumos:
                    conteo_insumos[nombre_insumo] += cantidad
                else:
                    conteo_insumos[nombre_insumo] = cantidad

            # Ordenar por cantidad y tomar el top N
            from collections import Counter
            contador = Counter(conteo_insumos)
            top_insumos = dict(contador.most_common(top_n))

            return {'success': True, 'data': top_insumos}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def calcular_tiempo_ciclo_segundos(self, fecha_inicio=None, fecha_fin=None):
        """
        Retorna (promedio_segundos, cantidad_ordenes_validas).
        Permite filtrar por rango de fechas de finalización.
        """
        filters = {'estado': 'COMPLETADA'}
        if fecha_inicio:
            filters['fecha_fin_gte'] = fecha_inicio.isoformat()
        if fecha_fin:
            filters['fecha_fin_lte'] = fecha_fin.isoformat()

        response = self.orden_produccion_model.find_all(filters)
        if not response.get('success'):
            return 0, 0

        ordenes = response.get('data', [])
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

    def obtener_tiempo_ciclo_promedio(self, fecha_inicio=None, fecha_fin=None):
        """
        Calcula el tiempo promedio desde el inicio hasta el fin de las órdenes completadas (Global o filtrado).
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
        Usado por KPIs que requieren un valor numérico único.
        """
        try:
            promedio_segundos, ordenes_validas = self.calcular_tiempo_ciclo_segundos(fecha_inicio, fecha_fin)
            
            promedio_horas = promedio_segundos / 3600
            return {'success': True, 'data': {'valor': promedio_horas, 'ordenes': ordenes_validas}}
            
        except Exception as e:
             return {'success': False, 'error': str(e)}

    def obtener_consumo_insumos_por_tiempo(self, fecha_inicio, fecha_fin, periodo='mensual'):
        """
        Calcula la evolución del consumo de insumos (cantidad reservada) a lo largo del tiempo.
        """
        try:
             # Usamos get_all_with_details_in_date_range que filtra por created_at
            response = self.reserva_insumo_model.get_all_with_details_in_date_range(fecha_inicio, fecha_fin)
            
            if not response.get('success'):
                 return {'success': False, 'error': 'No se pudieron obtener los consumos.'}
            
            reservas = response.get('data', [])
            data_agregada = {}
            
            # Inicializar claves de tiempo (opcional, o dejar dinámico)
            
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

            # Ordenar por fecha
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

    # def obtener_eficiencia_produccion(self):
    #     """
    #     Calcula la eficiencia de producción comparando la cantidad planificada con la producida.
    #     """
    #     try:
    #         response = self.orden_produccion_model.find_all({'estado': 'COMPLETADA'})
    #         if not response.get('success'):
    #             return {'success': False, 'error': 'No se pudieron obtener las órdenes de producción completadas.'}
    #
    #         ordenes = response.get('data', [])
    #         if not ordenes:
    #             return {'success': True, 'data': []}
    #
    #         eficiencia_por_orden = []
    #         for orden in ordenes:
    #             planificada = orden.get('cantidad_planificada', 0)
    #             producida = orden.get('cantidad_producida_real', 0) # Asumiendo este campo
    #             if planificada > 0:
    #                 eficiencia = (producida / planificada) * 100
    #                 eficiencia_por_orden.append({
    #                     'codigo_op': orden.get('codigo', 'N/A'),
    #                     'producto_nombre': orden.get('producto_nombre', 'N/A'),
    #                     'eficiencia': round(eficiencia, 2)
    #                 })
    #         
    #         return {'success': True, 'data': eficiencia_por_orden}
    #
    #     except Exception as e:
    #         return {'success': False, 'error': str(e)}

    def obtener_produccion_por_tiempo(self, periodo='semanal'):
        """
        Agrupa las órdenes de producción completadas por semana o mes.
        """
        try:
            response = self.orden_produccion_model.find_all({'estado': 'COMPLETADA'})
            if not response.get('success'):
                return {'success': False, 'error': 'No se pudieron obtener las órdenes de producción completadas.'}

            ordenes = response.get('data', [])
            if not ordenes:
                return {'success': True, 'data': {}}

            produccion_por_tiempo = {}
            for orden in ordenes:
                fecha_fin_str = orden.get('fecha_fin')
                if fecha_fin_str:
                    try:
                        fecha_fin = datetime.fromisoformat(fecha_fin_str)
                        if periodo == 'semanal':
                            # Agrupar por el lunes de la semana
                            llave = fecha_fin.strftime('%Y-%U')
                        else: # mensual
                            llave = fecha_fin.strftime('%Y-%m')
                        
                        if llave in produccion_por_tiempo:
                            produccion_por_tiempo[llave] += 1
                        else:
                            produccion_por_tiempo[llave] = 1
                    except ValueError:
                        continue
            
            # Ordenar por fecha
            sorted_produccion = dict(sorted(produccion_por_tiempo.items()))

            return {'success': True, 'data': sorted_produccion}

        except Exception as e:
            return {'success': False, 'error': str(e)}
