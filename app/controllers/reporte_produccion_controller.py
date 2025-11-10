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

    def obtener_top_insumos(self, top_n=5):
        """
        Obtiene los N insumos más utilizados en todas las órdenes de producción.
        """
        try:
            response = self.reserva_insumo_model.get_all_with_details()
            if not response.get('success'):
                return {'success': False, 'error': 'No se pudieron obtener las reservas de insumos.'}

            reservas = response.get('data', [])
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

    def obtener_tiempo_ciclo_promedio(self):
        """
        Calcula el tiempo promedio desde el inicio hasta el fin de las órdenes completadas.
        """
        try:
            response = self.orden_produccion_model.find_all({'estado': 'COMPLETADA'})
            if not response.get('success'):
                return {'success': False, 'error': 'No se pudieron obtener las órdenes de producción completadas.'}

            ordenes = response.get('data', [])
            if not ordenes:
                return {'success': True, 'data': {'dias': 0, 'horas': 0, 'minutos': 0}}

            total_diferencia = timedelta()
            ordenes_validas = 0

            for orden in ordenes:
                fecha_inicio_str = orden.get('fecha_inicio')
                fecha_fin_str = orden.get('fecha_fin')

                if fecha_inicio_str and fecha_fin_str:
                    try:
                        fecha_inicio = datetime.fromisoformat(fecha_inicio_str)
                        fecha_fin = datetime.fromisoformat(fecha_fin_str)
                        total_diferencia += fecha_fin - fecha_inicio
                        ordenes_validas += 1
                    except ValueError:
                        # Ignorar órdenes con formato de fecha inválido
                        continue
            
            if ordenes_validas == 0:
                return {'success': True, 'data': {'dias': 0, 'horas': 0, 'minutos': 0}}

            promedio = total_diferencia / ordenes_validas
            dias = promedio.days
            horas, rem = divmod(promedio.seconds, 3600)
            minutos, _ = divmod(rem, 60)

            return {'success': True, 'data': {'dias': dias, 'horas': horas, 'minutos': minutos}}

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
