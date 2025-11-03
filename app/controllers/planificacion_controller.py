import logging
from collections import defaultdict
from typing import List, Optional, Dict
from datetime import date, timedelta
import math
from decimal import Decimal

from app.controllers.base_controller import BaseController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.inventario_controller import InventarioController
from app.models.receta import RecetaModel
from app.models.insumo import InsumoModel
from app.models.centro_trabajo_model import CentroTrabajoModel

logger = logging.getLogger(__name__)

class PlanificacionController(BaseController):
    """
    Controlador para gestionar la planificación de la producción, incluyendo el Plan Maestro (MPS),
    la planificación semanal y la simulación de capacidad (CRP).
    """
    def __init__(self):
        super().__init__()
        self.orden_produccion_controller = OrdenProduccionController()
        self.inventario_controller = InventarioController()
        self.centro_trabajo_model = CentroTrabajoModel()
        self.receta_model = RecetaModel()
        self.insumo_model = InsumoModel()

    # region: API Pública del Controlador
    def consolidar_ops(self, op_ids: List[int], usuario_id: int) -> tuple:
        """
        Orquesta la consolidación de OPs llamando al controlador de órdenes de producción.
        """
        if not op_ids or len(op_ids) < 2:
            return self.error_response("Se requieren al menos dos órdenes para consolidar.", 400)
        try:
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
        Método principal para planificar un lote de OPs. Orquesta la consolidación (si es necesario),
        verifica la capacidad (CRP) y ejecuta la aprobación o replanificación según el estado de la OP.
        """
        try:
            op_a_planificar_id, op_data = self._obtener_datos_op_a_planificar(op_ids, usuario_id)
            if not op_a_planificar_id:
                return self.error_response(op_data, 500)

            op_estado_actual = op_data.get('estado')
            estados_permitidos = ['PENDIENTE', 'EN ESPERA', 'LISTA PARA PRODUCIR']
            if op_estado_actual not in estados_permitidos:
                msg = f"La OP {op_a_planificar_id} en estado '{op_estado_actual}' no puede ser (re)planificada."
                logger.warning(msg)
                return self.error_response(msg, 400), 400

            if len(op_ids) > 1 and op_estado_actual != 'PENDIENTE':
                msg = "La consolidación solo es posible para OPs en estado PENDIENTE."
                logger.warning(msg)
                return self.error_response(msg, 400), 400

            linea_propuesta = asignaciones.get('linea_asignada')
            fecha_inicio_str = asignaciones.get('fecha_inicio')
            if not linea_propuesta or not fecha_inicio_str:
                return self.error_response("Faltan línea o fecha de inicio.", 400)

            try:
                fecha_inicio_propuesta = date.fromisoformat(fecha_inicio_str)
            except ValueError:
                return self.error_response("Formato de fecha inválido. Usar YYYY-MM-DD.", 400)

            carga_total_op = float(self.orden_produccion_controller.calcular_carga_op(op_data))
            if carga_total_op <= 0:
                logger.warning(f"OP {op_a_planificar_id} con carga 0. Saltando verificación CRP.")
                dias_necesarios = 1
            else:
                simulacion_result = self._simular_asignacion_carga(
                    carga_total_op=carga_total_op,
                    linea_propuesta=linea_propuesta,
                    fecha_inicio_busqueda=fecha_inicio_propuesta,
                    op_id_a_excluir=op_a_planificar_id
                )

                if not simulacion_result['success']:
                    logger.warning(f"SOBRECARGA para OP {op_a_planificar_id}: {simulacion_result['error_data'].get('message')}")
                    return simulacion_result['error_data'], 409

                primer_dia_asignado = simulacion_result['fecha_inicio_real']
                fecha_fin_estimada = simulacion_result['fecha_fin_estimada']
                dias_necesarios = simulacion_result['dias_necesarios']
                asignaciones['fecha_inicio'] = primer_dia_asignado.isoformat()

                logger.info(f"Verificación CRP OK. OP {op_a_planificar_id} requiere ~{dias_necesarios} día(s).")
                logger.info(f"Inicio real: {primer_dia_asignado.isoformat()}, Fin aprox: {fecha_fin_estimada.isoformat()}.")

            if dias_necesarios > 1:
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
                if op_estado_actual == 'PENDIENTE':
                    return self._ejecutar_aprobacion_final(op_a_planificar_id, asignaciones, usuario_id)
                else:
                    return self._ejecutar_replanificacion_simple(op_a_planificar_id, asignaciones, usuario_id)

        except Exception as e:
            logger.error(f"Error crítico en consolidar_y_aprobar_lote: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    def confirmar_aprobacion_lote(self, op_id: int, asignaciones: dict, usuario_id: int) -> tuple:
        """
        Endpoint final para confirmar una aprobación. Omite la simulación de capacidad (ya se hizo)
        y ejecuta la acción basándose en el estado de la OP.
        """
        try:
            op_result = self.orden_produccion_controller.obtener_orden_por_id(op_id)
            if not op_result.get('success'):
                return self.error_response(f"No se encontró la OP ID {op_id}.", 404), 404

            op_estado_actual = op_result['data'].get('estado')
            logger.info(f"Confirmando aprobación para OP {op_id} (Estado: {op_estado_actual})...")

            if op_estado_actual == 'PENDIENTE':
                return self._ejecutar_aprobacion_final(op_id, asignaciones, usuario_id)
            elif op_estado_actual in ['EN ESPERA', 'LISTA PARA PRODUCIR']:
                return self._ejecutar_replanificacion_simple(op_id, asignaciones, usuario_id)
            else:
                msg = f"La OP {op_id} en estado '{op_estado_actual}' no puede ser confirmada."
                logger.warning(msg)
                return self.error_response(msg, 400), 400
        except Exception as e:
            logger.error(f"Error crítico en confirmar_aprobacion_lote: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500), 500

    def forzar_auto_planificacion(self, usuario_id: int) -> tuple:
        """
        Endpoint manual para forzar la ejecución de la planificación automática.
        """
        try:
            dias_horizonte_manual = 30
            resumen = self._ejecutar_planificacion_automatica(
                usuario_id=usuario_id,
                dias_horizonte=dias_horizonte_manual
            )
            return self.success_response(data=resumen, message="Planificación manual ejecutada.")
        except Exception as e:
            logger.error(f"Error en forzar_auto_planificacion: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    # endregion
    # ==============================================================================

    # region: Plan Maestro de Producción (MPS)
    # ==============================================================================

    def obtener_ops_pendientes_planificacion(self, dias_horizonte: int = 7) -> tuple:
        """
        Obtiene OPs PENDIENTES, las agrupa por producto y calcula sugerencias de planificación.
        """
        try:
            hoy = date.today()
            fecha_fin_horizonte = hoy + timedelta(days=int(dias_horizonte))
            filtros = {
                'estado': 'PENDIENTE',
                'fecha_meta_desde': hoy.isoformat(),
                'fecha_meta_hasta': fecha_fin_horizonte.isoformat()
            }
            response, _ = self.orden_produccion_controller.obtener_ordenes(filtros)
            if not response.get('success'):
                return self.error_response("Error al cargar órdenes pendientes.")

            mps_agrupado = self._agrupar_ops_por_producto(response.get('data', []))
            
            for _, data in mps_agrupado.items():
                self._calcular_sugerencias_para_grupo(data)

            mps_lista_ordenada = sorted(
                [{'producto_id': pid, 'producto_nombre': pname, **data}
                 for (pid, pname), data in mps_agrupado.items()],
                key=lambda x: x.get('fecha_meta_mas_proxima') or '9999-12-31'
            )

            resultado_final = {
                'mps_agrupado': mps_lista_ordenada,
                'inicio_horizonte': hoy.isoformat(),
                'fin_horizonte': fecha_fin_horizonte.isoformat(),
                'dias_horizonte': int(dias_horizonte)
            }
            return self.success_response(data=resultado_final)

        except Exception as e:
            logger.error(f"Error preparando MPS: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    # endregion
    # ==============================================================================

    # region: Planificación Semanal (Calendario)
    # ==============================================================================

    def obtener_planificacion_semanal(self, week_str: Optional[str] = None) -> tuple:
        """
        Orquesta la obtención de la planificación semanal para la vista de calendario.
        """
        try:
            rango_semana = self._determinar_rango_semana(week_str)
            start_of_week = rango_semana['start']
            end_of_week = rango_semana['end']

            ordenes_relevantes = self._obtener_ops_relevantes_para_rango(start_of_week, end_of_week)
            if not ordenes_relevantes:
                return self.success_response(data=self._generar_respuesta_vacia_semanal(rango_semana))

            ops_con_dias_ocupados = self._simular_dias_ocupados_para_ops(ordenes_relevantes, start_of_week, end_of_week)
            ops_visibles_por_dia = self._construir_vista_diaria(ops_con_dias_ocupados, start_of_week)

            resultado = {
                'ops_visibles_por_dia': ops_visibles_por_dia,
                'inicio_semana': start_of_week.isoformat(),
                'fin_semana': end_of_week.isoformat(),
                'semana_actual_str': rango_semana['identifier']
            }
            return self.success_response(data=resultado)

        except ValueError as ve:
            logger.warning(f"Error de formato en obtener_planificacion_semanal: {ve}")
            return self.error_response(str(ve), 400)
        except Exception as e:
            logger.error(f"Error crítico en obtener_planificacion_semanal: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    # endregion
    # ==============================================================================

    # region: Lógica de Planificación y Aprobación (Privado)
    # ==============================================================================

    def _ejecutar_aprobacion_final(self, op_id: int, asignaciones: dict, usuario_id: int) -> tuple:
        """ Ejecuta los pasos de pre-asignación y confirmación/aprobación. """
        try:
            datos_pre_asignar = {
                'linea_asignada': asignaciones.get('linea_asignada'),
                'supervisor_responsable_id': asignaciones.get('supervisor_id'),
                'operario_asignado_id': asignaciones.get('operario_id')
            }
            datos_pre_asignar = {k: v for k, v in datos_pre_asignar.items() if v is not None}

            res_pre_asig_dict, res_pre_asig_status = self.orden_produccion_controller.pre_asignar_recursos(
                op_id, datos_pre_asignar, usuario_id)
            if res_pre_asig_status >= 400:
                return res_pre_asig_dict, res_pre_asig_status

            res_conf_dict, res_conf_status = self.orden_produccion_controller.confirmar_inicio_y_aprobar(
                op_id, {'fecha_inicio_planificada': asignaciones.get('fecha_inicio')}, usuario_id)
            return res_conf_dict, res_conf_status
        except Exception as e:
            logger.error(f"Error en _ejecutar_aprobacion_final para OP {op_id}: {e}", exc_info=True)
            error_dict = self.error_response(f"Error interno al ejecutar aprobación final: {str(e)}", 500)
            return error_dict, 500

    def _ejecutar_replanificacion_simple(self, op_id: int, asignaciones: dict, usuario_id: int) -> tuple:
        """
        SOLO actualiza los campos de planificación de una OP que YA ESTÁ planificada.
        NO cambia el estado ni vuelve a verificar el stock.
        """
        logger.info(f"[RePlan] Ejecutando re-planificación simple para OP {op_id}...")
        try:
            update_data = {
                'fecha_inicio_planificada': asignaciones.get('fecha_inicio'),
                'linea_asignada': asignaciones.get('linea_asignada'),
                'supervisor_responsable_id': asignaciones.get('supervisor_id'),
                'operario_asignado_id': asignaciones.get('operario_id')
            }
            update_data = {k: v for k, v in update_data.items() if v is not None}
            update_result = self.orden_produccion_controller.model.update(op_id, update_data, 'id')

            if update_result.get('success'):
                return self.success_response(data=update_result.get('data'), message="OP re-planificada exitosamente.")
            else:
                return self.error_response(f"Error al actualizar la OP: {update_result.get('error')}", 500)
        except Exception as e:
            logger.error(f"Error en _ejecutar_replanificacion_simple para OP {op_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def _ejecutar_planificacion_automatica(self, usuario_id: int, dias_horizonte: int = 1) -> dict:
        """ Lógica central para la planificación automática. """
        logger.info(f"[AutoPlan] Iniciando ejecución para {dias_horizonte} día(s). Usuario: {usuario_id}")
        res_ops_pendientes, _ = self.obtener_ops_pendientes_planificacion(dias_horizonte)
        if not res_ops_pendientes.get('success'):
            return {'errores': ['No se pudieron obtener OPs pendientes.']}

        grupos = res_ops_pendientes.get('data', {}).get('mps_agrupado', [])
        if not grupos:
            return {'ops_planificadas': [], 'ops_con_oc': [], 'errores': []}

        resumen = {'ops_planificadas': [], 'ops_con_oc': [], 'errores': []}
        fecha_planificacion_str = date.today().isoformat()

        for grupo in grupos:
            op_ids = [op['id'] for op in grupo['ordenes']]
            op_codigos = [op['codigo'] for op in grupo['ordenes']]
            producto_nombre = grupo.get('producto_nombre', 'N/A')
            try:
                linea_sugerida = grupo.get('sugerencia_linea')
                if not linea_sugerida:
                    resumen['errores'].append(f"Grupo {producto_nombre} omitido: No hay línea sugerida.")
                    continue

                asignaciones = {'linea_asignada': linea_sugerida, 'fecha_inicio': fecha_planificacion_str}
                res_dict, res_status = self.consolidar_y_aprobar_lote(op_ids, asignaciones, usuario_id)

                if res_status < 400 and res_dict.get('success'):
                    resumen['ops_planificadas'].extend(op_codigos)
                    if res_dict.get('data', {}).get('oc_generada'):
                        resumen['ops_con_oc'].append({'ops': op_codigos, 'oc': res_dict['data'].get('oc_codigo', 'N/A')})
                elif res_dict.get('error') == 'MULTI_DIA_CONFIRM':
                    op_id_conf = res_dict.get('op_id_confirmar')
                    asig_conf = res_dict.get('asignaciones_confirmar')
                    res_aprob_dict, status_aprob = self._ejecutar_aprobacion_final(op_id_conf, asig_conf, usuario_id)
                    if status_aprob < 400 and res_aprob_dict.get('success'):
                        resumen['ops_planificadas'].extend(op_codigos)
                        if res_aprob_dict.get('data', {}).get('oc_generada'):
                            resumen['ops_con_oc'].append({'ops': op_codigos, 'oc': res_aprob_dict['data'].get('oc_codigo', 'N/A')})
                    else:
                        resumen['errores'].append(f"Grupo {producto_nombre} falló en aprobación final multi-día: {res_aprob_dict.get('error', 'Error')}")
                else:
                    resumen['errores'].append(f"Grupo {producto_nombre} falló: {res_dict.get('error', 'Desconocido')}")
            except Exception as e:
                resumen['errores'].append(f"Excepción crítica al procesar OPs {op_codigos}: {str(e)}")

        resumen.update({
            'total_planificadas': len(resumen['ops_planificadas']),
            'total_oc_generadas': len(resumen['ops_con_oc']),
            'total_errores': len(resumen['errores'])
        })
        logger.info(f"[AutoPlan] Finalizado. Resumen: {resumen}")
        return resumen

    # endregion
    # ==============================================================================

    # region: Lógica de Simulación de Capacidad (CRP) (Privado)
    # ==============================================================================

    def obtener_capacidad_disponible(self, centro_trabajo_ids: List[int], fecha_inicio: date, fecha_fin: date) -> Dict:
        """
        Calcula la capacidad disponible (en minutos) para centros de trabajo dados, entre dos fechas.
        """
        capacidad_por_centro_y_fecha = defaultdict(dict)
        num_dias = (fecha_fin - fecha_inicio).days + 1
        try:
            id_filter = ('in', tuple(centro_trabajo_ids))
            ct_result = self.centro_trabajo_model.find_all(filters={'id': id_filter})
            if not ct_result.get('success'):
                logger.error(f"Error obteniendo centros de trabajo: {ct_result.get('error')}")
                return {}

            centros_trabajo = {ct['id']: ct for ct in ct_result.get('data', [])}

            for dia_offset in range(num_dias):
                fecha_actual = fecha_inicio + timedelta(days=dia_offset)
                fecha_iso = fecha_actual.isoformat()
                for ct_id in centro_trabajo_ids:
                    centro = centros_trabajo.get(ct_id)
                    if not centro:
                        capacidad_por_centro_y_fecha[ct_id][fecha_iso] = 0.0
                        continue
                    capacidad_std = Decimal(centro.get('tiempo_disponible_std_dia', 0))
                    eficiencia = Decimal(centro.get('eficiencia', 1.0))
                    utilizacion = Decimal(centro.get('utilizacion', 1.0))
                    num_maquinas = int(centro.get('numero_maquinas', 1))
                    capacidad_neta_dia = capacidad_std * eficiencia * utilizacion * num_maquinas
                    capacidad_por_centro_y_fecha[ct_id][fecha_iso] = float(round(capacidad_neta_dia, 2))
            
            return dict(capacidad_por_centro_y_fecha)
        except Exception as e:
            logger.error(f"Error calculando capacidad disponible: {e}", exc_info=True)
            return {}

    def _simular_asignacion_carga(self, carga_total_op: float, linea_propuesta: int, fecha_inicio_busqueda: date, op_id_a_excluir: Optional[int] = None) -> dict:
        """
        Simula la asignación de carga día por día y devuelve la fecha de inicio real y la fecha de fin.
        """
        carga_restante_op = carga_total_op
        fecha_actual_simulacion = fecha_inicio_busqueda
        max_dias_simulacion = 30
        dias_necesarios = 0
        primer_dia_asignado = None
        
        for dia_actual_offset in range(max_dias_simulacion):
            if carga_restante_op < 0.01: break
            
            fecha_actual_sim = fecha_inicio_busqueda + timedelta(days=dia_actual_offset)
            fecha_actual_str = fecha_actual_sim.isoformat()

            cap_dict_dia = self.obtener_capacidad_disponible([linea_propuesta], fecha_actual_sim, fecha_actual_sim)
            cap_dia_actual = cap_dict_dia.get(linea_propuesta, {}).get(fecha_actual_str, 0.0)
            if cap_dia_actual <= 0: continue

            ops_existentes, _ = self.orden_produccion_controller.obtener_ordenes(filtros={
                'fecha_inicio_planificada': fecha_actual_str, 'linea_asignada': linea_propuesta,
                'estado': ('not.in', ['PENDIENTE', 'COMPLETADA', 'CANCELADA', 'CONSOLIDADA'])
            })
            carga_existente_dia = 0.0
            if ops_existentes.get('success'):
                ops_mismo_dia = [op for op in ops_existentes.get('data', []) if op.get('id') != op_id_a_excluir]
                if ops_mismo_dia:
                    # Este cálculo es una simplificación; un cálculo preciso distribuiría la carga de cada OP existente.
                    # Para CRP rápido, sumamos la carga total de OPs que *inician* ese día.
                    carga_existente_dia = sum(float(self.orden_produccion_controller.calcular_carga_op(op)) for op in ops_mismo_dia)

            cap_restante_dia = max(0.0, cap_dia_actual - carga_existente_dia)
            if cap_restante_dia < 1: continue

            if primer_dia_asignado is None:
                primer_dia_asignado = fecha_actual_sim

            carga_a_asignar_hoy = min(carga_restante_op, cap_restante_dia)
            if carga_a_asignar_hoy > 0:
                carga_restante_op -= carga_a_asignar_hoy
                dias_necesarios += 1 # Contar día solo si se usó
                fecha_fin_estimada = fecha_actual_sim

        if primer_dia_asignado is None or carga_restante_op > 0.01:
            error_data, _ = self._generar_respuesta_sobrecarga(
                linea_propuesta, (fecha_inicio_busqueda + timedelta(days=max_dias_simulacion-1)).isoformat(), 
                0, carga_restante_op, 0, horizonte_excedido=True)
            return {'success': False, 'error_data': error_data}

        return {
            'success': True, 'fecha_inicio_real': primer_dia_asignado, 'fecha_fin_estimada': fecha_fin_estimada,
            'dias_necesarios': dias_necesarios, 'error_data': None
        }

    # endregion
    # ==============================================================================

    # region: Métodos Privados y Helpers
    # ==============================================================================

    def _obtener_datos_op_a_planificar(self, op_ids: List[int], usuario_id: int) -> tuple:
        """ Obtiene los datos de la OP (consolidada o individual). Devuelve (id, data) o (None, error_msg). """
        if len(op_ids) > 1:
            resultado_consol = self.orden_produccion_controller.consolidar_ordenes_produccion(op_ids, usuario_id)
            if not resultado_consol.get('success'):
                return None, f"Error al consolidar: {resultado_consol.get('error')}"
            op_data = resultado_consol.get('data', {})
            return op_data.get('id'), op_data
        else:
            op_id = op_ids[0]
            op_result = self.orden_produccion_controller.obtener_orden_por_id(op_id)
            if not op_result.get('success'):
                return None, f"No se encontró la OP ID {op_id}."
            return op_id, op_result.get('data')

    def _generar_respuesta_sobrecarga(self, linea: int, fecha_str: str, cap_dia: float, carga_op_restante: float, carga_exist: float, horizonte_excedido: bool = False) -> tuple:
        """ Crea el diccionario y status code para error de sobrecarga con mensaje claro. """
        titulo = "⚠️ Sobrecarga de Capacidad Detectada"
        if horizonte_excedido:
            mensaje = f"No hay suficiente capacidad en los próximos 30 días para planificar {carga_op_restante:.0f} min restantes en la Línea {linea}."
        else:
            mensaje = (f"Capacidad insuficiente en la Línea {linea} para el día {fecha_str}. "
                       f"Se requieren {carga_op_restante:.0f} min pero solo quedan {max(0.0, cap_dia - carga_exist):.0f} min disponibles.")
        return {'success': False, 'error': 'SOBRECARGA_CAPACIDAD', 'title': titulo, 'message': mensaje}, 409

    def _agrupar_ops_por_producto(self, ordenes: List[Dict]) -> Dict:
        """ Agrupa una lista de OPs por producto. """
        mps_agrupado = defaultdict(lambda: {'cantidad_total': 0, 'ordenes': [], 'fecha_meta_mas_proxima': None, 'receta_id': None, 'unidad_medida': None})
        for op in ordenes:
            producto_id = op.get('producto_id')
            if not producto_id or op.get('cantidad_planificada', 0) <= 0 or not op.get('receta_id'):
                continue
            clave_producto = (producto_id, op.get('producto_nombre', 'Desconocido'))
            mps_agrupado[clave_producto]['cantidad_total'] += float(op['cantidad_planificada'])
            mps_agrupado[clave_producto]['ordenes'].append(op)
            if mps_agrupado[clave_producto]['receta_id'] is None:
                mps_agrupado[clave_producto]['receta_id'] = op['receta_id']
            if mps_agrupado[clave_producto]['unidad_medida'] is None:
                mps_agrupado[clave_producto]['unidad_medida'] = op.get('producto_unidad_medida')
            
            # Actualizar fecha meta más próxima
            fecha_meta_actual = mps_agrupado[clave_producto]['fecha_meta_mas_proxima']
            fecha_meta_op_str = op.get('fecha_meta')
            if fecha_meta_op_str and (fecha_meta_actual is None or date.fromisoformat(fecha_meta_op_str) < date.fromisoformat(fecha_meta_actual)):
                mps_agrupado[clave_producto]['fecha_meta_mas_proxima'] = fecha_meta_op_str
        return mps_agrupado

    def _calcular_sugerencias_para_grupo(self, data: Dict):
        """ Calcula tiempos, línea sugerida y stock para un grupo de OPs. """
        receta_id = data['receta_id']
        cantidad_total = data['cantidad_total']
        data.update({'sugerencia_t_prod_dias': 0, 'sugerencia_linea': None, 'sugerencia_t_proc_dias': 0, 'sugerencia_stock_ok': False, 'sugerencia_insumos_faltantes': [], 'linea_compatible': None})
        if not receta_id: return

        # Tiempo de Producción y Línea
        op_simulada = {'receta_id': receta_id, 'cantidad_planificada': cantidad_total}
        carga_total_min = float(self.orden_produccion_controller.calcular_carga_op(op_simulada))
        if carga_total_min > 0:
            data['sugerencia_t_prod_dias'] = math.ceil(carga_total_min / 480) # Asumiendo 8h/día

        receta_res = self.receta_model.find_by_id(receta_id, 'id')
        if receta_res.get('success'):
            receta = receta_res['data']
            linea_compatible_str = receta.get('linea_compatible', '2')
            data['linea_compatible'] = linea_compatible_str
            lineas = linea_compatible_str.split(',')
            if '1' in lineas and '2' in lineas: data['sugerencia_linea'] = 1 if cantidad_total >= 50 else 2
            elif '1' in lineas: data['sugerencia_linea'] = 1
            elif '2' in lineas: data['sugerencia_linea'] = 2

        # Verificación de Stock
        ingredientes_res = self.receta_model.get_ingredientes(receta_id)
        if ingredientes_res.get('success'):
            data['sugerencia_stock_ok'] = True
            for ing in ingredientes_res.get('data', []):
                cant_necesaria = ing['cantidad'] * cantidad_total
                stock_disp_res = self.inventario_controller.obtener_stock_disponible_insumo(ing['id_insumo'])
                stock_disp = stock_disp_res.get('data', {}).get('stock_disponible', 0)
                if stock_disp < cant_necesaria:
                    data['sugerencia_stock_ok'] = False
                    data['sugerencia_insumos_faltantes'].append({'nombre': ing.get('nombre_insumo'), 'cantidad_faltante': cant_necesaria - stock_disp})
            
            if not data['sugerencia_stock_ok']:
                tiempos_entrega = [self.insumo_model.find_by_id(ins['insumo_id'], 'id_insumo')['data'].get('tiempo_entrega_dias', 0) for ins in data['sugerencia_insumos_faltantes']]
                data['sugerencia_t_proc_dias'] = max(tiempos_entrega) if tiempos_entrega else 0
    
    def _determinar_rango_semana(self, week_str: Optional[str]) -> Dict:
        """ Calcula las fechas de inicio y fin de una semana. """
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
            identifier = f"{start.isocalendar().year}-W{start.isocalendar().week:02d}"
        
        end = start + timedelta(days=6)
        return {'start': start, 'end': end, 'identifier': identifier}

    def _obtener_ops_relevantes_para_rango(self, start_of_week: date, end_of_week: date) -> List[Dict]:
        """ Obtiene las OPs activas que inician antes del fin de la semana. """
        filtros = {
            'fecha_inicio_planificada_desde': (start_of_week - timedelta(days=14)).isoformat(),
            'fecha_inicio_planificada_hasta': end_of_week.isoformat(),
            'estado': ('in', ['EN ESPERA', 'LISTA PARA PRODUCIR', 'EN_LINEA_1', 'EN_LINEA_2', 'EN_EMPAQUETADO', 'CONTROL_DE_CALIDAD'])
        }
        response_ops, _ = self.orden_produccion_controller.obtener_ordenes(filtros)
        return response_ops.get('data', []) if response_ops.get('success') else []

    def _simular_dias_ocupados_para_ops(self, ordenes: List[Dict], start_of_week: date, end_of_week: date) -> List[Dict]:
        """ Para una lista de OPs, calcula y añade la clave 'dias_ocupados_calculados'. """
        fechas_inicio_ops = [date.fromisoformat(op['fecha_inicio_planificada']) for op in ordenes if op.get('fecha_inicio_planificada')]
        if not fechas_inicio_ops: return []
        
        fecha_min = min(fechas_inicio_ops)
        fecha_max = end_of_week + timedelta(days=14)
        capacidad_rango = self.obtener_capacidad_disponible([1, 2], fecha_min, fecha_max)
        carga_acumulada = {1: defaultdict(float), 2: defaultdict(float)}
        ordenes.sort(key=lambda op: op.get('fecha_inicio_planificada', '9999-12-31'))

        for orden in ordenes:
            linea, fecha_str = orden.get('linea_asignada'), orden.get('fecha_inicio_planificada')
            if not linea or not fecha_str: continue
            
            carga_total = float(self.orden_produccion_controller.calcular_carga_op(orden))
            if carga_total <= 0: continue

            dias_ocupados = []
            carga_restante = carga_total
            fecha_actual = date.fromisoformat(fecha_str)
            
            while carga_restante > 0.01:
                fecha_iso = fecha_actual.isoformat()
                cap_dia = capacidad_rango.get(linea, {}).get(fecha_iso, 0.0)
                carga_existente = carga_acumulada[linea].get(fecha_iso, 0.0)
                cap_restante = max(0.0, cap_dia - carga_existente)
                carga_a_asignar = min(carga_restante, cap_restante)
                
                if carga_a_asignar > 0:
                    dias_ocupados.append(fecha_iso)
                    carga_acumulada[linea][fecha_iso] += carga_a_asignar
                    carga_restante -= carga_a_asignar
                
                fecha_actual += timedelta(days=1)
            orden['dias_ocupados_calculados'] = dias_ocupados
        return ordenes

    def _construir_vista_diaria(self, ops_con_dias: List[Dict], start_of_week: date) -> Dict:
        """ Agrupa OPs en un diccionario por cada día de la semana visible. """
        vista_diaria = {(start_of_week + timedelta(days=i)).isoformat(): [] for i in range(7)}
        for op in ops_con_dias:
            for fecha_ocupada_iso in op.get('dias_ocupados_calculados', []):
                if fecha_ocupada_iso in vista_diaria and op not in vista_diaria[fecha_ocupada_iso]:
                    vista_diaria[fecha_ocupada_iso].append(op)
        return vista_diaria

    def _generar_respuesta_vacia_semanal(self, rango_semana: Dict) -> Dict:
        """ Genera una estructura de datos vacía para la planificación semanal. """
        return {
            'ops_visibles_por_dia': {(rango_semana['start'] + timedelta(days=i)).isoformat(): [] for i in range(7)},
            'inicio_semana': rango_semana['start'].isoformat(),
            'fin_semana': rango_semana['end'].isoformat(),
            'semana_actual_str': rango_semana['identifier']
        }

    # endregion
    # ==============================================================================
