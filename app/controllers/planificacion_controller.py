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
from decimal import Decimal


logger = logging.getLogger(__name__)

class PlanificacionController(BaseController):
    def __init__(self):
        super().__init__()
        self.orden_produccion_controller = OrdenProduccionController()
        self.inventario_controller = InventarioController()
        self.centro_trabajo_model = CentroTrabajoModel()
        self.receta_model = RecetaModel() # Asegúrate que esté inicializado
        self.insumo_model = InsumoModel() # Asegúrate que esté inicializado

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
    def _ejecutar_aprobacion_final(self, op_id: int, asignaciones: dict, usuario_id: int) -> tuple:
        """ Ejecuta los pasos de pre-asignación y confirmación/aprobación. """
        try:
            # PASO Pre-Asignar: Asegúrate de pasar todos los datos relevantes
            datos_pre_asignar = {
                'linea_asignada': asignaciones.get('linea_asignada'),
                'supervisor_responsable_id': asignaciones.get('supervisor_id'),
                'operario_asignado_id': asignaciones.get('operario_id')
            }
            datos_pre_asignar = {k: v for k, v in datos_pre_asignar.items() if v is not None} # Limpiar Nones

            res_pre_asig_dict, res_pre_asig_status = self.orden_produccion_controller.pre_asignar_recursos(
                op_id, datos_pre_asignar, usuario_id
            )
            if res_pre_asig_status >= 400: return res_pre_asig_dict, res_pre_asig_status

            # PASO Confirmar Inicio y Aprobar
            res_conf_dict, res_conf_status = self.orden_produccion_controller.confirmar_inicio_y_aprobar(
                op_id, {'fecha_inicio_planificada': asignaciones.get('fecha_inicio')}, usuario_id
            )
            return res_conf_dict, res_conf_status
        except Exception as e:
            logger.error(f"Error en _ejecutar_aprobacion_final para OP {op_id}: {e}", exc_info=True)
            # --- CORRECCIÓN AQUÍ ---
            # Devolver tupla explícitamente
            error_dict = self.error_response(f"Error interno al ejecutar aprobación final: {str(e)}", 500)
            return error_dict, 500
        # ----------------------

    # --- MÉTODO PRINCIPAL REFACTORIZADO ---
    def consolidar_y_aprobar_lote(self, op_ids: List[int], asignaciones: dict, usuario_id: int) -> tuple:
        """
        Orquesta la consolidación y aprobación de un lote de OPs, manejando la
        verificación de capacidad (CRP) y la lógica de aprobación.
        """
        try:
            # 1. Obtener y validar datos de la OP (consolidada o no)
            op_a_planificar_id, op_data = self._obtener_datos_op_a_planificar(op_ids, usuario_id)
            if not op_a_planificar_id:
                return self.error_response(op_data, 500) # op_data tiene el mensaje de error

            linea_propuesta = asignaciones.get('linea_asignada')
            fecha_inicio_str = asignaciones.get('fecha_inicio')

            if not linea_propuesta or not fecha_inicio_str:
                return self.error_response("Faltan línea o fecha de inicio.", 400)
            try:
                fecha_inicio_propuesta = date.fromisoformat(fecha_inicio_str)
            except ValueError:
                return self.error_response("Formato de fecha inválido. Usar YYYY-MM-DD.", 400)

            # 2. Calcular carga total de la OP
            carga_total_op = float(self.orden_produccion_controller.calcular_carga_op(op_data))
            if carga_total_op <= 0:
                logger.warning(f"OP {op_a_planificar_id} con carga 0. Aprobando directamente.")
                return self._ejecutar_aprobacion_final(op_a_planificar_id, asignaciones, usuario_id)

            # 3. Simular la planificación (CRP) para verificar capacidad
            logger.info(f"Iniciando simulación CRP para OP {op_a_planificar_id} en Línea {linea_propuesta} desde {fecha_inicio_str}...")
            resultado_simulacion = self._simular_crp_multi_dia(
                op_a_planificar_id, carga_total_op, linea_propuesta, fecha_inicio_propuesta
            )

            # 4. Actuar según el resultado de la simulación
            status = resultado_simulacion.get('status')

            if status == 'SOBRECARGA':
                # Generar respuesta de error detallada
                return self._generar_respuesta_sobrecarga(**resultado_simulacion['detalle'])

            elif status == 'OK':
                dias_necesarios = resultado_simulacion['dias_necesarios']
                fecha_fin_estimada_str = resultado_simulacion['fecha_fin_estimada'].isoformat()
                logger.info(f"Simulación CRP OK. OP {op_a_planificar_id} requiere ~{dias_necesarios} día(s), finalizando aprox. {fecha_fin_estimada_str}.")

                if dias_necesarios > 1:
                    # Requiere confirmación del usuario para planificación multi-día
                    return {
                        'success': False,
                        'error': 'MULTI_DIA_CONFIRM',
                        'message': (f"Esta OP requiere aproximadamente {dias_necesarios} días para completarse "
                                    f"(hasta {fecha_fin_estimada_str}) debido a la capacidad de la línea. "
                                    f"¿Desea confirmar la planificación?"),
                        'dias_necesarios': dias_necesarios,
                        'fecha_fin_estimada': fecha_fin_estimada_str,
                        'op_id_confirmar': op_a_planificar_id,
                        'asignaciones_confirmar': asignaciones
                    }, 200
                else:
                    # Cabe en un solo día, aprobar directamente
                    logger.info("OP cabe en un día. Ejecutando aprobación final...")
                    return self._ejecutar_aprobacion_final(op_a_planificar_id, asignaciones, usuario_id)
            else:
                 # Caso inesperado, como un status desconocido
                 return self.error_response("Resultado inesperado de la simulación de capacidad.", 500)

        except Exception as e:
            logger.error(f"Error crítico en consolidar_y_aprobar_lote: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)


    # --- NUEVO HELPER para obtener datos OP (MODIFICADO) ---
    def _obtener_datos_op_a_planificar(self, op_ids: List[int], usuario_id: int) -> tuple: # <-- AÑADIR usuario_id
        """ Obtiene los datos de la OP (consolidada o individual). Devuelve (id, data) o (None, error_msg). """
        op_a_planificar_id = None
        op_data = None
        if len(op_ids) > 1:
            # --- PASAR usuario_id ---
            resultado_consol = self.orden_produccion_controller.consolidar_ordenes_produccion(op_ids, usuario_id) # <-- USAR el usuario_id recibido
            # ------------------------
            if not resultado_consol.get('success'): return None, f"Error al consolidar: {resultado_consol.get('error')}"
            op_a_planificar_id = resultado_consol.get('data', {}).get('id')
            op_data = resultado_consol.get('data')
        else:
            op_a_planificar_id = op_ids[0]
            op_result = self.orden_produccion_controller.obtener_orden_por_id(op_a_planificar_id)
            if not op_result.get('success'): return None, f"No se encontró la OP ID {op_a_planificar_id}."
            op_data = op_result.get('data')

        if not op_a_planificar_id or not op_data: return None, "No se pudieron obtener los datos de la OP."
        return op_a_planificar_id, op_data

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

    def obtener_ops_pendientes_planificacion(self, dias_horizonte: int = 7) -> tuple:
        """
        Obtiene OPs PENDIENTES, agrupa, calcula sugerencias Y AÑADE unidad_medida y linea_compatible.
        """
        try:
            # 1. Calcular rango y filtrar OPs (sin cambios)
            hoy = date.today()
            dias_horizonte_int = int(dias_horizonte)
            fecha_fin_horizonte = hoy + timedelta(days=dias_horizonte_int)
            filtros = {
                'estado': 'PENDIENTE',
                'fecha_meta_desde': hoy.isoformat(),
                'fecha_meta_hasta': fecha_fin_horizonte.isoformat()
            }
            # Asume que obtener_ordenes trae 'producto_unidad_medida' gracias a get_all_enriched
            response, _ = self.orden_produccion_controller.obtener_ordenes(filtros)
            if not response.get('success'):
                logger.error(f"Error al obtener OPs pendientes para MPS: {response.get('error')}")
                return self.error_response("Error al cargar órdenes pendientes.")
            ordenes_en_horizonte = response.get('data', [])

            # 2. Agrupar por Producto y calcular totales
            mps_agrupado = defaultdict(lambda: {
                'cantidad_total': 0,
                'ordenes': [],
                'fecha_meta_mas_proxima': None,
                'receta_id': None,
                'unidad_medida': None # <-- Inicializar unidad_medida
            })
            for op in ordenes_en_horizonte:
                producto_id = op.get('producto_id')
                producto_nombre = op.get('producto_nombre', 'Desconocido')
                cantidad = op.get('cantidad_planificada', 0)
                fecha_meta_op_str = op.get('fecha_meta')
                receta_id_op = op.get('receta_id')
                unidad_medida_op = op.get('producto_unidad_medida') # <-- Obtener unidad de medida

                if not producto_id or cantidad <= 0 or not receta_id_op: continue

                clave_producto = (producto_id, producto_nombre)
                mps_agrupado[clave_producto]['cantidad_total'] += float(cantidad)
                mps_agrupado[clave_producto]['ordenes'].append(op)
                if mps_agrupado[clave_producto]['receta_id'] is None:
                    mps_agrupado[clave_producto]['receta_id'] = receta_id_op
                if mps_agrupado[clave_producto]['unidad_medida'] is None and unidad_medida_op: # <-- Guardar unidad de medida
                    mps_agrupado[clave_producto]['unidad_medida'] = unidad_medida_op

                # ... (lógica fecha_meta_mas_proxima sin cambios) ...
                fecha_meta_mas_proxima_actual = mps_agrupado[clave_producto]['fecha_meta_mas_proxima']
                if fecha_meta_op_str:
                     fecha_meta_op = date.fromisoformat(fecha_meta_op_str)
                     if fecha_meta_mas_proxima_actual is None or fecha_meta_op < date.fromisoformat(fecha_meta_mas_proxima_actual):
                          mps_agrupado[clave_producto]['fecha_meta_mas_proxima'] = fecha_meta_op_str


            # 3. Calcular sugerencia agregada (T_Prod, Línea, T_Proc, Stock)
            # Ya tienes receta_model e insumo_model inicializados en __init__

            for clave_producto, data in mps_agrupado.items():
                cantidad_total_agrupada = data['cantidad_total']
                receta_id_agrupada = data['receta_id']

                # Inicializar valores de sugerencia
                data['sugerencia_t_prod_dias'] = 0
                data['sugerencia_linea'] = None
                data['sugerencia_t_proc_dias'] = 0
                data['sugerencia_stock_ok'] = False
                data['sugerencia_insumos_faltantes'] = []
                data['linea_compatible'] = None # <-- Inicializar linea_compatible

                if not receta_id_agrupada: continue

                # a) Calcular Tiempo de Producción y Línea Sugerida
                receta_res = self.receta_model.find_by_id(receta_id_agrupada, 'id')
                if receta_res.get('success'):
                    receta = receta_res['data']
                    linea_compatible_str = receta.get('linea_compatible', '2') # <-- Obtener linea_compatible
                    data['linea_compatible'] = linea_compatible_str # <-- Guardar linea_compatible

                    linea_compatible_list = linea_compatible_str.split(',')
                    tiempo_prep = receta.get('tiempo_preparacion_minutos', 0)
                    tiempo_l1 = receta.get('tiempo_prod_unidad_linea1', 0)
                    tiempo_l2 = receta.get('tiempo_prod_unidad_linea2', 0)
                    UMBRAL_CANTIDAD_LINEA_1 = 50
                    puede_l1 = '1' in linea_compatible_list and tiempo_l1 > 0
                    puede_l2 = '2' in linea_compatible_list and tiempo_l2 > 0
                    linea_sug_agg = 0
                    tiempo_prod_unit_elegido_agg = 0
                    if puede_l1 and puede_l2:
                        linea_sug_agg = 1 if cantidad_total_agrupada >= UMBRAL_CANTIDAD_LINEA_1 else 2
                        tiempo_prod_unit_elegido_agg = tiempo_l1 if linea_sug_agg == 1 else tiempo_l2
                    elif puede_l1: linea_sug_agg = 1; tiempo_prod_unit_elegido_agg = tiempo_l1
                    elif puede_l2: linea_sug_agg = 2; tiempo_prod_unit_elegido_agg = tiempo_l2

                    if linea_sug_agg > 0:
                         t_prod_minutos_agg = tiempo_prep + (tiempo_prod_unit_elegido_agg * cantidad_total_agrupada)
                         data['sugerencia_t_prod_dias'] = math.ceil(t_prod_minutos_agg / 480)
                         data['sugerencia_linea'] = linea_sug_agg

                # b) Verificar Stock Agregado (sin cambios funcionales)
                ingredientes_result = self.receta_model.get_ingredientes(receta_id_agrupada)
                # ... (resto de lógica de stock y t_proc_dias sin cambios) ...
                insumos_faltantes_agg = []
                stock_ok_agg = True
                if ingredientes_result.get('success'):
                    for ingrediente in ingredientes_result.get('data', []):
                        insumo_id = ingrediente['id_insumo']
                        cant_necesaria_total = ingrediente['cantidad'] * cantidad_total_agrupada
                        stock_disp_res = self.inventario_controller.obtener_stock_disponible_insumo(insumo_id)
                        stock_disp = stock_disp_res.get('data', {}).get('stock_disponible', 0) if stock_disp_res.get('success') else 0
                        if stock_disp < cant_necesaria_total:
                            stock_ok_agg = False
                            faltante = cant_necesaria_total - stock_disp
                            insumos_faltantes_agg.append({ 'insumo_id': insumo_id, 'nombre': ingrediente.get('nombre_insumo', 'N/A'), 'cantidad_faltante': faltante })
                else: stock_ok_agg = False
                data['sugerencia_stock_ok'] = stock_ok_agg
                data['sugerencia_insumos_faltantes'] = insumos_faltantes_agg

                if not stock_ok_agg:
                    tiempos_entrega_agg = []
                    for insumo_f in insumos_faltantes_agg:
                        insumo_data_res = self.insumo_model.find_by_id(insumo_f['insumo_id'], 'id_insumo')
                        if insumo_data_res.get('success'): tiempos_entrega_agg.append(insumo_data_res['data'].get('tiempo_entrega_dias', 0))
                    data['sugerencia_t_proc_dias'] = max(tiempos_entrega_agg) if tiempos_entrega_agg else 0

            # 4. Convertir a lista ordenada (sin cambios)
            mps_lista_ordenada = sorted(
                [ { 'producto_id': pid, 'producto_nombre': pname, **data }
                  for (pid, pname), data in mps_agrupado.items() ],
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


    # --- MÉTODO PRINCIPAL REFACTORIZADO ---
    def obtener_planificacion_semanal(self, week_str: Optional[str] = None) -> tuple:
        """
        Orquesta la obtención de la planificación semanal, delegando la lógica
        compleja a métodos auxiliares.
        """
        try:
            # 1. Determinar el rango de la semana a visualizar
            rango_semana = self._determinar_rango_semana(week_str)
            start_of_week = rango_semana['start']
            end_of_week = rango_semana['end']
            week_identifier = rango_semana['identifier']

            # 2. Obtener todas las OPs que podrían ser relevantes para esta semana
            ordenes_relevantes = self._obtener_ops_relevantes_para_rango(start_of_week, end_of_week)
            if not ordenes_relevantes:
                # Si no hay OPs, devolver una respuesta vacía pero bien formada
                resultado_vacio = {
                    'ops_visibles_por_dia': { (start_of_week + timedelta(days=i)).isoformat(): [] for i in range(7) },
                    'inicio_semana': start_of_week.isoformat(),
                    'fin_semana': end_of_week.isoformat(),
                    'semana_actual_str': week_identifier
                }
                return self.success_response(data=resultado_vacio)

            # 3. Simular la duración y los días exactos que cada OP ocupará
            ops_con_dias_calculados = self._simular_dias_ocupados_para_ops(ordenes_relevantes, start_of_week, end_of_week)

            # 4. Construir la estructura final agrupando las OPs por día visible
            ops_visibles_por_dia = self._construir_vista_diaria(ops_con_dias_calculados, start_of_week)

            # 5. Devolver el resultado final
            resultado = {
                'ops_visibles_por_dia': ops_visibles_por_dia,
                'inicio_semana': start_of_week.isoformat(),
                'fin_semana': end_of_week.isoformat(),
                'semana_actual_str': week_identifier
            }
            return self.success_response(data=resultado)

        except ValueError as ve: # Capturar errores de formato de fecha/semana
            logger.warning(f"Error de formato en obtener_planificacion_semanal: {ve}")
            return self.error_response(str(ve), 400)
        except Exception as e:
            logger.error(f"Error crítico en obtener_planificacion_semanal: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    # --- NUEVOS HELPERS PARA obtener_planificacion_semanal ---

    def _determinar_rango_semana(self, week_str: Optional[str]) -> Dict:
        """
        Calcula las fechas de inicio y fin de una semana.
        Usa 'week_str' (ej. "2023-W45") o la semana actual si es None.
        """
        if week_str:
            try:
                year, week_num = map(int, week_str.split('-W'))
                start = date.fromisocalendar(year, week_num, 1)
                identifier = week_str
            except (ValueError, TypeError):
                raise ValueError("Formato de semana inválido. Usar 'YYYY-WNN'.")
        else:
            today = date.today()
            start = today - timedelta(days=today.weekday())
            # Usar isocalendar para obtener el formato YYYY-WNN consistente
            identifier = f"{start.isocalendar().year}-W{start.isocalendar().week:02d}"
        
        end = start + timedelta(days=6)
        return {'start': start, 'end': end, 'identifier': identifier}

    def _obtener_ops_relevantes_para_rango(self, start_of_week: date, end_of_week: date) -> List[Dict]:
        """
        Obtiene las OPs activas que inician antes del fin de la semana,
        con un margen para incluir OPs largas que pudieran seguir en proceso.
        """
        dias_margen_previo = 14 # Traer OPs que empezaron hasta 2 semanas antes
        fecha_inicio_filtro = start_of_week - timedelta(days=dias_margen_previo)

        filtros = {
            'fecha_inicio_planificada_desde': fecha_inicio_filtro.isoformat(),
            'fecha_inicio_planificada_hasta': end_of_week.isoformat(),
            'estado': ('in', [
                'EN ESPERA', 'LISTA PARA PRODUCIR', 'EN_LINEA_1', 'EN_LINEA_2',
                'EN_EMPAQUETADO', 'CONTROL_DE_CALIDAD'
            ])
        }
        response_ops, _ = self.orden_produccion_controller.obtener_ordenes(filtros)

        if not response_ops.get('success'):
            logger.error(f"Error al obtener OPs para cálculo semanal: {response_ops.get('error')}")
            # Lanzar una excepción o devolver lista vacía para que el método principal maneje el error.
            # Devolver lista vacía es más simple aquí.
            return []
        
        return response_ops.get('data', [])

    def _simular_dias_ocupados_para_ops(self, ordenes: List[Dict], start_of_week: date, end_of_week: date) -> List[Dict]:
        """
        Para una lista de OPs, calcula y añade la clave 'dias_ocupados_calculados'
        a cada una, simulando su duración día por día.
        """
        # 1. Determinar el rango de capacidad necesario
        fechas_inicio_ops = [date.fromisoformat(op['fecha_inicio_planificada']) for op in ordenes if op.get('fecha_inicio_planificada')]
        if not fechas_inicio_ops: return [] # No hay nada que simular
        
        fecha_min_calculo = min(fechas_inicio_ops)
        dias_margen_posterior = 14 # Margen por si las OPs son largas
        fecha_max_calculo = end_of_week + timedelta(days=dias_margen_posterior)
        
        capacidad_rango = self.obtener_capacidad_disponible([1, 2], fecha_min_calculo, fecha_max_calculo)

        # 2. Simulación
        carga_acumulada_simulacion = {1: defaultdict(float), 2: defaultdict(float)}
        ordenes.sort(key=lambda op: op.get('fecha_inicio_planificada', '9999-12-31')) # Procesar cronológicamente

        for orden in ordenes:
            try:
                linea = orden.get('linea_asignada')
                fecha_inicio_str = orden.get('fecha_inicio_planificada')
                if not linea or not fecha_inicio_str: continue

                fecha_inicio = date.fromisoformat(fecha_inicio_str)
                carga_total = float(self.orden_produccion_controller.calcular_carga_op(orden))
                if carga_total <= 0: continue

                dias_ocupados = []
                carga_restante = carga_total
                fecha_actual = fecha_inicio
                dias_simulados = 0
                max_dias_simulacion_op = 30 # Límite por OP

                while carga_restante > 0.01 and dias_simulados < max_dias_simulacion_op:
                    fecha_str = fecha_actual.isoformat()
                    cap_dia = capacidad_rango.get(linea, {}).get(fecha_str, 0.0)
                    carga_existente = carga_acumulada_simulacion[linea].get(fecha_str, 0.0)
                    cap_restante = max(0.0, cap_dia - carga_existente)
                    
                    carga_a_asignar = min(carga_restante, cap_restante)
                    
                    if carga_a_asignar > 0:
                        dias_ocupados.append(fecha_str)
                        carga_acumulada_simulacion[linea][fecha_str] += carga_a_asignar
                        carga_restante -= carga_a_asignar

                    if carga_restante > 0.01:
                        fecha_actual += timedelta(days=1)
                    dias_simulados += 1
                
                orden['dias_ocupados_calculados'] = dias_ocupados
            except Exception as e:
                logger.error(f"Error simulando duración para OP {orden.get('id')}: {e}", exc_info=True)
                orden['dias_ocupados_calculados'] = [] # Asegurarse que la clave exista

        return ordenes

    def _construir_vista_diaria(self, ops_con_dias: List[Dict], start_of_week: date) -> Dict:
        """
        Toma OPs con sus días ocupados y las agrupa en un diccionario
        por cada día de la semana visible.
        """
        vista_diaria = defaultdict(list)
        end_of_week_str = (start_of_week + timedelta(days=6)).isoformat()
        start_of_week_str = start_of_week.isoformat()
        
        # Inicializar todos los días de la semana
        for i in range(7):
            vista_diaria[(start_of_week + timedelta(days=i)).isoformat()] = []

        for op in ops_con_dias:
            for fecha_ocupada_iso in op.get('dias_ocupados_calculados', []):
                if start_of_week_str <= fecha_ocupada_iso <= end_of_week_str:
                    # Evitar duplicados si una OP se procesa de alguna manera dos veces
                    if op not in vista_diaria[fecha_ocupada_iso]:
                        vista_diaria[fecha_ocupada_iso].append(op)
        
        return dict(vista_diaria)

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


    def calcular_carga_capacidad(self, ordenes_planificadas: List[Dict]) -> Dict:
        """
        Calcula la carga (en minutos) por centro de trabajo y fecha, DISTRIBUYENDO
        la carga de cada OP a lo largo de los días necesarios según la capacidad diaria.
        Devuelve: { centro_id: { fecha_iso: carga_minutos_asignada_ese_dia, ... }, ... }
        """
        carga_distribuida = {1: defaultdict(float), 2: defaultdict(float)}
        # Necesitamos la capacidad para simular la distribución
        # Obtener rango de fechas mínimo y máximo de las OPs planificadas
        fechas_inicio = []
        for op in ordenes_planificadas:
             if op.get('fecha_inicio_planificada'):
                 try: fechas_inicio.append(date.fromisoformat(op['fecha_inicio_planificada']))
                 except ValueError: pass

        if not fechas_inicio: return {1:{}, 2:{}} # No hay OPs válidas para calcular

        fecha_min = min(fechas_inicio)
        # Estimar una fecha máxima razonable (ej. fecha min + 30 días, o basado en plazos)
        fecha_max_estimada = fecha_min + timedelta(days=30)

        # Obtener capacidad para todo el rango relevante
        capacidad_disponible_rango = self.obtener_capacidad_disponible([1, 2], fecha_min, fecha_max_estimada)

        # Ordenar OPs por fecha de inicio para procesar cronológicamente
        ordenes_ordenadas = sorted(
            [op for op in ordenes_planificadas if op.get('fecha_inicio_planificada')],
            key=lambda op: op['fecha_inicio_planificada']
        )

        for orden in ordenes_ordenadas:
            try:
                linea_asignada = orden.get('linea_asignada')
                fecha_inicio_op_str = orden.get('fecha_inicio_planificada')
                if linea_asignada not in [1, 2] or not fecha_inicio_op_str: continue

                fecha_inicio_op = date.fromisoformat(fecha_inicio_op_str)
                carga_total_op = float(self.orden_produccion_controller.calcular_carga_op(orden)) # Usar helper que calcula carga total
                if carga_total_op <= 0: continue

                logger.debug(f"Distribuyendo carga para OP {orden.get('codigo', orden.get('id'))}: {carga_total_op:.2f} min en Línea {linea_asignada} desde {fecha_inicio_op_str}")

                # Simular asignación día por día
                carga_restante_op = carga_total_op
                fecha_actual_sim = fecha_inicio_op
                dias_procesados = 0
                max_dias_op = 30 # Límite por OP

                while carga_restante_op > 0.01 and dias_procesados < max_dias_op: # Usar > 0.01 por precisión float
                    fecha_actual_str = fecha_actual_sim.isoformat()

                    # Capacidad NETA del día (considerando eficiencia, etc.)
                    capacidad_dia = capacidad_disponible_rango.get(linea_asignada, {}).get(fecha_actual_str, 0.0)

                    # Carga YA ASIGNADA a este día por OPs anteriores en este cálculo
                    carga_ya_asignada_este_dia = carga_distribuida[linea_asignada].get(fecha_actual_str, 0.0)

                    # Capacidad REALMENTE restante en el día
                    capacidad_restante_hoy = max(0.0, capacidad_dia - carga_ya_asignada_este_dia)

                    # Cuánto podemos asignar de la OP actual a este día
                    carga_a_asignar_hoy = min(carga_restante_op, capacidad_restante_hoy)

                    if carga_a_asignar_hoy > 0:
                        carga_distribuida[linea_asignada][fecha_actual_str] += carga_a_asignar_hoy
                        carga_restante_op -= carga_a_asignar_hoy
                        logger.debug(f"  -> Asignado {carga_a_asignar_hoy:.2f} min a {fecha_actual_str}. Restante OP: {carga_restante_op:.2f} min")
                    # else: # No cabe nada hoy
                    #    logger.debug(f"  -> No cabe carga en {fecha_actual_str}. Cap restante: {capacidad_restante_hoy:.2f}")


                    # Pasar al siguiente día
                    fecha_actual_sim += timedelta(days=1)
                    dias_procesados += 1

                if carga_restante_op > 0.01:
                     logger.warning(f"OP {orden.get('codigo', orden.get('id'))}: No se pudo asignar toda la carga ({carga_restante_op:.2f} min restantes) en {max_dias_op} días.")
                     # La carga que se pudo asignar hasta ahora sí se incluye en carga_distribuida

            except Exception as e:
                 logger.error(f"Error distribuyendo carga para OP {orden.get('codigo', orden.get('id'))}: {e}", exc_info=True)

        # Convertir defaultdicts internos a dicts normales para devolver
        resultado_final = {
            1: dict(carga_distribuida[1]),
            2: dict(carga_distribuida[2])
        }
        return resultado_final

    def obtener_ops_para_hoy(self) -> tuple:
        """
        Obtiene las órdenes de producción planificadas para comenzar hoy o que ya están
        en proceso, y las agrupa por estado para el tablero Kanban del operario.
        """
        try:
            today_iso = date.today().isoformat()
            
            # Filtra OPs que inician hoy o que ya están en un estado de producción activo
            # independientemente de cuándo iniciaron.
            filtros = {
                'fecha_inicio_planificada': today_iso,
                'estados_produccion': True # Un flag para una lógica de filtro especial en el modelo
            }

            response, _ = self.orden_produccion_controller.obtener_ordenes_para_kanban_hoy()

            if not response.get('success'):
                logger.error(f"Error al obtener OPs para el Kanban de hoy: {response.get('error')}")
                return self.error_response("Error al cargar las órdenes para el tablero de producción.")

            ordenes = response.get('data', [])
            
            # Agrupar por estado
            ordenes_por_estado = defaultdict(list)
            for orden in ordenes:
                estado = orden.get('estado')
                
                # Agrupar todos los estados de producción activos bajo "EN PROCESO"
                if estado in ['EN_LINEA_1', 'EN_LINEA_2', 'EN_EMPAQUETADO', 'EN_PRODUCCION']:
                    estado = 'EN_PROCESO'
                
                # Asegurarse de que el estado exista en las columnas definidas para el Kanban
                from app.utils.estados import OP_KANBAN_COLUMNAS
                if estado in OP_KANBAN_COLUMNAS:
                    ordenes_por_estado[estado].append(orden)
            
            return self.success_response(data=dict(ordenes_por_estado))

        except Exception as e:
            logger.error(f"Error crítico en obtener_ops_para_hoy: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    def obtener_datos_para_tablero_planificacion(self, week_str: Optional[str], horizonte_dias: int, user_roles: List[str]) -> tuple:
        """
        Orquesta la obtención de todos los datos necesarios para renderizar el tablero de planificación.
        """
        try:
            # Lógica para determinar la semana
            if not week_str:
                today = date.today()
                start_of_week_iso = today - timedelta(days=today.isoweekday() - 1)
                week_str = start_of_week_iso.strftime("%Y-W%V")

            # Obtener OPs pendientes para MPS
            response_pendientes, _ = self.obtener_ops_pendientes_planificacion(dias_horizonte=horizonte_dias)
            mps_data = {'mps_agrupado': [], 'inicio_horizonte': 'N/A', 'fin_horizonte': 'N/A', 'dias_horizonte': horizonte_dias}
            if response_pendientes.get('success'):
                mps_data = response_pendientes.get('data', mps_data)
            else:
                # En lugar de flashear un mensaje, lo devolveremos en la respuesta
                mps_data['error'] = response_pendientes.get('error', 'Error cargando MPS.')

            # Obtener planificación semanal
            response_semanal, _ = self.obtener_planificacion_semanal(week_str)
            ordenes_por_dia = {}
            inicio_semana = None
            fin_semana = None
            if response_semanal.get('success'):
                data_semanal = response_semanal.get('data', {})
                ordenes_por_dia = data_semanal.get('ops_visibles_por_dia', {})
                inicio_semana_str = data_semanal.get('inicio_semana')
                fin_semana_str = data_semanal.get('fin_semana')
                if inicio_semana_str: inicio_semana = date.fromisoformat(inicio_semana_str)
                if fin_semana_str: fin_semana = date.fromisoformat(fin_semana_str)

            # Lógica de CRP
            ops_semana = [op for dia, lista_ops in ordenes_por_dia.items() for op in lista_ops if op.get('estado') not in ['COMPLETADA', 'CANCELADA']]
            ops_combinadas_dict = {op['id']: op for op in ops_semana if op.get('id')}
            ordenes_combinadas = list(ops_combinadas_dict.values())
            
            ordenes_para_crp_filtradas = []
            if inicio_semana and fin_semana:
                for op in ordenes_combinadas:
                    fecha_inicio_op_str = op.get('fecha_inicio_planificada')
                    if fecha_inicio_op_str:
                        try:
                            fecha_inicio_op = date.fromisoformat(fecha_inicio_op_str)
                            if inicio_semana <= fecha_inicio_op <= fin_semana:
                                ordenes_para_crp_filtradas.append(op)
                        except ValueError:
                            pass
            
            carga_calculada = {}
            capacidad_disponible = {}
            if ordenes_para_crp_filtradas and inicio_semana and fin_semana:
                carga_calculada = self.calcular_carga_capacidad(ordenes_para_crp_filtradas)
                capacidad_disponible = self.obtener_capacidad_disponible([1, 2], inicio_semana, fin_semana)

            # Lógica de navegación de semana
            prev_week_str, next_week_str = None, None
            try:
                year, week_num_str = week_str.split('-W')
                week_num = int(week_num_str)
                current_week_start = date.fromisocalendar(int(year), week_num, 1)
                prev_week_start = current_week_start - timedelta(days=7)
                next_week_start = current_week_start + timedelta(days=7)
                prev_week_str = prev_week_start.strftime("%Y-W%V")
                next_week_str = next_week_start.strftime("%Y-W%V")
            except ValueError:
                logger.warning(f"Error parseando week_str {week_str}")

            # Datos de usuarios
            from app.controllers.usuario_controller import UsuarioController
            usuario_controller = UsuarioController()
            supervisores_resp = usuario_controller.obtener_usuarios_por_rol(['SUPERVISOR'])
            operarios_resp = usuario_controller.obtener_usuarios_por_rol(['OPERARIO'])
            supervisores = supervisores_resp.get('data', []) if supervisores_resp.get('success') else []
            operarios = operarios_resp.get('data', []) if operarios_resp.get('success') else []

            # Ensamblar el contexto para la plantilla
            context = {
                'mps_data': mps_data,
                'inicio_semana': inicio_semana.isoformat() if inicio_semana else None,
                'fin_semana': fin_semana.isoformat() if fin_semana else None,
                'semana_actual_str': week_str,
                'semana_anterior_str': prev_week_str,
                'semana_siguiente_str': next_week_str,
                'supervisores': supervisores,
                'operarios': operarios,
                'carga_crp': carga_calculada,
                'capacidad_crp': capacidad_disponible,
                'ordenes_por_dia': ordenes_por_dia,
                'is_operario': 'OPERARIO' in user_roles,
                'is_supervisor_calidad': 'SUPERVISOR_CALIDAD' in user_roles
            }
            return self.success_response(data=context)
        except Exception as e:
            logger.error(f"Error obteniendo datos para el tablero de planificación: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)
