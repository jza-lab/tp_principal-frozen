# app/controllers/produccion_kanban_controller.py
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from app.controllers.base_controller import BaseController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.receta_controller import RecetaController
from app.controllers.insumo_controller import InsumoController
from app.models.registro_desperdicio_model import RegistroDesperdicioModel
from app.utils.estados import OP_KANBAN_COLUMNAS

logger = logging.getLogger(__name__)

class ProduccionKanbanController(BaseController):
    def __init__(self):
        super().__init__()
        self.orden_produccion_controller = OrdenProduccionController()
        self.receta_controller = RecetaController()
        self.insumo_controller = InsumoController()
        self.desperdicio_model = RegistroDesperdicioModel()

    def obtener_datos_para_tablero(self, usuario_id: int, usuario_rol: str) -> tuple:
        """
        Orquesta la obtención de todos los datos necesarios para el tablero Kanban.
        Incluye la lógica de filtrado de OPs y de columnas según el rol.
        """
        try:
            # 1. Obtener las OPs del día
            response_ops, _ = self.orden_produccion_controller.obtener_ordenes_para_kanban_hoy()
            if not response_ops.get('success'):
                return self.error_response("Error al cargar las órdenes para el tablero.")

            ordenes = response_ops.get('data', [])
            
            # 2. Enrich and group orders
            ordenes_enriquecidas = []
            for orden in ordenes:
                orden['lote'] = self._obtener_lote_de_orden(orden)
                orden['prioridad'] = self._calcular_prioridad(orden)
                orden['fecha_meta_str'] = orden.get('fecha_meta') # Keep original for display
                orden['tiempo_hasta_meta_horas'] = self._calcular_tiempo_hasta_meta(orden)
                orden['es_retrasada'] = self._es_retrasada(orden)
                orden['tiempo_estimado_horas'] = self._calcular_tiempo_estimado(orden)
                orden['turno'] = self._obtener_turno_actual()
                orden['tiempo_transcurrido'] = self._formatear_tiempo_transcurrido(orden)
                orden['ritmo_actual'] = self._calcular_ritmo_actual(orden)
                orden['ritmo_objetivo'] = self._calcular_ritmo_objetivo(orden)
                orden['oee_actual'] = self._calcular_oee_actual(orden)
                orden['desperdicio_porcentaje'] = self._obtener_desperdicio_de_orden(orden)
                orden['materiales_disponibles'] = self._verificar_materiales_disponibles(orden)
                ordenes_enriquecidas.append(orden)

            ordenes_por_estado = defaultdict(list)
            for orden in ordenes_enriquecidas:
                estado_db = orden.get('estado', '').strip()
                estado_constante = estado_db.replace(' ', '_')
                if estado_constante in ['EN_LINEA_1', 'EN_LINEA_2', 'EN_EMPAQUETADO', 'EN_PRODUCCION']:
                    estado_constante = 'EN_PROCESO'
                if estado_constante in OP_KANBAN_COLUMNAS:
                    ordenes_por_estado[estado_constante].append(orden)

            # 3. Calculate daily metrics
            hoy_inicio = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            ordenes_hoy = [o for o in ordenes_enriquecidas if o.get('fecha_inicio') and datetime.fromisoformat(o['fecha_inicio']) >= hoy_inicio]
            
            completadas_hoy = [o for o in ordenes_hoy if o.get('estado') == 'COMPLETADA']
            
            oee_sum = sum(o.get('oee_actual', 0) for o in ordenes_hoy if o.get('oee_actual') is not None)
            oee_count = len([o for o in ordenes_hoy if o.get('oee_actual') is not None])
            oee_promedio = round(oee_sum / oee_count, 0) if oee_count > 0 else 0

            total_producido = sum(float(o.get('cantidad_producida', 0) or 0) for o in ordenes_hoy)
            total_desperdicio = sum(self._obtener_desperdicio_de_orden(o) for o in ordenes_hoy)
            desperdicio_promedio = round((total_desperdicio / (total_producido + total_desperdicio)) * 100, 1) if (total_producido + total_desperdicio) > 0 else 0.0

            a_tiempo_count = len([o for o in completadas_hoy if not o.get('es_retrasada')])
            a_tiempo_porcentaje = round((a_tiempo_count / len(completadas_hoy)) * 100, 0) if len(completadas_hoy) > 0 else 100

            metricas_dia = {
                'completadas': len(completadas_hoy),
                'en_proceso': len(ordenes_por_estado.get('EN_PROCESO', [])),
                'pendientes': len(ordenes_por_estado.get('LISTA_PARA_PRODUCIR', [])) + len(ordenes_por_estado.get('EN_ESPERA', [])),
                'oee_promedio': oee_promedio,
                'desperdicio': desperdicio_promedio,
                'a_tiempo': a_tiempo_porcentaje
            }

            # 4. Determine columns to show
            columnas = OP_KANBAN_COLUMNAS
            if usuario_rol == 'OPERARIO':
                columnas = {
                    'LISTA_PARA_PRODUCIR': 'Lista para Producir',
                    'EN_PROCESO': 'En Proceso'
                }
            
            # 5. Assemble context for the template
            contexto = {
                'ordenes_por_estado': dict(ordenes_por_estado),
                'columnas': columnas,
                'metricas_dia': metricas_dia,
                'usuario_rol': usuario_rol
            }
            return self.success_response(data=contexto)

        except Exception as e:
            logger.error(f"Error crítico al obtener datos para el tablero Kanban: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    # --- ENRICHMENT HELPERS ---

    def _obtener_lote_de_orden(self, orden):
        """
        Obtiene el lote a partir de la orden de producción.
        Genera un lote dinámicamente si no existe.
        """
        # Lógica provisional para generar un lote si no está en los datos de la orden
        return orden.get('lote') or f'LOTE-{datetime.now().year}-{orden.get("id", 0):03d}'

    def _obtener_desperdicio_de_orden(self, orden):
        """Suma el desperdicio registrado para una orden de producción."""
        op_id = orden.get('id')
        if not op_id:
            return 0.0
        
        response = self.desperdicio_model.find_all(filters={'orden_produccion_id': op_id})
        if response.get('success'):
            total_desperdicio = sum(float(item.get('cantidad', 0) or 0) for item in response.get('data', []))
            return total_desperdicio
        return 0.0

    def _calcular_prioridad(self, orden):
        """Calcula la prioridad basándose en el tiempo restante."""
        fecha_meta_str = orden.get('fecha_meta')
        if not fecha_meta_str:
            return 'NORMAL'

        try:
            fecha_meta = datetime.fromisoformat(fecha_meta_str)
            horas_restantes = (fecha_meta - datetime.now()).total_seconds() / 3600
            
            if horas_restantes < 0:
                return 'ALTA'
            elif horas_restantes < 4:
                return 'ALTA'
            elif horas_restantes < 24:
                return 'MEDIA'
            else:
                return 'NORMAL'
        except (ValueError, TypeError):
            return 'NORMAL'

    def _calcular_tiempo_hasta_meta(self, orden):
        """Calcula las horas restantes hasta la fecha meta."""
        fecha_meta_str = orden.get('fecha_meta')
        if not fecha_meta_str:
            return 9999
        try:
            fecha_meta = datetime.fromisoformat(fecha_meta_str).astimezone(timezone.utc)
            ahora = datetime.now(timezone.utc)
            delta = fecha_meta - ahora
            horas = delta.total_seconds() / 3600
            return round(max(0, horas), 1)
        except (ValueError, TypeError):
            return 9999

    def _es_retrasada(self, orden):
        """Verifica si la orden ya pasó su fecha meta."""
        fecha_meta_str = orden.get('fecha_meta')
        if not fecha_meta_str:
            return False
        try:
            fecha_meta = datetime.fromisoformat(fecha_meta_str)
            return datetime.now() > fecha_meta
        except (ValueError, TypeError):
            return False

    def _formatear_tiempo_transcurrido(self, orden):
        """Formatea el tiempo de producción transcurrido."""
        inicio_str = orden.get('fecha_inicio')
        if not inicio_str:
            return "0min"
        try:
            inicio = datetime.fromisoformat(inicio_str).astimezone(timezone.utc)
            ahora = datetime.now(timezone.utc)
            delta = ahora - inicio
            
            horas = int(delta.total_seconds() // 3600)
            minutos = int((delta.total_seconds() % 3600) // 60)
            
            if horas > 0:
                return f"{horas}h {minutos}min"
            else:
                return f"{minutos}min"
        except (ValueError, TypeError):
            return "0min"

    def _verificar_materiales_disponibles(self, orden):
        """Verifica si hay stock suficiente de todos los insumos para la OP."""
        receta_id = orden.get('receta_id')
        cantidad_planificada = orden.get('cantidad_planificada')
        if not receta_id or not cantidad_planificada:
            return False

        receta_res, _ = self.receta_controller.obtener_receta_con_ingredientes(receta_id)
        if not receta_res.get('success'):
            return False

        for ingrediente in receta_res['data'].get('ingredientes', []):
            insumo_id = ingrediente.get('id_insumo')
            cantidad_necesaria = ingrediente.get('cantidad', 0) * cantidad_planificada
            
            stock_res, _ = self.insumo_controller.obtener_con_stock(insumo_id)
            if not stock_res.get('success') or stock_res['data'].get('stock_actual', 0) < cantidad_necesaria:
                return False
        return True

    def _calcular_ritmo_actual(self, orden):
        """Calcula el ritmo de producción actual en kg/h."""
        inicio_str = orden.get('fecha_inicio')
        if not inicio_str or orden.get('estado') != 'EN_PROCESO':
            return 0.0

        try:
            inicio = datetime.fromisoformat(inicio_str)
            tiempo_transcurrido = datetime.now() - inicio
            horas = tiempo_transcurrido.total_seconds() / 3600
            
            if horas == 0:
                return 0.0
            
            cantidad_producida = float(orden.get('cantidad_producida', 0) or 0)
            ritmo = cantidad_producida / horas
            return round(ritmo, 1)
        except (ValueError, TypeError, ZeroDivisionError):
            return 0.0

    def _calcular_ritmo_objetivo(self, orden):
        """Calcula el ritmo objetivo basado en el tiempo disponible."""
        fecha_meta_str = orden.get('fecha_meta')
        if not fecha_meta_str:
            return 10.0 # Valor por defecto si no hay meta

        try:
            fecha_meta = datetime.fromisoformat(fecha_meta_str)
            tiempo_disponible = fecha_meta - datetime.now()
            horas_disponibles = tiempo_disponible.total_seconds() / 3600

            if horas_disponibles <= 0:
                return 9999.0

            cantidad_producida = float(orden.get('cantidad_producida', 0) or 0)
            cantidad_restante = float(orden.get('cantidad_planificada', 0)) - cantidad_producida
            ritmo_necesario = cantidad_restante / horas_disponibles
            return round(ritmo_necesario, 1)
        except (ValueError, TypeError, ZeroDivisionError):
            return 10.0

    def _calcular_oee_actual(self, orden):
        """Calcula el OEE actual de la orden."""
        if orden.get('estado') != 'EN_PROCESO' or not orden.get('fecha_inicio'):
            return 0
        try:
            # 1. Disponibilidad
            inicio = datetime.fromisoformat(orden['fecha_inicio']).astimezone(timezone.utc)
            ahora = datetime.now(timezone.utc)
            tiempo_total = (ahora - inicio).total_seconds()
            tiempo_pausas = 0 # Placeholder
            tiempo_productivo = tiempo_total - tiempo_pausas
            disponibilidad = (tiempo_productivo / tiempo_total) * 100 if tiempo_total > 0 else 100

            # 2. Rendimiento
            horas_productivas = tiempo_productivo / 3600
            ritmo_objetivo = self._calcular_ritmo_objetivo(orden)
            produccion_teorica = ritmo_objetivo * horas_productivas
            produccion_real = float(orden.get('cantidad_producida', 0) or 0)
            rendimiento = (produccion_real / produccion_teorica) * 100 if produccion_teorica > 0 else 100
            rendimiento = min(rendimiento, 100)

            # 3. Calidad
            desperdicio = self._obtener_desperdicio_de_orden(orden)
            cantidad_total = produccion_real + desperdicio
            calidad = (produccion_real / cantidad_total) * 100 if cantidad_total > 0 else 100

            oee = (disponibilidad * rendimiento * calidad) / 10000
            return round(oee, 0)
        except (ValueError, TypeError, ZeroDivisionError):
            return None

    def _calcular_tiempo_estimado(self, orden):
        """Calcula el tiempo de producción estimado para una orden."""
        receta_id = orden.get('receta_id')
        cantidad_planificada = float(orden.get('cantidad_planificada', 0))
        linea_asignada = orden.get('linea_asignada')

        if not all([receta_id, cantidad_planificada, linea_asignada]):
            return "N/D"

        receta_res, _ = self.receta_controller.obtener_receta_con_ingredientes(receta_id)
        if not receta_res.get('success'):
            return "N/D"
        
        receta = receta_res['data']
        tiempo_preparacion = float(receta.get('tiempo_preparacion_minutos', 0))
        
        tiempo_prod_key = f'tiempo_prod_unidad_linea{linea_asignada}'
        tiempo_prod_unidad = float(receta.get(tiempo_prod_key, 0))

        tiempo_total_minutos = tiempo_preparacion + (tiempo_prod_unidad * cantidad_planificada)
        
        if tiempo_total_minutos == 0:
            return "N/D"
            
        horas = int(tiempo_total_minutos // 60)
        minutos = int(tiempo_total_minutos % 60)

        if horas > 0:
            return f"{horas}h {minutos}min"
        else:
            return f"{minutos}min"

    def _obtener_turno_actual(self):
        """Determina el turno de producción actual basado en la hora."""
        hora_actual = datetime.now(timezone.utc).hour
        if 6 <= hora_actual < 14:
            return "Mañana (06:00-14:00)"
        elif 14 <= hora_actual < 22:
            return "Tarde (14:00-22:00)"
        else:
            return "Noche (22:00-06:00)"


    def mover_orden(self, op_id: int, nuevo_estado: str, user_role: str) -> tuple:
        """
        Orquesta el cambio de estado de una OP en el Kanban, validando permisos.
        """
        if not nuevo_estado:
            return self.error_response("El 'nuevo_estado' es requerido.", 400)

        try:
            op_actual_res = self.orden_produccion_controller.obtener_orden_por_id(op_id)
            if not op_actual_res.get('success'):
                return self.error_response("Orden de Producción no encontrada.", 404)
            estado_actual = op_actual_res['data'].get('estado')

            # Aquí se pueden añadir validaciones de transición específicas del Kanban si es necesario
            # Por ejemplo, un operario solo puede mover a ciertos estados.
            # Esta lógica es un ejemplo y puede ser ajustada.
            if user_role == 'OPERARIO':
                allowed_transitions = {
                    'LISTA_PARA_PRODUCIR': ['EN_PROCESO'],
                    'EN_PROCESO': ['CONTROL_DE_CALIDAD'] # Ejemplo
                }
                if estado_actual not in allowed_transitions or nuevo_estado not in allowed_transitions[estado_actual]:
                    return self.error_response(f"Movimiento de '{estado_actual}' a '{nuevo_estado}' no permitido.", 403)

            # Se delega el cambio de estado al controlador principal de OPs.
            # Usamos el método simple ya que el Kanban maneja estados intermedios.
            resultado = self.orden_produccion_controller.cambiar_estado_orden_simple(op_id, nuevo_estado)
            
            if resultado.get('success'):
                return self.success_response(data=resultado.get('data'))
            else:
                return self.error_response(resultado.get('error', 'Error al cambiar el estado.'), 500)

        except Exception as e:
            logger.error(f"Error crítico en mover_orden (Kanban) para OP {op_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def obtener_estado_produccion(self, op_id: int) -> tuple:
        """
        Obtiene el estado de producción en tiempo real para una OP, incluyendo el tiempo trabajado.
        """
        from app.models.op_cronometro_model import OpCronometroModel
        from datetime import datetime
        try:
            # Obtener el estado base de la producción
            estado_base_res, status_code = self.orden_produccion_controller.obtener_estado_produccion_op(op_id)
            if status_code >= 400:
                return estado_base_res, status_code

            estado_produccion = estado_base_res.get('data', {})

            # Calcular el tiempo trabajado
            cronometro_model = OpCronometroModel()
            intervalos_res = cronometro_model.get_intervalos_por_op(op_id)
            if not intervalos_res.get('success'):
                logger.error(f"No se pudieron obtener los intervalos del cronómetro para OP {op_id}")
                estado_produccion['tiempo_trabajado'] = 0
            else:
                intervalos = intervalos_res.get('data', [])
                tiempo_total_segundos = 0
                for intervalo in intervalos:
                    start_time = datetime.fromisoformat(intervalo['start_time'])
                    end_time_str = intervalo.get('end_time')
                    
                    if end_time_str:
                        end_time = datetime.fromisoformat(end_time_str)
                    else:
                        # Si el intervalo está abierto, calcular el tiempo hasta ahora
                        end_time = datetime.now(start_time.tzinfo)
                    
                    tiempo_total_segundos += (end_time - start_time).total_seconds()
                
                estado_produccion['tiempo_trabajado'] = int(tiempo_total_segundos)

            return self.success_response(data=estado_produccion)

        except Exception as e:
            logger.error(f"Error al obtener estado de producción para OP {op_id} desde KanbanController: {e}", exc_info=True)
            return self.error_response(f"Error interno al consultar estado: {str(e)}", 500)
