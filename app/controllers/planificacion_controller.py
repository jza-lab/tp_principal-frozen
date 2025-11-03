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
import os # <-- Añadir
from datetime import date # <-- Asegúrate que esté
from flask import jsonify # <-- Añadir (o usar desde tu BaseController si ya lo tienes)


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
            # --- CORRECCIÓN AQUÍ ---
            # Devolver tupla explícitamente
            error_dict = self.error_response(f"Error interno al ejecutar aprobación final: {str(e)}", 500)
            return error_dict, 500
        # ----------------------

    def _ejecutar_replanificacion_simple(self, op_id: int, asignaciones: dict, usuario_id: int) -> tuple:
        """
        SOLO actualiza los campos de planificación de una OP que YA ESTÁ planificada
        (Ej: 'EN ESPERA' o 'LISTA PARA PRODUCIR').
        NO cambia el estado ni vuelve a verificar el stock.
        """
        logger.info(f"[RePlan] Ejecutando re-planificación simple para OP {op_id}...")
        try:
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
        Orquesta: Consolida, VERIFICA CAPACIDAD MULTI-DÍA,
        SI CABE EN 1 DÍA -> Aprueba.
        SI CABE EN >1 DÍA -> Devuelve CONFIRMACIÓN.
        SI NO CABE -> Devuelve SOBRECARGA.
        """
        try:
            op_a_planificar_id, op_data = self._obtener_datos_op_a_planificar(op_ids, usuario_id)

            # --- CORRECCIÓN AQUÍ ---
            if not op_a_planificar_id:
                error_dict = self.error_response(op_data, 500) # op_data tiene el mensaje de error
                return error_dict, 500
            # ----------------------

            # --- ¡VALIDACIÓN AÑADIDA! ---
            op_estado_actual = op_data.get('estado')
            estados_permitidos = ['PENDIENTE', 'EN ESPERA', 'LISTA PARA PRODUCIR']

            if op_estado_actual not in estados_permitidos:
                msg = f"La OP {op_a_planificar_id} en estado '{op_estado_actual}' no puede ser (re)planificada."
                logger.warning(msg)
                return self.error_response(msg, 400), 400

            # Si es una consolidación (len > 1), DEBE estar en PENDIENTE
            if len(op_ids) > 1 and op_estado_actual != 'PENDIENTE':
                msg = "La consolidación solo es posible para OPs en estado PENDIENTE."
                logger.warning(msg)
                return self.error_response(msg, 400), 400
            # --- FIN VALIDACIÓN AÑADIDA ---

            linea_propuesta = asignaciones.get('linea_asignada')
            fecha_inicio_propuesta_str = asignaciones.get('fecha_inicio')
            if not linea_propuesta or not fecha_inicio_propuesta_str:
             error_dict = self.error_response("Faltan línea o fecha.", 400)
             return error_dict, 400
            try: fecha_inicio_propuesta = date.fromisoformat(fecha_inicio_propuesta_str)
            except ValueError:
                 # --- CORRECCIÓN AQUÍ ---
                 error_dict = self.error_response("Formato fecha inválido.", 400)
                 return error_dict, 400
                 # ----------------------

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

                # --- MODIFICADO: Nuevas variables para rastrear el inicio real ---
                primer_dia_asignado = None
                fecha_fin_estimada = fecha_inicio_propuesta # Se actualizará al último día USADO
                # ----------------------------------------------------------------

                # --- ¡NUEVA LLAMADA AL HELPER DE SIMULACIÓN! ---
                simulacion_result = self._simular_asignacion_carga(
                    carga_total_op=carga_adicional_total,
                    linea_propuesta=linea_propuesta,
                    fecha_inicio_busqueda=fecha_inicio_propuesta,
                    op_id_a_excluir=op_a_planificar_id # Excluir la propia OP si se está replanificando
                )

                if not simulacion_result['success']:
                    # La simulación falló (Sobrecarga)
                    logger.warning(f"SOBRECARGA para OP {op_a_planificar_id}: {simulacion_result['error_data'].get('message')}")
                    # Devolvemos el diccionario de error y el status 409
                    return simulacion_result['error_data'], 409

                # Si la simulación fue exitosa, extraemos los datos
                primer_dia_asignado = simulacion_result['fecha_inicio_real']
                fecha_fin_estimada = simulacion_result['fecha_fin_estimada']
                dias_necesarios = simulacion_result['dias_necesarios']

                # --- ¡NUEVA VALIDACIÓN DE FECHA META! ---
                fecha_meta_str = op_data.get('fecha_meta')
                va_a_terminar_tarde = False
                fecha_meta = None
                if fecha_meta_str:
                    try:
                        fecha_meta = date.fromisoformat(fecha_meta_str)
                        if fecha_fin_estimada > fecha_meta:
                            va_a_terminar_tarde = True
                            logger.warning(f"Validación OP {op_a_planificar_id}: Terminará tarde (Fin: {fecha_fin_estimada}, Meta: {fecha_meta})")
                    except ValueError:
                        logger.warning(f"OP {op_a_planificar_id} tiene fecha meta inválida: {fecha_meta_str}")
                # --- FIN VALIDACIÓN ---

                # ¡IMPORTANTE! Actualizar la fecha de inicio en 'asignaciones' a la real encontrada
                asignaciones['fecha_inicio'] = primer_dia_asignado.isoformat()

                logger.info(f"Verificación CRP OK. OP {op_a_planificar_id} requiere ~{dias_necesarios} día(s).")
                logger.info(f"Inicio real: {primer_dia_asignado.isoformat()}, Fin aprox: {fecha_fin_estimada.isoformat()}.")

            # --- LÓGICA DE DECISIÓN MODIFICADA ---
            if va_a_terminar_tarde:
                # 1. Si va a terminar tarde, FORZAR confirmación (incluso si es 1 día)
                return {
                    'success': False,
                    'error': 'LATE_CONFIRM', # <-- Nuevo tipo de error
                    'message': (f"⚠️ ¡Atención! La OP terminará el <b>{fecha_fin_estimada.isoformat()}</b>, "
                                f"que es <b>después</b> de su Fecha Meta (<b>{fecha_meta_str}</b>).\n\n"
                                f"Esto se debe a la falta de capacidad en la Línea {linea_propuesta}.\n\n"
                                f"¿Desea confirmar esta planificación de todos modos?"),
                    'fecha_fin_estimada': fecha_fin_estimada.isoformat(),
                    'fecha_meta': fecha_meta_str,
                    'op_id_confirmar': op_a_planificar_id,
                    'asignaciones_confirmar': asignaciones,
                    'estado_actual': op_estado_actual
                }, 200 # Usar 200 OK para que el frontend lo maneje como confirmación

            elif dias_necesarios > 1:
                # 2. Si es multi-día PERO está a tiempo
                return {
                    'success': False,
                    'error': 'MULTI_DIA_CONFIRM',
                    'message': (f"Esta OP requiere aproximadamente {dias_necesarios} días para completarse "
                                f"(hasta {fecha_fin_estimada.isoformat()}) debido a la capacidad de la línea. "
                                f"¿Desea confirmar la planificación?"),
                    'dias_necesarios': dias_necesarios,
                    'fecha_fin_estimada': fecha_fin_estimada.isoformat(),
                    'op_id_confirmar': op_a_planificar_id,
                    'asignaciones_confirmar': asignaciones,
                    'estado_actual': op_estado_actual
                }, 200
            else:
                # 3. Cabe en un día y está a tiempo
                logger.info(f"OP cabe en un día. Decidiendo flujo por estado '{op_estado_actual}'...")
                if op_estado_actual == 'PENDIENTE':
                    # ... (lógica 'PENDIENTE' sin cambios) ...
                    logger.info("Estado es PENDIENTE. Ejecutando aprobación final...")
                    return self._ejecutar_aprobacion_final(op_a_planificar_id, asignaciones, usuario_id)
                else:
                    # ... (lógica 're-planificación' sin cambios) ...
                    logger.info(f"Estado es {op_estado_actual}. Ejecutando re-planificación simple...")
                    return self._ejecutar_replanificacion_simple(op_a_planificar_id, asignaciones, usuario_id)
            # --- FIN LÓGICA DE DECISIÓN ---

        except Exception as e:
            logger.error(f"Error crítico en consolidar_y_aprobar_lote: {e}", exc_info=True)
            # --- CORRECCIÓN AQUÍ ---
            error_dict = self.error_response(f"Error interno: {str(e)}", 500)
            return error_dict, 500
            # ----------------------


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
                    'EN_LINEA_2': ['EN_EMPAQUETADO']
                }
                if estado_actual not in allowed_transitions or nuevo_estado not in allowed_transitions[estado_actual]:
                    return self.error_response(
                        f"Movimiento de '{estado_actual}' a '{nuevo_estado}' no permitido para Operario.",
                        403
                    )


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
                # 1. Crear una "OP simulada" con la cantidad total
                op_simulada = {
                    'receta_id': receta_id_agrupada,
                    'cantidad_planificada': cantidad_total_agrupada
                }

                # 2. Calcular la carga total en minutos usando el helper de la planificación real
                carga_total_minutos_agg = float(self._calcular_carga_op(op_simulada)) #

                if carga_total_minutos_agg > 0:
                    data['sugerencia_t_prod_dias'] = math.ceil(carga_total_minutos_agg / 480) # Asumiendo 480 min/día
                else:
                    data['sugerencia_t_prod_dias'] = 0

                # 3. Obtener compatibilidad de línea y sugerir (Lógica de sugerencia de línea separada)
                receta_res = self.receta_model.find_by_id(receta_id_agrupada, 'id')
                if receta_res.get('success'):
                    receta = receta_res['data']
                    linea_compatible_str = receta.get('linea_compatible', '2')
                    data['linea_compatible'] = linea_compatible_str

                    # Lógica de sugerencia de línea (esto puede permanecer igual)
                    linea_compatible_list = linea_compatible_str.split(',')
                    # Los campos de tiempo L1/L2 ahora solo se usan para decidir la línea, no para calcular el tiempo
                    tiempo_l1 = receta.get('tiempo_prod_unidad_linea1', 0)
                    tiempo_l2 = receta.get('tiempo_prod_unidad_linea2', 0)
                    UMBRAL_CANTIDAD_LINEA_1 = 50
                    puede_l1 = '1' in linea_compatible_list and tiempo_l1 > 0
                    puede_l2 = '2' in linea_compatible_list and tiempo_l2 > 0
                    linea_sug_agg = 0
                    if puede_l1 and puede_l2:
                        linea_sug_agg = 1 if cantidad_total_agrupada >= UMBRAL_CANTIDAD_LINEA_1 else 2
                    elif puede_l1: linea_sug_agg = 1
                    elif puede_l2: linea_sug_agg = 2

                    data['sugerencia_linea'] = linea_sug_agg if linea_sug_agg > 0 else None

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
    def obtener_planificacion_semanal(self, week_str: Optional[str] = None, ordenes_pre_cargadas: Optional[List[Dict]] = None) -> tuple:
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

            if ordenes_pre_cargadas is not None:
                # Usar la lista pre-cargada si se proveyó
                ordenes_relevantes = ordenes_pre_cargadas
                logger.debug("obtener_planificacion_semanal: Usando lista de OPs pre-cargada.")
            else:
                # Bloque de fallback: si no se pasa lista, buscarla como antes
                logger.debug("obtener_planificacion_semanal: No se pasó lista pre-cargada, buscando OPs...")
                dias_previos_margen = 14 # Traer OPs que empezaron hasta 2 semanas antes
                fecha_inicio_filtro = start_of_week - timedelta(days=dias_previos_margen)

                filtros_amplios = {
                    'fecha_inicio_planificada_desde': fecha_inicio_filtro.isoformat(),
                    'fecha_inicio_planificada_hasta': end_of_week.isoformat(),
                    'estado': ('in', [
                        'EN ESPERA',
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
            for i in range(7):
                dia_semana_actual = start_of_week + timedelta(days=i)
                ops_visibles_por_dia[dia_semana_actual.isoformat()] = []
            for op in ops_con_dias_ocupados:
                for fecha_ocupada_iso in op.get('dias_ocupados_calculados', []):
                    if start_of_week.isoformat() <= fecha_ocupada_iso <= end_of_week.isoformat():
                        if op not in ops_visibles_por_dia[fecha_ocupada_iso]:
                             ops_visibles_por_dia[fecha_ocupada_iso].append(op)

            # --- CORRECCIÓN: MAPEO MANUAL DE DÍAS ---
            # 6. Formatear claves con nombre del día (Usando mapeo manual)

##            # Diccionario para traducir abreviaturas de días (inglés -> español)
##            dias_abbr_es = {
##                'Mon': 'Lun', 'Tue': 'Mar', 'Wed': 'Mié',
##                'Thu': 'Jue', 'Fri': 'Vie', 'Sat': 'Sáb', 'Sun': 'Dom'
##            }
##
##            formatted_grouped_by_day = {}
##            ordered_ops_visibles = dict(sorted(ops_visibles_por_dia.items()))
##            for dia_iso, ops_dia in ordered_ops_visibles.items():
##                try:
##                    dia_dt = date.fromisoformat(dia_iso)
##                    # Obtener abreviatura en INGLÉS (%a)
##                    abbr_en = dia_dt.strftime("%a")
##                    # Traducir usando el diccionario (default a inglés si falla)
##                    abbr_es = dias_abbr_es.get(abbr_en, abbr_en)
##                    # Formatear fecha (DD/MM)
##                    fecha_num = dia_dt.strftime("%d/%m")
##                    # Crear clave final
##                    key_display = f"{abbr_es} {fecha_num}"
##                except ValueError:
##                    key_display = dia_iso # Fallback
##                formatted_grouped_by_day[key_display] = ops_dia
##            # --- FIN CORRECCIÓN ---

            resultado = {
                'ops_visibles_por_dia': ops_visibles_por_dia, # Usar el diccionario formateado
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

    def _ejecutar_planificacion_automatica(self, usuario_id: int, dias_horizonte: int = 1) -> dict:
        """
        Lógica central para la planificación automática.
        Intenta planificar OPs PENDIENTES en el horizonte dado.
        """
        dias_horizonte = 30

        logger.info(f"[AutoPlan] Iniciando ejecución para {dias_horizonte} día(s). Usuario: {usuario_id}")

        # 1. Obtener OPs agrupadas (las que están 'PENDIENTE')
        res_ops_pendientes, _ = self.obtener_ops_pendientes_planificacion(dias_horizonte)
        if not res_ops_pendientes.get('success'):
            logger.error("[AutoPlan] Fallo al obtener OPs pendientes.")
            return {'errores': ['No se pudieron obtener OPs pendientes.']}

        grupos_a_planificar = res_ops_pendientes.get('data', {}).get('mps_agrupado', [])
        if not grupos_a_planificar:
            logger.info("[AutoPlan] No se encontraron OPs pendientes en el horizonte.")
            return {'ops_planificadas': [], 'ops_con_oc': [], 'errores': []}

        # 2. Definir contadores para el resumen
        ops_planificadas_exitosamente = []
        ops_con_oc_generada = []
        errores_encontrados = []

        fecha_planificacion_str = date.today().isoformat()

        # 3. Iterar sobre cada grupo de producto
        for grupo in grupos_a_planificar:
            op_ids = [op['id'] for op in grupo['ordenes']]
            op_codigos = [op['codigo'] for op in grupo['ordenes']]
            producto_nombre = grupo.get('producto_nombre', 'N/A')

            try:
                # 4. Determinar asignaciones automáticas
                linea_sugerida = grupo.get('sugerencia_linea')
                if not linea_sugerida:
                    msg = f"Grupo {producto_nombre} (OPs: {op_codigos}) omitido: No hay línea sugerida."
                    logger.warning(f"[AutoPlan] {msg}")
                    errores_encontrados.append(msg)
                    continue

                asignaciones_auto = {
                    'linea_asignada': linea_sugerida,
                    'fecha_inicio': fecha_planificacion_str,
                    'supervisor_id': None, # El supervisor asignará esto manualmente
                    'operario_id': None
                }

                logger.info(f"[AutoPlan] Intentando planificar OPs {op_codigos} en Línea {linea_sugerida} para {fecha_planificacion_str}...")

                # 5. Llamar a la lógica de consolidación y aprobación existente
                # Esta función ya maneja la consolidación, verificación de CAPACIDAD
                # y (si pasa) la aprobación (que a su vez verifica STOCK y crea OC)
                res_planif_dict, res_planif_status = self.consolidar_y_aprobar_lote(
                    op_ids, asignaciones_auto, usuario_id
                )

                # 6. Interpretar la respuesta
                if res_planif_status == 200 and res_planif_dict.get('success'):
                    # ¡Éxito! La OP se planificó
                    logger.info(f"[AutoPlan] ÉXITO: OPs {op_codigos} planificadas.")
                    ops_planificadas_exitosamente.extend(op_codigos)

                    # Verificar si se generó una OC (respuesta de aprobar_orden)
                    if res_planif_dict.get('data', {}).get('oc_generada'):
                        oc_codigo = res_planif_dict['data'].get('oc_codigo', 'N/A')
                        logger.info(f"[AutoPlan] -> Se generó OC {oc_codigo} para OPs {op_codigos}.")
                        ops_con_oc_generada.append({'ops': op_codigos, 'oc': oc_codigo})

                elif res_planif_dict.get('error') == 'MULTI_DIA_CONFIRM':
                    # --- ¡NUEVA LÓGICA DE APROBACIÓN AUTOMÁTICA MULTI-DÍA! ---
                    dias_nec = res_planif_dict.get('dias_necesarios', 'varios')
                    logger.info(f"[AutoPlan] OP {op_codigos} requiere {dias_nec} días. Aprobando automáticamente...")

                    # Extraer los datos necesarios que la función de confirmación nos devolvió
                    op_id_para_confirmar = res_planif_dict.get('op_id_confirmar')
                    asignaciones_para_confirmar = res_planif_dict.get('asignaciones_confirmar')

                    if not op_id_para_confirmar or not asignaciones_para_confirmar:
                        msg = f"Grupo {producto_nombre} (OPs: {op_codigos}) es multi-día pero faltan datos para auto-confirmar."
                        logger.error(f"[AutoPlan] {msg}")
                        errores_encontrados.append(msg)
                        continue # Saltar al siguiente grupo

                    try:
                        # Llamar a la misma función que usaría el flujo manual al confirmar
                        # Esta función ya existe: _ejecutar_aprobacion_final
                        res_aprob_dict, status_aprob = self._ejecutar_aprobacion_final(
                            op_id_para_confirmar,
                            asignaciones_para_confirmar,
                            usuario_id
                        )

                        # Interpretar la respuesta de la aprobación final
                        if status_aprob < 400 and res_aprob_dict.get('success'):
                            logger.info(f"[AutoPlan] ÉXITO (Multi-Día): OPs {op_codigos} planificadas.")
                            # Usamos op_codigos que son los códigos de las OPs originales
                            # que se consolidaron en op_id_para_confirmar
                            ops_planificadas_exitosamente.extend(op_codigos)

                            # Re-chequear si esta aprobación generó una OC
                            # (La función aprobar_orden dentro de _ejecutar_aprobacion_final maneja esto)
                            if res_aprob_dict.get('data', {}).get('oc_generada'):
                                oc_codigo = res_aprob_dict['data'].get('oc_codigo', 'N/A')
                                logger.info(f"[AutoPlan] -> Se generó OC {oc_codigo} para OPs {op_codigos}.")
                                ops_con_oc_generada.append({'ops': op_codigos, 'oc': oc_codigo})
                        else:
                            # La aprobación final falló (ej. error de stock crítico en el último minuto)
                            msg = f"Grupo {producto_nombre} (OPs: {op_codigos}) falló en la aprobación final multi-día: {res_aprob_dict.get('error', 'Error desconocido')}"
                            logger.error(f"[AutoPlan] {msg}")
                            errores_encontrados.append(msg)

                    except Exception as e_aprob:
                        msg = f"Excepción crítica al auto-aprobar OPs {op_codigos}: {str(e_aprob)}"
                        logger.error(f"[AutoPlan] {msg}", exc_info=True)
                        errores_encontrados.append(msg)
                    # --- FIN NUEVA LÓGICA ---
                # --- ¡NUEVO BLOQUE AÑADIDO! ---
                elif res_planif_dict.get('error') == 'LATE_CONFIRM':
                    # La auto-planificación NO debe aprobar OPs que terminan tarde.
                    msg = f"Grupo {producto_nombre} (OPs: {op_codigos}) NO SE PLANIFICÓ: Terminaría después de su Fecha Meta. Requiere revisión manual."
                    logger.warning(f"[AutoPlan] {msg}")
                    errores_encontrados.append(msg)
                # --- FIN NUEVO BLOQUE ---

                elif res_planif_dict.get('error') == 'SOBRECARGA_CAPACIDAD':
                    # Error de capacidad
                    msg = f"Grupo {producto_nombre} (OPs: {op_codigos}) falló por SOBRECARGA de capacidad."
                    logger.warning(f"[AutoPlan] {msg}")
                    errores_encontrados.append(f"{msg} - {res_planif_dict.get('message', '')}")

                else:
                    # Otro error (ej. fallo al reservar stock, etc.)
                    msg = f"Grupo {producto_nombre} (OPs: {op_codigos}) falló: {res_planif_dict.get('error', 'Desconocido')}"
                    logger.error(f"[AutoPlan] {msg}")
                    errores_encontrados.append(msg)

            except Exception as e:
                msg = f"Excepción crítica al procesar OPs {op_codigos}: {str(e)}"
                logger.error(f"[AutoPlan] {msg}", exc_info=True)
                errores_encontrados.append(msg)

        # 7. Devolver el resumen
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


    def _simular_asignacion_carga(self, carga_total_op: float, linea_propuesta: int, fecha_inicio_busqueda: date, op_id_a_excluir: Optional[int] = None) -> dict:
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
            capacidad_dia_actual = capacidad_dict_dia.get(linea_propuesta, {}).get(fecha_actual_str, 0.0)

            if capacidad_dia_actual <= 0:
                fecha_actual_simulacion += timedelta(days=1)
                dia_actual_offset += 1
                continue # Saltar día no laborable

            # Obtener carga existente
            ops_existentes_resultado = self.orden_produccion_controller.obtener_ordenes(filtros={
                'fecha_inicio_planificada': fecha_actual_str,
                'linea_asignada': linea_propuesta,
                'estado': ('not.in', ['PENDIENTE', 'COMPLETADA', 'CANCELADA', 'CONSOLIDADA'])
            })
            carga_existente_dia = 0.0
            if isinstance(ops_existentes_resultado, tuple) and len(ops_existentes_resultado) == 2:
                ops_existentes_resp, _ = ops_existentes_resultado
                if ops_existentes_resp.get('success'):
                    # Excluir la OP que estamos replanificando (si aplica)
                    ops_mismo_dia = [op for op in ops_existentes_resp.get('data', []) if op.get('id') != op_id_a_excluir]
                    if ops_mismo_dia:
                        carga_existente_dict = self.calcular_carga_capacidad(ops_mismo_dia)
                        carga_existente_dia = carga_existente_dict.get(linea_propuesta, {}).get(fecha_actual_str, 0.0)

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
                    op_id_a_excluir=None # Es un pedido nuevo, no hay OP para excluir
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