import logging
from collections import defaultdict
from app.controllers.base_controller import BaseController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from typing import List, Optional # Añade esta importación
from datetime import date, timedelta
from collections import defaultdict
import locale # Para nombres de días en español


logger = logging.getLogger(__name__)

class PlanificacionController(BaseController):
    def __init__(self):
        super().__init__()
        self.orden_produccion_controller = OrdenProduccionController()

    def obtener_ops_para_tablero(self) -> tuple:
        """
        Obtiene todas las OPs activas y las agrupa por estado para el tablero Kanban.
        """
        try:
            # --- CORRECCIÓN DEFINITIVA ---
            # Usamos los nombres exactos de la base de datos y solo los que corresponden al tablero.
            estados_activos = [
                'LISTA PARA PRODUCIR',
                'EN PROCESO',
                'EN_LINEA_1',
                'EN_LINEA_2',
                'EN_EMPAQUETADO',      # <-- NUEVO
                'CONTROL_DE_CALIDAD',  # <-- NUEVO
                'COMPLETADA'
                # Añade aquí otros estados si tienes columnas para ellos, ej: 'EN ESPERA'
            ]
            # ----------------------------

            response, _ = self.orden_produccion_controller.obtener_ordenes(
                filtros={'estado': ('in', estados_activos)}
            )

            if not response.get('success'):
                return self.error_response("Error al cargar las órdenes de producción.")

            ordenes = response.get('data', [])

            # Agrupamos las órdenes por estado usando un defaultdict
            ordenes_por_estado = defaultdict(list)
            for orden in ordenes:
                ordenes_por_estado[orden['estado']].append(orden)

            return self.success_response(data=dict(ordenes_por_estado))

        except Exception as e:
            logger.error(f"Error preparando datos para el tablero: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def consolidar_ops(self, op_ids: List[int], usuario_id: int) -> tuple:
        """
        Orquesta la consolidación de OPs llamando al controlador de órdenes de producción.
        """
        if not op_ids or len(op_ids) < 2:
            return self.error_response("Se requieren al menos dos órdenes para consolidar.", 400)

        try:
            # Delegamos la lógica compleja al controlador que maneja la entidad
            resultado = self.orden_produccion_controller.consolidar_ordenes_produccion(op_ids, usuario_id)

            if resultado.get('success'):
                return self.success_response(data=resultado.get('data'))
            else:
                return self.error_response(resultado.get('error', 'Error desconocido durante la consolidación.'), 500)

        except Exception as e:
            logger.error(f"Error crítico en consolidar_ops: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)


    def recomendar_linea_produccion(self, op_id: int) -> tuple:
        """
        Analiza una OP y sugiere la línea de producción óptima.
        """
        try:
            # Obtenemos los datos completos de la OP a través del otro controlador
            op_result = self.orden_produccion_controller.obtener_orden_por_id(op_id)
            if not op_result.get('success'):
                return self.error_response("Orden de Producción no encontrada.", 404)

            op = op_result['data']
            cantidad = float(op.get('cantidad_planificada', 0))

            # --- MOTOR DE REGLAS DE DECISIÓN ---
            # Puedes hacer esta lógica tan compleja como necesites.
            # Por ahora, usaremos un umbral simple de cantidad.

            recomendacion = {}
            umbral_gran_volumen = 50.0  # Lotes de más de 50kg van a la línea moderna

            if cantidad > umbral_gran_volumen:
                recomendacion = {
                    'linea_sugerida': 1,
                    'nombre_linea': 'Línea 1 (Moderna)',
                    'motivo': f'El lote de {cantidad} kg es considerado de gran volumen.'
                }
            else:
                recomendacion = {
                    'linea_sugerida': 2,
                    'nombre_linea': 'Línea 2 (Clásica)',
                    'motivo': f'El lote de {cantidad} kg es de volumen estándar.'
                }

            # Futura mejora: Podrías verificar aquí si la línea recomendada ya está ocupada
            # y sugerir la otra como alternativa.

            return self.success_response(data=recomendacion)

        except Exception as e:
            logger.error(f"Error recomendando línea para OP {op_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def mover_orden(self, op_id: int, nuevo_estado: str) -> tuple:
        """
        Orquesta el cambio de estado de una OP.
        Es inteligente: si el estado es 'COMPLETADA', llama al método complejo.
        Si no, llama al método simple.
        """
        if not nuevo_estado:
            return self.error_response("El 'nuevo_estado' es requerido.", 400)

        try:
            resultado = {}
            # --- LÓGICA DE DECISIÓN ---
            # Si la tarjeta se mueve a una columna que implica una lógica de negocio compleja...
            if nuevo_estado == 'COMPLETADA':
                # Llamamos al método que sabe cómo crear lotes y reservas.
                # NOTA: Este método devuelve una tupla (response, status), la manejamos diferente.
                response_dict, _ = self.orden_produccion_controller.cambiar_estado_orden(op_id, nuevo_estado)
                resultado = response_dict
            else:
                # Para cualquier otro movimiento en el Kanban, usamos el método simple.
                resultado = self.orden_produccion_controller.cambiar_estado_orden_simple(op_id, nuevo_estado)

            if resultado.get('success'):
                return self.success_response(data=resultado.get('data'))
            else:
                # Usamos 500 para errores de negocio complejos que pueden ocurrir.
                return self.error_response(resultado.get('error'), 500)

        except Exception as e:
            logger.error(f"Error crítico en mover_orden para OP {op_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def obtener_ops_pendientes_planificacion(self) -> tuple:
        """
        Obtiene todas las OPs que están en estado PENDIENTE y
        tienen una fecha meta asignada (vienen de un Pedido de Venta).
        """
        try:
            filtros = {
                'estado': 'PENDIENTE',
                'fecha_meta': ('neq', None) # 'neq' significa "No es igual a Nulo"
            }
            # Reutilizamos el controlador de OPs para obtener los datos
            response, _ = self.orden_produccion_controller.obtener_ordenes(filtros)

            if not response.get('success'):
                return self.error_response("Error al cargar las órdenes pendientes.")

            ordenes_pendientes = response.get('data', [])
            return self.success_response(data=ordenes_pendientes)

        except Exception as e:
            logger.error(f"Error preparando OPs pendientes: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)


    def obtener_planificacion_semanal(self, week_str: Optional[str] = None) -> tuple:
        """
        Obtiene las OPs planificadas para una semana específica y las agrupa por día.
        """
        try:
            # Configurar locale para español (si no está globalmente)
            try:
                locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
            except locale.Error:
                try:
                    locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252') # Windows fallback
                except locale.Error:
                    logger.warning("Locale 'es_ES.UTF-8' o 'Spanish_Spain' no disponible. Los días se mostrarán en inglés.")
                    pass # Continuar con el locale por defecto

            # 1. Determinar la semana
            if week_str:
                try:
                    year, week_num = map(int, week_str.split('-W'))
                    # Obtener el lunes de esa semana
                    start_of_week = date.fromisocalendar(year, week_num, 1)
                except ValueError:
                    return self.error_response("Formato de semana inválido. Use YYYY-WNN.", 400)
            else:
                today = date.today()
                start_of_week = today - timedelta(days=today.weekday()) # Lunes de la semana actual
                week_str = start_of_week.strftime("%Y-W%W")

            end_of_week = start_of_week + timedelta(days=6) # Domingo

            # 2. Consultar OPs en ese rango de fechas
            filtros = {
            'fecha_inicio_planificada_desde': start_of_week.isoformat(), # Clave para >=
            'fecha_inicio_planificada_hasta': end_of_week.isoformat(),   # Clave para <=
            'estado': ('not.in', ['PENDIENTE', 'COMPLETADA', 'CANCELADA', 'CONSOLIDADA'])
            }
            # Usamos obtener_ordenes que ya trae datos enriquecidos (supervisor, operario)
            response_ops, _ = self.orden_produccion_controller.obtener_ordenes(filtros)

            if not response_ops.get('success'):
                return self.error_response("Error al obtener las órdenes planificadas.", 500)

            # 3. Agrupar por día
            ordenes = response_ops.get('data', [])
            grouped_by_day = defaultdict(list)

            # Crear entradas para todos los días de la semana, incluso si están vacíos
            dias_semana_iso = [(start_of_week + timedelta(days=i)).isoformat() for i in range(7)]
            for dia_iso in dias_semana_iso:
                 grouped_by_day[dia_iso] = []

            for op in ordenes:
                fecha_inicio = op.get('fecha_inicio_planificada')
                if fecha_inicio: # Asegurarse que la fecha existe
                     # La fecha puede venir como string, la normalizamos a ISO
                     try:
                         fecha_dt = date.fromisoformat(fecha_inicio[:10]) # Tomar solo YYYY-MM-DD
                         grouped_by_day[fecha_dt.isoformat()].append(op)
                     except ValueError:
                          logger.warning(f"Formato de fecha inválido para OP {op.get('codigo')}: {fecha_inicio}")


            # Ordenar el diccionario por fecha para la plantilla
            ordered_grouped_by_day = dict(sorted(grouped_by_day.items()))

            # Formatear claves con nombre del día
            formatted_grouped_by_day = {}
            for dia_iso, ops_dia in ordered_grouped_by_day.items():
                try:
                    dia_dt = date.fromisoformat(dia_iso)
                    # Formato: "Lunes 21/10"
                    key_display = dia_dt.strftime("%A %d/%m").capitalize()
                except ValueError:
                     key_display = dia_iso # Fallback
                formatted_grouped_by_day[key_display] = ops_dia


            resultado = {
                'ordenes_por_dia': formatted_grouped_by_day,
                'inicio_semana': start_of_week.isoformat(),
                'fin_semana': end_of_week.isoformat(),
                'semana_actual_str': week_str
            }
            return self.success_response(data=resultado)

        except Exception as e:
            logger.error(f"Error obteniendo planificación semanal: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)