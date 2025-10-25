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
        self.receta_model = RecetaModel() # Asegúrate que esté inicializado
        self.insumo_model = InsumoModel() # Asegúrate que esté inicializado

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
            return self.error_response(f"Error interno al ejecutar aprobación final: {str(e)}", 500)

    # --- MÉTODO PRINCIPAL MODIFICADO ---
    def consolidar_y_aprobar_lote(self, op_ids: List[int], asignaciones: dict, usuario_id: int) -> tuple:
        """
        Orquesta: Consolida, VERIFICA CAPACIDAD MULTI-DÍA,
        SI CABE EN 1 DÍA -> Aprueba.
        SI CABE EN >1 DÍA -> Devuelve CONFIRMACIÓN.
        SI NO CABE -> Devuelve SOBRECARGA.
        """
        try:
            op_a_planificar_id, op_data = self._obtener_datos_op_a_planificar(op_ids, usuario_id)
            if not op_a_planificar_id: return self.error_response(op_data, 500) # op_data tiene el error si falló

            linea_propuesta = asignaciones.get('linea_asignada')
            fecha_inicio_propuesta_str = asignaciones.get('fecha_inicio')
            if not linea_propuesta or not fecha_inicio_propuesta_str: return self.error_response("Faltan línea o fecha.", 400)
            try: fecha_inicio_propuesta = date.fromisoformat(fecha_inicio_propuesta_str)
            except ValueError: return self.error_response("Formato fecha inválido.", 400)

            logger.info(f"Verificando capacidad multi-día para OP {op_a_planificar_id} en Línea {linea_propuesta} desde {fecha_inicio_propuesta_str}...")

            carga_adicional_total = float(self._calcular_carga_op(op_data))
            dias_necesarios = 0
            fecha_fin_estimada = fecha_inicio_propuesta

            if carga_adicional_total <= 0:
                 logger.warning(f"OP {op_a_planificar_id} con carga 0. Saltando verificación CRP.")
                 dias_necesarios = 1
                 fecha_fin_estimada = fecha_inicio_propuesta
            else:
                carga_restante_op = carga_adicional_total
                fecha_actual_simulacion = fecha_inicio_propuesta
                dia_actual_offset = 0
                max_dias_simulacion = 30

                while carga_restante_op > 0.01 and dia_actual_offset < max_dias_simulacion:
                    fecha_actual_str = fecha_actual_simulacion.isoformat()
                    dias_necesarios += 1
                    fecha_fin_estimada = fecha_actual_simulacion

                    capacidad_dict_dia = self.obtener_capacidad_disponible([linea_propuesta], fecha_actual_simulacion, fecha_actual_simulacion)
                    capacidad_dia_actual = capacidad_dict_dia.get(linea_propuesta, {}).get(fecha_actual_str, 0.0)

                    if capacidad_dia_actual <= 0 and carga_restante_op > 0.01:
                         logger.warning(f"SOBRECARGA (Día sin capacidad): Línea {linea_propuesta}, Fecha: {fecha_actual_str}")
                         return self._generar_respuesta_sobrecarga(linea_propuesta, fecha_actual_str, 0, carga_restante_op, 0)

                    # Obtener carga existente (manejo seguro de respuesta)
                    ops_existentes_resultado = self.orden_produccion_controller.obtener_ordenes(filtros={
                        'fecha_inicio_planificada': fecha_actual_str,
                        'linea_asignada': linea_propuesta,
                        'estado': ('not.in', ['PENDIENTE', 'COMPLETADA', 'CANCELADA', 'CONSOLIDADA'])
                    })
                    carga_existente_dia = 0.0
                    if isinstance(ops_existentes_resultado, tuple) and len(ops_existentes_resultado) == 2:
                        ops_existentes_resp, _ = ops_existentes_resultado
                        if ops_existentes_resp.get('success'):
                            ops_mismo_dia = [op for op in ops_existentes_resp.get('data', []) if op.get('id') != op_a_planificar_id]
                            if ops_mismo_dia:
                                carga_existente_dict = self.calcular_carga_capacidad(ops_mismo_dia)
                                carga_existente_dia = carga_existente_dict.get(linea_propuesta, {}).get(fecha_actual_str, 0.0)
                    else: logger.error(f"Error inesperado al obtener OPs existentes para {fecha_actual_str}: {ops_existentes_resultado}")
                    logger.debug(f"    Carga existente: {carga_existente_dia:.2f} min")


                    capacidad_restante_dia = max(0.0, capacidad_dia_actual - carga_existente_dia)
                    logger.debug(f"    Capacidad restante día: {capacidad_restante_dia:.2f} min")


                    if capacidad_restante_dia < 1 and carga_restante_op > 0.01:
                        logger.warning(f"SOBRECARGA (Día ya lleno): Línea {linea_propuesta}, Fecha: {fecha_actual_str}.")
                        return self._generar_respuesta_sobrecarga(linea_propuesta, fecha_actual_str, capacidad_dia_actual, carga_restante_op, carga_existente_dia)

                    carga_a_asignar_hoy = min(carga_restante_op, capacidad_restante_dia)

                    if carga_a_asignar_hoy > 0:
                        carga_restante_op -= carga_a_asignar_hoy
                        logger.debug(f"  -> Asignado {carga_a_asignar_hoy:.2f} min a {fecha_actual_str}. Restante OP: {carga_restante_op:.2f} min")

                    fecha_actual_simulacion += timedelta(days=1)
                    dia_actual_offset += 1

                if carga_restante_op > 0.01: # No cupo en el horizonte
                    logger.warning(f"SOBRECARGA (Horizonte excedido)")
                    return self._generar_respuesta_sobrecarga(linea_propuesta, fecha_fin_estimada.isoformat(), 0, carga_restante_op, 0, horizonte_excedido=True)

            logger.info(f"Verificación CRP OK. OP {op_a_planificar_id} requiere ~{dias_necesarios} día(s), finalizando aprox. {fecha_fin_estimada.isoformat()}.")

            if dias_necesarios > 1:
                # Devolver respuesta para confirmación del usuario
                return {
                    'success': False, # No es un éxito final aún
                    'error': 'MULTI_DIA_CONFIRM',
                    'message': (f"Esta OP requiere aproximadamente {dias_necesarios} días para completarse "
                                f"(hasta {fecha_fin_estimada.isoformat()}) debido a la capacidad de la línea. "
                                f"¿Desea confirmar la planificación?"),
                    'dias_necesarios': dias_necesarios,
                    'fecha_fin_estimada': fecha_fin_estimada.isoformat(),
                    'op_id_confirmar': op_a_planificar_id,
                    # Pasar las asignaciones originales para la confirmación
                    'asignaciones_confirmar': asignaciones
                }, 200 # Usamos 200 OK para indicar solicitud de confirmación
            else:
                # Cabe en un día, aprobar directamente usando el helper
                logger.info("OP cabe en un día. Ejecutando aprobación final...")
                # Pasar las asignaciones originales al helper
                return self._ejecutar_aprobacion_final(op_a_planificar_id, asignaciones, usuario_id)

        except Exception as e:
            logger.error(f"Error crítico en consolidar_y_aprobar_lote: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)


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

    # --- NUEVO HELPER para calcular carga de una OP ---
    def _calcular_carga_op(self, op_data: Dict) -> Decimal:
        """ Calcula la carga total en minutos para una OP dada. """
        carga_total = Decimal(0)
        receta_id = op_data.get('receta_id')
        cantidad = Decimal(op_data.get('cantidad_planificada', 0))
        if not receta_id or cantidad <= 0: return carga_total

        operaciones = self.obtener_operaciones_receta(receta_id)
        if not operaciones: return carga_total

        for op_step in operaciones:
            t_prep = Decimal(op_step.get('tiempo_preparacion', 0))
            t_ejec_unit = Decimal(op_step.get('tiempo_ejecucion_unitario', 0))
            carga_total += t_prep + (t_ejec_unit * cantidad)
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


    # --- MÉTODO REESCRITO ---
    def obtener_planificacion_semanal(self, week_str: Optional[str] = None) -> tuple:
        """
        Obtiene las OPs planificadas para una semana específica, calculando los días
        que cada OP ocupa y agrupándolas por día visible.
        """
        try:
            # Configurar locale (sin cambios)
            try: locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
            except locale.Error:
                try: locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')
                except locale.Error: logger.warning("Locale español no disponible.")

            # 1. Determinar rango de la semana (sin cambios)
            if week_str:
                try:
                    year, week_num = map(int, week_str.split('-W'))
                    start_of_week = date.fromisocalendar(year, week_num, 1)
                except ValueError: return self.error_response("Formato semana inválido.", 400)
            else:
                today = date.today(); start_of_week = today - timedelta(days=today.weekday())
                week_str = start_of_week.strftime("%Y-%W") # Corregido a %W si %V daba error antes
            end_of_week = start_of_week + timedelta(days=6)

            # 2. Obtener OPs RELEVANTES (que podrían estar activas en la semana)
            #   - Que NO estén completadas/canceladas/consolidadas/pendientes
            #   - Que empiecen ANTES del FIN de la semana
            #   - (Opcional: añadir filtro para que terminen DESPUÉS del INICIO de la semana si tienes fecha_fin_estimada)
            dias_previos_margen = 14 # Traer OPs que empezaron hasta 2 semanas antes, por si son largas
            fecha_inicio_filtro = start_of_week - timedelta(days=dias_previos_margen)

            filtros_amplios = {
                'fecha_inicio_planificada_desde': fecha_inicio_filtro.isoformat(),
                'fecha_inicio_planificada_hasta': end_of_week.isoformat(), # Solo necesitamos las que empiezan hasta el final de la semana
                'estado': ('in', [ # Solo las activas en producción
                    'EN ESPERA', # Podría cambiar a Lista si llega stock
                    'LISTA PARA PRODUCIR',
                    'EN_LINEA_1',
                    'EN_LINEA_2',
                    'EN_EMPAQUETADO',
                    'CONTROL_DE_CALIDAD'
                 ])
            }
            response_ops, _ = self.orden_produccion_controller.obtener_ordenes(filtros_amplios)
            if not response_ops.get('success'):
                return self.error_response("Error al obtener OPs para cálculo semanal.", 500)

            ordenes_relevantes = response_ops.get('data', [])
            if not ordenes_relevantes: # Si no hay OPs, devolver vacío
                 resultado_vacio = { 'ops_visibles_por_dia': {}, 'inicio_semana': start_of_week.isoformat(), 'fin_semana': end_of_week.isoformat(), 'semana_actual_str': week_str }
                 return self.success_response(data=resultado_vacio)


            # 3. Obtener Capacidad para el rango necesario (desde la OP más temprana hasta el fin de semana)
            fechas_inicio_ops = [date.fromisoformat(op['fecha_inicio_planificada']) for op in ordenes_relevantes if op.get('fecha_inicio_planificada')]
            fecha_min_calculo = min(fechas_inicio_ops) if fechas_inicio_ops else start_of_week
            # Ampliar rango final por si OPs terminan después
            fecha_max_calculo = end_of_week + timedelta(days=14)

            capacidad_rango = self.obtener_capacidad_disponible([1, 2], fecha_min_calculo, fecha_max_calculo)

            # 4. Simular duración y días ocupados para CADA OP
            ops_con_dias_ocupados = []
            carga_acumulada_simulacion = {1: defaultdict(float), 2: defaultdict(float)} # Para simular carga existente

            # Ordenar para procesar las más antiguas primero (más realista)
            ordenes_relevantes.sort(key=lambda op: op.get('fecha_inicio_planificada', '9999-12-31'))

            for orden in ordenes_relevantes:
                op_id = orden.get('id')
                linea_asignada = orden.get('linea_asignada')
                fecha_inicio_str = orden.get('fecha_inicio_planificada')

                if not linea_asignada or not fecha_inicio_str: continue # Saltar si faltan datos clave

                try:
                    fecha_inicio_op = date.fromisoformat(fecha_inicio_str)
                    carga_total_op = float(self._calcular_carga_op(orden))
                    if carga_total_op <= 0: continue

                    dias_ocupados_por_esta_op = []
                    carga_restante_sim = carga_total_op
                    fecha_actual_sim = fecha_inicio_op
                    dias_simulados = 0
                    max_dias_op_sim = 30 # Límite

                    while carga_restante_sim > 0.01 and dias_simulados < max_dias_op_sim:
                        fecha_actual_sim_str = fecha_actual_sim.isoformat()
                        cap_dia = capacidad_rango.get(linea_asignada, {}).get(fecha_actual_sim_str, 0.0)
                        carga_existente_sim = carga_acumulada_simulacion[linea_asignada].get(fecha_actual_sim_str, 0.0)
                        cap_restante_sim = max(0.0, cap_dia - carga_existente_sim)

                        carga_a_asignar_sim = min(carga_restante_sim, cap_restante_sim)

                        if carga_a_asignar_sim > 0:
                            dias_ocupados_por_esta_op.append(fecha_actual_sim_str) # Añadir fecha a la lista de la OP
                            carga_acumulada_simulacion[linea_asignada][fecha_actual_sim_str] += carga_a_asignar_sim
                            carga_restante_sim -= carga_a_asignar_sim

                        # Si aún queda carga, pasar al siguiente día
                        if carga_restante_sim > 0.01:
                             fecha_actual_sim += timedelta(days=1)
                        dias_simulados += 1

                    # Guardar la OP junto con los días que ocupa
                    orden['dias_ocupados_calculados'] = dias_ocupados_por_esta_op
                    ops_con_dias_ocupados.append(orden)

                except Exception as e_sim:
                     logger.error(f"Error simulando OP {op_id}: {e_sim}", exc_info=True)


            # 5. Construir el diccionario final para la plantilla
            ops_visibles_por_dia = defaultdict(list)
            # Crear entradas para todos los días de la semana objetivo
            for i in range(7):
                dia_semana_actual = start_of_week + timedelta(days=i)
                ops_visibles_por_dia[dia_semana_actual.isoformat()] = []

            # Llenar con las OPs correspondientes
            for op in ops_con_dias_ocupados:
                for fecha_ocupada_iso in op.get('dias_ocupados_calculados', []):
                    # Solo añadir si la fecha ocupada está DENTRO de la semana que estamos mostrando
                    if start_of_week.isoformat() <= fecha_ocupada_iso <= end_of_week.isoformat():
                        # Evitar duplicados si una OP ya fue añadida a ese día
                        if op not in ops_visibles_por_dia[fecha_ocupada_iso]:
                             ops_visibles_por_dia[fecha_ocupada_iso].append(op)


            # 6. Formatear claves con nombre del día (sin cambios)
            formatted_grouped_by_day = {}
            # Ordenar por fecha antes de formatear
            ordered_ops_visibles = dict(sorted(ops_visibles_por_dia.items()))
            for dia_iso, ops_dia in ordered_ops_visibles.items():
                try:
                    dia_dt = date.fromisoformat(dia_iso)
                    key_display = dia_dt.strftime("%a %d/%m").capitalize()
                except ValueError: key_display = dia_iso
                formatted_grouped_by_day[key_display] = ops_dia

            resultado = {
                'ops_visibles_por_dia': formatted_grouped_by_day, # <-- Nuevo nombre de variable
                'inicio_semana': start_of_week.isoformat(),
                'fin_semana': end_of_week.isoformat(),
                'semana_actual_str': week_str
            }
            return self.success_response(data=resultado)

        except Exception as e:
            logger.error(f"Error obteniendo planificación semanal (v2): {e}", exc_info=True)
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
                carga_total_op = float(self._calcular_carga_op(orden)) # Usar helper que calcula carga total
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
