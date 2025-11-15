import logging
from collections import defaultdict
from app.controllers.base_controller import BaseController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from typing import List, Optional, Dict
from datetime import date, timedelta, datetime
from collections import defaultdict
import locale
from app.models.receta import RecetaModel
from app.models.insumo import InsumoModel
import math
from app.controllers.inventario_controller import InventarioController
from app.models.centro_trabajo_model import CentroTrabajoModel
from app.models.operacion_receta_model import OperacionRecetaModel
from decimal import Decimal
import os # <-- Añadir
from datetime import date # <-- Asegúrate que esté
from flask import jsonify # <-- Añadir (o usar desde tu BaseController si ya lo tienes)
from app.models.bloqueo_capacidad_model import BloqueoCapacidadModel # (Debes crear este modelo simple)
from app.models.issue_planificacion_model import IssuePlanificacionModel
import holidays


logger = logging.getLogger(__name__)

class PlanificacionController(BaseController):
    def __init__(self):
        super().__init__()
        self.orden_produccion_controller = OrdenProduccionController()
        self.inventario_controller = InventarioController()
        self.centro_trabajo_model = CentroTrabajoModel()
        self.operacion_receta_model = OperacionRecetaModel()
        self.receta_model = RecetaModel() # Asegúrate que esté inicializado
        self.insumo_model = InsumoModel() # Asegúrate que esté inicializado
        self.bloqueo_capacidad_model = BloqueoCapacidadModel() # <-- Añadir esto
        self.issue_planificacion_model = IssuePlanificacionModel()
        self.feriados_ar_cache = None # <-- ¡AÑADIR ESTA LÍNEA!


    def _calcular_sugerencias_para_op_optimizado(self, op: Dict, mapas_precargados: Dict) -> Dict:
        """
        Versión optimizada que NO consulta la DB.
        Calcula T_Prod, T_Proc, Línea Sug, y JIT para una ÚNICA OP
        usando los mapas de datos precargados.
        --- CORREGIDA PARA DÍAS NO LABORABLES ---
        """
        # Valores por defecto
        sugerencias = {
            'sugerencia_t_prod_dias': 0,
            'sugerencia_t_proc_dias': 0,
            'sugerencia_linea': None,
            'sugerencia_stock_ok': False,
            'sugerencia_fecha_inicio_jit': date.today().isoformat(),
            'linea_compatible': None
        }
        op_id_log = op.get('id', 'N/A')

        try:
            receta_id = op.get('receta_id')
            cantidad = Decimal(op.get('cantidad_planificada', 0))

            if not receta_id or cantidad <= 0:
                return sugerencias # Devuelve default si no hay datos

            # Mapas de datos
            operaciones_map = mapas_precargados.get('operaciones', {})
            recetas_map = mapas_precargados.get('recetas', {})
            centros_map = mapas_precargados.get('centros_trabajo', {})
            ingredientes_map = mapas_precargados.get('ingredientes', {})
            stock_map = mapas_precargados.get('stock', {})
            insumos_map = mapas_precargados.get('insumos', {})

            # 1. Calcular Carga Total (¡Usando helper optimizado!)
            operaciones_receta = operaciones_map.get(receta_id, [])
            carga_total_minutos = self._calcular_carga_op_precargada(op, operaciones_receta)

            # ... (Pasos 2-4: Calcular Línea, Capacidad y T_Prod - SIN CAMBIOS) ...
            # [Lógica copiada de planificacion_controller.py, lines 934-972]
            linea_sug = None
            capacidad_neta_linea_sugerida = Decimal(480.0)
            receta = recetas_map.get(receta_id)
            if receta:
                linea_compatible_str = receta.get('linea_compatible', '2')
                sugerencias['linea_compatible'] = linea_compatible_str
                linea_compatible_list = linea_compatible_str.split(',')
                tiempo_l1 = receta.get('tiempo_prod_unidad_linea1', 0)
                tiempo_l2 = receta.get('tiempo_prod_unidad_linea2', 0)
                UMBRAL_CANTIDAD_LINEA_1 = 50
                puede_l1 = '1' in linea_compatible_list and tiempo_l1 > 0
                puede_l2 = '2' in linea_compatible_list and tiempo_l2 > 0
                if puede_l1 and puede_l2:
                    linea_sug = 1 if cantidad >= UMBRAL_CANTIDAD_LINEA_1 else 2
                elif puede_l1: linea_sug = 1
                elif puede_l2: linea_sug = 2
                sugerencias['sugerencia_linea'] = linea_sug
                if linea_sug:
                    ct_data = centros_map.get(linea_sug)
                    if ct_data:
                        cap_std = Decimal(ct_data.get('tiempo_disponible_std_dia', 480))
                        eficiencia = Decimal(ct_data.get('eficiencia', 1.0))
                        utilizacion = Decimal(ct_data.get('utilizacion', 1.0))
                        cap_neta_calculada = cap_std * eficiencia * utilizacion
                        if cap_neta_calculada > 0:
                            capacidad_neta_linea_sugerida = cap_neta_calculada
            if carga_total_minutos > 0:
                sugerencias['sugerencia_t_prod_dias'] = math.ceil(
                    carga_total_minutos / capacidad_neta_linea_sugerida
                )

            # ... (Paso 5: Verificar Stock (T_Proc) - SIN CAMBIOS) ...
            # [Lógica copiada de planificacion_controller.py, lines 974-1002]
            ingredientes_receta = ingredientes_map.get(receta_id, [])
            stock_ok_agg = True
            tiempos_entrega_agg = []
            if ingredientes_receta:
                for ingrediente in ingredientes_receta:
                    insumo_id = ingrediente['id_insumo']
                    cantidad_ingrediente = Decimal(ingrediente.get('cantidad', 0))
                    cant_necesaria_total = cantidad_ingrediente * cantidad
                    stock_disp = stock_map.get(insumo_id, Decimal(0))
                    if stock_disp < cant_necesaria_total:
                        stock_ok_agg = False
                        insumo_data = insumos_map.get(insumo_id)
                        if insumo_data:
                            tiempos_entrega_agg.append(insumo_data.get('tiempo_entrega_dias', 0))
            else:
                stock_ok_agg = False
            sugerencias['sugerencia_stock_ok'] = stock_ok_agg
            if not stock_ok_agg:
                sugerencias['sugerencia_t_proc_dias'] = max(tiempos_entrega_agg) if tiempos_entrega_agg else 0

            # --- PASO 6: CALCULAR JIT (CORREGIDO) ---
            today = date.today()
            t_prod_dias = sugerencias['sugerencia_t_prod_dias']
            t_proc_dias = sugerencias['sugerencia_t_proc_dias']

            op_fecha_meta_str = op.get('fecha_meta')
            if not op_fecha_meta_str:
                op_fecha_meta_str = op.get('fecha_inicio_planificada')
                if not op_fecha_meta_str:
                    op_fecha_meta_str = (today + timedelta(days=7)).isoformat()

            fecha_meta_solo_str = op_fecha_meta_str.split('T')[0].split(' ')[0]
            fecha_meta_original = date.fromisoformat(fecha_meta_solo_str)

            # --- ¡INICIO DE LA CORRECCIÓN! ---
            # 1. Ajustar la Fecha Meta hacia atrás al último día laborable
            fecha_meta_ajustada = self._ajustar_meta_a_dia_laborable(fecha_meta_original)

            # 2. Calcular JIT usando la meta ajustada
            fecha_inicio_ideal = fecha_meta_ajustada - timedelta(days=t_prod_dias)
            fecha_disponibilidad_material = today + timedelta(days=t_proc_dias)
            fecha_inicio_base = max(fecha_inicio_ideal, fecha_disponibilidad_material)
            fecha_inicio_sugerida_jit = max(fecha_inicio_base, today)

            # 3. Ajustar la fecha de inicio sugerida hacia adelante al próximo día laborable
            fecha_inicio_sugerida_jit_laborable = self._ajustar_inicio_a_dia_laborable(fecha_inicio_sugerida_jit)

            sugerencias['sugerencia_fecha_inicio_jit'] = fecha_inicio_sugerida_jit_laborable.isoformat()
            # --- FIN DE LA CORRECCIÓN ---

        except Exception as e_jit:
            logger.error(f"[JIT MODAL {op_id_log}] EXCEPCIÓN INESPERADA (Optimizado): {e_jit}", exc_info=True)
            sugerencias['sugerencia_fecha_inicio_jit'] = date.today().isoformat()

        return sugerencias

    # ==================================================================
    # === 1. AÑADE ESTA NUEVA FUNCIÓN COMPLETA ===
    # Esta es la lógica que vamos a mover.
    # ==================================================================
    def ejecutar_planificacion_adaptativa(self, usuario_id: int) -> tuple:
        """
        Ejecuta la verificación de capacidad proactiva para los próximos 7 días.
        Esta función está diseñada para ser llamada por una TAREA PROGRAMADA (CRON).
        """
        logger.info("[PlanAdaptativa_CRON] INICIANDO TAREA PROGRAMADA.")
        nuevos_issues_generados = 0
        errores_encontrados = []

        try:
            fecha_inicio_chequeo = date.today()

            for i in range(15): # Chequear Hoy + 6 días
                fecha_a_chequear = fecha_inicio_chequeo + timedelta(days=i)

                if not self._es_dia_laborable(fecha_a_chequear):
                    logger.info(f"[PlanAdaptativa_CRON] Omitiendo chequeo para {fecha_a_chequear.isoformat()} (No laborable).")
                    continue

                logger.info(f"[PlanAdaptativa_CRON] Verificando día laborable: {fecha_a_chequear.isoformat()}...")

                try:
                    # Esta es la misma función que tenías antes
                    nuevos_issues_del_dia = self._verificar_y_replanificar_ops_por_fecha(
                        fecha=fecha_a_chequear,
                        usuario_id=usuario_id
                    )
                    if nuevos_issues_del_dia:
                        nuevos_issues_generados += len(nuevos_issues_del_dia)
                except Exception as e_dia:
                     logger.error(f"[PlanAdaptativa_CRON] Error verificando {fecha_a_chequear.isoformat()}: {e_dia}")
                     errores_encontrados.append(f"Error en {fecha_a_chequear.isoformat()}: {str(e_dia)}")

        except Exception as e_adapt:
            logger.error(f"[PlanAdaptativa_CRON] Error fatal en la TAREA PROGRAMADA: {e_adapt}", exc_info=True)
            errores_encontrados.append(f"Error fatal: {str(e_adapt)}")
            return self.error_response(f"Error fatal: {e_adapt}", 500)

        logger.info("[PlanAdaptativa_CRON] TAREA PROGRAMADA FINALIZADA.")
        return self.success_response(data={
            'issues_generados': nuevos_issues_generados,
            'errores': len(errores_encontrados),
            'detalles_error': errores_encontrados
        })
    def obtener_datos_para_vista_planificacion(self, week_str: str, horizonte_dias: int, current_user_id: int, current_user_rol: str) -> tuple:
        """
        Método orquestador que obtiene y procesa todos los datos necesarios para la
        vista de planificación de forma optimizada (con Precarga Total).
        """
        try:
            # --- Tarea de fondo (movida al scheduler) ---
            nuevos_issues_generados = []

            # 1. Determinar rango de la semana (Sin cambios)
            if week_str:
                try:
                    year, week_num = map(int, week_str.split('-W'))
                    inicio_semana = date.fromisocalendar(year, week_num, 1)
                except ValueError:
                    return self.error_response("Formato de semana inválido.", 400)
            else:
                today = date.today()
                inicio_semana = today - timedelta(days=today.weekday())

            fin_semana = inicio_semana + timedelta(days=6)

            # 2. Consulta de Órdenes de Producción (Sin cambios)
            estados_planificados_validos = [
                'EN ESPERA', 'EN_ESPERA',
                'LISTA PARA PRODUCIR', 'LISTA_PARA_PRODUCIR',
                'EN_LINEA_1', 'EN_LINEA_2',
                'EN_EMPAQUETADO',
                'CONTROL_DE_CALIDAD'
            ]
            filtros_planificadas = {
                'estado': ('in', estados_planificados_validos)
            }
            response_ops_planificadas, _ = self.orden_produccion_controller.obtener_ordenes(filtros_planificadas)
            if not response_ops_planificadas.get('success'):
                 return self.error_response("Error al obtener las órdenes planificadas.", 500)
            ops_planificadas = response_ops_planificadas.get('data', [])

            # 3. Procesamiento en Memoria (¡MODIFICADO!)
            # Primera llamada a MPS: solo para obtener la lista de OPs crudas
            response_mps, _ = self.obtener_ops_pendientes_planificacion(dias_horizonte=horizonte_dias, mapas_precargados_externos=None)
            mps_data_inicial = response_mps.get('data', {}) if response_mps.get('success') else {}

            # --- ¡INICIO DE LA PRECARGA TOTAL! ---
            logger.info("[Precarga] Iniciando precarga total de datos...")

            # A. Recolectar todos los IDs necesarios
            # Combinar OPs del calendario Y OPs pendientes
            all_ops = ops_planificadas + mps_data_inicial.get('mps_agrupado_ops_raw', [])
            receta_ids_globales = list(set(op.get('receta_id') for op in all_ops if op.get('receta_id')))

            # B. Consultar Modelos UNA SOLA VEZ
            operaciones_resp = self.operacion_receta_model.find_by_receta_ids(receta_ids_globales)
            recetas_resp = self.receta_model.find_by_ids(receta_ids_globales)
            ingredientes_resp = self.receta_model.get_ingredientes_by_receta_ids(receta_ids_globales)
            centros_resp = self.centro_trabajo_model.find_all() # Son solo 2-3, es barato
            stock_resp = self.inventario_controller.get_all_stock_disponible_map()

            # C. Construir los Mapas de Datos
            mapas_precargados = {
                'operaciones': defaultdict(list),
                'recetas': {r['id']: r for r in recetas_resp.get('data', [])},
                'centros_trabajo': {c['id']: c for c in centros_resp.get('data', [])},
                'ingredientes': defaultdict(list),
                'stock': stock_resp.get('data', {}),
                'insumos': {}
            }

            # Poblar mapa de operaciones
            for op_step in operaciones_resp.get('data', []):
                mapas_precargados['operaciones'][op_step['receta_id']].append(op_step)

            # Poblar mapas de ingredientes e insumos
            insumos_map_temp = {}
            if ingredientes_resp.get('success'):
                for ing in ingredientes_resp.get('data', []):
                    mapas_precargados['ingredientes'][ing['receta_id']].append(ing)

                    # --- ¡INICIO DE LA CORRECCIÓN! ---
                    # Cambiar 'insumos' por 'insumos_catalogo' para que coincida con la consulta
                    if ing.get('insumos_catalogo') and 'id_insumo' in ing.get('insumos_catalogo'):
                        insumo_data = ing.get('insumos_catalogo')
                    # --- FIN DE LA CORRECCIÓN! ---

                        insumos_map_temp[insumo_data['id_insumo']] = insumo_data

            mapas_precargados['insumos'] = insumos_map_temp
            logger.info(f"[Precarga] Finalizada. {len(mapas_precargados['recetas'])} recetas, {len(mapas_precargados['ingredientes'])} grupos de ingr., {len(mapas_precargados['stock'])} items de stock.")
            # --- ¡FIN DE LA PRECARGA TOTAL! ---

            # 3.b. Segunda llamada a MPS (¡AHORA CON MAPAS!)
            # Esta vez calculará las sugerencias JIT usando los mapas.
            response_mps_optimizado, _ = self.obtener_ops_pendientes_planificacion(
                dias_horizonte=horizonte_dias,
                mapas_precargados_externos=mapas_precargados
            )
            mps_data = response_mps_optimizado.get('data', {}) if response_mps_optimizado.get('success') else {}

            # 4. Obtener Planificación Semanal (¡AHORA CON MAPAS!)
            response_semanal, _ = self.obtener_planificacion_semanal(
                week_str,
                ordenes_pre_cargadas=ops_planificadas,
                mapas_precargados_externos=mapas_precargados # <--- ¡NUEVO!
            )
            data_semanal = response_semanal.get('data', {}) if response_semanal.get('success') else {}
            ordenes_por_dia = data_semanal.get('ops_visibles_por_dia', {})

            # --- Filtro para CRP (de la corrección anterior) ---
            ops_de_la_semana_set = set()
            for ops_del_dia in ordenes_por_dia.values():
                for op in ops_del_dia:
                    ops_de_la_semana_set.add(op['id'])
            ops_filtradas_para_semana = [
                op for op in ops_planificadas if op.get('id') in ops_de_la_semana_set
            ]
            # --- Fin Filtro CRP ---

            # --- Enriquecimiento del Calendario (¡ACTUALIZADO!) ---
            enriched_ordenes_por_dia = {}
            if ordenes_por_dia:
                for dia_iso, ops_del_dia in ordenes_por_dia.items():
                    ops_enriquecidas_dia = []
                    for op in ops_del_dia:
                        # Usar la función optimizada
                        sugerencias = self._calcular_sugerencias_para_op_optimizado(op, mapas_precargados) # <--- ¡OPTIMIZADO!
                        op['sugerencias_jit'] = sugerencias
                        ops_enriquecidas_dia.append(op)
                    enriched_ordenes_por_dia[dia_iso] = ops_enriquecidas_dia

            # --- CRP Data (¡ACTUALIZADO!) ---

            # 1. Obtenemos la carga "completa" (que puede tener fugas a 30 días)
            carga_calculada_full = self.calcular_carga_capacidad(ops_filtradas_para_semana, mapas_precargados_externos=mapas_precargados) # <-- ¡RENOMBRADA!

            # 2. Obtenemos la capacidad (que SÍ está limitada a la semana)
            capacidad_disponible = self.obtener_capacidad_disponible([1, 2], inicio_semana, fin_semana)

            # --- ¡INICIO DE LA CORRECCIÓN! ---
            # Filtramos la carga para que solo incluya los días de esta semana.
            # Usamos las claves de 'capacidad_disponible' como el filtro maestro.

            dias_de_la_semana_l1 = set(capacidad_disponible.get(1, {}).keys())
            dias_de_la_semana_l2 = set(capacidad_disponible.get(2, {}).keys())

            # 3. Creamos la carga FILTRADA (esta SÍ usa carga_calculada_full)
            carga_calculada_filtrada = {
                1: {fecha: carga for fecha, carga in carga_calculada_full.get(1, {}).items() # <-- Ahora funciona
                    if fecha in dias_de_la_semana_l1},
                2: {fecha: carga for fecha, carga in carga_calculada_full.get(2, {}).items() # <-- Ahora funciona
                    if fecha in dias_de_la_semana_l2}
            }
            # --- FIN DE LA CORRECCIÓN --

            # --- ¡BLOQUE DE ISSUES (¡ACTUALIZADO!) ---
            # ... (Lógica de combinación de issues sin cambios) ...
            response_issues = self.issue_planificacion_model.get_all_with_op_details()
            all_issues_raw = response_issues.get('data', []) if response_issues.get('success') else []
            planning_issues_raw_db = [issue for issue in all_issues_raw if issue.get('estado', 'PENDIENTE') == 'PENDIENTE']
            op_ids_en_memoria = {issue['orden_produccion_id'] for issue in nuevos_issues_generados}
            planning_issues_a_procesar = list(nuevos_issues_generados)
            for db_issue in planning_issues_raw_db:
                if db_issue.get('orden_produccion_id') not in op_ids_en_memoria:
                    planning_issues_a_procesar.append(db_issue)

            enriched_planning_issues = []
            enriched_planning_notifications = []

            if planning_issues_a_procesar:
                for issue in planning_issues_a_procesar:
                    # ... (lógica de 'if not op_id_para_jit') ...
                    if not issue.get('orden_produccion_id'): continue

                    # ... (lógica de 'if 'receta_id' in issue' para obtener op_data_real) ...
                    op_id_para_jit = issue.get('orden_produccion_id')
                    op_data_real = None
                    if 'receta_id' in issue:
                        op_data_real = issue
                    else:
                        op_result = self.orden_produccion_controller.obtener_orden_por_id(op_id_para_jit)
                        if op_result.get('success'):
                            op_data_real = op_result.get('data')
                            issue['op_codigo'] = op_data_real.get('codigo')
                            issue['op_producto_nombre'] = op_data_real.get('producto_nombre')
                            issue['cantidad_planificada'] = op_data_real.get('cantidad_planificada')
                            issue['op_fecha_meta'] = op_data_real.get('fecha_meta')
                        else:
                            logger.warning(f"[Vista Planif.] Issue {issue.get('id')} (OP: {op_id_para_jit}): NO SE PUDO CARGAR LA OP.")

                    # --- ¡CAMBIO! ---
                    if op_data_real:
                        sugerencias = self._calcular_sugerencias_para_op_optimizado(op_data_real, mapas_precargados) # <--- ¡OPTIMIZADO!
                    else:
                        sugerencias = {} # Fallback si la OP no se pudo cargar
                    issue['sugerencias_jit'] = sugerencias

                    # ... (Lógica de separación de issues/notificaciones) ...
                    if issue.get('tipo_error') == 'REPLAN_AUTO_AUSENCIA':
                        enriched_planning_notifications.append(issue)
                    else:
                        enriched_planning_issues.append(issue)
            # --- FIN BLOQUE ISSUES ---

            # 4. Obtener Datos Auxiliares (Usuarios) (Sin cambios)
            from app.controllers.usuario_controller import UsuarioController
            usuario_controller = UsuarioController()
            supervisores_resp = usuario_controller.obtener_usuarios_por_rol(['SUPERVISOR'])
            operarios_resp = usuario_controller.obtener_usuarios_por_rol(['OPERARIO'])
            supervisores = supervisores_resp.get('data', []) if supervisores_resp.get('success') else []
            operarios = operarios_resp.get('data', []) if operarios_resp.get('success') else []

            # 5. Ensamblar el resultado final (Sin cambios)
            datos_vista = {
                'mps_data': mps_data,
                'ordenes_por_dia': enriched_ordenes_por_dia,
                'carga_crp': carga_calculada_filtrada,
                'capacidad_crp': capacidad_disponible,
                'supervisores': supervisores,
                'operarios': operarios,
                'inicio_semana': inicio_semana.isoformat(),
                'fin_semana': fin_semana.isoformat(),
                'planning_issues': enriched_planning_issues,
                'planning_notifications': enriched_planning_notifications
            }

            return self.success_response(data=datos_vista)

        except Exception as e:
            logger.error(f"Error en obtener_datos_para_vista_planificacion: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    def _ajustar_meta_a_dia_laborable(self, fecha_meta: date) -> date:
        """
        Ajusta una Fecha Meta al último día laborable ANTERIOR o IGUAL.
        Ej: Domingo 16 -> Viernes 14.
        Ej: Sábado 15 -> Viernes 14.
        Ej: Viernes 14 -> Viernes 14.
        """
        fecha_ajustada = fecha_meta
        dias_chequeados = 0

        # Mover hacia atrás MIENTRAS no sea un día laborable
        while not self._es_dia_laborable(fecha_ajustada) and dias_chequeados < 7:
            fecha_ajustada -= timedelta(days=1)
            dias_chequeados += 1

        if dias_chequeados == 7:
            logger.warning(f"No se encontró día laborable para la meta {fecha_meta.isoformat()}. Usando meta original.")
            return fecha_meta # Fallback

        return fecha_ajustada
    def _ajustar_inicio_a_dia_laborable(self, fecha_inicio: date) -> date:
        """
        Ajusta una Fecha de Inicio al próximo día laborable SIGUIENTE o IGUAL.
        Ej: Sábado 15 -> Lunes 17.
        Ej: Domingo 16 -> Lunes 17.
        Ej: Lunes 17 -> Lunes 17.
        """
        fecha_ajustada = fecha_inicio
        dias_chequeados = 0

        # Mover hacia adelante MIENTRAS no sea un día laborable
        while not self._es_dia_laborable(fecha_ajustada) and dias_chequeados < 7:
            fecha_ajustada += timedelta(days=1)
            dias_chequeados += 1

        if dias_chequeados == 7:
            logger.warning(f"No se encontró día laborable para el inicio {fecha_inicio.isoformat()}. Usando inicio original.")
            return fecha_inicio # Fallback

        return fecha_ajustada

    def _calcular_sugerencias_para_op(self, op: Dict) -> Dict:
        """
        Calcula T_Prod, T_Proc, Línea Sug, y JIT para una ÚNICA OP.
        (Versión LENTA, N+1 queries. Necesaria para la 1ra pasada de precarga).
        --- CORREGIDA PARA DÍAS NO LABORABLES ---
        """
        # Valores por defecto
        sugerencias = {
            'sugerencia_t_prod_dias': 0,
            'sugerencia_t_proc_dias': 0,
            'sugerencia_linea': None,
            'sugerencia_stock_ok': False,
            'sugerencia_fecha_inicio_jit': date.today().isoformat(),
            'linea_compatible': None
        }
        op_id_log = op.get('id', 'N/A')

        try:
            receta_id = op.get('receta_id')
            cantidad = Decimal(op.get('cantidad_planificada', 0))

            if not receta_id or cantidad <= 0:
                logger.warning(f"[JIT Modal {op_id_log}] Cálculo abortado: falta receta_id o cantidad es 0.")
                return sugerencias

            # ... (Pasos 1-4: Calcular Carga, Línea, Capacidad y T_Prod - SIN CAMBIOS) ...
            # [Lógica copiada de planificacion_controller.py, lines 1729-1772]
            carga_total_minutos = Decimal(self._calcular_carga_op(op))
            receta_res = self.receta_model.find_by_id(receta_id, 'id')
            linea_sug = None
            capacidad_neta_linea_sugerida = Decimal(480.0)
            if receta_res.get('success'):
                receta = receta_res['data']
                linea_compatible_str = receta.get('linea_compatible', '2')
                sugerencias['linea_compatible'] = linea_compatible_str
                linea_compatible_list = linea_compatible_str.split(',')
                tiempo_l1 = receta.get('tiempo_prod_unidad_linea1', 0)
                tiempo_l2 = receta.get('tiempo_prod_unidad_linea2', 0)
                UMBRAL_CANTIDAD_LINEA_1 = 50
                puede_l1 = '1' in linea_compatible_list and tiempo_l1 > 0
                puede_l2 = '2' in linea_compatible_list and tiempo_l2 > 0
                if puede_l1 and puede_l2:
                    linea_sug = 1 if cantidad >= UMBRAL_CANTIDAD_LINEA_1 else 2
                elif puede_l1: linea_sug = 1
                elif puede_l2: linea_sug = 2
                sugerencias['sugerencia_linea'] = linea_sug
                if linea_sug:
                    ct_resp = self.centro_trabajo_model.find_by_id(linea_sug, 'id')
                    if ct_resp.get('success'):
                        ct_data = ct_resp.get('data', {})
                        cap_std = Decimal(ct_data.get('tiempo_disponible_std_dia', 480))
                        eficiencia = Decimal(ct_data.get('eficiencia', 1.0))
                        utilizacion = Decimal(ct_data.get('utilizacion', 1.0))
                        cap_neta_calculada = cap_std * eficiencia * utilizacion
                        if cap_neta_calculada > 0:
                            capacidad_neta_linea_sugerida = cap_neta_calculada
            if carga_total_minutos > 0:
                sugerencias['sugerencia_t_prod_dias'] = math.ceil(
                    carga_total_minutos / capacidad_neta_linea_sugerida
                )

            # ... (Paso 5: Verificar Stock (T_Proc) - SIN CAMBIOS) ...
            # [Lógica copiada de planificacion_controller.py, lines 1774-1808]
            ingredientes_result = self.receta_model.get_ingredientes(receta_id)
            insumos_faltantes_agg = []
            stock_ok_agg = True
            tiempos_entrega_agg = []
            if ingredientes_result.get('success'):
                for ingrediente in ingredientes_result.get('data', []):
                    insumo_id = ingrediente['id_insumo']
                    try: cantidad_ingrediente = Decimal(ingrediente['cantidad'])
                    except: cantidad_ingrediente = Decimal(0)
                    cant_necesaria_total = cantidad_ingrediente * cantidad
                    stock_disp_res = self.inventario_controller.obtener_stock_disponible_insumo(insumo_id)
                    stock_disp_raw = stock_disp_res.get('data', {}).get('stock_disponible', 0) if stock_disp_res.get('success') else 0
                    try: stock_disp = Decimal(stock_disp_raw)
                    except: stock_disp = Decimal(0)
                    if stock_disp < cant_necesaria_total:
                        stock_ok_agg = False
                        faltante = cant_necesaria_total - stock_disp
                        insumos_faltantes_agg.append({ 'insumo_id': insumo_id, 'nombre': ingrediente.get('nombre_insumo', 'N/A'), 'cantidad_faltante': faltante })
                        insumo_data_res = self.insumo_model.find_by_id(insumo_id, 'id_insumo')
                        if insumo_data_res.get('success'):
                            tiempos_entrega_agg.append(insumo_data_res['data'].get('tiempo_entrega_dias', 0))
            else:
                stock_ok_agg = False
            sugerencias['sugerencia_stock_ok'] = stock_ok_agg
            if not stock_ok_agg:
                sugerencias['sugerencia_t_proc_dias'] = max(tiempos_entrega_agg) if tiempos_entrega_agg else 0

            # --- PASO 6: CALCULAR JIT (CORREGIDO) ---
            today = date.today()
            t_prod_dias = sugerencias['sugerencia_t_prod_dias']
            t_proc_dias = sugerencias['sugerencia_t_proc_dias']

            op_fecha_meta_str = op.get('fecha_meta')
            if not op_fecha_meta_str:
                op_fecha_meta_str = op.get('fecha_inicio_planificada')
                if not op_fecha_meta_str:
                    op_fecha_meta_str = (today + timedelta(days=7)).isoformat()

            fecha_meta_solo_str = op_fecha_meta_str.split('T')[0].split(' ')[0]
            fecha_meta_original = date.fromisoformat(fecha_meta_solo_str)

            # --- ¡INICIO DE LA CORRECCIÓN! ---
            # 1. Ajustar la Fecha Meta hacia atrás al último día laborable
            fecha_meta_ajustada = self._ajustar_meta_a_dia_laborable(fecha_meta_original)

            # 2. Calcular JIT usando la meta ajustada
            fecha_inicio_ideal = fecha_meta_ajustada - timedelta(days=t_prod_dias)
            fecha_disponibilidad_material = today + timedelta(days=t_proc_dias)
            fecha_inicio_base = max(fecha_inicio_ideal, fecha_disponibilidad_material)
            fecha_inicio_sugerida_jit = max(fecha_inicio_base, today)

            # 3. Ajustar la fecha de inicio sugerida hacia adelante al próximo día laborable
            fecha_inicio_sugerida_jit_laborable = self._ajustar_inicio_a_dia_laborable(fecha_inicio_sugerida_jit)

            sugerencias['sugerencia_fecha_inicio_jit'] = fecha_inicio_sugerida_jit_laborable.isoformat()
            # --- FIN DE LA CORRECCIÓN ---

        except Exception as e_jit:
            op_id_log = op.get('id', 'N/A')
            logger.error(f"[JIT MODAL {op_id_log}] EXCEPCIÓN INESPERADA en _calcular_sugerencias_para_op: {e_jit}", exc_info=True)
            sugerencias['sugerencia_fecha_inicio_jit'] = date.today().isoformat()

        return sugerencias

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

    # --- HELPER: Ejecuta la aprobación final ---
    def _ejecutar_aprobacion_final(self, op_id: any, asignaciones: dict, usuario_id: int) -> tuple:
        """
        Ejecuta los pasos de pre-asignación y confirmación/aprobación.
        --- CORREGIDO ---
        'op_id' ahora puede ser un INT (una OP) o una LIST (grupo de OPs).
        Si es una LISTA, primero ejecuta la consolidación.
        """
        try:
            op_id_real_a_planificar = None

            if isinstance(op_id, list):
                # Es un grupo, debemos consolidarlo AHORA
                if len(op_id) > 1:
                    logger.info(f"[Aprobación] Consolidando grupo de OPs: {op_id}")
                    # 1. Llamar al controlador de OP para crear la "Super OP"
                    resultado_consol = self.orden_produccion_controller.consolidar_ordenes_produccion(op_id, usuario_id)
                    if not resultado_consol.get('success'):
                        logger.error(f"Fallo al consolidar el grupo {op_id} durante la aprobación final: {resultado_consol.get('error')}")
                        return self.error_response(f"Error al consolidar grupo: {resultado_consol.get('error')}", 500)

                    op_id_real_a_planificar = resultado_consol.get('data', {}).get('id')
                    if not op_id_real_a_planificar:
                         return self.error_response("La consolidación fue exitosa pero no devolvió un ID.", 500)
                    logger.info(f"[Aprobación] Grupo consolidado en nueva Super OP: {op_id_real_a_planificar}")

                elif len(op_id) == 1:
                    # Es una lista con un solo ID (del fallback)
                    op_id_real_a_planificar = op_id[0]
                else:
                    return self.error_response("Se intentó aprobar un grupo vacío.", 400)

            elif isinstance(op_id, int):
                # Es una OP individual
                op_id_real_a_planificar = op_id

            if not op_id_real_a_planificar:
                 return self.error_response("ID de OP inválido para aprobación final.", 400)

            # --- A partir de aquí, el flujo es el mismo, pero usa op_id_real_a_planificar ---

            self._resolver_issue_por_op(op_id_real_a_planificar)

            if isinstance(op_id, list):
                for op_hija_id in op_id:
                    self._resolver_issue_por_op(op_hija_id) # Resolver issues de las OPs hijas

            datos_pre_asignar = {
                'linea_asignada': asignaciones.get('linea_asignada'),
                'supervisor_responsable_id': asignaciones.get('supervisor_id'),
                'operario_asignado_id': asignaciones.get('operario_id')
            }
            datos_pre_asignar = {k: v for k, v in datos_pre_asignar.items() if v is not None}

            res_pre_asig_dict, res_pre_asig_status = self.orden_produccion_controller.pre_asignar_recursos(
                op_id_real_a_planificar, datos_pre_asignar, usuario_id
            )
            if res_pre_asig_status >= 400: return res_pre_asig_dict, res_pre_asig_status

            res_conf_dict, res_conf_status = self.orden_produccion_controller.confirmar_inicio_y_aprobar(
                op_id_real_a_planificar, {'fecha_inicio_planificada': asignaciones.get('fecha_inicio')}, usuario_id
            )
            return res_conf_dict, res_conf_status

        except Exception as e:
            logger.error(f"Error en _ejecutar_aprobacion_final para OP(s) {op_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno al ejecutar aprobación final: {str(e)}", 500)

    def _ejecutar_replanificacion_simple(self, op_id: int, asignaciones: dict, usuario_id: int) -> tuple:
        """
        SOLO actualiza los campos de planificación de una OP que YA ESTÁ planificada
        (Ej: 'EN ESPERA' o 'LISTA PARA PRODUCIR').
        NO cambia el estado ni vuelve a verificar el stock.
        """
        logger.info(f"[RePlan] Ejecutando re-planificación simple para OP {op_id}...")
        try:
            # --- ¡AÑADIR ESTA LÍNEA! ---
            self._resolver_issue_por_op(op_id) # Borra el issue
            # ---------------------------
            # Preparamos los datos a actualizar
            update_data = {
                'fecha_inicio_planificada': asignaciones.get('fecha_inicio'),
                'linea_asignada': asignaciones.get('linea_asignada'),
                'supervisor_responsable_id': asignaciones.get('supervisor_id'),
                'operario_asignado_id': asignaciones.get('operario_id')
            }
            # Limpiar Nones por si el usuario no seleccionó supervisor/operario
            update_data = {k: v for k, v in update_data.items() if v is not None}

            # Usar el controlador de OP para hacer el update directo en el modelo
            update_result = self.orden_produccion_controller.model.update(op_id, update_data, 'id')

            if update_result.get('success'):
                return self.success_response(data=update_result.get('data'), message="OP re-planificada exitosamente.")
            else:
                return self.error_response(f"Error al actualizar la OP: {update_result.get('error')}", 500)

        except Exception as e:
            logger.error(f"Error en _ejecutar_replanificacion_simple para OP {op_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

   # --- MÉTODO PRINCIPAL MODIFICADO ---
    def consolidar_y_aprobar_lote(self, op_ids: List[int], asignaciones: dict, usuario_id: int) -> tuple:
        """
        Orquesta: SIMULA la consolidación, VERIFICA CAPACIDAD MULTI-DÍA,
        y devuelve el resultado de la simulación (OK, LATE, MULTI_DIA, SOBRECARGA).
        DEVUELVE TUPLA (dict, status_code)
        """
        try:
            # 1. Obtener los datos de la OP (ya sea una existente o una consolidada nueva)
            # op_a_planificar_id será el ID de la OP a procesar, o un string de error si falla.
            op_a_planificar_id, op_data = self._obtener_datos_op_a_planificar(op_ids, usuario_id)

            # Si _obtener_datos_op_a_planificar falló, op_a_planificar_id contiene el mensaje de error.
            if not op_data:
                return self.error_response(op_a_planificar_id, 500)

            op_estado_actual = op_data.get('estado')

            # --- INICIO DE LA NUEVA VALIDACIÓN (Manual) ---
            # (Se coloca DESPUÉS de _obtener_datos_op_a_planificar)

            # Variable para forzar advertencia
            adv_cantidad_minima = False
            msg_cantidad_minima = ""

            producto_id = op_data.get('producto_id')
            if producto_id:
                logger.warning(f"--- [Simulación CHECK 2] Verificando Producto ID: {producto_id} (para OP/Grupo: {op_a_planificar_id}) ---")

                # --- ¡¡INICIO DE LA CORRECCIÓN!! ---
                # producto_resp.get('success') es incorrecto.
                # El método devuelve el DATO o None.
                producto_data = self.orden_produccion_controller.producto_controller.obtener_producto_por_id(producto_id)

                if producto_data: # <-- La comprobación correcta es si producto_data existe
                # --- ¡¡FIN DE LA CORRECCIÓN!! ---

                    # producto_data = producto_resp.get('data', {}) # <-- Ya no es necesario
                    cantidad_minima = Decimal(producto_data.get('cantidad_minima_produccion', 0))
                    cantidad_a_planificar = Decimal(op_data.get('cantidad_planificada', 0))

                    logger.warning(f"[Simulación CHECK 2] Producto: {producto_data.get('nombre', 'N/A')}")
                    logger.warning(f"[Simulación CHECK 2] Cant. Mínima (DB): {cantidad_minima}")
                    logger.warning(f"[Simulación CHECK 2] Cant. a Planificar (OP/Grupo): {cantidad_a_planificar}")

                    if cantidad_minima > 0 and cantidad_a_planificar < cantidad_minima:
                        logger.error(f"[Simulación CHECK 2] ¡VIOLACIÓN DETECTADA! {cantidad_a_planificar} < {cantidad_minima}. Seteando flag adv_cantidad_minima=True.")
                        adv_cantidad_minima = True
                        msg_cantidad_minima = (f"<b>Atención: Cantidad Mínima no Cumplida.</b>\n"
                                             f"La cantidad a planificar ({cantidad_a_planificar} un.) es menor que el mínimo "
                                             f"rentable de {cantidad_minima} un.\n\n")
                        logger.warning(f"[Planificación Manual] ADVERTENCIA por cantidad mínima para OP(s) {op_a_planificar_id}.")
                    else:
                         logger.warning(f"[Simulación CHECK 2] Chequeo OK. (Mínima: {cantidad_minima}, Planificada: {cantidad_a_planificar})")

                # --- ¡¡INICIO DE LA CORRECCIÓN!! ---
                else:
                    logger.error(f"[Simulación CHECK 2] FALLO. No se pudo obtener producto_data para ID: {producto_id}")
                    # ¡FALLO CRÍTICO! No se pudo cargar el producto. DETENER SIMULACIÓN.
                    return self.error_response(f"Fallo al verificar cantidad mínima: No se pudo cargar Producto ID {producto_id}", 500)
                # --- ¡¡FIN DE LA CORRECCIÓN!! ---

            else:
                logger.error(f"[Simulación CHECK 2] FALLO. La OP/Grupo simulado no tiene 'producto_id'.")
                # ¡FALLO CRÍTICO! No hay producto_id. DETENER SIMULACIÓN.
                return self.error_response("Fallo al verificar cantidad mínima: La OP/Grupo no tiene producto_id.", 500)

            # --- FIN DE LA NUEVA VALIDACIÓN ---


            # 2. Cargar datos de la asignación

            # --- ¡¡NUEVO LOG DE PRUEBA!! ---
            logger.warning(f"[Simulación] Verificando 'asignaciones' recibidas: {asignaciones}")
            # --- ¡¡FIN NUEVO LOG!! ---

            fecha_inicio_iso = asignaciones.get('fecha_inicio')
            linea_asignada = asignaciones.get('linea_asignada')

            if not fecha_inicio_iso or not linea_asignada:
                logger.error(f"[Simulación] ¡FALLO 400! 'fecha_inicio' o 'linea_asignada' están faltando en 'asignaciones'.")
                return self.error_response("Datos de asignación (fecha_inicio, linea_asignada) incompletos.", 400)

            fecha_inicio = date.fromisoformat(fecha_inicio_iso)

            # Actualizar los datos de la OP con las asignaciones (sin guardar, solo para simulación)
            op_data.update(asignaciones)

            # 3. Calcular la carga de la OP
            carga_total_op = self._calcular_carga_op(op_data)
            if carga_total_op <= 0:
                return self.error_response(f"La OP {op_a_planificar_id} tiene una carga de 0 minutos. Verifique la receta.", 400)

            # 4. SIMULAR ASIGNACIÓN
            simulacion_result = self._simular_asignacion_carga(
                carga_total_op=float(carga_total_op),
                linea_propuesta=linea_asignada,
                fecha_inicio_busqueda=fecha_inicio,
                op_id_a_excluir=op_a_planificar_id,
                carga_actual_map=None # Forzar a que recalcule el mapa de carga
            )

            # 5. Analizar el resultado de la simulación
            if not simulacion_result.get('success'):
                # Caso 1: SOBRECARGA (No se pudo planificar)
                # El simulador devuelve el error (SOBRECARGA_CAPACIDAD)
                logger.warning(f"[Simulación] FALLO para OP {op_a_planificar_id}: {simulacion_result.get('error')}")

                if simulacion_result.get('error_type') == 'SOBRECARGA_CAPACIDAD':
                    # Devolvemos el mensaje del simulador al frontend
                    return {
                        'success': False,
                        'error': 'SOBRECARGA_CAPACIDAD',
                        'title': 'Conflicto de Capacidad',
                        'message': simulacion_result.get('error')
                    }, 409 # 409 Conflict
                else:
                    # Otro error de simulación
                    return self.error_response(simulacion_result.get('error', 'Error desconocido en la simulación.'), 500)

            # Caso 2: ÉXITO (Se encontró lugar)
            logger.info(f"[Simulación] ÉXITO para OP {op_a_planificar_id}. Días requeridos: {simulacion_result.get('dias_requeridos', 0)}")

            fecha_fin_estimada = simulacion_result['fecha_fin_estimada']
            dias_requeridos = simulacion_result.get('dias_requeridos', 1)
            es_multi_dia = dias_requeridos > 1

            # 6. Verificar si la planificación resulta en un RETRASO (LATE)
            es_retraso = False
            fecha_meta_str = op_data.get('fecha_meta')
            fecha_meta = None
            if fecha_meta_str:
                try:
                    fecha_meta = date.fromisoformat(fecha_meta_str.split('T')[0].split(' ')[0])
                    if fecha_fin_estimada > fecha_meta:
                        es_retraso = True
                except (ValueError, TypeError):
                    logger.warning(f"Fecha meta inválida '{fecha_meta_str}' para OP {op_a_planificar_id}.")
                    pass # Si la fecha meta es inválida, no podemos compararla.

            # 7. Construir la respuesta final (JSON) para el modal

            # Preparar los datos que se guardarán si el usuario confirma
            datos_para_confirmar = {
                'op_id_confirmar': op_a_planificar_id,
                'asignaciones_confirmar': asignaciones,
                'estado_actual': op_estado_actual
            }

            # --- Añadir nuestra nueva advertencia a los mensajes ---
            msg_final = f"La OP se planificará desde <b>{fecha_inicio_iso}</b> hasta <b>{fecha_fin_estimada.isoformat()}</b>."
            if msg_cantidad_minima:
                msg_final = msg_cantidad_minima + msg_final # Añadir advertencia al inicio

            if es_retraso:
                msg_final += f"\n\n<b>¡Atención!</b> La fecha de finalización ({fecha_fin_estimada.isoformat()}) es posterior a la Fecha Meta ({fecha_meta.isoformat()})."

            if es_multi_dia and not es_retraso:
                 msg_final += "\n\nEsta OP requiere múltiples días. ¿Confirma la planificación?"

            # Decidir el tipo de respuesta

            logger.warning(f"[Simulación CHECK 2] Evaluando flags. adv_cantidad_minima={adv_cantidad_minima}, es_retraso={es_retraso}, es_multi_dia={es_multi_dia}")

            if adv_cantidad_minima:
                # ¡LA VIOLACIÓN DE CANTIDAD MÍNIMA ES LA MÁXIMA PRIORIDAD!
                tipo_confirmacion = 'MIN_QUANTITY_CONFIRM' # Nuevo tipo de confirmación
                titulo_confirmacion = '⚠️ Confirmar Cantidad Mínima'
                logger.error(f"[Simulación CHECK 2] Decisión: MIN_QUANTITY_CONFIRM")
            elif es_retraso:
                tipo_confirmacion = 'LATE_CONFIRM'
                titulo_confirmacion = '⚠️ Confirmar Retraso'
                logger.warning(f"[Simulación CHECK 2] Decisión: LATE_CONFIRM") # Log de fallback
            elif es_multi_dia:
                tipo_confirmacion = 'MULTI_DIA_CONFIRM'
                titulo_confirmacion = 'Confirmación Multi-Día'
                logger.warning(f"[Simulación CHECK 2] Decisión: MULTI_DIA_CONFIRM") # Log de fallback
            else:
                tipo_confirmacion = None # Es un éxito simple
                logger.warning(f"[Simulación CHECK 2] Decisión: OK (None)") # Log de fallback

            if tipo_confirmacion:
                # Devolver un "error" 200 que requiere confirmación
                logger.info(f"[Simulación] Requiere confirmación '{tipo_confirmacion}' para OP {op_a_planificar_id}.")
                return {
                    'success': False, # Éxito de simulación, pero no de guardado
                    'error': tipo_confirmacion,
                    'title': titulo_confirmacion,
                    'message': msg_final,
                    **datos_para_confirmar
                }, 200
            else:
                # Éxito simple, no se requiere confirmación (ej. OP de 1 día, a tiempo, cantidad ok)
                logger.info(f"[Simulación] Éxito simple (sin confirmación) para OP {op_a_planificar_id}.")
                return {
                    'success': True,
                    'message': msg_final,
                    **datos_para_confirmar
                }, 200

        except Exception as e:
            logger.error(f"Error crítico en consolidar_y_aprobar_lote: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    # --- NUEVO HELPER para obtener datos OP (MODIFICADO) ---
    def _obtener_datos_op_a_planificar(self, op_ids: List[int], usuario_id: int) -> tuple:
        """
        Obtiene los datos de la OP.
        --- CORREGIDO ---
        Si es un grupo (op_ids > 1), SIMULA la consolidación en memoria
        en lugar de crear la "Super OP" en la base de datos.
        Devuelve (id, data) o (None, error_msg).
        El 'id' será el id real si es 1 OP, o una lista de IDs si es un grupo.
        """
        if len(op_ids) == 1:
            # Flujo para una sola OP
            op_a_planificar_id = op_ids[0]
            op_result = self.orden_produccion_controller.obtener_orden_por_id(op_a_planificar_id)
            if not op_result.get('success'):
                return None, f"No se encontró la OP ID {op_a_planificar_id}."
            op_data = op_result.get('data')
            return op_a_planificar_id, op_data

        elif len(op_ids) > 1:
            # Flujo para un GRUPO: Simular la consolidación en memoria
            try:
                # 1. Obtener los datos de las OPs originales
                ops_res = self.orden_produccion_controller.model.find_by_ids(op_ids)
                if not ops_res.get('success') or not ops_res.get('data'):
                    return None, "No se pudieron encontrar las OPs para simular la consolidación."

                ops_originales = ops_res['data']

                # 2. Validar que no estén ya consolidadas (importante para el fallback)
                for op in ops_originales:
                    if op.get('estado') != 'PENDIENTE':
                        msg = f"La OP {op.get('codigo')} (ID: {op.get('id')}) está en estado '{op.get('estado')}' y no puede ser consolidada."
                        logger.warning(f"[Simulación] {msg}")
                        return None, msg

                # 3. Calcular los datos consolidados (lógica copiada de _calcular_datos_super_op)
                cantidad_total = sum(Decimal(op['cantidad_planificada']) for op in ops_originales)
                primera_op = ops_originales[0]
                fechas_meta_originales = []

                for op in ops_originales:
                    fecha_meta_str = op.get('fecha_meta')
                    if fecha_meta_str:
                        try:
                            fecha_meta_solo_str = fecha_meta_str.split('T')[0].split(' ')[0]
                            fechas_meta_originales.append(date.fromisoformat(fecha_meta_solo_str))
                        except ValueError:
                            logger.warning(f"Formato de fecha meta inválido en OP {op.get('id')}: {fecha_meta_str}")

                fecha_meta_mas_temprana = min(fechas_meta_originales) if fechas_meta_originales else None

                # 4. Crear el diccionario de "Super OP" simulada
                op_data_simulada = {
                    'id': None, # No tiene ID real todavía
                    'op_ids_originales': op_ids, # Guardamos los IDs originales
                    'producto_id': primera_op['producto_id'],
                    'cantidad_planificada': str(cantidad_total),
                    'receta_id': primera_op['receta_id'],
                    'fecha_meta': fecha_meta_mas_temprana.isoformat() if fecha_meta_mas_temprana else None,
                    'estado': 'PENDIENTE'
                }

                # Usamos la lista de IDs como 'ID' para la simulación
                return op_ids, op_data_simulada

            except Exception as e:
                logger.error(f"Error simulando consolidación para {op_ids}: {e}", exc_info=True)
                return None, f"Error interno al simular consolidación: {str(e)}"

        else:
            return None, "No se proporcionaron IDs de OP."

    def _calcular_carga_op_precargada(self, op_data: Dict, operaciones: List[Dict]) -> Decimal:
        """
        Calcula la carga total en minutos para una OP,
        usando una lista de operaciones precargadas.
        (Lógica extraída de _calcular_carga_op)
        """
        carga_total = Decimal(0)
        cantidad = Decimal(op_data.get('cantidad_planificada', 0))
        if not operaciones or cantidad <= 0:
            return carga_total

        for op_step in operaciones:
            t_prep = Decimal(op_step.get('tiempo_preparacion', 0))
            t_ejec_unit = Decimal(op_step.get('tiempo_ejecucion_unitario', 0))
            carga_total += t_prep + (t_ejec_unit * cantidad)
        return carga_total


    # ==================================================================
    # === 4. REEMPLAZA TU FUNCIÓN '_calcular_carga_op' ===
    # (Esta es la que tiene LOGGING, la mantenemos para depuración manual si es necesario)
    # ==================================================================
    def _calcular_carga_op(self, op_data: Dict) -> Decimal:
        """ Calcula la carga total en minutos para una OP dada (con logging). """
        carga_total = Decimal(0)
        receta_id = op_data.get('receta_id')
        cantidad = Decimal(op_data.get('cantidad_planificada', 0))
        op_id = op_data.get('id', 'N/A')

        if not receta_id or cantidad <= 0:
            logger.warning(f"[Carga OP {op_id}] Carga 0.0 (No hay receta_id o cantidad es 0).")
            return carga_total

        # Llama al helper que consulta la DB
        operaciones = self.obtener_operaciones_receta(receta_id)

        if not operaciones:
            logger.warning(f"[Carga OP {op_id}] Carga 0.0 (Receta {receta_id} no tiene operaciones).")
            return carga_total

        logger.info(f"--- Calculando Carga para OP {op_id} (Receta: {receta_id}, Cant: {cantidad}) ---")

        for op_step in operaciones:
            nombre_paso = op_step.get('nombre_operacion', 'Paso Desconocido')
            t_prep = Decimal(op_step.get('tiempo_preparacion', 0))
            t_ejec_unit = Decimal(op_step.get('tiempo_ejecucion_unitario', 0))
            carga_paso_actual = t_prep + (t_ejec_unit * cantidad)
            carga_total += carga_paso_actual
            logger.info(f"[Carga OP {op_id}] Paso: '{nombre_paso}'")
            logger.info(f"  -> T. Prep: {t_prep} min")
            logger.info(f"  -> T. Ejec: {t_ejec_unit} min/u * {cantidad} u = {t_ejec_unit * cantidad} min")
            logger.info(f"  -> Carga de este paso: {carga_paso_actual:.2f} min")
            logger.info(f"  -> CARGA TOTAL ACUMULADA: {carga_total:.2f} min")

        logger.info(f"--- [Carga OP {op_id}] Carga Final Total: {carga_total:.2f} min ---")
        return carga_total

    # --- HELPER para generar respuesta de sobrecarga (MENSAJE MEJORADO) ---
    def _generar_respuesta_sobrecarga(self, linea: int, fecha_str: str, cap_dia: float, carga_op_restante: float, carga_exist: float, horizonte_excedido: bool = False) -> tuple:
         """ Crea el diccionario y status code para error de sobrecarga con mensaje claro. """
         max_dias_simulacion = 30 # Asegúrate que esta variable esté definida o pásala como argumento

         titulo = "⚠️ Sobrecarga de Capacidad Detectada"
         mensaje = "" # Inicializar mensaje

         if horizonte_excedido:
              mensaje = (f"No hay suficiente capacidad en los próximos {max_dias_simulacion} días para planificar toda la carga de esta OP ({carga_op_restante:.0f} min restantes) "
                         f"en la Línea {linea}, comenzando desde {fecha_str}.\n\n"
                         f"**Sugerencia:** Considere dividir la OP manualmente en lotes más pequeños o ajustar la capacidad disponible.")
         else:
              carga_proyectada_dia = carga_exist + carga_op_restante
              exceso = carga_proyectada_dia - cap_dia
              if cap_dia - carga_exist <= 0 and carga_exist > 0: # Si el día ya estaba lleno
                  exceso = carga_op_restante # El exceso es toda la carga que intentamos poner
                  mensaje = (f"La Línea {linea} ya está completa para el día {fecha_str}.\n"
                             f"(Capacidad: {cap_dia:.0f} min, Carga ya asignada: {carga_exist:.0f} min).\n\n"
                             f"No se pueden añadir los {carga_op_restante:.0f} min requeridos por esta OP.\n\n"
                             f"**Acción requerida: Por favor, seleccione una fecha de inicio diferente o asigne la OP a la Línea {2 if linea == 1 else 1} si es compatible.")
              elif cap_dia - carga_exist <=0 and carga_exist == 0: # Si el día no tiene capacidad
                   mensaje = (f"La **Línea {linea}** tiene 0 minutos de capacidad disponible para el día {fecha_str} (puede ser feriado o estar inactiva).\n\n"
                              f"No se pueden asignar los {carga_op_restante:.0f} min requeridos por esta OP.\n\n"
                              f"Acción requerida: Por favor, seleccione una fecha de inicio diferente.")
              else: # Si cabe algo, pero no todo
                  capacidad_real_restante = max(0.0, cap_dia - carga_exist)
                  exceso_real = carga_op_restante - capacidad_real_restante
                  mensaje = (f"Capacidad insuficiente en la Línea {linea} para el día {fecha_str}.\n"
                             f"- Capacidad total del día: {cap_dia:.0f} min\n"
                             f"- Carga ya asignada: {carga_exist:.0f} min\n"
                             f"- Capacidad restante: {capacidad_real_restante:.0f} min\n\n"
                             f"Esta OP requiere {carga_op_restante:.0f} min adicionales, excediendo la capacidad en {exceso_real:.0f} min.\n\n"
                             f"Acción requerida: Elija una fecha de inicio posterior, asigne a otra línea (si es compatible) o divida la OP.")

         # Devolver diccionario con título separado (opcional) y status code
         return {
             'success': False,
             'error': 'SOBRECARGA_CAPACIDAD',
             'title': titulo, # Puedes usar esto en el modal si quieres
             'message': mensaje
         }, 409

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

    def mover_orden(self, op_id: int, nuevo_estado: str, user_role: str) -> tuple:
        """
        Orquesta el cambio de estado de una OP, validando permisos según el rol.
        """
        if not nuevo_estado:
            return self.error_response("El 'nuevo_estado' es requerido.", 400)

        # --- Lógica de Permisos Específica por Rol ---
        try:
            # Obtener el estado actual para validar la transición
            op_actual_res = self.orden_produccion_controller.obtener_orden_por_id(op_id)
            if not op_actual_res.get('success'):
                return self.error_response("Orden de Producción no encontrada.", 404)
            estado_actual = op_actual_res['data'].get('estado')

            # Validar permisos para SUPERVISOR_CALIDAD
            if user_role == 'SUPERVISOR_CALIDAD':
                # Mapa de transiciones permitidas: {estado_origen: [estados_destino_validos]}
                allowed_transitions = {
                    'EN_EMPAQUETADO': ['CONTROL_DE_CALIDAD'],
                    'CONTROL_DE_CALIDAD': ['COMPLETADA']
                }
                # Verificar si la transición solicitada es válida
                if estado_actual not in allowed_transitions or nuevo_estado not in allowed_transitions[estado_actual]:
                    return self.error_response(
                        f"Movimiento de '{estado_actual}' a '{nuevo_estado}' no permitido para Supervisor de Calidad.",
                        403
                    )

            # Validar permisos para OPERARIO
            elif user_role == 'OPERARIO':
                 # El OPERARIO solo puede mover desde 'LISTA PARA PRODUCIR' a una línea,
                 # o desde una línea a 'EMPAQUETADO'.
                allowed_transitions = {
                    'LISTA PARA PRODUCIR': ['EN_LINEA_1', 'EN_LINEA_2'],
                    'EN_LINEA_1': ['EN_EMPAQUETADO'],
                    'EN_LINEA_2': ['EN_EMPAQUETADO'],
                    'EN_EMPAQUETADO': ['CONTROL_DE_CALIDAD']
                }
                if estado_actual not in allowed_transitions or nuevo_estado not in allowed_transitions[estado_actual]:
                    return self.error_response(
                        f"Movimiento de '{estado_actual}' a '{nuevo_estado}' no permitido para Operario.",
                        403
                    )


            # --- INICIO DE LA LÓGICA DE CONSUMO DE STOCK ---
            estados_de_consumo = ['EN_LINEA_1', 'EN_LINEA_2']
            if estado_actual == 'LISTA PARA PRODUCIR' and nuevo_estado in estados_de_consumo:
                logger.info(f"OP {op_id} movida a producción. Consumiendo stock de insumos...")

                # Obtener el ID del usuario actual para registrar el consumo
                # (Asumimos que está disponible en el contexto de la petición o se pasa como argumento)
                # Aquí usamos un valor por defecto, pero debería ser el usuario autenticado.
                usuario_id = 1 # OJO: Reemplazar con el ID del usuario real

                consumo_result = self.inventario_controller.consumir_stock_para_op(op_actual_res['data'], usuario_id)

                if not consumo_result.get('success'):
                    error_msg = f"No se pudo iniciar la producción por falta de stock: {consumo_result.get('error')}"
                    logger.error(error_msg)
                    return self.error_response(error_msg, 409) # 409 Conflict es un buen código para esto
            # --- FIN DE LA LÓGICA DE CONSUMO DE STOCK ---

            # --- Ejecución del cambio de estado ---
            resultado = {}
            # Lógica existente para manejar 'COMPLETADA' u otros estados
            if nuevo_estado == 'COMPLETADA':
                response_dict, _ = self.orden_produccion_controller.cambiar_estado_orden(op_id, nuevo_estado)
                resultado = response_dict
            else:
                resultado = self.orden_produccion_controller.cambiar_estado_orden_simple(op_id, nuevo_estado)

            if resultado.get('success'):
                return self.success_response(data=resultado.get('data'))
            else:
                # Proveer un mensaje de error más específico si está disponible
                error_msg = resultado.get('error', 'Error desconocido al cambiar el estado.')
                return self.error_response(error_msg, 500)

        except Exception as e:
            logger.error(f"Error crítico en mover_orden para OP {op_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def obtener_ops_pendientes_planificacion(self, dias_horizonte: int = 7, mapas_precargados_externos: Optional[Dict] = None) -> tuple:
        """
        Obtiene OPs PENDIENTES, agrupa, calcula sugerencias Y AÑADE unidad_medida y linea_compatible.
        --- MODIFICADO ---
        Si 'mapas_precargados_externos' se provee, usa la versión optimizada.
        """
        try:
            # 1. Calcular rango y filtrar OPs (Sin cambios)
            hoy = date.today()
            dias_horizonte_int = int(dias_horizonte)
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

            # 2. Agrupar por Producto y SEMANA (Sin cambios)
            mps_agrupado = defaultdict(lambda: {
                'producto_id': 0,
                'producto_nombre': '',
                'cantidad_total': 0,
                'ordenes': [],
                'fecha_meta_mas_proxima': None,
                'receta_id': None,
                'unidad_medida': None
            })

            for op in ordenes_en_horizonte:
                producto_id = op.get('producto_id')
                if not producto_id: continue
                op_fecha_meta_str = op.get('fecha_meta')
                grupo_key = ""
                op_fecha_meta = None
                if op_fecha_meta_str:
                    try:
                        op_fecha_meta = date.fromisoformat(op_fecha_meta_str.split('T')[0].split(' ')[0])
                        year, week, _ = op_fecha_meta.isocalendar()
                        grupo_key = f"{producto_id}-{year}-{week}"
                    except ValueError:
                        logger.warning(f"OP {op.get('id')} tiene fecha meta inválida: {op_fecha_meta_str}. Agrupando sin semana.")
                        grupo_key = f"{producto_id}-FECHA_INVALIDA"
                else:
                    grupo_key = f"{producto_id}-NO_META"
                item = mps_agrupado[grupo_key]
                item['producto_id'] = producto_id
                item['producto_nombre'] = op.get('producto_nombre', 'Desconocido')
                item['cantidad_total'] += float(op.get('cantidad_planificada', 0))
                item['ordenes'].append(op)
                if item['receta_id'] is None:
                    item['receta_id'] = op.get('receta_id')
                if item['unidad_medida'] is None:
                    item['unidad_medida'] = op.get('producto_unidad_medida')
                if op_fecha_meta:
                    fecha_meta_mas_proxima_actual_str = item.get('fecha_meta_mas_proxima')
                    if fecha_meta_mas_proxima_actual_str:
                        fecha_meta_actual = date.fromisoformat(fecha_meta_mas_proxima_actual_str.split('T')[0].split(' ')[0])
                        if op_fecha_meta < fecha_meta_actual:
                            item['fecha_meta_mas_proxima'] = op_fecha_meta_str
                    else:
                        item['fecha_meta_mas_proxima'] = op_fecha_meta_str

            # 3. Calcular sugerencia agregada (¡MODIFICADO!)

            # Decidir qué función de cálculo usar
            usar_calculo_optimizado = mapas_precargados_externos is not None

            if not usar_calculo_optimizado:
                # Si estamos en la primera pasada (sin mapas), preparamos la devolución de OPs crudas
                # para que la función principal pueda construir los mapas.
                resultado_vacio_con_ops_crudas = {
                    'mps_agrupado': [], # Devolvemos vacío aquí...
                    'mps_agrupado_ops_raw': ordenes_en_horizonte, # ...pero con las OPs aquí.
                    'inicio_horizonte': hoy.isoformat(),
                    'fin_horizonte': fecha_fin_horizonte.isoformat(),
                    'dias_horizonte': dias_horizonte_int
                }
                # (Continuamos para llenar el 'mps_agrupado' con la función LENTA)

            for grupo_key, data in mps_agrupado.items():
                cantidad_total_agrupada = data['cantidad_total']
                receta_id_agrupada = data['receta_id']

                op_simulada = {
                    'receta_id': receta_id_agrupada,
                    'cantidad_planificada': cantidad_total_agrupada,
                    'fecha_meta': data.get('fecha_meta_mas_proxima')
                }

                # --- ¡CAMBIO DE LÓGICA! ---
                if usar_calculo_optimizado:
                    sugerencias = self._calcular_sugerencias_para_op_optimizado(op_simulada, mapas_precargados_externos)
                else:
                    # Usar la función antigua (lenta) si no hay mapas
                    sugerencias = self._calcular_sugerencias_para_op(op_simulada)

                data.update(sugerencias) # fusionar el dict de sugerencias

            # 4. Convertir a lista ordenada (Sin cambios)
            mps_lista_ordenada = []
            for grupo_key, data in mps_agrupado.items():
                producto_id_str = grupo_key.split('-')[0]
                producto_nombre = data['ordenes'][0].get('producto_nombre', 'Desconocido') if data['ordenes'] else 'Desconocido'
                mps_lista_ordenada.append({
                    'producto_id': int(producto_id_str) if producto_id_str.isdigit() else None,
                    'producto_nombre': producto_nombre,
                    **data
                })
            mps_lista_ordenada.sort(key=lambda x: x.get('fecha_meta_mas_proxima') or '9999-12-31')

            # Devolver el resultado final
            resultado_final = {
                 'mps_agrupado': mps_lista_ordenada,
                 'mps_agrupado_ops_raw': ordenes_en_horizonte, # Siempre devolvemos las OPs crudas
                 'inicio_horizonte': hoy.isoformat(),
                 'fin_horizonte': fecha_fin_horizonte.isoformat(),
                 'dias_horizonte': dias_horizonte_int
            }
            return self.success_response(data=resultado_final)

        except Exception as e:
            logger.error(f"Error preparando MPS: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)


    # ==================================================================
    # === 2. REEMPLAZA TU FUNCIÓN 'obtener_planificacion_semanal' ===
    # ==================================================================
    def obtener_planificacion_semanal(self, week_str: Optional[str] = None, ordenes_pre_cargadas: Optional[List[Dict]] = None, mapas_precargados_externos: Optional[Dict] = None) -> tuple:
        """
        Obtiene las OPs planificadas para una semana específica.
        --- OPTIMIZADO (N+1) ---
        Acepta 'mapas_precargados_externos' para usar datos de operaciones ya cargados.
        """
        try:
            # ... (Lógica inicial: locale, rango de semana, sin cambios) ...
            try: locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
            except locale.Error:
                try: locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')
                except locale.Error: logger.warning("Locale español no disponible.")

            if week_str:
                try:
                    year, week_num = map(int, week_str.split('-W'))
                    start_of_week = date.fromisocalendar(year, week_num, 1)
                except ValueError: return self.error_response("Formato semana inválido.", 400)
            else:
                today = date.today(); start_of_week = today - timedelta(days=today.weekday())
                week_str = start_of_week.strftime("%Y-%W")
            end_of_week = start_of_week + timedelta(days=6)

            # ... (Lógica de 'ordenes_pre_cargadas' y 'fallback', sin cambios) ...
            if ordenes_pre_cargadas is not None:
                ordenes_relevantes = ordenes_pre_cargadas
            else:
                # ... (código de fallback para buscar OPs) ...
                dias_previos_margen = 14
                fecha_inicio_filtro = start_of_week - timedelta(days=dias_previos_margen)
                filtros_amplios = {
                    'fecha_inicio_planificada_desde': fecha_inicio_filtro.isoformat(),
                    'fecha_inicio_planificada_hasta': end_of_week.isoformat(),
                    'estado': ('in', [
                        'EN ESPERA', 'LISTA PARA PRODUCIR', 'EN_LINEA_1',
                        'EN_LINEA_2', 'EN_EMPAQUETADO', 'CONTROL_DE_CALIDAD'
                     ])
                }
                response_ops, _ = self.orden_produccion_controller.obtener_ordenes(filtros_amplios)
                ordenes_relevantes = response_ops.get('data', [])

            if not ordenes_relevantes:
                 resultado_vacio = { 'ops_visibles_por_dia': {}, 'inicio_semana': start_of_week.isoformat(), 'fin_semana': end_of_week.isoformat(), 'semana_actual_str': week_str }
                 return self.success_response(data=resultado_vacio)

            # ... (Lógica de Obtener Capacidad, sin cambios) ...
            fechas_inicio_ops = [date.fromisoformat(op['fecha_inicio_planificada']) for op in ordenes_relevantes if op.get('fecha_inicio_planificada')]
            fecha_min_calculo = min(fechas_inicio_ops) if fechas_inicio_ops else start_of_week
            fecha_max_calculo = end_of_week + timedelta(days=14)
            capacidad_rango = self.obtener_capacidad_disponible([1, 2], fecha_min_calculo, fecha_max_calculo)

            # ... (Lógica de Simulación, sin cambios) ...
            ops_con_dias_ocupados = []
            carga_acumulada_simulacion = {1: defaultdict(float), 2: defaultdict(float)}
            ordenes_relevantes.sort(key=lambda op: op.get('fecha_inicio_planificada') or '9999-12-31')

            # --- ¡INICIO DE LA OPTIMIZACIÓN N+1 (MODIFICADA)! ---
            operaciones_map_sem = {}
            if mapas_precargados_externos:
                logger.debug("[Plan Semanal] Usando mapa de operaciones precargado.")
                operaciones_map_sem = mapas_precargados_externos.get('operaciones', {})
            else:
                # Fallback: Usar la optimización del Paso 2 (si no se pasaron mapas)
                logger.warning("[Plan Semanal] ¡Fallback! Cargando operaciones (N+1 optimizado).")
                receta_ids_unicos_sem = list(set(op.get('receta_id') for op in ordenes_relevantes if op.get('receta_id')))
                if receta_ids_unicos_sem:
                    operaciones_resp_sem = self.operacion_receta_model.find_by_receta_ids(receta_ids_unicos_sem)
                    if operaciones_resp_sem.get('success'):
                        for op_step in operaciones_resp_sem.get('data', []):
                            operaciones_map_sem.setdefault(op_step['receta_id'], []).append(op_step)
            # --- FIN DE LA OPTIMIZACIÓN N+1 ---

            for orden in ordenes_relevantes:
                # ... (lógica del bucle sin cambios, ya usa _calcular_carga_op_precargada) ...
                # ...
                op_id = orden.get('id')
                linea_asignada = orden.get('linea_asignada')
                fecha_inicio_str = orden.get('fecha_inicio_planificada')
                receta_id = orden.get('receta_id')

                if not linea_asignada or not fecha_inicio_str or not receta_id: continue

                try:
                    fecha_inicio_op = date.fromisoformat(fecha_inicio_str)

                    operaciones_para_esta_op = operaciones_map_sem.get(receta_id, [])
                    carga_total_op = float(self._calcular_carga_op_precargada(orden, operaciones_para_esta_op))

                    if carga_total_op <= 0: continue

                    dias_ocupados_por_esta_op = []
                    carga_restante_sim = carga_total_op
                    fecha_actual_sim = fecha_inicio_op
                    dias_simulados = 0
                    max_dias_op_sim = 30

                    while carga_restante_sim > 0.01 and dias_simulados < max_dias_op_sim:
                        fecha_actual_sim_str = fecha_actual_sim.isoformat()
                        cap_dia_dict = capacidad_rango.get(linea_asignada, {}).get(fecha_actual_sim_str, {})
                        cap_dia = cap_dia_dict.get('neta', 0.0)
                        carga_existente_sim = carga_acumulada_simulacion[linea_asignada].get(fecha_actual_sim_str, 0.0)
                        cap_restante_sim = max(0.0, cap_dia - carga_existente_sim)
                        carga_a_asignar_sim = min(carga_restante_sim, cap_restante_sim) # Corregido
                        if carga_a_asignar_sim > 0:
                            dias_ocupados_por_esta_op.append(fecha_actual_sim_str)
                            carga_acumulada_simulacion[linea_asignada][fecha_actual_sim_str] += carga_a_asignar_sim
                            carga_restante_sim -= carga_a_asignar_sim
                        if carga_restante_sim > 0.01:
                             fecha_actual_sim += timedelta(days=1)
                        dias_simulados += 1

                    orden['dias_ocupados_calculados'] = dias_ocupados_por_esta_op
                    ops_con_dias_ocupados.append(orden)

                except Exception as e_sim:
                     logger.error(f"Error simulando OP {op_id}: {e_sim}", exc_info=True)

            # ... (Lógica final: construir diccionario y devolver, sin cambios) ...
            ops_visibles_por_dia = defaultdict(list)
            for i in range(7):
                dia_semana_actual = start_of_week + timedelta(days=i)
                ops_visibles_por_dia[dia_semana_actual.isoformat()] = []
            for op in ops_con_dias_ocupados:
                for fecha_ocupada_iso in op.get('dias_ocupados_calculados', []):
                    if start_of_week.isoformat() <= fecha_ocupada_iso <= end_of_week.isoformat():
                        if op not in ops_visibles_por_dia[fecha_ocupada_iso]:
                             ops_visibles_por_dia[fecha_ocupada_iso].append(op)
            resultado = {
                'ops_visibles_por_dia': ops_visibles_por_dia,
                'inicio_semana': start_of_week.isoformat(),
                'fin_semana': end_of_week.isoformat(),
                'semana_actual_str': week_str
            }
            return self.success_response(data=resultado)

        except Exception as e:
            logger.error(f"Error obteniendo planificación semanal (v2): {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    # --- MÉTODO MODIFICADO ---
    # (Reemplaza la función completa, aprox. línea 1032)

    # ==================================================================
    # === 3. REEMPLAZA TU FUNCIÓN 'obtener_capacidad_disponible' ===
    # (¡IMPORTANTE! Este es el del,
    # NO el _calcular_carga_op de la línea 918)
    # ==================================================================
    def obtener_capacidad_disponible(self, centro_trabajo_ids: List[int], fecha_inicio: date, fecha_fin: date) -> Dict:
        """
        Calcula la capacidad disponible (en minutos) para centros de trabajo dados,
        entre dos fechas (inclusive). Considera estándar, eficiencia, utilización, BLOQUEOS,
        FINES DE SEMANA y FERIADOS.
        """
        # ... (Esta función ya está optimizada y no llama a _calcular_carga_op) ...
        # ... (Puedes dejar tu versión existente de esta función sin cambios) ...
        # ... (O pegar la versión completa de) ...
        capacidad_por_centro_y_fecha = defaultdict(dict)
        num_dias = (fecha_fin - fecha_inicio).days + 1

        try:
            id_filter = ('in', tuple(centro_trabajo_ids))
            ct_result = self.centro_trabajo_model.find_all(filters={'id': id_filter})
            if not ct_result.get('success'):
                logger.error(f"Error obteniendo centros de trabajo: {ct_result.get('error')}")
                return {}
            centros_trabajo = {ct['id']: ct for ct in ct_result.get('data', [])}

            filtros_bloqueo = {
                'centro_trabajo_id': ('in', tuple(centro_trabajo_ids)),
                'fecha_gte': fecha_inicio.isoformat(),
                'fecha_lte': fecha_fin.isoformat()
            }
            bloqueos_resp = self.bloqueo_capacidad_model.find_all(filtros_bloqueo)
            bloqueos_map = defaultdict(dict)
            if bloqueos_resp.get('success'):
                for bloqueo in bloqueos_resp.get('data', []):
                    bloqueos_map[bloqueo['centro_trabajo_id']][bloqueo['fecha']] = bloqueo
            try:
                years_to_check = list(set(range(fecha_inicio.year, fecha_fin.year + 1)))
                feriados_ar = holidays.country_holidays('AR', years=years_to_check)
                logger.info(f"Cargados {len(feriados_ar)} feriados de Argentina para los años {years_to_check}")
            except Exception as e_hol:
                logger.error(f"Error al inicializar la librería 'holidays': {e_hol}. Los feriados no se descontarán.")
                feriados_ar = {}
            for dia_offset in range(num_dias):
                fecha_actual = fecha_inicio + timedelta(days=dia_offset)
                fecha_iso = fecha_actual.isoformat()
                dia_de_semana = fecha_actual.weekday()
                es_fin_de_semana = (dia_de_semana >= 5)
                nombre_feriado = feriados_ar.get(fecha_actual)
                es_feriado = nombre_feriado is not None
                for ct_id in centro_trabajo_ids:
                    centro = centros_trabajo.get(ct_id)
                    cap_data = {
                        'bruta': Decimal(0), 'bloqueado': Decimal(0), 'neta': Decimal(0),
                        'motivo_bloqueo': None, 'hora_inicio': None, 'hora_fin': None
                    }
                    if es_fin_de_semana or es_feriado:
                        cap_data['motivo_bloqueo'] = nombre_feriado if es_feriado else 'Fin de Semana'
                        capacidad_por_centro_y_fecha[ct_id][fecha_iso] = cap_data
                        continue
                    if centro:
                        capacidad_std = Decimal(centro.get('tiempo_disponible_std_dia', 0))
                        eficiencia = Decimal(centro.get('eficiencia', 1.0))
                        utilizacion = Decimal(centro.get('utilizacion', 1.0))
                        num_maquinas = int(centro.get('numero_maquinas', 1))
                        capacidad_bruta_dia = capacidad_std * eficiencia * utilizacion * num_maquinas
                        bloqueo_data = bloqueos_map.get(ct_id, {}).get(fecha_iso, {})
                        minutos_bloqueados_dec = Decimal(bloqueo_data.get('minutos_bloqueados', 0))
                        if minutos_bloqueados_dec > 0:
                            cap_data['motivo_bloqueo'] = bloqueo_data.get('motivo')
                            cap_data['hora_inicio'] = bloqueo_data.get('hora_inicio')
                            cap_data['hora_fin'] = bloqueo_data.get('hora_fin')
                        capacidad_neta_dia = max(Decimal(0), capacidad_bruta_dia - minutos_bloqueados_dec)
                        cap_data['bruta'] = round(capacidad_bruta_dia, 2)
                        cap_data['bloqueado'] = round(minutos_bloqueados_dec, 2)
                        cap_data['neta'] = round(capacidad_neta_dia, 2)
                    capacidad_por_centro_y_fecha[ct_id][fecha_iso] = cap_data
            resultado_final_float_dict = {}
            for centro_id, cap_fecha in capacidad_por_centro_y_fecha.items():
                resultado_final_float_dict[centro_id] = {}
                for fecha, cap_dict in cap_fecha.items():
                    resultado_final_float_dict[centro_id][fecha] = {
                        'bruta': float(cap_dict['bruta']), 'bloqueado': float(cap_dict['bloqueado']),
                        'neta': float(cap_dict['neta']), 'motivo_bloqueo': cap_dict['motivo_bloqueo'],
                        'hora_inicio': cap_dict['hora_inicio'], 'hora_fin': cap_dict['hora_fin']
                    }
            return resultado_final_float_dict
        except Exception as e:
            logger.error(f"Error calculando capacidad disponible: {e}", exc_info=True)
            return {}


    def obtener_operaciones_receta(self, receta_id: int) -> List[Dict]:
        """ Obtiene las operaciones de una receta desde el modelo. """
        result = self.operacion_receta_model.find_by_receta_id(receta_id)
        return result.get('data', []) if result.get('success') else []


    # ==================================================================
    # === 5. REEMPLAZA TU FUNCIÓN 'calcular_carga_capacidad' ===
    # ==================================================================
    def calcular_carga_capacidad(self, ordenes_planificadas: List[Dict], mapas_precargados_externos: Optional[Dict] = None) -> Dict:
        """
        Calcula la carga (en minutos) por centro de trabajo y fecha.
        --- OPTIMIZADO (N+1) ---
        Acepta 'mapas_precargados_externos' para usar datos de operaciones ya cargados.
        """
        carga_distribuida = {1: defaultdict(float), 2: defaultdict(float)}
        fechas_inicio = []

        # --- ¡INICIO DE LA OPTIMIZACIÓN N+1 (MODIFICADA)! ---
        operaciones_map = {}
        if mapas_precargados_externos:
            logger.debug("[Calc Carga] Usando mapa de operaciones precargado.")
            operaciones_map = mapas_precargados_externos.get('operaciones', {})
        else:
            # Fallback: Usar la optimización del Paso 2 (si no se pasaron mapas)
            logger.warning("[Calc Carga] ¡Fallback! Cargando operaciones (N+1 optimizado).")
            receta_ids_unicos = list(set(op.get('receta_id') for op in ordenes_planificadas if op.get('receta_id')))
            if receta_ids_unicos:
                operaciones_resp = self.operacion_receta_model.find_by_receta_ids(receta_ids_unicos)
                if operaciones_resp.get('success'):
                    for op_step in operaciones_resp.get('data', []):
                        operaciones_map.setdefault(op_step['receta_id'], []).append(op_step)
        # --- FIN DE LA OPTIMIZACIÓN N+1 ---


        # ... (Lógica de rango de fechas, sin cambios) ...
        for op in ordenes_planificadas:
             if op.get('fecha_inicio_planificada'):
                 try: fechas_inicio.append(date.fromisoformat(op['fecha_inicio_planificada']))
                 except ValueError: pass

        if not fechas_inicio: return {1:{}, 2:{}}
        fecha_min = min(fechas_inicio)
        fecha_max_estimada = fecha_min + timedelta(days=30)
        capacidad_disponible_rango = self.obtener_capacidad_disponible([1, 2], fecha_min, fecha_max_estimada)

        # ... (Lógica de ordenar OPs, sin cambios) ...
        ordenes_ordenadas = sorted(
            [op for op in ordenes_planificadas if op.get('fecha_inicio_planificada')],
            key=lambda op: op['fecha_inicio_planificada']
        )

        for orden in ordenes_ordenadas:
            # ... (lógica del bucle sin cambios, ya usa _calcular_carga_op_precargada) ...
            # ...
            try:
                linea_asignada = orden.get('linea_asignada')
                fecha_inicio_op_str = orden.get('fecha_inicio_planificada')
                receta_id = orden.get('receta_id')

                if linea_asignada not in [1, 2] or not fecha_inicio_op_str or not receta_id: continue

                fecha_inicio_op = date.fromisoformat(fecha_inicio_op_str)

                # (Ya estaba optimizado en el Paso 2)
                operaciones_para_esta_op = operaciones_map.get(receta_id, [])
                carga_total_op = float(self._calcular_carga_op_precargada(orden, operaciones_para_esta_op))

                if carga_total_op <= 0: continue

                logger.debug(f"Distribuyendo carga para OP {orden.get('codigo', orden.get('id'))}: {carga_total_op:.2f} min en Línea {linea_asignada} desde {fecha_inicio_op_str}")

                carga_restante_op = carga_total_op
                fecha_actual_sim = fecha_inicio_op
                dias_procesados = 0
                max_dias_op = 30

                while carga_restante_op > 0.01 and dias_procesados < max_dias_op:
                    fecha_actual_str = fecha_actual_sim.isoformat()
                    cap_dia_dict = capacidad_disponible_rango.get(linea_asignada, {}).get(fecha_actual_str, {})
                    capacidad_dia = cap_dia_dict.get('neta', 0.0)
                    carga_ya_asignada_este_dia = carga_distribuida[linea_asignada].get(fecha_actual_str, 0.0)
                    capacidad_restante_hoy = max(0.0, capacidad_dia - carga_ya_asignada_este_dia)
                    carga_a_asignar_hoy = min(carga_restante_op, capacidad_restante_hoy)
                    if carga_a_asignar_hoy > 0:
                        carga_distribuida[linea_asignada][fecha_actual_str] += carga_a_asignar_hoy
                        carga_restante_op -= carga_a_asignar_hoy
                        logger.debug(f"  -> Asignado {carga_a_asignar_hoy:.2f} min a {fecha_actual_str}. Restante OP: {carga_restante_op:.2f} min")
                    fecha_actual_sim += timedelta(days=1)
                    dias_procesados += 1
                if carga_restante_op > 0.01:
                     logger.warning(f"OP {orden.get('codigo', orden.get('id'))}: No se pudo asignar toda la carga ({carga_restante_op:.2f} min restantes) en {max_dias_op} días.")
            except Exception as e:
                 logger.error(f"Error distribuyendo carga para OP {orden.get('codigo', orden.get('id'))}: {e}", exc_info=True)

        # ... (Lógica final de 'return', sin cambios) ...
        resultado_final = {
            1: dict(carga_distribuida[1]),
            2: dict(carga_distribuida[2])
        }
        return resultado_final

    def _ejecutar_planificacion_automatica(self, usuario_id: int, dias_horizonte: int = 1) -> dict:
        """
        Lógica central para la planificación automática.
        --- CORREGIDO ---
        Mensajes de error generados en español para el modal de resumen.
        """
        dias_horizonte = 30
        logger.info(f"[AutoPlan] Iniciando ejecución para {dias_horizonte} día(s). Usuario: {usuario_id}")

        # ... (Lógica de exclusión de issues, sin cambios) ...
        ops_con_issue_ids = []
        try:
            response_issues = self.issue_planificacion_model.find_all({'estado': 'PENDIENTE'})
            if response_issues.get('success'):
                issues_pendientes = response_issues.get('data', [])
                ops_con_issue_ids = [
                    issue['orden_produccion_id'] for issue in issues_pendientes if 'orden_produccion_id' in issue
                ]
                if ops_con_issue_ids:
                    logger.info(f"[AutoPlan] Excluyendo {len(ops_con_issue_ids)} OPs con issues PENDIENTES (ej: {ops_con_issue_ids[0]}).")
        except Exception as e_issue:
            logger.error(f"[AutoPlan] Error al buscar issues pendientes, no se excluirá nada: {e_issue}")

        # ... (Lógica de 'obtener_ops_pendientes_planificacion', sin cambios) ...
        res_ops_pendientes, _ = self.obtener_ops_pendientes_planificacion(dias_horizonte)
        if not res_ops_pendientes.get('success'):
            logger.error("[AutoPlan] Fallo al obtener OPs pendientes.")
            return {'errores': ['No se pudieron obtener OPs pendientes.']}

        grupos_a_planificar_raw = res_ops_pendientes.get('data', {}).get('mps_agrupado', [])

        # ... (Lógica de filtrado de grupos con issues, sin cambios) ...
        grupos_a_planificar = []
        ids_excluidos = set(ops_con_issue_ids)
        for grupo in grupos_a_planificar_raw:
            ops_limpias_en_grupo = [op for op in grupo['ordenes'] if op['id'] not in ids_excluidos]
            if not ops_limpias_en_grupo:
                logger.warning(f"[AutoPlan] Grupo de {grupo.get('producto_nombre')} omitido. Todas sus OPs tienen issues pendientes.")
                continue
            if len(ops_limpias_en_grupo) < len(grupo['ordenes']):
                logger.info(f"[AutoPlan] Re-calculando grupo de {grupo.get('producto_nombre')} (algunas OPs tenían issues).")
                grupo['ordenes'] = ops_limpias_en_grupo
                grupo['cantidad_total'] = sum(float(op.get('cantidad_planificada', 0)) for op in ops_limpias_en_grupo)
            grupos_a_planificar.append(grupo)

        if not grupos_a_planificar:
            logger.info("[AutoPlan] No se encontraron OPs pendientes (limpias de issues) en el horizonte.")
            # --- INICIO DE LA CORRECCIÓN ---
            # Devolver el resumen completo con los totales en 0
            return {
                'ops_planificadas': [],
                'ops_con_oc': [],
                'errores': [],
                'total_planificadas': 0,
                'total_oc_generadas': 0,
                'total_errores': 0
            }

        # ... (Contadores y bucle 'for', sin cambios) ...
        ops_planificadas_exitosamente = []
        ops_con_oc_generada = []
        errores_encontrados = []
        fecha_planificacion_str = date.today().isoformat()

        for grupo in grupos_a_planificar:
            op_ids = [op['id'] for op in grupo['ordenes']]
            op_codigos = [op['codigo'] for op in grupo['ordenes']]
            producto_nombre = grupo.get('producto_nombre', 'N/A')
            producto_id = grupo.get('producto_id') # <-- Necesitamos el ID
            try:

                # --- INICIO DE LA NUEVA VALIDACIÓN (Auto-Plan) ---
                if producto_id:
                    # 1. Obtener datos del producto
                    logger.info(f"--- [AutoPlan CHECK 1] Verificando Producto ID: {producto_id} ---")

                    # --- ¡¡INICIO DE LA CORRECCIÓN!! ---
                    # producto_resp.get('success') es incorrecto.
                    # El método devuelve el DATO o None.
                    producto_data = self.orden_produccion_controller.producto_controller.obtener_producto_por_id(producto_id)

                    if producto_data: # <-- La comprobación correcta es si producto_data existe
                    # --- ¡¡FIN DE LA CORRECCIÓN!! ---

                        # producto_data = producto_resp.get('data', {}) # <-- Ya no es necesario
                        cantidad_minima = Decimal(producto_data.get('cantidad_minima_produccion', 0))
                        cantidad_total_grupo = Decimal(grupo.get('cantidad_total', 0))

                        logger.info(f"[AutoPlan CHECK 1] Producto: {producto_data.get('nombre', 'N/A')}")
                        logger.info(f"[AutoPlan CHECK 1] Cant. Mínima (DB): {cantidad_minima}")
                        logger.info(f"[AutoPlan CHECK 1] Cant. a Planificar (Grupo): {cantidad_total_grupo}")

                        # 2. Comparar
                        if cantidad_minima > 0 and cantidad_total_grupo < cantidad_minima:
                            logger.error(f"[AutoPlan CHECK 1] ¡VIOLACIÓN DETECTADA! {cantidad_total_grupo} < {cantidad_minima}. Creando Issue.")
                            msg = (f"Grupo {producto_nombre} (OPs: {op_codigos}) omitido: "
                                   f"La cantidad total ({cantidad_total_grupo}) no cumple el mínimo de {cantidad_minima}.")

                            logger.warning(f"[AutoPlan] {msg}")
                            errores_encontrados.append(msg)

                            # 3. Crear el Issue (la "Alerta")
                            for op_id_individual in op_ids:
                                self._crear_o_actualizar_issue(
                                    op_id_individual,
                                    'CANTIDAD_MINIMA', # <-- Nuevo tipo de error
                                    f"La OP no cumple la cantidad mínima de producción ({cantidad_minima}). Consolide manually.",
                                    {'cantidad_op': float(cantidad_total_grupo), 'cantidad_minima': float(cantidad_minima)}
                                )

                            continue # <-- 4. Omitir este grupo
                        else:
                            logger.info(f"[AutoPlan CHECK 1] Chequeo de cantidad mínima OK para {producto_nombre}.")

                    # --- ¡¡INICIO DE LA CORRECCIÓN!! ---
                    else:
                        # ¡FALLO CRÍTICO! No se pudo cargar el producto
                        logger.error(f"[AutoPlan CHECK 1] ¡FALLO CRÍTICO! No se pudo cargar el Producto ID {producto_id} ({producto_nombre}).")
                        logger.error(f"[AutoPlan CHECK 1] Omitiendo grupo {op_codigos} por seguridad.")
                        errores_encontrados.append(f"Grupo {op_codigos} omitido: No se pudo verificar la cantidad mínima (Error al cargar producto {producto_id}).")
                        continue # <-- ¡MUY IMPORTANTE! NO CONTINUAR SI FALLA LA CARGA
                    # --- ¡¡FIN DE LA CORRECCIÓN!! ---

                # --- FIN DE LA NUEVA VALIDACIÓN ---

                # ... (Lógica de asignaciones_auto_grupo, sin cambios) ...
                linea_sugerida_grupo = grupo.get('sugerencia_linea')
                if not linea_sugerida_grupo:
                    msg = f"Grupo {producto_nombre} (OPs: {op_codigos}) omitido: No hay línea sugerida."
                    logger.warning(f"[AutoPlan] {msg}")
                    errores_encontrados.append(msg)
                    continue
                fecha_inicio_busqueda_grupo = grupo.get('sugerencia_fecha_inicio_jit', fecha_planificacion_str)
                asignaciones_auto_grupo = {
                    'linea_asignada': linea_sugerida_grupo,
                    'fecha_inicio': fecha_inicio_busqueda_grupo,
                    'supervisor_id': None, 'operario_id': None
                }

                logger.info(f"[AutoPlan] Intentando planificar GRUPO {op_codigos} en Línea {linea_sugerida_grupo} (JIT Start: {fecha_inicio_busqueda_grupo})...")

                res_planif_dict, res_planif_status = self.consolidar_y_aprobar_lote(
                    op_ids, asignaciones_auto_grupo, usuario_id
                )
                logger.debug(f"[DEBUG JIT] Resultado para GRUPO {op_codigos}: Status={res_planif_status}, Error='{res_planif_dict.get('error')}'")

                # ... (Lógica de 'if res_planif_status == 200 and res_planif_dict.get('success')', sin cambios) ...
                if res_planif_status == 200 and res_planif_dict.get('success'):
                    logger.info(f"[AutoPlan] ÉXITO: GRUPO {op_codigos} planificado.")
                    op_id_para_confirmar = res_planif_dict.get('op_id_confirmar')
                    asignaciones_para_confirmar = res_planif_dict.get('asignaciones_confirmar')
                    res_aprob_dict, status_aprob = self._ejecutar_aprobacion_final(
                        op_id_para_confirmar, asignaciones_para_confirmar, usuario_id
                    )
                    if status_aprob < 400 and res_aprob_dict.get('success'):
                        ops_planificadas_exitosamente.extend(op_codigos)
                        if res_aprob_dict and res_aprob_dict.get('data') and res_aprob_dict['data'].get('oc_generada'):
                            ocs_creadas = res_aprob_dict['data'].get('ocs_creadas', [])
                            if ocs_creadas:
                                primer_oc_codigo = ocs_creadas[0].get('codigo_oc', 'N/A')
                                ops_con_oc_generada.append({'ops': op_codigos, 'oc': primer_oc_codigo})
                    else:
                        errores_encontrados.append(f"Grupo {op_codigos} simuló OK pero falló aprobación: {res_aprob_dict.get('error')}")

                # ... (Lógica de 'elif res_planif_dict.get('error') == 'MULTI_DIA_CONFIRM'', sin cambios) ...
                elif res_planif_dict.get('error') == 'MULTI_DIA_CONFIRM':
                    logger.info(f"[AutoPlan] GRUPO {op_codigos} requiere {res_planif_dict.get('dias_necesarios')} días. Aprobando automáticamente...")
                    op_id_para_confirmar = res_planif_dict.get('op_id_confirmar')
                    asignaciones_para_confirmar = res_planif_dict.get('asignaciones_confirmar')
                    if not op_id_para_confirmar or not asignaciones_para_confirmar:
                         errores_encontrados.append(f"Grupo {op_codigos} multi-día pero faltan datos.")
                         continue
                    try:
                        res_aprob_dict, status_aprob = self._ejecutar_aprobacion_final(
                            op_id_para_confirmar, asignaciones_para_confirmar, usuario_id
                        )
                        if status_aprob < 400 and res_aprob_dict.get('success'):
                            logger.info(f"[AutoPlan] ÉXITO (Multi-Día): GRUPO {op_codigos} planificado.")
                            ops_planificadas_exitosamente.extend(op_codigos)
                            if res_aprob_dict and res_aprob_dict['data'] and res_aprob_dict['data'].get('oc_generada'):
                                oc_codigo = res_aprob_dict['data'].get('oc_codigo', 'N/A')
                                ops_con_oc_generada.append({'ops': op_codigos, 'oc': oc_codigo})
                        else:
                            error_msg = res_aprob_dict.get('error', 'Error') if isinstance(res_aprob_dict, dict) else str(res_aprob_dict)
                            errores_encontrados.append(f"Grupo {op_codigos} falló aprobación multi-día: {error_msg}")
                    except Exception as e_aprob:
                         errores_encontrados.append(f"Excepción al auto-aprobar GRUPO {op_codigos}: {str(e_aprob)}")

                elif res_planif_dict.get('error') in ['LATE_CONFIRM', 'SOBRECARGA_CAPACIDAD', 'MIN_QUANTITY_CONFIRM']:
                    error_tipo_grupo = res_planif_dict.get('error')
                    # --- INICIO DE LA CORRECCIÓN DE MENSAJE ---
                    if error_tipo_grupo == 'LATE_CONFIRM':
                        error_msg_grupo_es = f"el grupo consolidado terminaría TARDE (después de su Fecha Meta)."
                    elif error_tipo_grupo == 'MIN_QUANTITY_CONFIRM':
                        error_msg_grupo_es = f"el grupo consolidado NO CUMPLE LA CANTIDAD MÍNIMA de producción."
                    else: # SOBRECARGA_CAPACIDAD
                        error_msg_grupo_es = f"el grupo consolidado genera SOBRECARGA de capacidad."
                    # --- FIN DE LA CORRECCIÓN DE MENSAJE ---

                    if len(op_ids) > 1:
                        logger.warning(f"[AutoPlan] GRUPO {op_codigos} falló ({error_tipo_grupo}). Intentando OPs individuales...")
                        errores_encontrados.append(f"Grupo {op_codigos} falló porque {error_msg_grupo_es} Intentando OPs individuales...")

                        for op_individual in grupo['ordenes']:
                            op_id_individual = op_individual['id']
                            op_codigo_individual = op_individual['codigo']

                            logger.info(f"[AutoPlan/Fallback] Intentando OP individual: {op_codigo_individual} (ID: {op_id_individual})")

                            # ... (Lógica de Recálculo JIT Individual, sin cambios) ...
                            try:
                                op_meta_str = op_individual.get('fecha_meta')
                                op_meta_date = date.fromisoformat(op_meta_str.split('T')[0].split(' ')[0])
                                jit_data_ind = self._calcular_tiempos_jit_op(
                                    cantidad=float(op_individual.get('cantidad_planificada', 0)),
                                    receta_id=op_individual.get('receta_id'),
                                    fecha_meta=op_meta_date,
                                    linea_compatible=op_individual.get('linea_compatible')
                                )
                                fecha_inicio_busqueda_ind = jit_data_ind['sugerencia_fecha_inicio_jit']
                                linea_sugerida_ind = jit_data_ind['sugerencia_linea']
                                if not linea_sugerida_ind:
                                    msg = f"OP {op_codigo_individual} (fallback) omitida: No hay línea sugerida individual."
                                    logger.warning(f"[AutoPlan/Fallback] {msg}")
                                    errores_encontrados.append(msg)
                                    continue
                                logger.info(f"[AutoPlan/Fallback] JIT para {op_codigo_individual}: T_Proc={jit_data_ind['sugerencia_t_proc_dias']}d, T_Prod={jit_data_ind['sugerencia_t_prod_dias']}d -> Iniciar búsqueda en {fecha_inicio_busqueda_ind}")
                            except Exception as e_jit_ind:
                                logger.warning(f"No se pudo calcular JIT para fallback {op_codigo_individual}. Usando 'hoy'. Error: {e_jit_ind}")
                                fecha_inicio_busqueda_ind = fecha_planificacion_str
                                linea_sugerida_ind = linea_sugerida_grupo
                            asignaciones_individual = {
                                'linea_asignada': linea_sugerida_ind,
                                'fecha_inicio': fecha_inicio_busqueda_ind,
                                'supervisor_id': None, 'operario_id': None
                            }

                            try:
                                res_ind_dict, res_ind_status = self.consolidar_y_aprobar_lote(
                                    [op_id_individual], asignaciones_individual, usuario_id
                                )

                                # ... (Lógica de 'if res_ind_status == 200 and res_ind_dict.get('success')', sin cambios) ...
                                if res_ind_status == 200 and res_ind_dict.get('success'):
                                    logger.info(f"[AutoPlan/Fallback] ÉXITO (1-día): OP {op_codigo_individual} simulada OK. Aprobando...")
                                    op_id_conf_ind = res_ind_dict.get('op_id_confirmar')
                                    asig_conf_ind = res_ind_dict.get('asignaciones_confirmar')
                                    res_aprob_ind_dict, status_aprob_ind = self._ejecutar_aprobacion_final(
                                        op_id_conf_ind, asig_conf_ind, usuario_id
                                    )
                                    if status_aprob_ind < 400 and res_aprob_ind_dict.get('success'):
                                        logger.info(f"[AutoPlan/Fallback] ÉXITO: OP {op_codigo_individual} planificada individualmente.")
                                        ops_planificadas_exitosamente.append(op_codigo_individual)
                                        if res_aprob_ind_dict and res_aprob_ind_dict.get('data') and res_aprob_ind_dict['data'].get('oc_generada'):
                                            ocs_creadas = res_aprob_ind_dict['data'].get('ocs_creadas', [])
                                            if ocs_creadas:
                                                primer_oc_codigo = ocs_creadas[0].get('codigo_oc', 'N/A')
                                                ops_con_oc_generada.append({'ops': [op_codigo_individual], 'oc': primer_oc_codigo})
                                    else:
                                        errores_encontrados.append(f"OP {op_codigo_individual} simuló OK pero falló aprobación: {res_aprob_ind_dict.get('error')}")

                                # ... (Lógica de 'elif res_ind_dict.get('error') == 'MULTI_DIA_CONFIRM'', sin cambios) ...
                                elif res_ind_dict.get('error') == 'MULTI_DIA_CONFIRM':
                                    logger.info(f"[AutoPlan/Fallback] OP {op_codigo_individual} es multi-día. Aprobando...")
                                    op_id_conf_ind = res_ind_dict.get('op_id_confirmar')
                                    asig_conf_ind = res_ind_dict.get('asignaciones_confirmar')
                                    if not op_id_conf_ind or not asig_conf_ind:
                                        errores_encontrados.append(f"OP {op_codigo_individual} (fallback) multi-día faltan datos.")
                                        continue
                                    try:
                                        res_aprob_ind_dict, status_aprob_ind = self._ejecutar_aprobacion_final(
                                            op_id_conf_ind, asig_conf_ind, usuario_id
                                        )
                                        if status_aprob_ind < 400 and res_aprob_ind_dict.get('success'):
                                            logger.info(f"[AutoPlan/Fallback] ÉXITO (Multi-Día): OP {op_codigo_individual} planificada.")
                                            ops_planificadas_exitosamente.append(op_codigo_individual)
                                            if res_aprob_ind_dict and res_aprob_ind_dict.get('data') and res_aprob_ind_dict.get('oc_generada'):
                                                oc_codigo = res_aprob_ind_dict['data'].get('oc_codigo', 'N/A')
                                                ops_con_oc_generada.append({'ops': [op_codigo_individual], 'oc': oc_codigo})
                                        else:
                                            error_msg_ind = res_aprob_ind_dict.get('error', 'Error') if isinstance(res_aprob_ind_dict, dict) else str(res_aprob_ind_dict)
                                            errores_encontrados.append(f"OP {op_codigo_individual} (fallback) falló aprobación multi-día: {error_msg_ind}")
                                    except Exception as e_aprob_ind:
                                        errores_encontrados.append(f"Excepción al auto-aprobar OP {op_codigo_individual} (fallback): {str(e_aprob_ind)}")

                                elif res_ind_dict.get('error') in ['LATE_CONFIRM', 'SOBRECARGA_CAPACIDAD', 'MIN_QUANTITY_CONFIRM']:
                                    # --- INICIO DE LA CORRECCIÓN DE MENSAJE ---
                                    error_tipo_ind = res_ind_dict.get('error')
                                    if error_tipo_ind == 'LATE_CONFIRM':
                                        error_msg_ind_es = "terminaría TARDE"
                                    elif error_tipo_ind == 'MIN_QUANTITY_CONFIRM':
                                        error_msg_ind_es = "NO CUMPLE LA CANTIDAD MÍNIMA"
                                    else: # SOBRECARGA
                                        error_msg_ind_es = "genera SOBRECARGA"

                                    msg = f"OP {op_codigo_individual} NO SE PLANIFICÓ (falla individual): {error_msg_ind_es}. Requiere revisión manual."
                                    # --- FIN DE LA CORRECCIÓN DE MENSAJE ---

                                    logger.warning(f"[AutoPlan/Fallback] {msg}")
                                    errores_encontrados.append(msg)
                                    self._crear_o_actualizar_issue(
                                        op_id_individual, error_tipo_ind, msg, res_ind_dict
                                    )
                                else:
                                    msg = f"OP {op_codigo_individual} (fallback) falló: {res_ind_dict.get('error', 'Desconocido')}"
                                    logger.error(f"[AutoPlan/Fallback] {msg}")
                                    errores_encontrados.append(msg)

                            except Exception as e_fallback:
                                msg = f"Excepción crítica al procesar fallback para OP {op_codigo_individual}: {str(e_fallback)}"
                                logger.error(f"[AutoPlan/Fallback] {msg}", exc_info=True)
                                errores_encontrados.append(msg)

                    else:
                        # El GRUPO falló, pero solo tenía 1 OP.
                        # --- INICIO DE LA CORRECCIÓN DE MENSAJE ---
                        if error_tipo_grupo == 'LATE_CONFIRM':
                            error_msg_es = "terminaría TARDE"
                        elif error_tipo_grupo == 'MIN_QUANTITY_CONFIRM':
                            error_msg_es = "NO CUMPLE LA CANTIDAD MÍNIMA"
                        else: # SOBRECARGA
                            error_msg_es = "genera SOBRECARGA"
                        msg = f"Grupo {producto_nombre} (OP: {op_codigos[0]}) NO SE PLANIFICÓ: {error_msg_es}. Requiere revisión manual."
                        # --- FIN DE LA CORRECCIÓN DE MENSAJE ---

                        logger.warning(f"[AutoPlan] {msg}")
                        errores_encontrados.append(msg)
                        self._crear_o_actualizar_issue(
                            op_ids[0], error_tipo_grupo, msg, res_planif_dict
                        )

                else:
                    msg = f"Grupo {producto_nombre} (OPs: {op_codigos}) falló: {res_planif_dict.get('error', 'Desconocido')}"
                    logger.error(f"[AutoPlan] {msg}")
                    errores_encontrados.append(msg)

            except Exception as e:
                msg = f"Excepción crítica al procesar OPs {op_codigos}: {str(e)}"
                logger.error(f"[AutoPlan] {msg}", exc_info=True)
                errores_encontrados.append(msg)

        # ... (Resumen final, sin cambios) ...
        resumen = {
            'ops_planificadas': ops_planificadas_exitosamente,
            'ops_con_oc': ops_con_oc_generada,
            'errores': errores_encontrados,
            'total_planificadas': len(ops_planificadas_exitosamente),
            'total_oc_generadas': len(ops_con_oc_generada),
            'total_errores': len(errores_encontrados)
        }
        logger.info(f"[AutoPlan] Finalizado. Resumen: {resumen}")
        return resumen

    def forzar_auto_planificacion(self, usuario_id: int) -> tuple:
        """
        Endpoint manual para forzar la ejecución de la planificación automática.
        Usa un horizonte más amplio (ej. 7 días) por defecto.
        """
        try:
            # Puedes hacer que el horizonte sea un parámetro de la request si quieres
            dias_horizonte_manual = 30

            # Reutiliza la lógica central
            resumen = self._ejecutar_planificacion_automatica(
                usuario_id=usuario_id,
                dias_horizonte=dias_horizonte_manual
            )

            return self.success_response(data=resumen, message="Planificación manual ejecutada.")

        except Exception as e:
            logger.error(f"Error en forzar_auto_planificacion: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)


    def confirmar_aprobacion_lote(self, op_id: int, asignaciones: dict, usuario_id: int) -> tuple:
        """
        Endpoint final para confirmar una aprobación (multi-día o no).
        Omite la simulación de capacidad (ya se hizo) y ejecuta la acción
        basándose en el estado de la OP.
        """
        try:
            # 1. Obtener el estado actual de la OP
            op_result = self.orden_produccion_controller.obtener_orden_por_id(op_id)
            if not op_result.get('success'):
                return self.error_response(f"No se encontró la OP ID {op_id}.", 404), 404

            op_estado_actual = op_result['data'].get('estado')
            logger.info(f"Confirmando aprobación para OP {op_id} (Estado: {op_estado_actual})...")

            # 2. Decidir qué helper llamar basado en el estado
            if op_estado_actual == 'PENDIENTE':
                # Flujo original: Aprobar (pre-asignar + confirmar/aprobar)
                logger.info("Estado es PENDIENTE. Ejecutando aprobación final...")
                return self._ejecutar_aprobacion_final(op_id, asignaciones, usuario_id)

            elif op_estado_actual in ['EN ESPERA', 'LISTA PARA PRODUCIR']:
                # Flujo nuevo: Re-planificar (solo actualizar)
                logger.info(f"Estado es {op_estado_actual}. Ejecutando re-planificación simple...")
                return self._ejecutar_replanificacion_simple(op_id, asignaciones, usuario_id)

            else:
                msg = f"La OP {op_id} en estado '{op_estado_actual}' no puede ser confirmada."
                logger.warning(msg)
                return self.error_response(msg, 400), 400

        except Exception as e:
            logger.error(f"Error crítico en confirmar_aprobacion_lote: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500), 500


    def _simular_asignacion_carga(self, carga_total_op: float, linea_propuesta: int, fecha_inicio_busqueda: date, op_id_a_excluir: Optional[int] = None, carga_actual_map: Optional[Dict] = None) -> dict:
        """
        Simula la asignación de carga día por día y devuelve la fecha de inicio real y la fecha de fin.
        Reutiliza la lógica del bucle 'while' de 'consolidar_y_aprobar_lote'.

        Devuelve: {
            'success': bool,
            'fecha_inicio_real': date | None,
            'fecha_fin_estimada': date | None,
            'dias_necesarios': int,
            'error_data': dict | None
        }
        """
        carga_restante_op = carga_total_op
        fecha_actual_simulacion = fecha_inicio_busqueda
        dia_actual_offset = 0
        max_dias_simulacion = 30 # Horizonte de búsqueda
        dias_necesarios = 0

        primer_dia_asignado = None
        fecha_fin_estimada = fecha_inicio_busqueda

        while carga_restante_op > 0.01 and dia_actual_offset < max_dias_simulacion:
            fecha_actual_str = fecha_actual_simulacion.isoformat()

            capacidad_dict_dia = self.obtener_capacidad_disponible([linea_propuesta], fecha_actual_simulacion, fecha_actual_simulacion)

            # --- ¡CAMBIO! Usar .get('neta') ---
            cap_dia_dict = capacidad_dict_dia.get(linea_propuesta, {}).get(fecha_actual_str, {})
            capacidad_dia_actual = cap_dia_dict.get('neta', 0.0)
            # --- FIN CAMBIO ---

            if capacidad_dia_actual <= 0:
                fecha_actual_simulacion += timedelta(days=1)
                dia_actual_offset += 1
                continue # Saltar día no laborable

            # Obtener carga existente (¡MODIFICADO!)
            # Ya no consultamos la DB, usamos el mapa de carga pre-calculado.
            if carga_actual_map is None:
                carga_actual_map = {} # Asegurar que el mapa exista

            carga_existente_dia = carga_actual_map.get(linea_propuesta, {}).get(fecha_actual_str, 0.0)
            capacidad_restante_dia = max(0.0, capacidad_dia_actual - carga_existente_dia)

            if capacidad_restante_dia < 1:
                fecha_actual_simulacion += timedelta(days=1)
                dia_actual_offset += 1
                continue # Saltar día lleno

            # Día válido encontrado
            if primer_dia_asignado is None:
                primer_dia_asignado = fecha_actual_simulacion

            dias_necesarios += 1
            fecha_fin_estimada = fecha_actual_simulacion
            carga_a_asignar_hoy = min(carga_restante_op, capacidad_restante_dia)

            if carga_a_asignar_hoy > 0:
                carga_restante_op -= carga_a_asignar_hoy

            fecha_actual_simulacion += timedelta(days=1)
            dia_actual_offset += 1

        # --- Fin del bucle ---

        if primer_dia_asignado is None:
            error_data, _ = self._generar_respuesta_sobrecarga(linea_propuesta, (fecha_actual_simulacion - timedelta(days=1)).isoformat(), 0, carga_total_op, 0, horizonte_excedido=True)
            return {'success': False, 'fecha_inicio_real': None, 'fecha_fin_estimada': None, 'dias_necesarios': 0, 'error_data': error_data}

        if carga_restante_op > 0.01:
            error_data, _ = self._generar_respuesta_sobrecarga(linea_propuesta, fecha_fin_estimada.isoformat(), 0, carga_restante_op, 0, horizonte_excedido=True)
            return {'success': False, 'fecha_inicio_real': primer_dia_asignado, 'fecha_fin_estimada': fecha_fin_estimada, 'dias_necesarios': dias_necesarios, 'error_data': error_data}

        return {
            'success': True,
            'fecha_inicio_real': primer_dia_asignado,
            'fecha_fin_estimada': fecha_fin_estimada,
            'dias_necesarios': dias_necesarios,
            'error_data': None
        }

    def api_validar_fecha_requerida(self, items_data: List[Dict], fecha_requerida_str: str) -> tuple:
        """
        Endpoint API para validar si un conjunto de items de pedido puede
        ser producido para una fecha requerida.
        """
        try:
            fecha_requerida_cliente = date.fromisoformat(fecha_requerida_str)
            fecha_sugerida_mas_tardia = date.today()

            # --- ¡NUEVA LÓGICA DE CARGA REAL! ---
            # 1. Obtener TODAS las OPs planificadas que afectan la capacidad futura
            filtros_ops = {
                'estado': ('in', [
                    'EN ESPERA', 'LISTA PARA PRODUCIR', 'EN_LINEA_1',
                    'EN_LINEA_2', 'EN_EMPAQUETADO', 'CONTROL_DE_CALIDAD'
                ])
            }
            ops_resp, _ = self.orden_produccion_controller.obtener_ordenes(filtros_ops)
            ops_actuales = ops_resp.get('data', []) if ops_resp.get('success') else []

            # 2. Calcular el mapa de carga real (usando la misma lógica del CRP)
            logger.info(f"[api_validar_fecha] Calculando carga actual basada en {len(ops_actuales)} OPs...")
            carga_actual_map = self.calcular_carga_capacidad(ops_actuales)
            # --- FIN NUEVA LÓGICA ---

            # 1. Simular la carga de cada item que requiera producción
            for item in items_data:
                producto_id = item.get('producto_id')
                cantidad = float(item.get('cantidad', 0))
                if not producto_id or cantidad <= 0:
                    continue

                # 2. Verificar si el producto necesita producción (tiene receta)
                receta_res = self.receta_model.find_all({'producto_id': int(producto_id), 'activa': True}, limit=1)
                if not receta_res.get('success') or not receta_res.get('data'):
                    continue # Este item es solo de stock, no afecta la planificación de producción

                receta = receta_res['data'][0]

                # 3. Calcular carga total para este item
                op_simulada = {'receta_id': receta['id'], 'cantidad_planificada': cantidad}
                carga_total_min = float(self._calcular_carga_op(op_simulada))
                if carga_total_min <= 0:
                    continue

                # 4. Encontrar línea sugerida (lógica de 'obtener_ops_pendientes')
                # (Esta lógica se simplifica, puedes mejorarla)
                linea_compatible_str = receta.get('linea_compatible', '2')
                linea_compatible_list = linea_compatible_str.split(',')
                linea_sugerida = int(linea_compatible_list[0]) # Tomar la primera compatible como sugerencia simple

                # 5. Simular asignación
                simulacion_result = self._simular_asignacion_carga(
                    carga_total_op=carga_total_min,
                    linea_propuesta=linea_sugerida,
                    fecha_inicio_busqueda=date.today(), # Buscar desde hoy
                    op_id_a_excluir=None, # Es un pedido nuevo, no hay OP para excluir
                    carga_actual_map=carga_actual_map # <-- ¡PASAR EL MAPA DE CARGA REAL!
                )

                if simulacion_result['success']:
                    fecha_fin_item = simulacion_result['fecha_fin_estimada']
                    fecha_sugerida_mas_tardia = max(fecha_sugerida_mas_tardia, fecha_fin_item)
                else:
                    # Si la simulación falla (sin capacidad en 30 días), devolvemos el error
                    return self.error_response(f"No hay capacidad en los próximos 30 días para {item.get('nombre_producto')}. {simulacion_result['error_data'].get('message')}", 409)

            # 6. Comparar y devolver resultado
            data_respuesta = {
                'fecha_requerida_cliente': fecha_requerida_cliente.isoformat(),
                'fecha_sugerida_mas_proxima': fecha_sugerida_mas_tardia.isoformat(),
                'llega_a_tiempo': fecha_sugerida_mas_tardia <= fecha_requerida_cliente
            }

            return self.success_response(data=data_respuesta)

        except Exception as e:
            logger.error(f"Error en api_validar_fecha_requerida: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    # --- MÉTODOS NUEVOS PARA LA PÁGINA DE CONFIGURACIÓN ---

    def obtener_datos_configuracion(self) -> tuple:
        """Obtiene los datos de líneas (Centros) y los bloqueos existentes."""
        try:
            lineas_resp = self.centro_trabajo_model.find_all()
            bloqueos_resp = self.bloqueo_capacidad_model.get_all_with_details() # (Debes crear este método en el modelo)

            if not lineas_resp.get('success'):
                return self.error_response("No se pudieron cargar las líneas.", 500)

            return self.success_response(data={
                "lineas": lineas_resp.get('data', []),
                "bloqueos": bloqueos_resp.get('data', []) if bloqueos_resp.get('success') else []
            })
        except Exception as e:
            logger.error(f"Error en obtener_datos_configuracion: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def actualizar_configuracion_linea(self, data: dict) -> tuple:
        """Actualiza la eficiencia y utilización de una línea."""
        try:
            linea_id = data.get('linea_id')
            if not linea_id:
                return self.error_response("Falta ID de línea.", 400)

            # Convertir los porcentajes (ej: 85) a decimales (ej: 0.85)
            eficiencia_pct = Decimal(data.get('eficiencia', 100))
            utilizacion_pct = Decimal(data.get('utilizacion', 100))

            update_data = {
                'eficiencia': eficiencia_pct / 100, # <-- CORRECCIÓN
                'utilizacion': utilizacion_pct / 100, # <-- CORRECCIÓN
                'tiempo_disponible_std_dia': Decimal(data.get('capacidad_std', 480))
            }

            result = self.centro_trabajo_model.update(linea_id, update_data, 'id')
            if result.get('success'):
                return self.success_response(message="Línea actualizada.")
            else:
                return self.error_response(f"Error al actualizar: {result.get('error')}", 500)
        except Exception as e:
            return self.error_response(f"Error: {str(e)}", 500)

    def agregar_bloqueo(self, data: dict) -> tuple:
        """Agrega un nuevo bloqueo de capacidad, calculando minutos desde las horas."""
        try:
            hora_inicio_str = data.get('hora_inicio') # Ej: "08:00"
            hora_fin_str = data.get('hora_fin')       # Ej: "10:30"
            fecha_str = data.get('fecha_bloqueo')

            if not hora_inicio_str or not hora_fin_str or not fecha_str:
                return self.error_response("Fecha, hora de inicio y hora de fin son requeridas.", 400)

            # 1. Calcular minutos
            try:
                FMT = '%H:%M'
                t_inicio = datetime.strptime(hora_inicio_str, FMT).time()
                t_fin = datetime.strptime(hora_fin_str, FMT).time()

                if t_fin <= t_inicio:
                    return self.error_response("La hora de fin debe ser mayor que la hora de inicio.", 400)

                # Usamos una fecha dummy (como 'hoy' o 'date.min') para poder restar
                dummy_date = date.today()
                dt_inicio = datetime.combine(dummy_date, t_inicio)
                dt_fin = datetime.combine(dummy_date, t_fin)

                minutos_calculados = (dt_fin - dt_inicio).total_seconds() / 60

            except ValueError:
                return self.error_response("Formato de hora inválido. Use HH:MM.", 400)
            except Exception as e_calc:
                 logger.error(f"Error calculando minutos de bloqueo: {e_calc}")
                 return self.error_response(f"Error interno al calcular minutos: {e_calc}", 500)


            nuevo_bloqueo = {
                'centro_trabajo_id': int(data.get('centro_trabajo_id')),
                'fecha': fecha_str,
                'hora_inicio': hora_inicio_str, # Guardamos el string
                'hora_fin': hora_fin_str,     # Guardamos el string
                'minutos_bloqueados': Decimal(minutos_calculados), # Guardamos lo calculado
                'motivo': data.get('motivo_bloqueo')
            }

            if nuevo_bloqueo['minutos_bloqueados'] <= 0:
                # Esta validación ahora es redundante si t_fin > t_inicio, pero la dejamos por seguridad
                return self.error_response("El rango de horas resulta en 0 minutos.", 400)

            result = self.bloqueo_capacidad_model.create(nuevo_bloqueo)
            if result.get('success'):
                return self.success_response(data=result.get('data'), message="Bloqueo agregado.", status_code=201)
            else:
                # Manejar error de unicidad (ya existe un bloqueo para ese día/línea)
                if 'bloqueos_capacidad_centro_fecha_key' in str(result.get('error')):
                    return self.error_response("Ya existe un bloqueo para esa línea en esa fecha. Edite el existente.", 409)
                return self.error_response(f"Error: {result.get('error')}", 500)
        except Exception as e:
            return self.error_response(f"Error: {str(e)}", 500)

    def eliminar_bloqueo(self, bloqueo_id: int) -> tuple:
        """Elimina un bloqueo de capacidad."""
        try:
            result = self.bloqueo_capacidad_model.delete(bloqueo_id, 'id')
            if result.get('success'):
                return self.success_response(message="Bloqueo eliminado.")
            else:
                return self.error_response(f"Error al eliminar: {result.get('error')}", 500)
        except Exception as e:
            return self.error_response(f"Error: {str(e)}", 500)


    def _crear_o_actualizar_issue(self, op_id: int, tipo_error: str, mensaje: str, datos_snapshot: Dict) -> Dict:
        """
        Guarda el issue de planificación.
        Busca si ya existe uno por op_id; si es así, lo actualiza. Si no, lo crea.
        DEVUELVE el issue creado/actualizado.
        """
        try:
            # 1. Buscar issue existente PENDIENTE
            existing_issue_resp = self.issue_planificacion_model.find_all(
                filters={'orden_produccion_id': op_id}, # <-- ¡CORREGIDO!
                limit=1
            )

            issue_data = {
                'orden_produccion_id': op_id,
                'tipo_error': tipo_error,
                'mensaje': mensaje,
                'datos_snapshot': datos_snapshot,
                'estado': 'PENDIENTE',
                'updated_at': datetime.now().isoformat()
            }

            if existing_issue_resp.get('success') and existing_issue_resp.get('data'):
                # 2a. Actualizar issue existente
                issue_id = existing_issue_resp['data'][0]['id']
                logger.info(f"Actualizando Issue '{tipo_error}' existente (ID: {issue_id}) para OP: {op_id}")
                result = self.issue_planificacion_model.update(issue_id, issue_data, 'id')
            else:
                # 2b. Crear issue nuevo
                logger.info(f"Registrando Nuevo Issue '{tipo_error}' para OP: {op_id}")
                result = self.issue_planificacion_model.create(issue_data)

            if result.get('success'):
                return result.get('data') # <-- ¡Devolver el objeto!
            else:
                logger.error(f"Error al guardar issue: {result.get('error')}")
                return None

        except Exception as e:
            logger.error(f"Error en _crear_o_actualizar_issue para OP {op_id}: {e}", exc_info=True)
            return None

    # --- AÑADIR ESTE OTRO HELPER ---
    def _resolver_issue_por_op(self, op_id: int):
        """ Elimina un issue de la tabla cuando se planifica manualmente. """
        try:
            self.issue_planificacion_model.delete_by_op_id(op_id)
            logger.info(f"Issue para OP {op_id} resuelto y eliminado.")
        except Exception as e:
            logger.error(f"Error al resolver/eliminar issue para OP {op_id}: {e}", exc_info=True)


    def _calcular_sugerencias_para_op_optimizado(self, op: Dict, mapas_precargados: Dict) -> Dict:
        """
        Versión optimizada que NO consulta la DB.
        Calcula T_Prod, T_Proc, Línea Sug, y JIT para una ÚNICA OP
        usando los mapas de datos precargados.
        """
        sugerencias = {
            'sugerencia_t_prod_dias': 0, 'sugerencia_t_proc_dias': 0,
            'sugerencia_linea': None, 'sugerencia_stock_ok': False,
            'sugerencia_fecha_inicio_jit': date.today().isoformat(), 'linea_compatible': None
        }
        op_id_log = op.get('id', 'N/A')

        try:
            receta_id = op.get('receta_id')
            cantidad = Decimal(op.get('cantidad_planificada', 0))

            if not receta_id or cantidad <= 0:
                return sugerencias # Devuelve default si no hay datos

            # Mapas de datos
            operaciones_map = mapas_precargados.get('operaciones', {})
            recetas_map = mapas_precargados.get('recetas', {})
            centros_map = mapas_precargados.get('centros_trabajo', {})
            ingredientes_map = mapas_precargados.get('ingredientes', {})
            stock_map = mapas_precargados.get('stock', {})
            insumos_map = mapas_precargados.get('insumos', {})

            # 1. Calcular Carga Total (¡Usando helper optimizado!)
            operaciones_receta = operaciones_map.get(receta_id, [])
            carga_total_minutos = self._calcular_carga_op_precargada(op, operaciones_receta)

            # 2. Calcular Línea Sugerida y Capacidad Neta (¡Desde mapas!)
            linea_sug = None
            capacidad_neta_linea_sugerida = Decimal(480.0) # Fallback
            receta = recetas_map.get(receta_id)

            if receta:
                linea_compatible_str = receta.get('linea_compatible', '2')
                sugerencias['linea_compatible'] = linea_compatible_str
                # ... (lógica de decisión de línea_sug, igual que antes) ...
                linea_compatible_list = linea_compatible_str.split(',')
                tiempo_l1 = receta.get('tiempo_prod_unidad_linea1', 0)
                tiempo_l2 = receta.get('tiempo_prod_unidad_linea2', 0)
                UMBRAL_CANTIDAD_LINEA_1 = 50
                puede_l1 = '1' in linea_compatible_list and tiempo_l1 > 0
                puede_l2 = '2' in linea_compatible_list and tiempo_l2 > 0
                if puede_l1 and puede_l2:
                    linea_sug = 1 if cantidad >= UMBRAL_CANTIDAD_LINEA_1 else 2
                elif puede_l1: linea_sug = 1
                elif puede_l2: linea_sug = 2
                sugerencias['sugerencia_linea'] = linea_sug

                # 3. Obtener Capacidad Real (¡Desde mapa!)
                if linea_sug:
                    ct_data = centros_map.get(linea_sug) # <-- ¡CAMBIO!
                    if ct_data:
                        cap_std = Decimal(ct_data.get('tiempo_disponible_std_dia', 480))
                        eficiencia = Decimal(ct_data.get('eficiencia', 1.0))
                        utilizacion = Decimal(ct_data.get('utilizacion', 1.0))
                        cap_neta_calculada = cap_std * eficiencia * utilizacion
                        if cap_neta_calculada > 0:
                            capacidad_neta_linea_sugerida = cap_neta_calculada

            # 4. Calcular T_Prod (Días)
            if carga_total_minutos > 0:
                sugerencias['sugerencia_t_prod_dias'] = math.ceil(
                    carga_total_minutos / capacidad_neta_linea_sugerida
                )

            # 5. Verificar Stock (T_Proc) (¡Desde mapas!)
            ingredientes_receta = ingredientes_map.get(receta_id, [])
            stock_ok_agg = True
            tiempos_entrega_agg = []

            if ingredientes_receta:
                for ingrediente in ingredientes_receta:
                    insumo_id = ingrediente['id_insumo']
                    cantidad_ingrediente = Decimal(ingrediente.get('cantidad', 0))
                    cant_necesaria_total = cantidad_ingrediente * cantidad

                    stock_disp = stock_map.get(insumo_id, Decimal(0)) # <-- ¡CAMBIO!

                    if stock_disp < cant_necesaria_total:
                        stock_ok_agg = False
                        # Obtener tiempo de entrega (¡Desde mapa!)
                        insumo_data = insumos_map.get(insumo_id) # <-- ¡CAMBIO!
                        if insumo_data:
                            tiempos_entrega_agg.append(insumo_data.get('tiempo_entrega_dias', 0))
            else:
                stock_ok_agg = False

            sugerencias['sugerencia_stock_ok'] = stock_ok_agg
            if not stock_ok_agg:
                sugerencias['sugerencia_t_proc_dias'] = max(tiempos_entrega_agg) if tiempos_entrega_agg else 0

            # 6. Calcular JIT (igual que antes, solo usa variables locales)
            # ... (lógica JIT sin cambios) ...
            today = date.today()
            t_prod_dias = sugerencias['sugerencia_t_prod_dias']
            t_proc_dias = sugerencias['sugerencia_t_proc_dias']
            op_fecha_meta_str = op.get('fecha_meta')
            if not op_fecha_meta_str:
                op_fecha_meta_str = op.get('fecha_inicio_planificada')
                if not op_fecha_meta_str:
                    op_fecha_meta_str = (today + timedelta(days=7)).isoformat()
            fecha_meta_solo_str = op_fecha_meta_str.split('T')[0].split(' ')[0]
            fecha_meta = date.fromisoformat(fecha_meta_solo_str)
            fecha_inicio_ideal = fecha_meta - timedelta(days=t_prod_dias)
            fecha_disponibilidad_material = today + timedelta(days=t_proc_dias)
            fecha_inicio_base = max(fecha_inicio_ideal, fecha_disponibilidad_material)
            fecha_inicio_sugerida_jit = max(fecha_inicio_base, today)
            sugerencias['sugerencia_fecha_inicio_jit'] = fecha_inicio_sugerida_jit.isoformat()

        except Exception as e_jit:
            logger.error(f"[JIT MODAL {op_id_log}] EXCEPCIÓN INESPERADA (Optimizado): {e_jit}", exc_info=True)
            sugerencias['sugerencia_fecha_inicio_jit'] = date.today().isoformat()

        return sugerencias

    def _verificar_y_replanificar_ops_por_fecha(self, fecha: date, usuario_id: int):
        """
        Verifica si las OPs planificadas para una fecha específica aún caben
        en la capacidad neta real de ese día (considerando bloqueos de último minuto).
        Si no caben, las mueve al próximo día disponible y crea un Issue.
        --- ¡MODIFICADO! Devuelve la lista de issues/notificaciones que genera. ---
        """
        logger.info(f"[PlanAdaptativa] Verificando OPs para {fecha.isoformat()}...")
        fecha_iso = fecha.isoformat()
        issues_generados_en_run = [] # <-- ¡NUEVO!

        # 1. Obtener capacidad REAL neta del día
        try:
            capacidad_hoy = self.obtener_capacidad_disponible([1, 2], fecha, fecha)
            cap_neta_l1 = capacidad_hoy.get(1, {}).get(fecha_iso, {}).get('neta', 0.0)
            cap_neta_l2 = capacidad_hoy.get(2, {}).get(fecha_iso, {}).get('neta', 0.0)
            capacidad_restante_map = { 1: cap_neta_l1, 2: cap_neta_l2 }
            logger.info(f"[PlanAdaptativa] Capacidad neta HOY: L1={cap_neta_l1} min, L2={cap_neta_l2} min")
        except Exception as e_cap:
            logger.error(f"[PlanAdaptativa] No se pudo obtener la capacidad de hoy. Abortando. Error: {e_cap}")
            return issues_generados_en_run # Devuelve lista vacía

        # 2. Obtener todas las OPs que inician (o debían iniciar) en esa fecha
        estados_a_verificar = [
            'EN ESPERA', 'EN_ESPERA',
            'LISTA PARA PRODUCIR', 'LISTA_PARA_PRODUCIR',
        ]
        filtros_ops = {
            'fecha_inicio_planificada': fecha_iso,
            'estado': ('in', estados_a_verificar)
        }

        ops_resp, _ = self.orden_produccion_controller.obtener_ordenes(filtros_ops)
        if not ops_resp.get('success') or not ops_resp.get('data'):
            logger.info(f"[PlanAdaptativa] No se encontraron OPs planificadas para {fecha_iso}. Verificación finalizada.")
            return issues_generados_en_run

        ops_del_dia = ops_resp['data']
        ops_del_dia.sort(key=lambda op: op.get('fecha_meta') or '9999-12-31')
        logger.info(f"[PlanAdaptativa] {len(ops_del_dia)} OPs encontradas para {fecha_iso}. Verificando si caben...")

        # 3. Obtener el mapa de carga futura
        filtros_ops_futuras = {
            'estado': ('in', estados_a_verificar),
            'fecha_inicio_planificada_neq': fecha_iso
        }

        ops_futuras_resp, _ = self.orden_produccion_controller.obtener_ordenes(filtros_ops_futuras)
        ops_futuras = ops_futuras_resp.get('data', []) if ops_futuras_resp.get('success') else []
        carga_actual_map_futura = self.calcular_carga_capacidad(ops_futuras)

        # 4. Iterar sobre las OPs de hoy y verificar si caben
        for op in ops_del_dia:
            op_id = op.get('id')
            op_codigo = op.get('codigo')
            linea = op.get('linea_asignada')

            if not linea in [1, 2]: continue

            # --- INICIO DE LA CORRECCIÓN ESTRUCTURAL ---

            # 1. Obtenemos la capacidad diaria CONFIGURABLE de la línea
            cap_diaria_linea = self._obtener_capacidad_diaria_estandar(linea)

            # 2. Calculamos la carga total de la OP
            carga_op_total = float(self._calcular_carga_op(op))

            # 3. Calculamos la carga que esta OP consumirá el PRIMER DÍA
            carga_del_primer_dia = min(carga_op_total, cap_diaria_linea)

            # 4. Comparamos la carga del PRIMER DÍA con la capacidad restante de HOY
            if carga_del_primer_dia <= capacidad_restante_map[linea]:
                # OK, cabe. Restamos solo la carga de este día
                capacidad_restante_map[linea] -= carga_del_primer_dia
                logger.info(f"[PlanAdaptativa] OK: OP {op_codigo} (Carga Día 1: {carga_del_primer_dia:.0f} min) cabe en L{linea} (Restante: {capacidad_restante_map[linea]:.0f} min).")

            else:
                # CONFLICTO: No cabe ni siquiera el primer día.
                logger.warning(f"[PlanAdaptativa] ¡CONFLICTO! OP {op_codigo} (Carga Día 1: {carga_del_primer_dia:.0f} min) NO cabe en L{linea} (Restante: {capacidad_restante_map[linea]:.0f} min).")

                # Iniciar la replanificación
                fecha_manana = fecha + timedelta(days=1)
                simulacion_result = self._simular_asignacion_carga(
                    carga_total_op=carga_op_total,
                    linea_propuesta=linea,
                    fecha_inicio_busqueda=fecha_manana,
                    op_id_a_excluir=op_id,
                    carga_actual_map=carga_actual_map_futura
                )

                if simulacion_result['success']:
                    nueva_fecha_inicio = simulacion_result['fecha_inicio_real']

                    # --- ¡INICIO DE LA CORRECCIÓN! ---
                    # 1. Obtener la FECHA DE FIN de la simulación
                    fecha_fin_estimada_simulada = simulacion_result['fecha_fin_estimada']
                    # --- FIN DE LA CORRECCIÓN! ---

                    self.orden_produccion_controller.model.update(op_id, {'fecha_inicio_planificada': nueva_fecha_inicio.isoformat()}, 'id')

                    # --- INICIO DE LA MEJORA (Lógica de Retraso) ---

                    op_completa_resp = self.orden_produccion_controller.obtener_orden_por_id(op_id)
                    op_completa = op_completa_resp.get('data', op)

                    fecha_meta_str = op_completa.get('fecha_meta')
                    fecha_meta = None
                    es_retraso_agravado = False

                    if fecha_meta_str:
                        try:
                            fecha_meta = date.fromisoformat(fecha_meta_str.split('T')[0].split(' ')[0])

                            # --- ¡INICIO DE LA CORRECCIÓN! ---
                            # 2. Comparar la FECHA DE FIN contra la FECHA META
                            if fecha_fin_estimada_simulada > fecha_meta:
                            # --- FIN DE LA CORRECCIÓN! ---
                                es_retraso_agravado = True
                        except ValueError:
                            pass

                    if es_retraso_agravado:
                        # --- ¡INICIO DE LA CORRECCIÓN! ---
                        # 3. Actualizar el mensaje para que muestre la fecha de fin
                        meta_str = f"(Meta: {fecha_meta.isoformat()})" if fecha_meta else "(Sin Fecha Meta)"
                        mensaje_issue = f"¡RETRASO AGRAVADO! Movida por falta de capacidad. Terminará el {fecha_fin_estimada_simulada.isoformat()} {meta_str}"
                        # --- FIN DE LA CORRECCIÓN! ---

                        tipo_error_final = 'SOBRECARGA_INMINENTE'
                        snapshot_datos = {'motivo': 'REPLAN_AUTO_AUSENCIA', 'fecha_original': fecha_iso, 'fecha_nueva': nueva_fecha_inicio.isoformat(), 'fecha_meta': fecha_meta.isoformat()}
                    else:
                        mensaje_issue = f"Movida del {fecha_iso} al {nueva_fecha_inicio.isoformat()} por falta de capacidad (ej. ausentismo o bloqueo)."
                        tipo_error_final = 'REPLAN_AUTO_AUSENCIA'
                        snapshot_datos = {'motivo': 'REPLAN_AUTO_AUSENCIA', 'fecha_original': fecha_iso, 'fecha_nueva': nueva_fecha_inicio.isoformat()}

                    nuevo_issue = self._crear_o_actualizar_issue(op_id, tipo_error_final, mensaje_issue, snapshot_datos)
                    # --- FIN DE LA MEJORA ---

                    if nuevo_issue:
                        # Enriquecer 'nuevo_issue' con los datos de op_completa
                        nuevo_issue['op_codigo'] = op_completa.get('codigo')
                        nuevo_issue['op_producto_nombre'] = op_completa.get('producto_nombre')
                        nuevo_issue['cantidad_planificada'] = op_completa.get('cantidad_planificada')
                        nuevo_issue['op_fecha_meta'] = op_completa.get('fecha_meta')
                        nuevo_issue['receta_id'] = op_completa.get('receta_id')
                        issues_generados_en_run.append(nuevo_issue)

                    logger.info(f"[PlanAdaptativa] ¡MOVIDA! {mensaje_issue}")
                    # Actualizar el mapa de carga futura para la siguiente iteración del bucle
                    carga_actual_map_futura.setdefault(linea, {})[nueva_fecha_inicio.isoformat()] = \
                        carga_actual_map_futura.get(linea, {}).get(nueva_fecha_inicio.isoformat(), 0.0) + carga_op_total

                else:
                    # Falló la simulación (no hay espacio en 30 días)
                    mensaje_issue = f"OP {op_codigo} no cabe hoy ({fecha_iso}) y NO se encontró espacio en los próximos 30 días."
                    logger.error(f"[PlanAdaptativa] ¡ERROR CRÍTICO! {mensaje_issue}")

                    nuevo_issue = self._crear_o_actualizar_issue(op_id, 'SOBRECARGA_INMINENTE', mensaje_issue, {})
                    if nuevo_issue:
                        # ... (enriquecer 'nuevo_issue' con op_codigo, etc.) ...
                        nuevo_issue['op_codigo'] = op.get('codigo') # Usar 'op' ligera como fallback
                        nuevo_issue['op_producto_nombre'] = op.get('producto_nombre')
                        nuevo_issue['op_cantidad'] = op.get('cantidad_planificada')
                        nuevo_issue['op_fecha_meta'] = op.get('fecha_meta')
                        nuevo_issue['receta_id'] = op.get('receta_id')
                        issues_generados_en_run.append(nuevo_issue)

            # --- FIN DE LA CORRECCIÓN ESTRUCTURAL ---

        logger.info(f"[PlanAdaptativa] Verificación de {fecha.isoformat()} finalizada.")
        return issues_generados_en_run # <-- ¡Devolver la lista!

    def _obtener_capacidad_diaria_estandar(self, linea_id: int) -> float:
        """
        Obtiene la capacidad neta estándar de un día para una línea (fallback a 480).
        """
        try:
            ct_resp = self.centro_trabajo_model.find_by_id(linea_id, 'id') #
            if ct_resp.get('success'):
                ct_data = ct_resp.get('data', {})
                # LEE TUS VALORES CONFIGURABLES
                cap_std = Decimal(ct_data.get('tiempo_disponible_std_dia', 480)) #
                eficiencia = Decimal(ct_data.get('eficiencia', 1.0)) #
                utilizacion = Decimal(ct_data.get('utilizacion', 1.0)) #

                cap_neta = float(cap_std * eficiencia * utilizacion)
                return cap_neta if cap_neta > 0 else 480.0
        except Exception:
            pass # Fallback
        return 480.0

    def _get_feriados_ar(self, years: List[int]) -> dict:
        """
        Helper para obtener y cachear el objeto de feriados de Argentina.
        Evita tener que reinstanciarlo en cada llamada.
        """
        try:
            # Comprobar si el caché existe y si cubre los años solicitados
            if self.feriados_ar_cache and all(y in self.feriados_ar_cache.years for y in years):
                return self.feriados_ar_cache

            # Si no, (re)crear el caché
            self.feriados_ar_cache = holidays.country_holidays('AR', years=years)
            logger.info(f"[Holidays] Caché de feriados de Argentina actualizado para años: {years}")
            return self.feriados_ar_cache
        except Exception as e_hol:
            logger.error(f"Error al inicializar o acceder al caché de 'holidays': {e_hol}.")
            return {} # Fallback a un dict vacío

    def _es_dia_laborable(self, fecha: date) -> bool:
        """
        Verifica si un día es laborable (no es fin de semana Y no es feriado).
        """
        # 1. Chequear Fin de Semana (0=Lunes, 5=Sábado, 6=Domingo)
        if fecha.weekday() >= 5:
            return False

        # 2. Chequear Feriado
        try:
            feriados_ar = self._get_feriados_ar(years=[fecha.year])
            if fecha in feriados_ar:
                return False # Es feriado
        except Exception as e:
            logger.error(f"Error al chequear feriado para {fecha.isoformat()}: {e}")
            # Ser conservador: si falla la librería, asumir que es laborable
            pass

        return True # Es laborable

    def resolver_issue_api(self, issue_id: int) -> tuple:
        """
        Endpoint para marcar un issue como 'RESUELTO'.
        """
        try:
            logger.info(f"[Issue] Marcando issue {issue_id} como RESUELTO.")
            update_data = {'estado': 'RESUELTO'}

            # Usamos el modelo base para actualizar por ID
            result = self.issue_planificacion_model.update(issue_id, update_data, 'id')

            if result.get('success'):
                return self.success_response(message="Issue archivado.")
            else:
                logger.error(f"[Issue] Error al actualizar issue {issue_id}: {result.get('error')}")
                return self.error_response(f"Error al actualizar: {result.get('error')}", 500)
        except Exception as e:
            logger.error(f"[Issue] Excepción en resolver_issue_api: {e}", exc_info=True)
            return self.error_response(f"Error: {str(e)}", 500)