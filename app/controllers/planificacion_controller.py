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
            op_a_planificar_id, op_data = self._obtener_datos_op_a_planificar(op_ids, usuario_id)

            if not op_data:
                return self.error_response(op_a_planificar_id, 500) # op_a_planificar_id tiene el msg de error

            op_estado_actual = op_data.get('estado')
            estados_permitidos = ['PENDIENTE', 'EN ESPERA', 'LISTA PARA PRODUCIR']

            if op_estado_actual not in estados_permitidos:
                msg = f"La OP {op_a_planificar_id} en estado '{op_estado_actual}' no puede ser (re)planificada."
                logger.warning(msg)
                return self.error_response(msg, 400)

            if isinstance(op_a_planificar_id, list) and len(op_a_planificar_id) > 1 and op_estado_actual != 'PENDIENTE':
                 msg = "La consolidación solo es posible para OPs en estado PENDIENTE."
                 logger.warning(msg)
                 return self.error_response(msg, 400)

            linea_propuesta = asignaciones.get('linea_asignada')
            fecha_inicio_propuesta_str = asignaciones.get('fecha_inicio')
            if not linea_propuesta or not fecha_inicio_propuesta_str:
                 return self.error_response("Faltan línea o fecha.", 400)
            try: fecha_inicio_propuesta = date.fromisoformat(fecha_inicio_propuesta_str)
            except ValueError:
                 return self.error_response("Formato fecha inválido.", 400)

            id_a_excluir_en_sim = op_a_planificar_id if isinstance(op_a_planificar_id, int) else None

            logger.info(f"Verificando capacidad multi-día para OP(s) {op_a_planificar_id} en Línea {linea_propuesta} desde {fecha_inicio_propuesta_str}...")

            carga_adicional_total = float(self._calcular_carga_op(op_data))

            if carga_adicional_total <= 0:
                 logger.warning(f"OP(s) {op_a_planificar_id} con carga 0. Saltando verificación CRP.")
                 dias_necesarios = 1
                 fecha_fin_estimada = fecha_inicio_propuesta
                 primer_dia_asignado = fecha_inicio_propuesta
            else:
                filtros_ops = {
                    'estado': ('in', [
                        'EN ESPERA', 'LISTA PARA PRODUCIR', 'EN_LINEA_1',
                        'EN_LINEA_2', 'EN_EMPAQUETADO', 'CONTROL_DE_CALIDAD'
                    ]),
                }
                if id_a_excluir_en_sim:
                    filtros_ops['id'] = ('not.in', [id_a_excluir_en_sim])

                ops_resp, _ = self.orden_produccion_controller.obtener_ordenes(filtros_ops)
                ops_actuales = ops_resp.get('data', []) if ops_resp.get('success') else []
                logger.info(f"[consolidar_lote] Calculando carga actual basada en {len(ops_actuales)} OPs (excluyendo {id_a_excluir_en_sim})...")
                carga_actual_map = self.calcular_carga_capacidad(ops_actuales)

                simulacion_result = self._simular_asignacion_carga(
                    carga_total_op=carga_adicional_total,
                    linea_propuesta=linea_propuesta,
                    fecha_inicio_busqueda=fecha_inicio_propuesta,
                    op_id_a_excluir=id_a_excluir_en_sim,
                    carga_actual_map=carga_actual_map
                )

                if not simulacion_result['success']:
                    logger.warning(f"SOBRECARGA para OP(s) {op_a_planificar_id}: {simulacion_result['error_data'].get('message')}")
                    # Devolvemos el diccionario de error y el status 409
                    return simulacion_result['error_data'], 409

                primer_dia_asignado = simulacion_result['fecha_inicio_real']
                fecha_fin_estimada = simulacion_result['fecha_fin_estimada']
                dias_necesarios = simulacion_result['dias_necesarios']

                fecha_meta_str = op_data.get('fecha_meta')
                va_a_terminar_tarde = False
                fecha_meta = None
                if fecha_meta_str:
                    try:
                        fecha_meta_solo_str = fecha_meta_str.split('T')[0].split(' ')[0]
                        fecha_meta = date.fromisoformat(fecha_meta_solo_str)
                        if fecha_fin_estimada > fecha_meta:
                            va_a_terminar_tarde = True
                            logger.warning(f"Validación OP {op_a_planificar_id}: Terminará tarde (Fin: {fecha_fin_estimada}, Meta: {fecha_meta})")
                    except ValueError:
                         logger.warning(f"OP {op_a_planificar_id} tiene fecha meta inválida: {fecha_meta_str}")

            asignaciones['fecha_inicio'] = primer_dia_asignado.isoformat()

            id_para_confirmar = op_a_planificar_id

            logger.info(f"Verificación CRP OK. OP(s) {op_a_planificar_id} requiere ~{dias_necesarios} día(s).")
            logger.info(f"Inicio real: {primer_dia_asignado.isoformat()}, Fin aprox: {fecha_fin_estimada.isoformat()}.")

            if va_a_terminar_tarde:
                # 1. Si va a terminar tarde
                # (Devolver 200 OK para que el frontend/auto-planner lo maneje)
                return {
                    'success': False,
                    'error': 'LATE_CONFIRM',
                    'title': '⚠️ CONFIRMAR RETRASO:', # <-- TÍTULO AÑADIDO
                    'message': (f"⚠️ ¡Atención! La OP terminará el <b>{fecha_fin_estimada.isoformat()}</b>, "
                                f"que es <b>después</b> de su Fecha Meta (<b>{fecha_meta_str}</b>).\n\n"
                                f"¿Desea confirmar esta planificación de todos modos?"),
                    'fecha_fin_estimada': fecha_fin_estimada.isoformat(),
                    'fecha_meta': fecha_meta_str,
                    'op_id_confirmar': id_para_confirmar,
                    'asignaciones_confirmar': asignaciones,
                    'estado_actual': op_estado_actual
                }, 200

            elif dias_necesarios > 1:
                # 2. Si es multi-día PERO está a tiempo
                return {
                    'success': False,
                    'error': 'MULTI_DIA_CONFIRM',
                    'title': 'CONFIRMAR LOTE MULTI-DÍA:',
                    'message': (f"Esta OP requiere aproximadamente {dias_necesarios} días para completarse "
                                f"(hasta {fecha_fin_estimada.isoformat()}). "
                                f"¿Desea confirmar la planificación?"),
                    'dias_necesarios': dias_necesarios,
                    'fecha_fin_estimada': fecha_fin_estimada.isoformat(),
                    'op_id_confirmar': id_para_confirmar,
                    'asignaciones_confirmar': asignaciones,
                    'estado_actual': op_estado_actual
                }, 200
            else:
                # 3. Cabe en un día y está a tiempo
                logger.info(f"OP(s) {op_a_planificar_id} cabe en un día y está a tiempo. Simulación OK.")
                return {
                   'success': True,
                   'error': None,
                   'message': "Simulación OK. Lista para aprobación final.",
                   'op_id_confirmar': id_para_confirmar,
                   'asignaciones_confirmar': asignaciones,
                   'estado_actual': op_estado_actual
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

    # --- NUEVO HELPER para calcular carga de una OP (CON LOGGING CORREGIDO) ---
    def _calcular_carga_op(self, op_data: Dict) -> Decimal:
        """ Calcula la carga total en minutos para una OP dada. """
        carga_total = Decimal(0)
        receta_id = op_data.get('receta_id')
        cantidad = Decimal(op_data.get('cantidad_planificada', 0))
        op_id = op_data.get('id', 'N/A') # Para trazar la OP

        if not receta_id or cantidad <= 0:
            logger.warning(f"[Carga OP {op_id}] Carga 0.0 (No hay receta_id o cantidad es 0).")
            return carga_total

        # --- INICIO DE LA CORRECCIÓN ---
        # El nombre correcto es con 'r' minúscula
        operaciones = self.obtener_operaciones_receta(receta_id)
        # --- FIN DE LA CORRECCIÓN ---

        if not operaciones:
            logger.warning(f"[Carga OP {op_id}] Carga 0.0 (Receta {receta_id} no tiene operaciones).")
            return carga_total

        logger.info(f"--- Calculando Carga para OP {op_id} (Receta: {receta_id}, Cant: {cantidad}) ---")

        for op_step in operaciones:

            # --- INICIO DEL LOG ---
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
            # --- FIN DEL LOG ---

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

    def obtener_ops_pendientes_planificacion(self, dias_horizonte: int = 7) -> tuple:
        """
        Obtiene OPs PENDIENTES, agrupa, calcula sugerencias Y AÑADE unidad_medida y linea_compatible.
        --- CORREGIDO (v_capacidad_real) ---
        La sugerencia de días ahora usa la capacidad neta de la línea (considerando
        eficiencia y utilización) en lugar de un valor estático de 480.
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


            # 3. Calcular sugerencia agregada (T_Prod, Línea, T_Proc, Stock)
            for grupo_key, data in mps_agrupado.items():
                cantidad_total_agrupada = data['cantidad_total']
                receta_id_agrupada = data['receta_id']

                # Inicializar valores de sugerencia
                data['sugerencia_t_prod_dias'] = 0
                data['sugerencia_linea'] = None
                data['sugerencia_t_proc_dias'] = 0
                data['sugerencia_stock_ok'] = False
                data['sugerencia_insumos_faltantes'] = []
                data['linea_compatible'] = None

                if not receta_id_agrupada: continue

                # a) Calcular Carga Total (Minutos)
                op_simulada = {
                    'receta_id': receta_id_agrupada,
                    'cantidad_planificada': cantidad_total_agrupada
                }
                carga_total_minutos_agg = Decimal(self._calcular_carga_op(op_simulada))

                # --- INICIO DE LA LÓGICA CORREGIDA ---

                # b) Calcular Línea Sugerida PRIMERO
                receta_res = self.receta_model.find_by_id(receta_id_agrupada, 'id')
                linea_sug_agg = None
                # Usamos 480 como fallback MUY defensivo
                capacidad_neta_linea_sugerida = Decimal(480.0)

                if receta_res.get('success'):
                    receta = receta_res['data']
                    linea_compatible_str = receta.get('linea_compatible', '2')
                    data['linea_compatible'] = linea_compatible_str
                    linea_compatible_list = linea_compatible_str.split(',')
                    tiempo_l1 = receta.get('tiempo_prod_unidad_linea1', 0)
                    tiempo_l2 = receta.get('tiempo_prod_unidad_linea2', 0)
                    UMBRAL_CANTIDAD_LINEA_1 = 50
                    puede_l1 = '1' in linea_compatible_list and tiempo_l1 > 0
                    puede_l2 = '2' in linea_compatible_list and tiempo_l2 > 0

                    if puede_l1 and puede_l2:
                        linea_sug_agg = 1 if cantidad_total_agrupada >= UMBRAL_CANTIDAD_LINEA_1 else 2
                    elif puede_l1: linea_sug_agg = 1
                    elif puede_l2: linea_sug_agg = 2

                    data['sugerencia_linea'] = linea_sug_agg if linea_sug_agg > 0 else None

                    # --- ¡NUEVO! OBTENER CAPACIDAD REAL DE LA LÍNEA SUGERIDA ---
                    if linea_sug_agg:
                        try:
                            # Usamos el modelo de centro de trabajo (que ya está en self)
                            ct_resp = self.centro_trabajo_model.find_by_id(linea_sug_agg, 'id')
                            if ct_resp.get('success'):
                                ct_data = ct_resp.get('data', {})
                                cap_std = Decimal(ct_data.get('tiempo_disponible_std_dia', 480))
                                eficiencia = Decimal(ct_data.get('eficiencia', 1.0))
                                utilizacion = Decimal(ct_data.get('utilizacion', 1.0))

                                # Esta es la capacidad base NETA (sin bloqueos)
                                cap_neta_calculada = cap_std * eficiencia * utilizacion

                                if cap_neta_calculada > 0:
                                    capacidad_neta_linea_sugerida = cap_neta_calculada
                                    logger.info(f"Usando capacidad NETA {capacidad_neta_linea_sugerida} para sugerencia (Línea {linea_sug_agg})")
                                else:
                                    logger.warning(f"Capacidad neta para Línea {linea_sug_agg} es 0. Usando 480.")
                            else:
                                logger.warning(f"No se encontró CT {linea_sug_agg} para get cap. Usando 480.")
                        except Exception as e_cap:
                            logger.error(f"Error obteniendo cap para {linea_sug_agg}: {e_cap}. Usando 480.")

                # c) Calcular Tiempo de Producción (AHORA USANDO LA CAPACIDAD CORRECTA)
                if carga_total_minutos_agg > 0:
                    # (Línea 687 CORREGIDA)
                    data['sugerencia_t_prod_dias'] = math.ceil(
                        carga_total_minutos_agg / capacidad_neta_linea_sugerida
                    )
                else:
                    data['sugerencia_t_prod_dias'] = 0

                # --- FIN DE LA LÓGICA CORREGIDA ---

                # d) Verificar Stock Agregado (antes era b)
                ingredientes_result = self.receta_model.get_ingredientes(receta_id_agrupada)
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

                # e) Calcular JIT (antes era c)
                try:
                    today = date.today()
                    t_prod_dias = data.get('sugerencia_t_prod_dias', 0)
                    t_proc_dias = data.get('sugerencia_t_proc_dias', 0)
                    fecha_meta_str_jit = data.get('fecha_meta_mas_proxima')
                    if not fecha_meta_str_jit:
                        logger.warning(f"Grupo {grupo_key} sin fecha meta, usando 'hoy' + 7 días para JIT.")
                        fecha_meta_str_jit = (today + timedelta(days=7)).isoformat()
                    fecha_meta_solo_str = fecha_meta_str_jit.split('T')[0].split(' ')[0]
                    fecha_meta = date.fromisoformat(fecha_meta_solo_str)
                    fecha_inicio_ideal = fecha_meta - timedelta(days=t_prod_dias)
                    fecha_disponibilidad_material = today + timedelta(days=t_proc_dias)
                    fecha_inicio_base = max(fecha_inicio_ideal, fecha_disponibilidad_material)
                    fecha_inicio_sugerida_jit = max(fecha_inicio_base, today)
                    data['sugerencia_fecha_inicio_jit'] = fecha_inicio_sugerida_jit.isoformat()
                except Exception as e_jit_modal:
                    logger.warning(f"No se pudo calcular JIT para modal (Grupo: {grupo_key}): {e_jit_modal}")
                    data['sugerencia_fecha_inicio_jit'] = date.today().isoformat()

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
                ordenes_relevantes = []
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

                        # --- ¡CAMBIO! Usar .get('neta') ---
                        cap_dia_dict = capacidad_rango.get(linea_asignada, {}).get(fecha_actual_sim_str, {})
                        cap_dia = cap_dia_dict.get('neta', 0.0)
                        # --- FIN CAMBIO ---

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

    # --- MÉTODO MODIFICADO ---
    # (Reemplaza la función completa, aprox. línea 1032)

    def obtener_capacidad_disponible(self, centro_trabajo_ids: List[int], fecha_inicio: date, fecha_fin: date) -> Dict:
        """
        Calcula la capacidad disponible (en minutos) para centros de trabajo dados,
        entre dos fechas (inclusive). Considera estándar, eficiencia, utilización, BLOQUEOS,
        FINES DE SEMANA y FERIADOS.
        """
        capacidad_por_centro_y_fecha = defaultdict(dict)
        num_dias = (fecha_fin - fecha_inicio).days + 1

        try:
            # 1. Obtener datos de Centros de Trabajo (sin cambios)
            id_filter = ('in', tuple(centro_trabajo_ids))
            ct_result = self.centro_trabajo_model.find_all(filters={'id': id_filter})
            if not ct_result.get('success'):
                logger.error(f"Error obteniendo centros de trabajo: {ct_result.get('error')}")
                return {}
            centros_trabajo = {ct['id']: ct for ct in ct_result.get('data', [])}

            # 2. Obtener Bloqueos para este rango (sin cambios)
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

            # --- ¡INICIO DE LA MODIFICACIÓN (FERIADOS)! ---
            try:
                # 3. Obtener los años únicos del rango de fechas
                years_to_check = list(set(range(fecha_inicio.year, fecha_fin.year + 1)))
                # 4. Inicializar el objeto de feriados para Argentina
                # (country_holidays('AR') es un alias para holidays.Argentina())
                feriados_ar = holidays.country_holidays('AR', years=years_to_check)
                logger.info(f"Cargados {len(feriados_ar)} feriados de Argentina para los años {years_to_check}")
            except Exception as e_hol:
                logger.error(f"Error al inicializar la librería 'holidays': {e_hol}. Los feriados no se descontarán.")
                feriados_ar = {} # Fallback a un dict vacío
            # --- FIN DE LA MODIFICACIÓN (FERIADOS) ---


            # 5. Calcular capacidad día por día
            for dia_offset in range(num_dias):
                fecha_actual = fecha_inicio + timedelta(days=dia_offset)
                fecha_iso = fecha_actual.isoformat()

                # --- ¡LÓGICA COMBINADA (FIN DE SEMANA + FERIADOS)! ---
                dia_de_semana = fecha_actual.weekday() # 0=Lunes, 5=Sábado, 6=Domingo
                es_fin_de_semana = (dia_de_semana >= 5)

                # Comprobar si la fecha está en el set de feriados
                nombre_feriado = feriados_ar.get(fecha_actual) # Devuelve el nombre del feriado o None
                es_feriado = nombre_feriado is not None
                # --- FIN LÓGICA COMBINADA ---

                for ct_id in centro_trabajo_ids:
                    centro = centros_trabajo.get(ct_id)

                    cap_data = {
                        'bruta': Decimal(0),
                        'bloqueado': Decimal(0),
                        'neta': Decimal(0),
                        'motivo_bloqueo': None,
                        'hora_inicio': None,
                        'hora_fin': None
                    }

                    # --- ¡CONDICIÓN MODIFICADA! ---
                    # Si es fin de semana O feriado, NO calcular capacidad (capacidad neta = 0)
                    if es_fin_de_semana or es_feriado:
                        # Asigna el motivo (ej. "Día de la Revolución de Mayo" o "Fin de Semana")
                        cap_data['motivo_bloqueo'] = nombre_feriado if es_feriado else 'Fin de Semana'
                        capacidad_por_centro_y_fecha[ct_id][fecha_iso] = cap_data
                        continue # Saltar al siguiente centro de trabajo
                    # --- FIN DE LA MODIFICIÓN ---


                    if centro:
                        # Calcular capacidad estándar (sin cambios)
                        capacidad_std = Decimal(centro.get('tiempo_disponible_std_dia', 0))
                        eficiencia = Decimal(centro.get('eficiencia', 1.0))
                        utilizacion = Decimal(centro.get('utilizacion', 1.0))
                        num_maquinas = int(centro.get('numero_maquinas', 1))

                        capacidad_bruta_dia = capacidad_std * eficiencia * utilizacion * num_maquinas

                        # Restar bloqueos (sin cambios)
                        bloqueo_data = bloqueos_map.get(ct_id, {}).get(fecha_iso, {})
                        minutos_bloqueados_dec = Decimal(bloqueo_data.get('minutos_bloqueados', 0))

                        # Si ya hay un bloqueo (ej. Mantenimiento), que tenga prioridad
                        if minutos_bloqueados_dec > 0:
                            cap_data['motivo_bloqueo'] = bloqueo_data.get('motivo')
                            cap_data['hora_inicio'] = bloqueo_data.get('hora_inicio')
                            cap_data['hora_fin'] = bloqueo_data.get('hora_fin')

                        capacidad_neta_dia = max(Decimal(0), capacidad_bruta_dia - minutos_bloqueados_dec)
                        # ----------------------------

                        cap_data['bruta'] = round(capacidad_bruta_dia, 2)
                        cap_data['bloqueado'] = round(minutos_bloqueados_dec, 2)
                        cap_data['neta'] = round(capacidad_neta_dia, 2)
                        # (El motivo ya se asignó si había bloqueo)

                    capacidad_por_centro_y_fecha[ct_id][fecha_iso] = cap_data

            # 6. Convertir Decimals a floats para JSON (sin cambios)
            resultado_final_float_dict = {}
            for centro_id, cap_fecha in capacidad_por_centro_y_fecha.items():
                resultado_final_float_dict[centro_id] = {}
                for fecha, cap_dict in cap_fecha.items():
                    resultado_final_float_dict[centro_id][fecha] = {
                        'bruta': float(cap_dict['bruta']),
                        'bloqueado': float(cap_dict['bloqueado']),
                        'neta': float(cap_dict['neta']),
                        'motivo_bloqueo': cap_dict['motivo_bloqueo'],
                        'hora_inicio': cap_dict['hora_inicio'],
                        'hora_fin': cap_dict['hora_fin']
                    }

            return resultado_final_float_dict

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

                    # --- ¡CAMBIO! Usar .get('neta') ---
                    # Capacidad NETA del día (considerando eficiencia, etc.)
                    cap_dia_dict = capacidad_disponible_rango.get(linea_asignada, {}).get(fecha_actual_str, {})
                    capacidad_dia = cap_dia_dict.get('neta', 0.0)
                    # --- FIN CAMBIO ---

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
            return {'ops_planificadas': [], 'ops_con_oc': [], 'errores': []}

        # ... (Contadores y bucle 'for', sin cambios) ...
        ops_planificadas_exitosamente = []
        ops_con_oc_generada = []
        errores_encontrados = []
        fecha_planificacion_str = date.today().isoformat()

        for grupo in grupos_a_planificar:
            op_ids = [op['id'] for op in grupo['ordenes']]
            op_codigos = [op['codigo'] for op in grupo['ordenes']]
            producto_nombre = grupo.get('producto_nombre', 'N/A')

            try:
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

                elif res_planif_dict.get('error') in ['LATE_CONFIRM', 'SOBRECARGA_CAPACIDAD']:
                    error_tipo_grupo = res_planif_dict.get('error')
                    # --- INICIO DE LA CORRECCIÓN DE MENSAJE ---
                    if error_tipo_grupo == 'LATE_CONFIRM':
                        error_msg_grupo_es = f"el grupo consolidado terminaría TARDE (después de su Fecha Meta)."
                    else:
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

                                elif res_ind_dict.get('error') in ['LATE_CONFIRM', 'SOBRECARGA_CAPACIDAD']:
                                    # --- INICIO DE LA CORRECCIÓN DE MENSAJE ---
                                    error_tipo_ind = res_ind_dict.get('error')
                                    if error_tipo_ind == 'LATE_CONFIRM':
                                        error_msg_ind_es = "terminaría TARDE"
                                    else:
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
                        else:
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

    def obtener_datos_para_vista_planificacion(self, week_str: str, horizonte_dias: int, current_user_id: int, current_user_rol: str) -> tuple:
        """
        Método orquestador que obtiene y procesa todos los datos necesarios para la
        vista de planificación de forma optimizada.
        """
        try:
            # 1. Determinar rango de la semana
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

            # 2. Consulta de Órdenes de Producción (LÓGICA RESTAURADA)

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

            ops_planificadas = response_ops_planificadas.get('data', []) # <-- Esta es la variable correcta

            # 3. Procesamiento en Memoria

            # --- MPS Data (usa una versión simplificada de la lógica original) ---
            response_mps, _ = self.obtener_ops_pendientes_planificacion(dias_horizonte=horizonte_dias)
            mps_data = response_mps.get('data', {}) if response_mps.get('success') else {}

            # --- Calendario Semanal (usa la lista ya filtrada) ---
            response_semanal, _ = self.obtener_planificacion_semanal(week_str, ordenes_pre_cargadas=ops_planificadas)
            data_semanal = response_semanal.get('data', {}) if response_semanal.get('success') else {}
            ordenes_por_dia = data_semanal.get('ops_visibles_por_dia', {})

            # --- NUEVO: ENRIQUECER OPs DEL CALENDARIO (ordenes_por_dia) ---
            enriched_ordenes_por_dia = {}
            if ordenes_por_dia: # Solo si no está vacío
                for dia_iso, ops_del_dia in ordenes_por_dia.items():
                    ops_enriquecidas_dia = []
                    for op in ops_del_dia:
                        # Calcular sugerencias JIT para esta OP individual
                        sugerencias = self._calcular_sugerencias_para_op(op)
                        op['sugerencias_jit'] = sugerencias # Añadir el dict de sugerencias
                        ops_enriquecidas_dia.append(op)
                    enriched_ordenes_por_dia[dia_iso] = ops_enriquecidas_dia
            # --- FIN NUEVO BLOQUE ---

            # --- CRP Data (usa la lista de OPs planificadas) ---
            carga_calculada = self.calcular_carga_capacidad(ops_planificadas)
            capacidad_disponible = self.obtener_capacidad_disponible([1, 2], inicio_semana, fin_semana)

            # --- ¡BLOQUE MODIFICADO! ---
            # --- Obtener Issues de Planificación ---
            response_issues = self.issue_planificacion_model.get_all_with_op_details()
            planning_issues = response_issues.get('data', []) if response_issues.get('success') else []
            # --- FIN --

            # --- NUEVO: ENRIQUECER OPs DE ISSUES (VERSIÓN CORREGIDA) ---
            enriched_planning_issues = []
            if planning_issues:
                for issue in planning_issues:
                    op_id_para_jit = issue.get('orden_produccion_id')

                    if not op_id_para_jit:
                        logger.warning(f"Issue {issue.get('id')} omitido: no tiene 'orden_produccion_id'.")
                        issue['sugerencias_jit'] = {} # Poner vacío
                        enriched_planning_issues.append(issue)
                        continue

                    # --- INICIO DE LA CORRECCIÓN ---
                    # En lugar de simular, obtenemos la OP real.
                    # Esto es crucial porque la 'issue' no tiene todos los datos (ej. receta_id)
                    op_result = self.orden_produccion_controller.obtener_orden_por_id(op_id_para_jit)

                    if not op_result.get('success'):
                        logger.warning(f"Issue {issue.get('id')} (OP: {op_id_para_jit}): No se pudo encontrar la OP asociada.")
                        issue['sugerencias_jit'] = {}
                        enriched_planning_issues.append(issue)
                        continue

                    op_data_real = op_result.get('data')
                    # --- FIN DE LA CORRECCIÓN ---

                    # Ahora llamamos al helper con el objeto OP completo y real
                    sugerencias = self._calcular_sugerencias_para_op(op_data_real)
                    issue['sugerencias_jit'] = sugerencias
                    enriched_planning_issues.append(issue)
            # --- FIN BLOQUE ISSUES ---

            # 4. Obtener Datos Auxiliares (Usuarios)
            from app.controllers.usuario_controller import UsuarioController
            usuario_controller = UsuarioController()
            supervisores_resp = usuario_controller.obtener_usuarios_por_rol(['SUPERVISOR'])
            operarios_resp = usuario_controller.obtener_usuarios_por_rol(['OPERARIO'])
            supervisores = supervisores_resp.get('data', []) if supervisores_resp.get('success') else []
            operarios = operarios_resp.get('data', []) if operarios_resp.get('success') else []

            # 5. Ensamblar el resultado final
            datos_vista = {
                'mps_data': mps_data,
                'ordenes_por_dia': enriched_ordenes_por_dia,
                'carga_crp': carga_calculada,
                'capacidad_crp': capacidad_disponible,
                # 'bloqueos_crp' no es necesario, ya está dentro de 'capacidad_crp'
                'supervisores': supervisores,
                'operarios': operarios,
                'inicio_semana': inicio_semana.isoformat(),
                'fin_semana': fin_semana.isoformat(),
                'planning_issues': enriched_planning_issues
            }

            return self.success_response(data=datos_vista)

        except Exception as e:
            logger.error(f"Error en obtener_datos_para_vista_planificacion: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)


    # --- AÑADIR ESTE NUEVO HELPER ---
    def _crear_o_actualizar_issue(self, op_id: int, tipo_error: str, mensaje: str, datos_snapshot: Dict):
        """ Guarda el issue de planificación en la nueva tabla. """
        try:
            issue_data = {
                'tipo_error': tipo_error,
                'mensaje': mensaje,
                'datos_snapshot': datos_snapshot,
                'estado': 'PENDIENTE',
                'updated_at': datetime.now().isoformat() # Asegurarse de actualizar la fecha
            }
            self.issue_planificacion_model.create_or_update_by_op_id(op_id, issue_data)
            logger.info(f"Registrado Issue '{tipo_error}' para OP: {op_id}")
        except Exception as e:
            logger.error(f"Error al guardar issue de planificación para OP {op_id}: {e}", exc_info=True)

    # --- AÑADIR ESTE OTRO HELPER ---
    def _resolver_issue_por_op(self, op_id: int):
        """ Elimina un issue de la tabla cuando se planifica manualmente. """
        try:
            self.issue_planificacion_model.delete_by_op_id(op_id)
            logger.info(f"Issue para OP {op_id} resuelto y eliminado.")
        except Exception as e:
            logger.error(f"Error al resolver/eliminar issue para OP {op_id}: {e}", exc_info=True)


    def _calcular_sugerencias_para_op(self, op: Dict) -> Dict:
        """
        Calcula T_Prod, T_Proc, Línea Sug, y JIT para una ÚNICA OP.
        (Lógica adaptada de 'obtener_ops_pendientes_planificacion')
        --- CORREGIDO (Manejo de TypeError float-Decimal) ---
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
        op_id_log = op.get('id', 'N/A') # Para logging de errores

        try:
            receta_id = op.get('receta_id')
            cantidad = Decimal(op.get('cantidad_planificada', 0))

            if not receta_id or cantidad <= 0:
                logger.warning(f"[JIT Modal {op_id_log}] Cálculo abortado: falta receta_id o cantidad es 0.")
                return sugerencias

            # 1. Calcular Carga Total (Minutos)
            carga_total_minutos = Decimal(self._calcular_carga_op(op))

            # 2. Calcular Línea Sugerida y Capacidad Neta
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

                # 3. Obtener Capacidad Real
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

            # 4. Calcular T_Prod (Días)
            if carga_total_minutos > 0:
                sugerencias['sugerencia_t_prod_dias'] = math.ceil(
                    carga_total_minutos / capacidad_neta_linea_sugerida
                )

            # 5. Verificar Stock (T_Proc)
            ingredientes_result = self.receta_model.get_ingredientes(receta_id)
            insumos_faltantes_agg = []
            stock_ok_agg = True
            tiempos_entrega_agg = []

            if ingredientes_result.get('success'):
                for ingrediente in ingredientes_result.get('data', []):
                    insumo_id = ingrediente['id_insumo']

                    try:
                        cantidad_ingrediente = Decimal(ingrediente['cantidad'])
                    except:
                        logger.error(f"[JIT Modal {op_id_log}] Error al convertir ingrediente['cantidad'] a Decimal. Valor: {ingrediente['cantidad']}")
                        cantidad_ingrediente = Decimal(0)

                    cant_necesaria_total = cantidad_ingrediente * cantidad
                    stock_disp_res = self.inventario_controller.obtener_stock_disponible_insumo(insumo_id)

                    # --- ¡AQUÍ ESTÁ LA CORRECCIÓN! ---
                    stock_disp_raw = stock_disp_res.get('data', {}).get('stock_disponible', 0) if stock_disp_res.get('success') else 0
                    try:
                        stock_disp = Decimal(stock_disp_raw)
                    except:
                        logger.error(f"[JIT Modal {op_id_log}] Error al convertir stock_disp a Decimal. Valor: {stock_disp_raw}")
                        stock_disp = Decimal(0)
                    # --- FIN DE LA CORRECCIÓN ---

                    if stock_disp < cant_necesaria_total:
                        stock_ok_agg = False
                        faltante = cant_necesaria_total - stock_disp # <-- Ahora esto funcionará
                        insumos_faltantes_agg.append({ 'insumo_id': insumo_id, 'nombre': ingrediente.get('nombre_insumo', 'N/A'), 'cantidad_faltante': faltante })

                        insumo_data_res = self.insumo_model.find_by_id(insumo_id, 'id_insumo')
                        if insumo_data_res.get('success'):
                            tiempos_entrega_agg.append(insumo_data_res['data'].get('tiempo_entrega_dias', 0))
            else:
                stock_ok_agg = False
                logger.warning(f"[JIT Modal {op_id_log}] No se pudieron obtener ingredientes para receta {receta_id}")

            sugerencias['sugerencia_stock_ok'] = stock_ok_agg
            if not stock_ok_agg:
                sugerencias['sugerencia_t_proc_dias'] = max(tiempos_entrega_agg) if tiempos_entrega_agg else 0

            # 6. Calcular JIT (con el fallback que ya teníamos)
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
            op_id_log = op.get('id', 'N/A')
            logger.error(f"[JIT MODAL {op_id_log}] EXCEPCIÓN INESPERADA en _calcular_sugerencias_para_op: {e_jit}", exc_info=True)
            sugerencias['sugerencia_fecha_inicio_jit'] = date.today().isoformat()

        return sugerencias