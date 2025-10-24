import logging
from collections import defaultdict
from app.controllers.base_controller import BaseController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from typing import List, Optional, Dict
from datetime import date, timedelta
from collections import defaultdict
import locale
from app.models.receta import RecetaModel
from app.models.insumo import InsumoModel
import math
from app.controllers.inventario_controller import InventarioController
from app.models.centro_trabajo_model import CentroTrabajoModel
from app.models.operacion_receta_model import OperacionRecetaModel
from decimal import Decimal


logger = logging.getLogger(__name__)

class PlanificacionController(BaseController):
    def __init__(self):
        super().__init__()
        self.orden_produccion_controller = OrdenProduccionController()
        self.inventario_controller = InventarioController()
        self.centro_trabajo_model = CentroTrabajoModel()
        self.operacion_receta_model = OperacionRecetaModel()

    def obtener_ops_para_tablero(self) -> tuple:
        """
        Obtiene todas las OPs activas y las agrupa por estado para el tablero Kanban.
        """
        try:
            # --- CORRECCIÓN DEFINITIVA ---
            # Usamos los nombres exactos de la base de datos y solo los que corresponden al tablero.
            estados_activos = [
                'EN ESPERA',
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

    def consolidar_y_aprobar_lote(self, op_ids: List[int], asignaciones: dict, usuario_id: int) -> tuple:
        """
        Orquesta el flujo completo de la modal:
        1. Consolida (si es necesario).
        2. Pre-asigna recursos (Línea, Sup, Op).
        3. Confirma el inicio (guarda fecha y ejecuta aprobación/stock check).
        Reutiliza la lógica de OrdenProduccionController.
        """
        try:
            if not op_ids:
                return self.error_response("Se requiere al menos una orden para planificar el lote.", 400)

            op_a_planificar_id = None

            # --- PASO 1: CONSOLIDAR (si hay más de 1 OP) ---
            if len(op_ids) > 1:
                logger.info(f"Consolidando {len(op_ids)} OPs...")
                # Llama a la lógica de tu orden_produccion_controller
                resultado_consol = self.orden_produccion_controller.consolidar_ordenes_produccion(op_ids, usuario_id)
                if not resultado_consol.get('success'):
                    return self.error_response(f"Error al consolidar: {resultado_consol.get('error')}", 500)

                op_a_planificar_id = resultado_consol.get('data', {}).get('id')
                if not op_a_planificar_id:
                    return self.error_response("La consolidación falló, no se devolvió ID.", 500)
                logger.info(f"Super OP creada con ID: {op_a_planificar_id}")
            else:
                # Si es solo una OP, usamos su ID directamente
                op_a_planificar_id = op_ids[0]
                logger.info(f"Planificando OP individual con ID: {op_a_planificar_id}")


            # --- PASO 2: PRE-ASIGNAR RECURSOS (Línea, Supervisor, Operario) ---
            datos_pre_asignar = {
                'linea_asignada': asignaciones.get('linea_asignada'),
                'supervisor_responsable_id': asignaciones.get('supervisor_id'),
                'operario_asignado_id': asignaciones.get('operario_id')
            }
            # Limpiar claves None (si el supervisor/operario es opcional)
            datos_pre_asignar = {k: v for k, v in datos_pre_asignar.items() if v is not None}

            if 'linea_asignada' not in datos_pre_asignar:
                return self.error_response("La Línea de Producción es requerida.", 400)

            # Llama a la lógica de tu orden_produccion_controller
            res_pre_asig_dict, res_pre_asig_status = self.orden_produccion_controller.pre_asignar_recursos(
                op_a_planificar_id, datos_pre_asignar, usuario_id
            )

            if res_pre_asig_status >= 400:
                logger.error(f"Fallo en pre_asignar_recursos: {res_pre_asig_dict.get('error')}")
                # Devolvemos el error que nos dio el controlador de OP
                return res_pre_asig_dict, res_pre_asig_status


            # --- PASO 3: CONFIRMAR INICIO Y APROBAR (Fecha, Stock Check, Cambio de Estado) ---
            datos_confirmar = {
                'fecha_inicio_planificada': asignaciones.get('fecha_inicio')
            }
            if not datos_confirmar['fecha_inicio_planificada']:
                 return self.error_response("La Fecha de Inicio es requerida.", 400)

            # Llama a la lógica de tu orden_produccion_controller
            # Este método ya guarda la fecha Y ejecuta la lógica de aprobación (stock, etc.)
            res_conf_dict, res_conf_status = self.orden_produccion_controller.confirmar_inicio_y_aprobar(
                op_a_planificar_id, datos_confirmar, usuario_id
            )

            # Devolvemos el resultado final de la aprobación
            return res_conf_dict, res_conf_status

        except Exception as e:
            logger.error(f"Error crítico en consolidar_y_aprobar_lote: {e}", exc_info=True)
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

    def obtener_ops_pendientes_planificacion(self, dias_horizonte: int = 7) -> tuple:
        """
        Obtiene OPs PENDIENTES en horizonte, agrupa por producto,
        calcula tiempo de producción total estimado y verifica stock agregado.
        """
        try:
            # 1. Calcular rango de fechas y filtrar OPs (sin cambios)
            hoy = date.today()
            # ... (validación dias_horizonte_int) ...
            dias_horizonte_int = int(dias_horizonte) # Simplificado
            fecha_fin_horizonte = hoy + timedelta(days=dias_horizonte_int)
            filtros = {
                'estado': 'PENDIENTE',
                'fecha_meta_desde': hoy.isoformat(),
                'fecha_meta_hasta': fecha_fin_horizonte.isoformat()
            }
            response, _ = self.orden_produccion_controller.obtener_ordenes(filtros)
            if not response.get('success'):
                logger.error(f"Error al obtener OPs pendientes para MPS: {response.get('error')}")
                return self.error_response("Error al cargar órdenes pendientes.")
            ordenes_en_horizonte = response.get('data', [])

            # 2. Agrupar por Producto y calcular totales (sin cambios)
            mps_agrupado = defaultdict(lambda: {'cantidad_total': 0, 'ordenes': [], 'fecha_meta_mas_proxima': None, 'receta_id': None}) # Añadir receta_id
            for op in ordenes_en_horizonte:
                producto_id = op.get('producto_id')
                producto_nombre = op.get('producto_nombre', 'Desconocido')
                cantidad = op.get('cantidad_planificada', 0)
                fecha_meta_op_str = op.get('fecha_meta')
                receta_id_op = op.get('receta_id') # Capturar receta_id

                if not producto_id or cantidad <= 0 or not receta_id_op: # Validar receta_id también
                    continue
                clave_producto = (producto_id, producto_nombre)
                mps_agrupado[clave_producto]['cantidad_total'] += float(cantidad)
                mps_agrupado[clave_producto]['ordenes'].append(op)
                # Guardar el receta_id (asumimos que es el mismo para el mismo producto)
                if mps_agrupado[clave_producto]['receta_id'] is None:
                    mps_agrupado[clave_producto]['receta_id'] = receta_id_op
                # ... (lógica fecha_meta_mas_proxima sin cambios) ...
                fecha_meta_mas_proxima_actual = mps_agrupado[clave_producto]['fecha_meta_mas_proxima']
                if fecha_meta_op_str:
                     fecha_meta_op = date.fromisoformat(fecha_meta_op_str)
                     if fecha_meta_mas_proxima_actual is None or fecha_meta_op < date.fromisoformat(fecha_meta_mas_proxima_actual):
                          mps_agrupado[clave_producto]['fecha_meta_mas_proxima'] = fecha_meta_op_str


            # --- INICIO NUEVA LÓGICA: Calcular sugerencia agregada ---
            receta_model = RecetaModel()
            insumo_model = InsumoModel()

            for clave_producto, data in mps_agrupado.items():
                producto_id = clave_producto[0]
                cantidad_total_agrupada = data['cantidad_total']
                receta_id_agrupada = data['receta_id']

                # Inicializar valores de sugerencia agregada
                data['sugerencia_t_prod_dias'] = 0
                data['sugerencia_linea'] = None
                data['sugerencia_t_proc_dias'] = 0
                data['sugerencia_stock_ok'] = False
                data['sugerencia_insumos_faltantes'] = [] # Lista detallada (opcional)

                if not receta_id_agrupada: continue # Saltar si no hay receta

                # a) Calcular Tiempo de Producción Agregado
                receta_res = receta_model.find_by_id(receta_id_agrupada, 'id')
                if receta_res.get('success'):
                    receta = receta_res['data']
                    # Reutilizar lógica de selección de línea y cálculo de t_prod_dias
                    # (Similar a la de sugerir_fecha_inicio, adaptada)
                    linea_compatible = receta.get('linea_compatible', '2').split(',')
                    tiempo_prep = receta.get('tiempo_preparacion_minutos', 0)
                    tiempo_l1 = receta.get('tiempo_prod_unidad_linea1', 0)
                    tiempo_l2 = receta.get('tiempo_prod_unidad_linea2', 0)
                    UMBRAL_CANTIDAD_LINEA_1 = 50 # Definir umbral
                    puede_l1 = '1' in linea_compatible and tiempo_l1 > 0
                    puede_l2 = '2' in linea_compatible and tiempo_l2 > 0
                    linea_sug_agg = 0
                    tiempo_prod_unit_elegido_agg = 0
                    if puede_l1 and puede_l2:
                        linea_sug_agg = 1 if cantidad_total_agrupada >= UMBRAL_CANTIDAD_LINEA_1 else 2
                        tiempo_prod_unit_elegido_agg = tiempo_l1 if linea_sug_agg == 1 else tiempo_l2
                    elif puede_l1: linea_sug_agg = 1; tiempo_prod_unit_elegido_agg = tiempo_l1
                    elif puede_l2: linea_sug_agg = 2; tiempo_prod_unit_elegido_agg = tiempo_l2

                    if linea_sug_agg > 0:
                         t_prod_minutos_agg = tiempo_prep + (tiempo_prod_unit_elegido_agg * cantidad_total_agrupada)
                         data['sugerencia_t_prod_dias'] = math.ceil(t_prod_minutos_agg / 480) # Jornada 8h
                         data['sugerencia_linea'] = linea_sug_agg

                # b) Verificar Stock Agregado
                # Necesitamos un método en InventarioController que verifique stock para una cantidad y receta
                # Adaptaremos verificar_stock_para_op temporalmente aquí (idealmente estaría en el controller)
                ingredientes_result = receta_model.get_ingredientes(receta_id_agrupada)
                insumos_faltantes_agg = []
                stock_ok_agg = True
                if ingredientes_result.get('success'):
                    for ingrediente in ingredientes_result.get('data', []):
                        insumo_id = ingrediente['id_insumo']
                        cant_necesaria_total = ingrediente['cantidad'] * cantidad_total_agrupada
                        # Llamar a la función que calcula stock real disponible
                        stock_disp_res = self.inventario_controller.obtener_stock_disponible_insumo(insumo_id)
                        stock_disp = stock_disp_res.get('data', {}).get('stock_disponible', 0) if stock_disp_res.get('success') else 0

                        if stock_disp < cant_necesaria_total:
                            stock_ok_agg = False
                            faltante = cant_necesaria_total - stock_disp
                            insumos_faltantes_agg.append({
                                'insumo_id': insumo_id,
                                'nombre': ingrediente.get('nombre_insumo', 'N/A'),
                                'cantidad_faltante': faltante
                            })
                else:
                     stock_ok_agg = False # Si no podemos obtener ingredientes, asumimos que falta stock

                data['sugerencia_stock_ok'] = stock_ok_agg
                data['sugerencia_insumos_faltantes'] = insumos_faltantes_agg # Guardar lista detallada

                # c) Calcular Tiempo de Aprovisionamiento Agregado (si falta stock)
                if not stock_ok_agg:
                    tiempos_entrega_agg = []
                    for insumo_f in insumos_faltantes_agg:
                        insumo_data_res = insumo_model.find_by_id(insumo_f['insumo_id'], 'id_insumo')
                        if insumo_data_res.get('success'):
                            tiempo = insumo_data_res['data'].get('tiempo_entrega_dias', 0)
                            tiempos_entrega_agg.append(tiempo)
                    data['sugerencia_t_proc_dias'] = max(tiempos_entrega_agg) if tiempos_entrega_agg else 0
            # --- FIN NUEVA LÓGICA ---


            # 5. Convertir a lista ordenada (sin cambios)
            mps_lista_ordenada = sorted(
                [ {
                    'producto_id': pid, 'producto_nombre': pname,
                    **data # Añadir todos los datos calculados (cantidad_total, ordenes, sugerencias, etc.)
                   } for (pid, pname), data in mps_agrupado.items()
                ],
                key=lambda x: x.get('fecha_meta_mas_proxima') or '9999-12-31'
            )

            resultado_final = {
                 'mps_agrupado': mps_lista_ordenada,
                 'inicio_horizonte': hoy.isoformat(),
                 'fin_horizonte': fecha_fin_horizonte.isoformat(),
                 'dias_horizonte': dias_horizonte_int
            }
            return self.success_response(data=resultado_final)

        except Exception as e:
            logger.error(f"Error preparando MPS: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)


    def obtener_planificacion_semanal(self, week_str: Optional[str] = None) -> tuple:
        """
        Obtiene las OPs planificadas para una semana específica y las agrupa por día.
        """
        try:
            # Configurar locale para español (si no está globalmente)
            try:
                locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
                logger.info("Locale establecido a es_ES.UTF-8")
            except locale.Error:
                try:
                    locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')
                    logger.info("Locale establecido a Spanish_Spain.1252")
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

    def obtener_capacidad_disponible(self, centro_trabajo_ids: List[int], fecha_inicio: date, fecha_fin: date) -> Dict:
        """
        Calcula la capacidad disponible (en minutos) para centros de trabajo dados,
        entre dos fechas (inclusive). Considera estándar, eficiencia y utilización.
        Devuelve: { centro_id: { fecha_iso: capacidad_minutos, ... }, ... }
        """
        capacidad_por_centro_y_fecha = defaultdict(dict)
        num_dias = (fecha_fin - fecha_inicio).days + 1

        try:
            # --- CORRECCIÓN: Usar find_all con filtro 'in' ---
            # Prepara el filtro para buscar por la lista de IDs
            id_filter = ('in', tuple(centro_trabajo_ids)) # 'in' usualmente espera una tupla
            ct_result = self.centro_trabajo_model.find_all(filters={'id': id_filter})
            # ------------------------------------------------

            if not ct_result.get('success'):
                logger.error(f"Error obteniendo centros de trabajo: {ct_result.get('error')}")
                return {}

            centros_trabajo = {ct['id']: ct for ct in ct_result.get('data', [])}

            # ... (resto de la lógica para calcular capacidad sin cambios) ...
            for dia_offset in range(num_dias):
                fecha_actual = fecha_inicio + timedelta(days=dia_offset)
                fecha_iso = fecha_actual.isoformat()
                for ct_id in centro_trabajo_ids:
                    centro = centros_trabajo.get(ct_id)
                    if not centro:
                        capacidad_por_centro_y_fecha[ct_id][fecha_iso] = 0
                        continue
                    capacidad_std = Decimal(centro.get('tiempo_disponible_std_dia', 0))
                    eficiencia = Decimal(centro.get('eficiencia', 1.0))
                    utilizacion = Decimal(centro.get('utilizacion', 1.0))
                    num_maquinas = int(centro.get('numero_maquinas', 1))
                    capacidad_neta_dia = capacidad_std * eficiencia * utilizacion * num_maquinas
                    capacidad_por_centro_y_fecha[ct_id][fecha_iso] = round(capacidad_neta_dia, 2)


            # --- CONVERSIÓN A FLOAT ---
            resultado_final_float = {}
            for centro_id, cap_fecha in capacidad_por_centro_y_fecha.items():
                resultado_final_float[centro_id] = {fecha: float(cap) for fecha, cap in cap_fecha.items()}
            # --------------------------

            # return dict(capacidad_por_centro_y_fecha) # <- Línea antigua
            return resultado_final_float # <- Devolver el diccionario con floats

        except Exception as e:
            logger.error(f"Error calculando capacidad disponible: {e}", exc_info=True)
            return {}


    def obtener_operaciones_receta(self, receta_id: int) -> List[Dict]:
        """ Obtiene las operaciones de una receta desde el modelo. """
        result = self.operacion_receta_model.find_by_receta_id(receta_id)
        return result.get('data', []) if result.get('success') else []


    def calcular_carga_capacidad(self, ordenes_planificadas: List[Dict]) -> Dict:
        """
        Calcula la carga (en minutos) por centro de trabajo y fecha para las OPs dadas.
        Usa la 'linea_asignada' de la OP para distribuir la carga.
        Devuelve: { centro_id: { fecha_iso: carga_minutos, ... }, ... }
        """
        carga_por_centro_y_fecha = {1: defaultdict(Decimal), 2: defaultdict(Decimal)} # Inicializa para Linea 1 y 2

        for orden in ordenes_planificadas:
            try:
                receta_id = orden.get('receta_id')
                # Convertir cantidad a Decimal para precisión
                cantidad = Decimal(orden.get('cantidad_planificada', 0))
                fecha_inicio_str = orden.get('fecha_inicio_planificada')
                linea_asignada = orden.get('linea_asignada')

                # Validar datos esenciales
                if not receta_id or cantidad <= 0 or not fecha_inicio_str or linea_asignada not in [1, 2]:
                    logger.warning(f"OP {orden.get('codigo', orden.get('id'))} omitida del cálculo de carga (datos incompletos/inválidos: R:{receta_id}, C:{cantidad}, F:{fecha_inicio_str}, L:{linea_asignada})")
                    continue

                # Convertir fecha a ISO para usar como clave
                fecha_iso = date.fromisoformat(fecha_inicio_str).isoformat()

                # Obtener operaciones
                operaciones = self.obtener_operaciones_receta(receta_id)
                if not operaciones:
                    logger.warning(f"No se encontraron operaciones para receta {receta_id} (OP {orden.get('codigo')}). Carga no calculada.")
                    continue

                # Calcular tiempo total para la orden sumando tiempos de operación
                tiempo_total_orden = Decimal(0)
                for op in operaciones:
                    t_prep = Decimal(op.get('tiempo_preparacion', 0))
                    t_ejec_unit = Decimal(op.get('tiempo_ejecucion_unitario', 0))
                    tiempo_total_orden += t_prep + (t_ejec_unit * cantidad)

                # Acumular la carga TOTAL en la línea asignada para la fecha de inicio
                carga_por_centro_y_fecha[linea_asignada][fecha_iso] += tiempo_total_orden
                # logger.info(f"OP {orden.get('codigo')}: Carga de {tiempo_total_orden:.2f} min asignada a Línea {linea_asignada} en {fecha_iso}")


            except (ValueError, TypeError, AttributeError) as e:
                 logger.error(f"Error procesando OP {orden.get('codigo', orden.get('id'))} para cálculo de carga: {e}", exc_info=True)
                 continue # Saltar esta OP si hay error en sus datos

        # Convertir defaultdicts a dicts normales y redondear/convertir a float
        resultado_final_float = {}
        for centro_id, cargas_fecha in carga_por_centro_y_fecha.items():
            # Convierte Decimal a float y redondea si quieres (opcional)
            resultado_final_float[centro_id] = {fecha: float(round(carga, 2)) for fecha, carga in cargas_fecha.items()}

        # return resultado_final # <- Línea antigua
        return resultado_final_float # <- Devolver el diccionario con floats
