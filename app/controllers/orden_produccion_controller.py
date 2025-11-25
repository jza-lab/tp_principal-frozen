from app.controllers.base_controller import BaseController
from app.controllers.registro_controller import RegistroController
from app.models.orden_produccion import OrdenProduccionModel
from app.schemas.orden_produccion_schema import OrdenProduccionSchema
from flask_jwt_extended import get_current_user
from typing import Dict, Optional, List
from decimal import Decimal
from marshmallow import ValidationError
from app.controllers.producto_controller import ProductoController
from app.controllers.receta_controller import RecetaController
from app.controllers.usuario_controller import UsuarioController
from datetime import datetime, timedelta
import logging
import math # <--- IMPORTACIÓN NECESARIA PARA math.ceil()

# --- NUEVAS IMPORTACIONES Y DEPENDENCIAS ---
from app.controllers.inventario_controller import InventarioController
from app.controllers.orden_compra_controller import OrdenCompraController
from app.controllers.insumo_controller import InsumoController
from app.controllers.lote_producto_controller import LoteProductoController
from app.models.pedido import PedidoModel
from datetime import date
from app.models.receta import RecetaModel
from app.models.insumo import InsumoModel # Asegúrate de importar esto
from app.models.motivo_paro_model import MotivoParoModel
from app.models.motivo_desperdicio_model import MotivoDesperdicioModel
from app.models.registro_paro_model import RegistroParoModel
from app.models.registro_desperdicio_model import RegistroDesperdicioModel
from app.models.operacion_receta_model import OperacionRecetaModel
from app.controllers.op_cronometro_controller import OpCronometroController
# Importar el controlador de configuración para usar la nueva lógica
from app.controllers.configuracion_controller import (
    ConfiguracionController,
    TOLERANCIA_SOBREPRODUCCION_PORCENTAJE,
    DEFAULT_TOLERANCIA_SOBREPRODUCCION
)
# --- NUEVAS IMPORTACIONES PARA TRASPASO ---
from app.models.traspaso_turno_model import TraspasoTurnoModel
from app.schemas.traspaso_turno_schema import TraspasoTurnoSchema
from app.models.asignacion_pedido_model import AsignacionPedidoModel
from app.controllers.pedido_controller import PedidoController
from app.models.registro_desperdicio_lote_insumo_model import RegistroDesperdicioLoteInsumoModel
from app.models.motivo_desperdicio_lote_model import MotivoDesperdicioLoteModel


logger = logging.getLogger(__name__)


class OrdenProduccionController(BaseController):
    """
    Controlador para la lógica de negocio de las Órdenes de Producción.
    """

    # region Inicialización
    def __init__(self):
        super().__init__()
        self.model = OrdenProduccionModel()
        self.schema = OrdenProduccionSchema()
        self.producto_controller = ProductoController()
        self.receta_controller = RecetaController()
        self.usuario_controller = UsuarioController()
        # --- NUEVOS CONTROLADORES ---
        self.inventario_controller = InventarioController()
        self.orden_compra_controller = OrdenCompraController()
        self.insumo_controller = InsumoController()
        self.lote_producto_controller = LoteProductoController()
        self.pedido_model = PedidoModel()
        self.receta_model = RecetaModel()
        self.insumo_model = InsumoModel()
        self.operacion_receta_model = OperacionRecetaModel()
        self.op_cronometro_controller = OpCronometroController()
        self.configuracion_controller = ConfiguracionController()
        # --- NUEVOS MODELOS Y SCHEMAS PARA TRASPASO ---
        self.traspaso_turno_model = TraspasoTurnoModel()
        self.traspaso_turno_schema = TraspasoTurnoSchema()
        self.asignacion_pedido_model = AsignacionPedidoModel()
        self._planificacion_controller = None
        self.registro_controller = RegistroController()
        self.registro_merma_model = RegistroDesperdicioLoteInsumoModel()

    @property
    def planificacion_controller(self):
        """Lazy loader for PlanificacionController to prevent circular dependency."""
        if self._planificacion_controller is None:
            from app.controllers.planificacion_controller import PlanificacionController
            self._planificacion_controller = PlanificacionController()
        return self._planificacion_controller

    # endregion

    # region Métodos Públicos (API)

    def calcular_carga_op(self, op_data: Dict) -> Decimal:
        """ Calcula la carga total en minutos para una OP dada. """
        carga_total = Decimal(0)
        receta_id = op_data.get('receta_id')
        cantidad = Decimal(op_data.get('cantidad_planificada', 0))
        if not receta_id or cantidad <= 0: return carga_total

        operaciones = self._obtener_operaciones_receta(receta_id)
        if not operaciones: return carga_total

        for op_step in operaciones:
            t_prep = Decimal(op_step.get('tiempo_preparacion', 0))
            t_ejec_unit = Decimal(op_step.get('tiempo_ejecucion_unitario', 0))
            carga_total += t_prep + (t_ejec_unit * cantidad)
        return carga_total

    def _obtener_operaciones_receta(self, receta_id: int) -> List[Dict]:
        """ Obtiene las operaciones de una receta desde el modelo. """
        result = self.operacion_receta_model.find_by_receta_id(receta_id)
        return result.get('data', []) if result.get('success') else []

    def obtener_ordenes(self, filtros: Optional[Dict] = None) -> tuple:
        """
        Obtiene una lista de órdenes de producción, aplicando filtros.
        Devuelve una tupla en formato (datos, http_status_code).
        """
        try:
            result = self.model.get_all_enriched(filtros)

            if result.get('success'):
                # --- INICIO LÓGICA DE ENRIQUECIMIENTO PARA MATERIALES ---
                ordenes = result.get('data', [])
                for orden in ordenes:
                    estado = orden.get('estado')
                    # El estado 'LISTA PARA PRODUCIR' implica que el stock fue verificado y reservado.
                    # El estado 'EN ESPERA' implica que se está esperando la llegada de insumos via OC.
                    if estado in ['LISTA PARA PRODUCIR', 'LISTA_PARA_PRODUCIR']:
                        orden['materiales_disponibles'] = True
                    # --- INICIO DE LA CORRECCIÓN ---
                    # Normalizar el estado para que coincida con los filtros del frontend
                    if estado:
                        orden['estado'] = estado.replace(' ', '_')
                    elif estado == 'EN_ESPERA':
                        orden['materiales_disponibles'] = False
                # --- FIN LÓGICA DE ENRIQUECIMIENTO ---
                return self.success_response(data=ordenes)
            else:
                error_msg = result.get('error', 'Error desconocido al obtener órdenes.')
                status_code = 404 if "no encontradas" in str(error_msg).lower() else 500
                return self.error_response(error_msg, status_code)
        except Exception as e:
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def obtener_cantidad_ordenes_estado(self, estado: str, fecha: Optional[str] = None) -> Optional[Dict]:
        filtros = {'estado': estado} if estado else {}

        if fecha:
            filtros['fecha_planificada'] = fecha

        response, status_code = self.obtener_ordenes(filtros)
        if(response.get('success')):
            ordenes=response.get('data', [])
            cantidad= len(ordenes)
            return self.success_response(data={'cantidad': cantidad})
        else:
            error_msg =response.get('error', 'No se pudo contar las ordenes planificadas')
            status_code = 404 if "no encontradas" in str(error_msg).lower() else 500
            return self.error_response(error_msg, status_code)



    def obtener_orden_por_id(self, orden_id: int) -> Optional[Dict]:
        """
        Obtiene el detalle de una orden de producción específica.
        """
        try:
            result = self.model.get_one_enriched(orden_id)
            if isinstance(result, dict):
                return result

            orden_data = result.get('data')
            if not orden_data:
                return self.error_response(f"No se encontraron datos para la OP {orden_id}.", 404)

            # 2. Obtener todas las órdenes de compra asociadas
            ocs_asociadas_res, _ = self.orden_compra_controller.get_all_ordenes(
                filtros={'orden_produccion_id': orden_id}
            )

            ocs_asociadas = []
            if ocs_asociadas_res.get('success'):
                ocs_asociadas = ocs_asociadas_res.get('data', [])

            # 3. Adjuntar las OCs a los datos de la OP
            orden_data['ocs_asociadas'] = ocs_asociadas

            # 4. Obtener todas las OPs hijas asociadas
            ops_hijas_res = self.model.find_all(filters={'id_op_padre': orden_id})
            ops_hijas = []
            if ops_hijas_res.get('success'):
                ops_hijas = ops_hijas_res.get('data', [])

            orden_data['ops_hijas'] = ops_hijas
            result['data'] = orden_data

            return result

        except Exception as e:
            logger.error(f"Excepción en obtener_orden_por_id para OP {orden_id}: {e}", exc_info=True)
            return {'success': False, 'error': f"Excepción al procesar la solicitud para la OP {orden_id}."}


    def obtener_desglose_origen(self, orden_id: int) -> Dict:
        """
        Obtiene los items de pedido que componen una orden de producción.
        """
        return self.model.obtener_desglose_origen(orden_id)

    def crear_orden(self, form_data: Dict, usuario_id: int) -> Dict:
        """
        Valida datos y crea una o varias órdenes de producción.
        """
        from app.models.receta import RecetaModel
        receta_model = RecetaModel()

        try:
            productos = form_data.get('productos')
            if not productos:
                return {'success': False, 'error': 'No se han seleccionado productos para crear las órdenes.'}

            ordenes_creadas = []
            errores = []

            for producto_data in productos:
                producto_id = producto_data.get('id')
                cantidad = producto_data.get('cantidad')

                if not producto_id or not cantidad:
                    errores.append(f"Producto inválido o cantidad faltante: {producto_data}")
                    continue

                datos_op = {
                    'producto_id': int(producto_id),
                    'cantidad_planificada': float(cantidad),
                    'fecha_meta': form_data.get('fecha_meta'),
                    'observaciones': form_data.get('observaciones'),
                    'estado': 'PENDIENTE',
                    'id_op_padre': form_data.get('id_op_padre')
                }

                receta_result = receta_model.find_all({'producto_id': int(producto_id), 'activa': True}, limit=1)
                if not receta_result.get('success') or not receta_result.get('data'):
                    errores.append(f'No se encontró una receta activa para el producto ID: {producto_id}.')
                    continue

                datos_op['receta_id'] = receta_result['data'][0]['id']

                try:
                    # Limpiar datos nulos que no deben ir al schema si no existen
                    datos_op_limpios = {k: v for k, v in datos_op.items() if v is not None}
                    validated_data = self.schema.load(datos_op_limpios)
                    validated_data['codigo'] = f"OP-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                    validated_data['usuario_creador_id'] = usuario_id

                    result = self.model.create(validated_data)
                    if result.get('success'):
                        op = result.get('data')
                        ordenes_creadas.append(op)
                        detalle = f"Se creó la orden de producción {op.get('codigo')}."
                        self.registro_controller.crear_registro(get_current_user(), 'Ordenes de produccion', 'Creación', detalle)
                    else:
                        errores.append(f"Error al crear OP para producto {producto_id}: {result.get('error')}")

                except ValidationError as e:
                    errores.append(f"Datos inválidos para producto {producto_id}: {e.messages}")

            if errores:
                return {'success': False, 'error': '; '.join(errores), 'data': {'creadas': ordenes_creadas}}

            codigos_ops = [op.get('codigo', f"ID {op.get('id')}") for op in ordenes_creadas]
            msg_ops = ", ".join(codigos_ops) if codigos_ops else ""
            return {'success': True, 'data': ordenes_creadas, 'message': f'Se crearon {len(ordenes_creadas)} órdenes de producción: {msg_ops}'}

        except Exception as e:
            logger.error(f"Error inesperado en crear_orden: {e}", exc_info=True)
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def asignar_supervisor(self, orden_id: int, supervisor_id: int) -> tuple:
            """
            Asigna un supervisor a una orden de producción existente.
            """
            try:
                if not supervisor_id:
                    return self.error_response("El ID del supervisor es requerido.", 400)

                update_data = {'supervisor_responsable_id': int(supervisor_id)}
                result = self.model.update(id_value=orden_id, data=update_data, id_field='id')

                if result.get('success'):
                    return self.success_response(data=result.get('data'), message="Supervisor asignado correctamente.")
                else:
                    return self.error_response('Error al asignar supervisor.', 500)
            except Exception as e:
                return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def verificar_y_actualizar_op_especifica(self, orden_produccion_id: int) -> Dict:
        """
        Verifica una orden de producción específica por su ID.
        Si la OP está 'EN ESPERA' y su stock ya está disponible (porque sus OCs se completaron),
        la pasa a 'LISTA PARA PRODUCIR'.
        """
        logger.info(f"Iniciando verificación específica para OP ID: {orden_produccion_id}.")
        try:
            # 1. Obtener la orden específica
            orden_res = self.model.find_by_id(orden_produccion_id)
            if not orden_res.get('success') or not orden_res.get('data'):
                msg = f"No se encontró la OP con ID {orden_produccion_id} para la verificación."
                logger.warning(msg)
                return {'success': False, 'error': msg}

            orden = orden_res['data']

            # Solo actuar si está 'EN ESPERA'
            if orden.get('estado') != 'EN ESPERA':
                msg = f"La OP {orden_produccion_id} no está 'EN ESPERA' (estado actual: {orden.get('estado')}). No se requiere acción."
                logger.info(msg)
                return {'success': True, 'message': msg}

            # --- NUEVA LÓGICA: Verificar si YA está cubierta (por la OC que acaba de llegar) ---
            esta_cubierta = self.inventario_controller.verificar_cobertura_reservas_op(orden)

            if esta_cubierta:
                logger.info(f"OP {orden_produccion_id} tiene cobertura completa de reservas. Avanzando estado.")

                nuevo_estado = 'LISTA PARA PRODUCIR'
                self.model.cambiar_estado(orden_produccion_id, nuevo_estado)

                return {'success': True, 'message': f"OP {orden_produccion_id} actualizada a {nuevo_estado} (Insumos ya reservados)."}
            # -----------------------------------------------------------------------------------

            # 2. Verificar stock (la lógica de OCs ya se cumplió si llegamos aquí)
            logger.debug(f"Verificando stock para OP {orden_produccion_id}...")
            verificacion_result = self.inventario_controller.verificar_stock_para_op(orden)

            if not verificacion_result.get('success'):
                error_msg = f"Fallo la verificación de stock para OP {orden_produccion_id}: {verificacion_result.get('error')}"
                logger.warning(error_msg)
                return {'success': False, 'error': error_msg}

            insumos_faltantes = verificacion_result['data']['insumos_faltantes']

            # 3. Si no hay faltantes, proceder a reservar y cambiar estado
            if not insumos_faltantes:
                logger.info(f"Stock completo encontrado para OP {orden_produccion_id}. Procediendo a reservar...")

                usuario_creador_id = orden.get('usuario_creador_id')
                if not usuario_creador_id:
                    error_msg = f"La OP {orden_produccion_id} no tiene un usuario creador. No se puede reservar el stock."
                    logger.error(error_msg)
                    return {'success': False, 'error': error_msg}

                # Reservar el stock
                reserva_result = self.inventario_controller.reservar_stock_insumos_para_op(orden, usuario_creador_id)
                if not reserva_result.get('success'):
                    error_msg = f"Stock disponible para OP {orden_produccion_id}, pero la reserva falló: {reserva_result.get('error')}"
                    logger.error(error_msg)
                    return {'success': False, 'error': error_msg}

                # Cambiar el estado
                nuevo_estado = 'LISTA PARA PRODUCIR'
                cambio_estado_result = self.model.cambiar_estado(orden_produccion_id, nuevo_estado)

                if cambio_estado_result.get('success'):
                    msg = f"Éxito: La OP {orden_produccion_id} ha sido actualizada a '{nuevo_estado}'."
                    logger.info(msg)
                    return {'success': True, 'message': msg}
                else:
                    error_msg = f"Fallo al cambiar el estado de la OP {orden_produccion_id}: {cambio_estado_result.get('error')}"
                    logger.error(error_msg)
                    return {'success': False, 'error': error_msg}
            else:
                # Esto no debería pasar si la lógica de la OC funcionó bien, pero es una salvaguarda.
                msg = f"Stock aún insuficiente para OP {orden_produccion_id} después de la recepción de OC. Verificación manual requerida."
                logger.warning(msg)
                return {'success': False, 'error': msg}

        except Exception as e:
            logger.error(f"Error inesperado procesando la OP {orden_produccion_id} en la verificación específica: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def verificar_y_actualizar_ordenes_en_espera(self) -> Dict:
        """
        Verifica todas las órdenes 'EN ESPERA'.
        1. Comprueba que TODAS las OCs vinculadas (Padres/Hijas) estén en 'RECEPCION COMPLETA'.
        2. Si lo están, comprueba que el stock de insumos esté disponible.
        Si ambas condiciones se cumplen, la OP pasa a 'LISTA PARA PRODUCIR'.
        """
        logger.info("Iniciando verificación proactiva de órdenes de producción 'EN ESPERA'.")
        # 1. Obtener todas las órdenes 'EN ESPERA'
        ordenes_en_espera_res = self.model.find_all(filters={'estado': 'EN ESPERA'})

        if not ordenes_en_espera_res.get('success') or not ordenes_en_espera_res.get('data'):
            logger.info("No se encontraron órdenes 'EN ESPERA' para verificar.")
            return {'success': True, 'message': 'No hay órdenes en espera para procesar.'}

        ordenes_en_espera = ordenes_en_espera_res['data']
        ordenes_actualizadas_count = 0
        errores = []

        # 2. Iterar sobre cada orden
        for orden in ordenes_en_espera:
            try:
                orden_id = orden['id']
                logger.debug(f"Iniciando verificación para OP {orden_id} (Código: {orden.get('codigo')})...")

                # --- INICIO DE LA NUEVA LÓGICA DE VERIFICACIÓN DE OC ---
                logger.debug(f"Verificando estado de OCs vinculadas para OP {orden_id}...")

                # 1. Encontrar todas las OCs "Padre" vinculadas a esta OP
                ocs_vinculadas_res = self.orden_compra_controller.model.find_all(
                    filters={'orden_produccion_id': orden_id}
                )

                # Si la OP tiene OCs vinculadas, debemos chequearlas
                if ocs_vinculadas_res.get('success') and ocs_vinculadas_res.get('data'):
                    ocs_padre = ocs_vinculadas_res.get('data')
                    todas_ocs_completas = True

                    for oc_padre in ocs_padre:
                        oc_padre_id = oc_padre.get('id')

                        # 2. Buscar si esta OC Padre tiene una Hija
                        oc_hija_res = self.orden_compra_controller.model.find_all(
                            filters={'complementa_a_orden_id': oc_padre_id},
                            limit=1
                        )

                        oc_hija = None
                        if oc_hija_res.get('success') and oc_hija_res.get('data'):
                            oc_hija = oc_hija_res.get('data')[0]

                        # 3. Determinar qué estado verificar
                        if oc_hija:
                            # Si hay hija, el estado de la hija es el que importa
                            if oc_hija.get('estado') != 'RECEPCION_COMPLETA':
                                logger.info(f"OP {orden_id} en espera. OC Hija {oc_hija.get('id')} ({oc_hija.get('estado')}) aún no está 'RECEPCION COMPLETA'.")
                                todas_ocs_completas = False
                                break # Salir del bucle for oc_padre
                        else:
                            # Si no hay hija, el estado de la padre es el que importa
                            if oc_padre.get('estado') != 'RECEPCION_COMPLETA':
                                logger.info(f"OP {orden_id} en espera. OC Padre {oc_padre_id} ({oc_padre.get('estado')}) (sin hija) aún no está 'RECEPCION COMPLETA'.")
                                todas_ocs_completas = False
                                break # Salir del bucle for oc_padre

                    # 4. Si alguna OC (la Hija si existe, o la Padre si no) no está completa, saltar esta OP
                    if not todas_ocs_completas:
                        continue # Pasar a la siguiente OP en 'EN ESPERA'

                else:
                    # No se encontraron OCs vinculadas. En este caso, la OP depende solo del stock.
                    logger.debug(f"OP {orden_id} no tiene OCs vinculadas, depende solo de stock.")

                logger.info(f"Verificación de OCs superada para OP {orden_id}. Procediendo a verificar stock.")
                # --- FIN DE LA NUEVA LÓGICA DE VERIFICACIÓN DE OC ---


                # 3. Verificar si hay stock disponible (dry run)
                verificacion_result = self.inventario_controller.verificar_stock_para_op(orden)

                if not verificacion_result.get('success'):
                    logger.warning(f"Fallo la verificación de stock para OP {orden_id}: {verificacion_result.get('error')}")
                    continue

                insumos_faltantes = verificacion_result['data']['insumos_faltantes']

                # 4. Si no hay faltantes, proceder a reservar y cambiar estado
                if not insumos_faltantes:
                    logger.info(f"Stock completo encontrado para OP {orden_id}. Procediendo a reservar y actualizar estado.")

                    usuario_creador_id = orden.get('usuario_creador_id')
                    if not usuario_creador_id:
                        logger.error(f"La OP {orden_id} no tiene un usuario creador. No se puede reservar el stock. Saltando.")
                        errores.append(f"OP {orden_id}: Falta usuario creador.")
                        continue

                    # 5. Reservar el stock
                    reserva_result = self.inventario_controller.reservar_stock_insumos_para_op(orden, usuario_creador_id)
                    if not reserva_result.get('success'):
                        logger.error(f"Stock disponible para OP {orden_id}, pero la reserva falló: {reserva_result.get('error')}")
                        errores.append(f"OP {orden_id}: Fallo en reserva - {reserva_result.get('error')}")
                        continue

                    # 6. Cambiar el estado de la orden
                    nuevo_estado = 'LISTA PARA PRODUCIR'
                    cambio_estado_result = self.model.cambiar_estado(orden_id, nuevo_estado)

                    if cambio_estado_result.get('success'):
                        logger.info(f"Éxito: La OP {orden_id} ha sido actualizada a '{nuevo_estado}'.")
                        ordenes_actualizadas_count += 1
                    else:
                        logger.error(f"Fallo al cambiar el estado de la OP {orden_id} a '{nuevo_estado}': {cambio_estado_result.get('error')}")
                        errores.append(f"OP {orden_id}: Fallo al cambiar estado - {cambio_estado_result.get('error')}")

                else:
                    logger.debug(f"Stock aún insuficiente para OP {orden_id}.")

            except Exception as e:
                logger.error(f"Error inesperado procesando la OP {orden.get('id')} en la verificación proactiva: {e}", exc_info=True)
                errores.append(f"OP {orden.get('id')}: Error - {str(e)}")

        # 7. Preparar el resumen final
        summary_message = f"Verificación completada. {ordenes_actualizadas_count} órdenes actualizadas."
        if errores:
            summary_message += f" Se encontraron {len(errores)} errores: {'; '.join(errores)}"

        logger.info(summary_message)
        return {'success': True, 'message': summary_message, 'data': {'actualizadas': ordenes_actualizadas_count, 'errores': len(errores)}}

    def verificar_stock_para_op(self, orden_simulada: Dict) -> Dict:
        # Extraer fecha para pasarla explícitamente
        fecha_uso = None
        f_str = orden_simulada.get('fecha_inicio_planificada') or orden_simulada.get('fecha_meta')
        if f_str:
             try: fecha_uso = date.fromisoformat(f_str.split('T')[0])
             except: pass

        return self.inventario_controller.verificar_stock_para_op(orden_simulada, fecha_requisito=fecha_uso)

    # --- MÉTODO CORREGIDO ---
    def aprobar_orden_con_oc(self, orden_id: int, usuario_id: int, oc_id: int) -> tuple:
        """
        Vincula una OC (conocida) a una OP PENDIENTE (flujo manual).
        NO cambia el estado de la OP.
        """
        try:
            # 1. Asocia la OC a la OP (Descomentado)
            # Asegúrate que tu modelo OP tenga el campo 'orden_compra_id'
            update_oc_result = self.model.update(orden_id, {'orden_compra_id': oc_id}, 'id')
            if not update_oc_result.get('success'):
                 # Si falla la vinculación, devolvemos error
                 logger.error(f"Fallo al vincular OP {orden_id} con OC {oc_id}: {update_oc_result.get('error')}")
                 return self.error_response(f"Fallo al vincular la OP con la OC: {update_oc_result.get('error')}", 500)

            # 2. La OP permanece en PENDIENTE
            logger.info(f"OP {orden_id} vinculada exitosamente con OC {oc_id}. Estado permanece PENDIENTE.")
            return self.success_response(
                data=update_oc_result.get('data'), # Devuelve la OP actualizada
                message="Orden de Compra vinculada. La Orden de Producción sigue PENDIENTE."
            )
        except Exception as e:
            logger.error(f"Error en aprobar_orden_con_oc para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    # --- MÉTODO CORREGIDO ---
    def aprobar_orden(self, orden_id: int, usuario_id: int) -> tuple:
        """
        Orquesta el proceso de aprobación de una orden PENDIENTE, delegando la
        lógica a helpers según la disponibilidad de stock.
        """
        try:
            orden_produccion, error_response = self._validar_estado_para_aprobacion(orden_id)
            if error_response:
                return error_response

            # --- INICIO CORRECCIÓN ---
            # Obtener la fecha real de uso (Planificada > Meta > Hoy)
            fecha_uso_str = orden_produccion.get('fecha_inicio_planificada') or orden_produccion.get('fecha_meta')
            fecha_uso = date.today()

            if fecha_uso_str:
                try:
                    fecha_limpia = fecha_uso_str.split('T')[0]
                    fecha_uso = date.fromisoformat(fecha_limpia)
                except ValueError:
                    pass

            logger.info(f"Verificando stock para OP {orden_id} con fecha de requisito: {fecha_uso}")

            # Pasar la fecha explícitamente
            verificacion_result = self.inventario_controller.verificar_stock_para_op(
                orden_produccion,
                fecha_requisito=fecha_uso # <--- CLAVE
            )
            # --- FIN CORRECCIÓN ---

            if not verificacion_result.get('success'):
                return self.error_response(f"Error al verificar stock: {verificacion_result.get('error')}", 500)

            insumos_faltantes = verificacion_result['data']['insumos_faltantes']

            if insumos_faltantes:
                return self._gestionar_stock_faltante(orden_produccion, insumos_faltantes, usuario_id)
            else:
                return self._gestionar_stock_disponible(orden_produccion, usuario_id)

        except Exception as e:
            logger.error(f"Error en el proceso de aprobación de OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def _generar_orden_de_compra_automatica(self, insumos_faltantes: List[Dict], usuario_id: int, orden_produccion_id: int) -> Dict:
        from collections import defaultdict

        items_por_proveedor = defaultdict(list)

        # 1. Agrupar insumos por proveedor
        for insumo in insumos_faltantes:
            try:
                insumo_id = insumo['insumo_id']
                insumo_data_res = self.insumo_model.find_by_id(insumo_id, 'id_insumo')
                if not insumo_data_res.get('success'):
                    return {'success': False, 'error': f"No se encontró el insumo con ID {insumo_id}."}

                insumo_data = insumo_data_res['data']
                proveedor_id = insumo_data.get('id_proveedor')
                if not proveedor_id:
                    return {'success': False, 'error': f"El insumo '{insumo_data.get('nombre')}' no tiene un proveedor asociado."}

                # --- INICIO DE LA MODIFICACIÓN PARA NO DUPLICAR OCS ---

                # A. Obtener el faltante físico reportado por inventario
                cantidad_faltante_fisica = float(insumo['cantidad_faltante'])

                # B. Consultar qué cantidad de este insumo ya está pedida en OCs activas (Pendientes/En tránsito)
                #    vinculadas a esta misma OP.
                cantidad_en_camino = self._obtener_cantidad_insumo_en_curso(orden_produccion_id, insumo_id)

                # C. Calcular lo que realmente necesitamos comprar ahora
                cantidad_real_a_comprar = cantidad_faltante_fisica - cantidad_en_camino

                logger.info(f"[Auto-Compra OP-{orden_produccion_id}] Insumo {insumo_id}: Faltante Físico={cantidad_faltante_fisica}, En Camino={cantidad_en_camino}. A comprar={cantidad_real_a_comprar}")

                # D. Si ya está todo pedido (o sobra), saltamos este insumo
                if cantidad_real_a_comprar <= 0:
                    continue

                # E. Usamos la nueva cantidad calculada para el redondeo
                cantidad_redondeada = math.ceil(cantidad_real_a_comprar)

                # --- FIN DE LA MODIFICACIÓN ---

                if cantidad_redondeada <= 0: continue

                items_por_proveedor[proveedor_id].append({
                    'insumo_id': insumo_id,
                    'cantidad_solicitada': cantidad_redondeada,
                    'precio_unitario': float(insumo_data.get('precio_unitario', 0))
                })
            except Exception as e:
                logger.error(f"Error procesando insumo faltante {insumo.get('insumo_id')}: {e}")
                return {'success': False, 'error': f"Error al procesar insumo {insumo.get('insumo_id')}: {e}"}

        if not items_por_proveedor:
            # Cambiamos el mensaje de error por uno de éxito si se "cubrió" todo con OCs en curso
            return {'success': True, 'data': [], 'message': 'No se generaron nuevas OCs. Los insumos faltantes ya están pedidos en OCs activas.'}

        # 2. Crear una OC por cada proveedor
        resultados_creacion = []
        for proveedor_id, items in items_por_proveedor.items():
            subtotal = sum(item['cantidad_solicitada'] * item['precio_unitario'] for item in items)
            iva = subtotal * 0.21
            total = subtotal + iva

            datos_oc = {
                'proveedor_id': proveedor_id,
                'fecha_emision': date.today().isoformat(),
                'prioridad': 'ALTA',
                'observaciones': f"Generada automáticamente para OP ID: {orden_produccion_id}",
                'orden_produccion_id': orden_produccion_id,
                'subtotal': round(subtotal, 2),
                'iva': round(iva, 2),
                'total': round(total, 2)
            }

            items_para_crear = [{'insumo_id': i['insumo_id'], 'cantidad_solicitada': i['cantidad_solicitada'], 'precio_unitario': i['precio_unitario'], 'cantidad_recibida': 0.0} for i in items]

            resultado = self.orden_compra_controller.crear_orden(datos_oc, items_para_crear, usuario_id)
            if resultado.get('success'):
                resultados_creacion.append(resultado['data'])
            else:
                # Si una falla, se retorna el error de esa OC. En un sistema más complejo, se podría implementar un rollback.
                return {'success': False, 'error': f"Fallo al crear OC para proveedor {proveedor_id}: {resultado.get('error')}"}

        return {'success': True, 'data': resultados_creacion, 'message': f'Se crearon {len(resultados_creacion)} órdenes de compra.'}

    def generar_orden_de_compra_automatica(self, insumos_faltantes: List[Dict], usuario_id: int, orden_produccion_id: int) -> Dict:
        """Wrapper publico para el helper privado _generar_orden_de_compra_automatica."""
        return self._generar_orden_de_compra_automatica(insumos_faltantes, usuario_id, orden_produccion_id)


    def rechazar_orden(self, orden_id: int, motivo: str) -> Dict:
        """
        Rechaza una orden, cambiando su estado a CANCELADA.
        """
        result = self.model.cambiar_estado(orden_id, 'CANCELADA', observaciones=f"Rechazada: {motivo}")
        if result.get('success'):
            op = result.get('data')
            detalle = f"Se canceló la orden de producción {op.get('codigo')}. Motivo: {motivo}"
            self.registro_controller.crear_registro(get_current_user(), 'Ordenes de produccion', 'Cancelación', detalle)
        return result

    def cambiar_estado_orden(self, orden_id: int, nuevo_estado: str, usuario_id: Optional[int] = None, qc_data: Optional[Dict] = None) -> tuple:
        """
        Cambia el estado de una orden.
        Si es 'COMPLETADA', crea el lote y lo deja 'RESERVADO' si está
        vinculado a un pedido, o 'DISPONIBLE' si es para stock general.
        Acepta datos de control de calidad (qc_data) para la creación del lote.
        """
        try:
            from flask_jwt_extended import get_jwt_identity

            orden_result = self.obtener_orden_por_id(orden_id)
            if not orden_result.get('success'):
                return self.error_response("Orden de producción no encontrada.", 404)
            orden_produccion = orden_result['data']
            estado_actual = orden_produccion['estado']

            update_data = {}
            message_to_use = f"Estado actualizado a {nuevo_estado.replace('_', ' ')}." # Mensaje por defecto

            if nuevo_estado == 'COMPLETADA':
                if not estado_actual or estado_actual.strip() != 'CONTROL_DE_CALIDAD':
                    return self.error_response("La orden debe estar en 'CONTROL DE CALIDAD' para ser completada.", 400)

                usuario_id_actual = get_jwt_identity()
                update_data['aprobador_calidad_id'] = usuario_id_actual

                lote_result, lote_status = self.lote_producto_controller.crear_lote_y_reservas_desde_op(
                    orden_produccion_data=orden_produccion,
                    usuario_id=usuario_id_actual,
                    qc_data=qc_data
                )

                if lote_status >= 400:
                    return self.error_response(f"Fallo al procesar el lote/reserva: {lote_result.get('error')}", 500)

                message_to_use = f"Orden completada. {lote_result.get('message', '')}"

            result = self.model.cambiar_estado(orden_id, nuevo_estado, extra_data=update_data)
            if result.get('success'):
                op = result.get('data')
                detalle = f"La orden de producción {op.get('codigo')} cambió de estado a {nuevo_estado}."
                self.registro_controller.crear_registro(get_current_user(), 'Ordenes de produccion', 'Cambio de Estado', detalle)

                return self.success_response(data=result.get('data'), message=message_to_use)
            else:
                return self.error_response(result.get('error', 'Error al cambiar el estado.'), 500)

        except Exception as e:
            logger.error(f"Error en cambiar_estado_orden para la orden {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def crear_orden_desde_planificacion(self, producto_id: int, item_ids: List[int], usuario_id: int) -> Dict:
        """
        Orquesta la creación de una orden consolidada desde el módulo de planificación.
        """
        from app.models.pedido import PedidoModel
        from app.models.receta import RecetaModel
        from datetime import date

        pedido_model = PedidoModel()
        receta_model = RecetaModel()

        try:
            # 1. Obtener los ítems y calcular la cantidad total
            items_result = pedido_model.find_all_items(filters={'id': ('in', item_ids)})
            if not items_result.get('success') or not items_result.get('data'):
                return {'success': False, 'error': 'No se encontraron los ítems de pedido para consolidar.'}

            items = items_result['data']
            cantidad_total = sum(item['cantidad'] for item in items)

            # --- NUEVA LÓGICA: Obtener el ID del Pedido (Orden de Venta) de referencia ---
            # Se toma el ID del primer ítem como referencia principal para el campo.
            primer_pedido_id = items[0].get('pedido_id') if items else None
            # ---------------------------------------------------------------------------

            # 2. Encontrar receta activa
            receta_result = receta_model.find_all({'producto_id': producto_id, 'activa': True}, limit=1)
            if not receta_result.get('data'):
                return {'success': False, 'error': f'No se encontró una receta activa para el producto ID {producto_id}.'}
            receta = receta_result['data'][0]

            # 3. Crear la orden de producción
            datos_orden = {
                'producto_id': producto_id,
                'cantidad_planificada': cantidad_total,
                'fecha_planificada': date.today().isoformat(),
                'receta_id': receta['id'],
                'prioridad': 'NORMAL',
                # --- INCLUIR EL CAMPO pedido_id EN LOS DATOS ---
                'pedido_id': primer_pedido_id
                # -----------------------------------------------
            }
            resultado_creacion = self.crear_orden(datos_orden, usuario_id)

            if not resultado_creacion.get('success'):
                return resultado_creacion

            # 4. Actualizar los ítems de pedido en lote
            orden_creada = resultado_creacion['data']
            update_data = {
                'estado': 'PLANIFICADO',
                'orden_produccion_id': orden_creada['id']
            }
            pedido_model.update_items(item_ids, update_data)

            return {'success': True, 'data': orden_creada}

        except Exception as e:
            return {'success': False, 'error': f'Error en el proceso de consolidación: {str(e)}'}

    def obtener_datos_para_formulario(self) -> Dict:
        """
        Obtiene los datos necesarios para popular los menús desplegables
        en el formulario de creación/edición de órdenes, usando los nuevos controladores.
        """
        try:
            productos = self.producto_controller.obtener_todos_los_productos()
            recetas = self.receta_controller.obtener_recetas({'activa': True})
            todos_los_usuarios = self.usuario_controller.obtener_todos_los_usuarios()
            operarios = [u for u in todos_los_usuarios if u.get('roles', {}).get('codigo') in ['OPERARIO', 'SUPERVISOR']]

            return {
                'productos': productos,
                'recetas': recetas,
                'operarios': operarios
            }
        except Exception as e:
            return {
                'productos': [], 'recetas': [], 'operarios': [],
                'error': f'Error obteniendo datos para el formulario: {str(e)}'
            }

    def consolidar_ordenes_produccion(self, op_ids: List[int], usuario_id: int) -> Dict:
        """
        Orquesta la fusión de varias OPs en una Super OP, delegando cada
        paso a métodos auxiliares privados.
        """
        try:
            ops_originales, error = self._validar_y_obtener_ops_para_consolidar(op_ids)
            if error:
                return error

            super_op_data = self._calcular_datos_super_op(ops_originales, op_ids)

            resultado_creacion = self.crear_orden(super_op_data, usuario_id)
            if not resultado_creacion.get('success'):
                return resultado_creacion

            nueva_super_op = resultado_creacion['data']

            relink_result = self._relinkear_items_pedido(op_ids, nueva_super_op[0]['id'])
            if not relink_result.get('success'):
                # NOTA: En un sistema real, aquí se debería intentar revertir la creación de la Super OP.
                return relink_result

            self._actualizar_ops_originales(op_ids, nueva_super_op[0]['id'])

            return {'success': True, 'data': nueva_super_op}
        except Exception as e:
            logger.error(f"Error en consolidar_ordenes_produccion: {e}", exc_info=True)
            return {'success': False, 'error': f'Error interno del servidor: {str(e)}'}

    def cambiar_estado_orden_simple(self, orden_id: int, nuevo_estado: str) -> Dict:
        """
        Cambia el estado de una orden de producción. Ideal para el Kanban.
        Reutiliza la lógica robusta del modelo.
        """
        try:
            # Validación simple de estados (opcional pero recomendado)
            orden_result = self.obtener_orden_por_id(orden_id)
            if not orden_result.get('success'):
                return {'success': False, 'error': "Orden de producción no encontrada."}

            # Aquí podrías añadir reglas de negocio, ej:
            # "No se puede mover de 'EN LINEA 1' a 'LISTA PARA PRODUCIR'"

            # Llamamos al método del modelo que ya sabe cómo cambiar estados y fechas
            result = self.model.cambiar_estado(orden_id, nuevo_estado)
            return result

        except Exception as e:
            logger.error(f"Error en cambiar_estado_orden_simple para OP {orden_id}: {e}", exc_info=True)
            return {'success': False, 'error': f"Error interno: {str(e)}"}

    def sugerir_fecha_inicio(self, orden_id: int, usuario_id: int) -> tuple:
        """
        Calcula fecha de inicio sugerida, considerando la línea de producción
        óptima y su eficiencia para la cantidad dada.
        """
        try:
            # 1. Obtener OP y Fecha Meta (sin cambios)
            op_result = self.obtener_orden_por_id(orden_id)
            if not op_result.get('success'):
                return self.error_response("OP no encontrada.", 404)
            op_data = op_result['data']
            fecha_meta_str = op_data.get('fecha_meta')
            if not fecha_meta_str:
                return self.error_response("OP sin fecha meta.", 400)
            fecha_meta = date.fromisoformat(fecha_meta_str)
            cantidad = float(op_data['cantidad_planificada'])

            # 2. Obtener Receta y determinar Línea Óptima y Tiempo de Producción
            receta_model = RecetaModel()
            receta_res = receta_model.find_by_id(op_data['receta_id'], 'id')
            if not receta_res.get('success'):
                return self.error_response("Receta no encontrada.", 404)
            receta = receta_res['data']

            linea_compatible = receta.get('linea_compatible', '2').split(',') # Default a línea 2 si no está definido
            tiempo_prep = receta.get('tiempo_preparacion_minutos', 0)
            tiempo_l1 = receta.get('tiempo_prod_unidad_linea1', 0)
            tiempo_l2 = receta.get('tiempo_prod_unidad_linea2', 0)

            linea_sugerida = 0
            tiempo_prod_unit_elegido = 0

            # --- Lógica de Selección de Línea ---
            # Define tu umbral para considerar "gran cantidad" y justificar la línea 1
            UMBRAL_CANTIDAD_LINEA_1 = 50

            puede_l1 = '1' in linea_compatible and tiempo_l1 > 0
            puede_l2 = '2' in linea_compatible and tiempo_l2 > 0

            if puede_l1 and puede_l2: # Compatible con ambas
                if cantidad >= UMBRAL_CANTIDAD_LINEA_1:
                    linea_sugerida = 1 # Grande -> Línea 1
                    tiempo_prod_unit_elegido = tiempo_l1
                else:
                    linea_sugerida = 2 # Pequeña -> Línea 2 (más barata)
                    tiempo_prod_unit_elegido = tiempo_l2
            elif puede_l1: # Solo compatible con Línea 1
                linea_sugerida = 1
                tiempo_prod_unit_elegido = tiempo_l1
            elif puede_l2: # Solo compatible con Línea 2
                linea_sugerida = 2
                tiempo_prod_unit_elegido = tiempo_l2
            else:
                return self.error_response("La receta no tiene tiempos válidos o compatibilidad de línea definida.", 400)

            # Calcular T_Prod basado en la línea elegida
            t_prod_minutos = tiempo_prep + (tiempo_prod_unit_elegido * cantidad)
            t_prod_dias = math.ceil(t_prod_minutos / 480) # Asumiendo jornada de 8h

            # --- 3. Calcular Tiempo de Aprovisionamiento (T_Proc) (sin cambios) ---
            verificacion_res = self.inventario_controller.verificar_stock_para_op(op_data)
            # ... (la lógica para calcular t_proc_dias se mantiene igual) ...
            insumos_faltantes = verificacion_res['data']['insumos_faltantes']
            t_proc_dias = 0
            if insumos_faltantes:
                # ... (buscar el max(tiempo_entrega_dias)) ...
                 insumo_model = InsumoModel()
                 tiempos_entrega = []
                 for insumo in insumos_faltantes:
                     insumo_data_res = insumo_model.find_by_id(insumo['insumo_id'], 'id_insumo')
                     if insumo_data_res.get('success'):
                         tiempo = insumo_data_res['data'].get('tiempo_entrega_dias', 0)
                         tiempos_entrega.append(tiempo)
                 t_proc_dias = max(tiempos_entrega) if tiempos_entrega else 0


            # --- 4. Calcular Fecha de Inicio Sugerida (sin cambios) ---
            plazo_total_dias = t_prod_dias + t_proc_dias
            fecha_inicio_sugerida = fecha_meta - timedelta(days=plazo_total_dias)

            # --- 5. Añadir Recomendación de Eficiencia ---
            recomendacion_eficiencia = ""
            # Si se sugiere la línea 1 pero la cantidad es baja...
            if linea_sugerida == 1 and cantidad < UMBRAL_CANTIDAD_LINEA_1:
                recomendacion_eficiencia = (f"¡Atención! La cantidad ({cantidad}) es baja para la Línea 1. "
                                            f"Considere si es eficiente encenderla o si puede agrupar con otras OPs.")
            # Si solo es compatible con la 1 y la cantidad es baja...
            elif linea_sugerida == 1 and not puede_l2 and cantidad < UMBRAL_CANTIDAD_LINEA_1:
                 recomendacion_eficiencia = (f"La cantidad ({cantidad}) es baja, pero esta receta solo es compatible con la Línea 1.")


            # 6. Preparar la respuesta detallada
            detalle = {
            'fecha_meta': fecha_meta.isoformat(),
            'linea_sugerida': linea_sugerida,
            'plazo_total_dias': plazo_total_dias,
            't_produccion_dias': t_prod_dias,
            't_aprovisionamiento_dias': t_proc_dias,
            'fecha_inicio_sugerida': fecha_inicio_sugerida.isoformat(),
            'recomendacion_eficiencia': recomendacion_eficiencia,
            'insumos_faltantes': insumos_faltantes
            }

            # --- INICIO NUEVA LÓGICA: GUARDAR SUGERENCIA ---
            datos_para_guardar = {
                'sugerencia_fecha_inicio': detalle['fecha_inicio_sugerida'],
                'sugerencia_plazo_total_dias': detalle['plazo_total_dias'],
                'sugerencia_t_produccion_dias': detalle['t_produccion_dias'],
                'sugerencia_t_aprovisionamiento_dias': detalle['t_aprovisionamiento_dias'],
                'sugerencia_linea': detalle['linea_sugerida']
            }
            # Actualizamos la OP en la base de datos con estos datos
            update_result = self.model.update(orden_id, datos_para_guardar, 'id')
            if not update_result.get('success'):
                # Si falla el guardado, no es crítico, pero sí loggeamos/advertimos
                logger.warning(f"No se pudo guardar la sugerencia calculada para OP {orden_id}. Error: {update_result.get('error')}")
            # --- FIN NUEVA LÓGICA ---

            # 7. Devolver la respuesta detallada (sin cambios)
            return self.success_response(data=detalle)

        except Exception as e:
            logger.error(f"Error en sugerir_fecha_inicio para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def pre_asignar_recursos(self, orden_id: int, data: Dict, usuario_id: int) -> tuple:
        """
        1. Valida compatibilidad de línea.
        2. GUARDA la línea, supervisor y operario asignados.
        3. NO cambia el estado ni aprueba la orden todavía.
        """
        try:
            # 0. Obtener OP y Receta (sin cambios)
            op_result = self.obtener_orden_por_id(orden_id)
            if not op_result.get('success'): return self.error_response("OP no encontrada.", 404)
            op_data = op_result['data']; receta_id = op_data.get('receta_id')

            # 1. Validar datos de entrada (sin cambios)
            linea_asignada = data.get('linea_asignada'); supervisor_id = data.get('supervisor_responsable_id')
            operario_id = data.get('operario_asignado_id')
            if not linea_asignada or linea_asignada not in [1, 2]:
                return self.error_response("Línea inválida.", 400)

            # Validar compatibilidad de línea (sin cambios)
            receta_model = RecetaModel()
            receta_res = receta_model.find_by_id(receta_id, 'id')
            # ... (código de validación de compatibilidad) ...
            if not receta_res.get('success'):
                return self.error_response(f"Receta no encontrada (ID: {receta_id}).", 404)
            receta_data = receta_res['data']
            lineas_compatibles = receta_data.get('linea_compatible', '2').split(',')
            if str(linea_asignada) not in lineas_compatibles:
                return self.error_response(f"Línea {linea_asignada} incompatible. Permitidas: {', '.join(lineas_compatibles)}.", 400)


            # 2. Preparar y actualizar la OP con las asignaciones
            update_data = {
                'linea_asignada': linea_asignada,
                'supervisor_responsable_id': supervisor_id,
                'operario_asignado_id': operario_id
            }
            update_result = self.model.update(orden_id, update_data, 'id')
            if not update_result.get('success'):
                return self.error_response(f"Error al asignar recursos: {update_result.get('error')}", 500)

            # 3. Devolver éxito SIN llamar a aprobar_orden
            # Devolvemos los datos actualizados para referencia
            return self.success_response(data=update_result.get('data'), message="Recursos pre-asignados. Confirme la fecha de inicio.")

        except Exception as e:
            logger.error(f"Error crítico en pre_asignar_recursos para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)


    def confirmar_inicio_y_aprobar(self, orden_id: int, data: Dict, usuario_id: int) -> tuple:
        """
        1. Guarda la fecha de inicio planificada confirmada.
        2. Asigna automáticamente un supervisor de producción.
        3. Ejecuta la lógica de aprobación (verificar stock, reservar/crear OC, cambiar estado).
        """
        try:
            from datetime import time, datetime
            fecha_inicio_confirmada = data.get('fecha_inicio_planificada')
            if not fecha_inicio_confirmada:
                return self.error_response("Debe seleccionar una fecha de inicio.", 400)

            update_data = {'fecha_inicio_planificada': fecha_inicio_confirmada}

            # --- LÓGICA DE ASIGNACIÓN AUTOMÁTICA DE SUPERVISOR ---
            supervisores_resp, status_code = self.usuario_controller.obtener_usuarios_por_rol(['SUPERVISOR'])

            if status_code != 200:
                # Si falla la obtención de supervisores, no es un error fatal.
                # Se registra una advertencia y se procede sin asignar supervisor.
                error_message = supervisores_resp.get('error', 'Error desconocido') if isinstance(supervisores_resp, dict) else str(supervisores_resp)
                logger.warning(f"No se pudieron obtener supervisores para asignación automática: {error_message}. La orden se aprobará sin supervisor.")
                supervisores = [] # Asegurarse de que la lista esté vacía para continuar
            else:
                supervisores = supervisores_resp.get('data', [])

            # TODO: Usar la hora real de la OP si está disponible. Por ahora, asumimos el inicio del turno de la mañana.
            target_time = time(8, 0, 0)
            assigned_supervisor_id = None

            for supervisor in supervisores:
                in_produccion = any(s and s.get('codigo') == 'PRODUCCION' for s in supervisor.get('sectores', []))
                if not in_produccion:
                    continue

                turno = supervisor.get('turno')
                if turno and turno.get('hora_inicio') and turno.get('hora_fin'):
                    try:
                        hora_inicio = time.fromisoformat(turno['hora_inicio'])
                        hora_fin = time.fromisoformat(turno['hora_fin'])

                        if hora_inicio <= hora_fin:
                            if hora_inicio <= target_time < hora_fin:
                                assigned_supervisor_id = supervisor.get('id')
                                break
                        else:
                            if target_time >= hora_inicio or target_time < hora_fin:
                                assigned_supervisor_id = supervisor.get('id')
                                break
                    except (ValueError, TypeError) as e:
                        logger.warning(f"No se pudo parsear el turno para supervisor {supervisor.get('id')}: {e}")

            if assigned_supervisor_id:
                update_data['supervisor_responsable_id'] = assigned_supervisor_id
                logger.info(f"Supervisor {assigned_supervisor_id} asignado automáticamente a la OP {orden_id}.")
            # --- FIN DE LA LÓGICA DE ASIGNACIÓN ---

            update_result = self.model.update(orden_id, update_data, 'id')
            if not update_result.get('success'):
                return self.error_response(f"Error al guardar fecha y supervisor: {update_result.get('error')}", 500)

            aprobacion_dict, aprobacion_status_code = self.aprobar_orden(orden_id, usuario_id)

            if aprobacion_dict.get('success'):
                 aprobacion_dict['message'] = f"Inicio confirmado para {fecha_inicio_confirmada}. {aprobacion_dict.get('message', '')}"

            return aprobacion_dict, aprobacion_status_code

        except Exception as e:
            logger.error(f"Error crítico en confirmar_inicio_y_aprobar para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def obtener_conteo_ordenes_reabiertas(self) -> int:
        """Obtiene el conteo de órdenes en estado de reproceso."""
        try:
            result = self.model.find_all(filters={'estado': 'REPROCESO'})
            if result.get('success'):
                return len(result.get('data', []))
            return 0
        except Exception as e:
            logger.error(f"Error contando órdenes en reproceso: {str(e)}")
            return 0

    def obtener_datos_para_tablero(self) -> Dict:
        """
        Prepara los datos necesarios para el tablero Kanban de producción.
        """
        from collections import defaultdict
        from datetime import datetime, timedelta

        try:
            # 1. Definir las columnas del tablero
            columnas = {
                'EN ESPERA': 'En Espera',
                'LISTA PARA PRODUCIR': 'Lista para producir',
                'EN_LINEA_1': 'Línea 1',
                'EN_LINEA_2': 'Línea 2',
                'EN_EMPAQUETADO': 'Empaquetado',
                'CONTROL_DE_CALIDAD': 'Control de Calidad',
            }

            # 2. Obtener todas las órdenes de producción relevantes
            response, status_code = self.obtener_ordenes({'estado.neq': 'CANCELADA'})
            ordenes = []
            if status_code == 200 and response.get('success'):
                ordenes = response.get('data', [])

            # 3. Agrupar órdenes por estado
            ordenes_por_estado = defaultdict(list)

            for orden in ordenes:
                estado = orden.get('estado')
                if estado in columnas:
                    ordenes_por_estado[estado].append(orden)

            # 4. Obtener datos para los modales (supervisores y operarios)
            todos_los_usuarios = self.usuario_controller.obtener_todos_los_usuarios()
            supervisores = [u for u in todos_los_usuarios if u.get('roles', {}).get('codigo') == 'SUPERVISOR']
            operarios = [u for u in todos_los_usuarios if u.get('roles', {}).get('codigo') == 'OPERARIO']

            return {
                'columnas': columnas,
                'ordenes_por_estado': dict(ordenes_por_estado),
                'supervisores': supervisores,
                'operarios': operarios,
                'now': datetime.now(),
                'timedelta': timedelta
            }
        except Exception as e:
            logger.error(f"Error en obtener_datos_para_tablero: {e}", exc_info=True)
            return {
                'columnas': {}, 'ordenes_por_estado': {}, 'supervisores': [], 'operarios': [],
                'now': datetime.now(), 'timedelta': timedelta, 'error': str(e)
            }

    def obtener_datos_para_vista_foco(self, orden_id: int) -> tuple:
        """
        Prepara todos los datos necesarios para la vista de foco de una orden de producción.
        Enriquece los ingredientes con la cantidad total requerida para la OP.
        """
        try:
            # 1. Obtener los datos principales de la orden
            orden_result = self.obtener_orden_por_id(orden_id)
            if not orden_result.get('success'):
                return self.error_response("Orden de producción no encontrada.", 404)
            orden_data = orden_result['data']

            # 2. Obtener los ingredientes de la receta y calcular totales
            receta_id = orden_data.get('receta_id')
            ingredientes = []
            cantidad_planificada = float(orden_data.get('cantidad_planificada', 0))

            if receta_id:
                receta_model = RecetaModel()
                # --- NUEVO: Obtener reservas para calcular 'Max Desperdiciable' ---
                # Usamos el modelo del controlador de inventario ya instanciado
                reserva_model = self.inventario_controller.reserva_insumo_model
                
                # Buscamos TODAS las reservas (Reservado/Consumido) asociadas a esta OP
                reservas_op_res = reserva_model.find_all({'orden_produccion_id': orden_id})
                mapa_reservas = {}
                mapa_lotes_insumos = {} # Para mapear lotes a insumos y calcular merma
                
                if reservas_op_res.get('success'):
                    for res in reservas_op_res.get('data', []):
                        # Intentamos ambas variantes comunes por seguridad
                        iid = res.get('insumo_id') or res.get('id_insumo')
                        lid = res.get('lote_inventario_id')
                        qty = float(res.get('cantidad_reservada', 0))
                        
                        if iid:
                            mapa_reservas[iid] = mapa_reservas.get(iid, 0.0) + qty
                            # Log para depuración
                            estado_res = res.get('estado', 'UNKNOWN')
                            logger.info(f"Reserva encontrada para insumo {iid}: {qty} (Estado: {estado_res})")
                        else:
                            logger.warning(f"Reserva sin ID de insumo detectada: {res}")
                        if lid and iid:
                            mapa_lotes_insumos[lid] = iid

                # Obtener Merma acumulada para restar del disponible
                mermas_res = self.registro_merma_model.find_all({'orden_produccion_id': orden_id})
                mapa_mermas = {}
                if mermas_res.get('success'):
                    for m in mermas_res.get('data', []):
                        qty = float(m.get('cantidad', 0))
                        lid = m.get('lote_insumo_id')
                        # Intentar obtener insumo_id del mapa de lotes
                        iid = mapa_lotes_insumos.get(lid)
                        if iid:
                            mapa_mermas[iid] = mapa_mermas.get(iid, 0.0) + qty

                cantidad_producida_actual = float(orden_data.get('cantidad_producida', 0))

                ingredientes_result = receta_model.get_ingredientes(receta_id)
                if ingredientes_result.get('success'):
                    ingredientes_raw = ingredientes_result.get('data', [])
                    for ing in ingredientes_raw:
                        cantidad_unitaria = float(ing.get('cantidad', 0))
                        ing['cantidad_unitaria'] = cantidad_unitaria
                        ing['cantidad_total_requerida'] = round(cantidad_unitaria * cantidad_planificada, 4)
                        
                        # --- CÁLCULO DINÁMICO DEL DISPONIBLE PARA MERMA ---
                        # 1. Total Asignado (Reservas actuales en DB, incluye lo refilleado)
                        # Usamos 'id_insumo' que ahora viene asegurado desde el modelo (raw id de receta_ingredientes)
                        key_insumo = ing.get('id_insumo')
                            
                        total_asignado_actual = mapa_reservas.get(key_insumo, 0.0)
                        
                        # 2. Consumo Teórico (Lo que "debería" haberse gastado para lo producido OK)
                        consumo_teorico = cantidad_unitaria * cantidad_producida_actual

                        # 3. Total Mermado (Lo que ya se perdió y se refilleó)
                        total_merma = mapa_mermas.get(key_insumo, 0.0)
                        
                        # 4. Disponible Real = Asignado - Consumo Teórico - Merma
                        disponible_real = max(0.0, total_asignado_actual - consumo_teorico - total_merma)
                        
                        logger.info(f"Cálculo Disponible Insumo {key_insumo}: Asignado={total_asignado_actual}, Unitario={cantidad_unitaria}, Producido={cantidad_producida_actual} -> Teórico={consumo_teorico}, Merma={total_merma} -> Disponible={disponible_real}")
                        
                        ing['disponible_real'] = round(disponible_real, 4)
                        ing['asignado_real'] = round(total_asignado_actual, 4)
                        ingredientes.append(ing)

            # 3. Calcular Ritmo Objetivo
            orden_data['ritmo_objetivo'] = self._calcular_ritmo_objetivo(orden_data)

            # 3. Obtener los motivos de paro y desperdicio
            motivo_paro_model = MotivoParoModel()
            motivos_paro_result = motivo_paro_model.find_all()
            motivos_paro = motivos_paro_result.get('data', []) if motivos_paro_result.get('success') else []

            motivo_desperdicio_model = MotivoDesperdicioModel()
            motivos_desperdicio_result = motivo_desperdicio_model.find_all()
            motivos_desperdicio = motivos_desperdicio_result.get('data', []) if motivos_desperdicio_result.get('success') else []

            # --- NUEVO: MOTIVOS MERMA (INSUMOS) ---
            motivo_merma_model = MotivoDesperdicioLoteModel()
            motivos_merma_result = motivo_merma_model.get_all()
            motivos_merma = motivos_merma_result.get('data', []) if motivos_merma_result.get('success') else []

            # --- NUEVO: OBTENER TRASPASO PENDIENTE ---
            traspaso_pendiente_result = self.traspaso_turno_model.find_latest_pending_by_op_id(orden_id)
            traspaso_pendiente = traspaso_pendiente_result.get('data') if traspaso_pendiente_result.get('success') else None

            # --- NUEVO: OBTENER UNIDAD DE MEDIDA Y TURNO ACTUAL ---
            producto_id = orden_data.get('producto_id')
            producto_data = self.producto_controller.obtener_producto_por_id(producto_id).get('data', {})
            orden_data['producto_unidad_medida'] = producto_data.get('unidad_medida', 'unidades')

            from app.models.usuario_turno import UsuarioTurnoModel
            turno_model = UsuarioTurnoModel()
            turno_actual_result = turno_model.find_current_shift()
            turno_actual = turno_actual_result.get('data') if turno_actual_result.get('success') else {}

            # --- NUEVO: OBTENER TOTAL DESPERDICIO ---
            desperdicio_model = RegistroDesperdicioModel()
            desperdicios_result = desperdicio_model.find_all(filters={'orden_produccion_id': orden_id})
            total_desperdicio = 0
            if desperdicios_result.get('success'):
                total_desperdicio = sum(Decimal(d.get('cantidad', 0)) for d in desperdicios_result.get('data', []))
            orden_data['total_desperdicio'] = total_desperdicio


            # 4. Ensamblar todos los datos
            datos_completos = {
                'orden': orden_data,
                'ingredientes': ingredientes,
                'motivos_paro': motivos_paro,
                'motivos_desperdicio': motivos_desperdicio,
                'motivos_merma': motivos_merma, # <-- Añadido para reporte de insumos
                'traspaso_pendiente': traspaso_pendiente, # <-- Añadir al contexto
                'turno_actual': turno_actual
            }

            return self.success_response(data=datos_completos)

        except Exception as e:
            logger.error(f"Error en obtener_datos_para_vista_foco para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    # endregion

    # region Lógica de Traspaso de Turno

    def crear_traspaso_de_turno(self, orden_id: int, data: Dict, usuario_saliente_id: int) -> tuple:
        """
        Crea un registro de traspaso de turno cuando un operario pausa por "Cambio de Turno".
        """
        try:
            # 1. Preparar y validar los datos para el traspaso
            datos_traspaso = {
                "orden_produccion_id": orden_id,
                "usuario_saliente_id": usuario_saliente_id,
                "fecha_traspaso": datetime.now().isoformat(),
                "notas_novedades": data.get("notas_novedades"),
                "notas_insumos": data.get("notas_insumos"),
                "resumen_produccion": data.get("resumen_produccion", {})
            }
            validated_data = self.traspaso_turno_schema.load(datos_traspaso)

            # 2. Crear el registro en la base de datos
            result = self.traspaso_turno_model.create(validated_data)

            if result.get('success'):
                return self.success_response(data=result.get('data'), message="Traspaso de turno registrado.")
            else:
                return self.error_response(f"No se pudo crear el traspaso: {result.get('error')}", 500)

        except ValidationError as e:
            return self.error_response(f"Datos de traspaso inválidos: {e.messages}", 400)
        except Exception as e:
            logger.error(f"Error al crear traspaso para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def aceptar_traspaso_de_turno(self, orden_id: int, traspaso_id: int, usuario_entrante_id: int) -> tuple:
        """
        Marca un traspaso como recibido por el operario entrante y reanuda la producción.
        """
        try:
            # 1. Actualizar el registro de traspaso con el usuario entrante
            update_data = {
                "usuario_entrante_id": usuario_entrante_id,
                "fecha_recepcion": datetime.now().isoformat()
            }
            update_result = self.traspaso_turno_model.update(traspaso_id, update_data)
            if not update_result.get('success'):
                return self.error_response(f"Error al confirmar el traspaso: {update_result.get('error')}", 500)

            # 2. Reanudar la producción (esto ya cambia el estado de la OP a EN_PROCESO)
            return self.reanudar_produccion(orden_id, usuario_entrante_id)

        except Exception as e:
            logger.error(f"Error al aceptar traspaso {traspaso_id} para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    # endregion

    # region Helpers de Aprobación

    def _validar_estado_para_aprobacion(self, orden_id: int) -> tuple:
        """Obtiene una OP y valida que su estado sea 'PENDIENTE'."""
        orden_result = self.obtener_orden_por_id(orden_id)
        if not orden_result.get('success'):
            return None, self.error_response("Orden de producción no encontrada.", 404)

        orden_produccion = orden_result['data']
        if orden_produccion['estado'] != 'PENDIENTE':
            return None, self.error_response(f"La orden ya está en estado '{orden_produccion['estado']}'.", 400)

        return orden_produccion, None

    def _gestionar_stock_faltante(self, orden_produccion: Dict, insumos_faltantes: List[Dict], usuario_id: int) -> tuple:
        """
        Gestiona el caso donde falta stock, generando una o más OCs (una por proveedor)
        y actualizando el estado de la OP.
        """
        orden_id = orden_produccion['id']
        logger.info(f"Stock insuficiente para OP {orden_id}. Generando OC(s)...")

        oc_result = self._generar_orden_de_compra_automatica(insumos_faltantes, usuario_id, orden_id)

        if not oc_result.get('success'):
            return self.error_response(f"Stock insuficiente, pero no se pudo generar la OC: {oc_result.get('error')}", 500)

        ocs_creadas = oc_result.get('data', [])
        if not ocs_creadas:
            return self.error_response("Se reportó éxito en la creación de OCs, pero no se devolvieron datos.", 500)

        # Vincular la OP con la PRIMERA OC creada para mantener una referencia de trazabilidad simple.
        primera_oc = ocs_creadas[0]
        primer_oc_id = primera_oc.get('id')
        primer_oc_codigo = primera_oc.get('codigo_oc', f"ID {primer_oc_id}")

        if primer_oc_id:
            logger.info(f"Vinculando OP {orden_id} con la primera OC generada: {primer_oc_codigo}...")
            self.model.update(orden_id, {'orden_compra_id': primer_oc_id}, 'id')
        else:
            logger.error(f"Se crearon OCs para la OP {orden_id}, pero la primera OC no tiene un ID para vincular.")

        logger.info(f"Cambiando estado de OP {orden_id} a EN ESPERA.")
        self.model.cambiar_estado(orden_id, 'EN ESPERA')

        # Construir un mensaje claro para el usuario
        if len(ocs_creadas) > 1:
            codigos_ocs = [oc.get('codigo_oc', f"ID {oc.get('id')}") for oc in ocs_creadas]
            message = f"Stock insuficiente. Se generaron {len(ocs_creadas)} OCs ({', '.join(codigos_ocs)}) y la OP está 'En Espera'."
        else:
            message = f"Stock insuficiente. Se generó la OC {primer_oc_codigo} y la OP está 'En Espera'."

        detalle = f"Se aprobó la orden de producción {orden_produccion.get('codigo')}. {message}"
        self.registro_controller.crear_registro(get_current_user(), 'Ordenes de produccion', 'Aprobación', detalle)
        return self.success_response(
            data={'oc_generada': True, 'ocs_creadas': ocs_creadas},
            message=message
        )

    def _gestionar_stock_disponible(self, orden_produccion: Dict, usuario_id: int) -> tuple:
        """Gestiona el caso donde hay stock disponible, reservando y actualizando el estado."""
        orden_id = orden_produccion['id']
        logger.info(f"Stock disponible para OP {orden_id}. Reservando insumos...")

        # --- INICIO DE LA MODIFICACIÓN ---
        # Llamar al método del InventarioController para que cree los registros de reserva.
        reserva_result = self.inventario_controller.reservar_stock_insumos_para_op(orden_produccion, usuario_id)
        if not reserva_result.get('success'):
            # Si la reserva falla por cualquier motivo, no se debe continuar.
            return self.error_response(f"Fallo crítico al reservar insumos: {reserva_result.get('error')}", 500)
        # --- FIN DE LA MODIFICACIÓN ---

        nuevo_estado_op = 'LISTA PARA PRODUCIR'
        logger.info(f"Cambiando estado de OP {orden_id} a {nuevo_estado_op}.")
        estado_change_result = self.model.cambiar_estado(orden_id, nuevo_estado_op)
        if not estado_change_result.get('success'):
            logger.error(f"Error al cambiar estado a {nuevo_estado_op} para OP {orden_id}: {estado_change_result.get('error')}")
            # Considerar revertir la reserva si el cambio de estado falla
            return self.error_response(f"Error al cambiar estado a {nuevo_estado_op}: {estado_change_result.get('error')}", 500)

        message = f"Stock disponible. La orden está '{nuevo_estado_op}' y los insumos reservados."
        detalle = f"Se aprobó la orden de producción {orden_produccion.get('codigo')}. {message}"
        self.registro_controller.crear_registro(get_current_user(), 'Ordenes de produccion', 'Aprobación', detalle)
        return self.success_response(
            message=message
        )

    # endregion

    # region Helpers de Consolidación

    def _validar_y_obtener_ops_para_consolidar(self, op_ids: List[int]) -> tuple:
        """Valida que las OPs existan, sean del mismo producto y estén en estado 'PENDIENTE'."""
        ops_a_consolidar_res = self.model.find_by_ids(op_ids)
        if not ops_a_consolidar_res.get('success') or not ops_a_consolidar_res.get('data'):
            return None, {'success': False, 'error': 'Una o más órdenes no fueron encontradas.'}

        ops_originales = ops_a_consolidar_res['data']
        if len(ops_originales) != len(op_ids):
            return None, {'success': False, 'error': 'Algunas órdenes no pudieron ser cargadas.'}

        primer_producto_id = ops_originales[0]['producto_id']
        if not all(op['producto_id'] == primer_producto_id for op in ops_originales):
            return None, {'success': False, 'error': 'Todas las órdenes deben ser del mismo producto.'}

        return ops_originales, None

    def _calcular_datos_super_op(self, ops_originales: List[Dict], op_ids: List[int]) -> Dict:
        """Calcula los datos consolidados para la nueva Super OP."""
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

        return {
            'productos': [{
                'id': primera_op['producto_id'],
                'cantidad': str(cantidad_total)
            }],
            'fecha_planificada': primera_op.get('fecha_planificada'),
            'receta_id': primera_op['receta_id'],
            'fecha_meta': fecha_meta_mas_temprana.isoformat() if fecha_meta_mas_temprana else None,
            'prioridad': 'ALTA',
            'observaciones': f'Super OP consolidada desde las OPs: {", ".join(map(str, op_ids))}',
            'estado': 'PENDIENTE',
            'es_consolidada': True
        }

    def _relinkear_items_pedido(self, op_ids: List[int], super_op_id: int) -> dict:
        """Actualiza los items de pedido de las OPs originales para que apunten a la nueva Super OP."""
        try:
            self.pedido_model.db.table('pedido_items').update({
                'orden_produccion_id': super_op_id
            }).in_('orden_produccion_id', op_ids).execute()
            logger.info(f"Relinkeo de items de pedido a Super OP {super_op_id} completado.")
            return {'success': True}
        except Exception as e:
            logger.error(f"CRÍTICO: Fallo al re-linkear items de pedido a Super OP {super_op_id}. Error: {e}", exc_info=True)
            return {'success': False, 'error': f'La Super OP fue creada, pero falló la asignación de pedidos. Contacte a soporte. Error: {str(e)}'}

    def _actualizar_ops_originales(self, op_ids: List[int], super_op_id: int):
        """Marca las OPs originales como 'CONSOLIDADA' y las vincula a la Super OP."""
        update_data = {
            'estado': 'CONSOLIDADA'
            # 'super_op_id': super_op_id # <-- Columna no existe, comentado
        }
        for op_id in op_ids:
            self.model.update(id_value=op_id, data=update_data, id_field='id')
        logger.info(f"OPs originales {op_ids} actualizadas a estado CONSOLIDADA.")

    def _obtener_capacidad_linea(self, linea_id: int, fecha: date) -> Decimal:
        """
        Obtiene la capacidad neta de una línea para una fecha específica.
        --- CORREGIDO ---
        Ahora extrae el valor 'neta' del diccionario devuelto
        por el planificacion_controller.
        """
        try:
            if not linea_id or not fecha:
                return Decimal(0)

            if not self.planificacion_controller:
                 self.planificacion_controller = PlanificacionController()

            # 1. Llamar a la función que devuelve el mapa
            capacidad_map = self.planificacion_controller.obtener_capacidad_disponible(
                [linea_id], fecha, fecha
            )

            fecha_iso = fecha.isoformat()

            # 2. Extraer el diccionario de capacidad para ese día
            # (Ej: {'neta': 480.0, 'bloqueado': 0.0, ...})
            capacidad_dict_dia = capacidad_map.get(linea_id, {}).get(fecha_iso, {})

            # 3. Obtener el valor 'neta' (¡Esta es la corrección!)
            capacidad_en_minutos = capacidad_dict_dia.get('neta', 0.0)

            # El resto de la función (línea 1132 del traceback) ahora funcionará
            return Decimal(str(capacidad_en_minutos))

        except Exception as e:
            logger.error(f"Error en _obtener_capacidad_linea para {linea_id} en {fecha}: {e}", exc_info=True)
            return Decimal(0)

    def _calcular_ritmo_objetivo(self, orden: Dict) -> Decimal:
        """
        Calcula el ritmo objetivo en kg/h basado en tiempo disponible y capacidad.
        """
        from datetime import datetime, date

        ritmo_necesario = Decimal('0.0')

        # Método 1: Basado en tiempo disponible hasta la fecha meta
        try:
            fecha_meta_str = orden.get('fecha_meta')
            if fecha_meta_str:
                # Handle ISO format with or without time (T or space separator)
                fecha_clean = fecha_meta_str.split('T')[0].split(' ')[0]
                fecha_meta = date.fromisoformat(fecha_clean)
                dias_disponibles = (fecha_meta - date.today()).days

                if dias_disponibles > 0:
                    capacidad_total_horizonte_minutos = Decimal('0.0')
                    for i in range(dias_disponibles):
                        fecha_a_consultar = date.today() + timedelta(days=i)
                        capacidad_total_horizonte_minutos += self._obtener_capacidad_linea(
                            orden.get('linea_asignada'), fecha_a_consultar
                        )

                    horas_disponibles = capacidad_total_horizonte_minutos / Decimal('60.0')
                    cantidad_planificada = Decimal(orden.get('cantidad_planificada', '0.0'))

                    if horas_disponibles > 0:
                        ritmo_necesario = cantidad_planificada / horas_disponibles
        except Exception as e:
            logger.warning(f"No se pudo calcular el ritmo necesario por tiempo para OP {orden.get('id')}: {e}")

        # Método 2: Basado en capacidad de la línea para el día de hoy (como referencia)
        capacidad_linea_hoy_minutos = self._obtener_capacidad_linea(orden.get('linea_asignada'), date.today())

        ritmo_por_capacidad = Decimal('0.0')
        if capacidad_linea_hoy_minutos > 0:
            # Para obtener kg/h, necesitamos saber cuántos kg se pueden hacer en esos minutos.
            # Esto depende del tiempo de producción unitario de la receta.
            receta_result = self.receta_model.find_by_id(orden.get('receta_id'), 'id')
            if receta_result.get('success'):
                receta = receta_result['data']
                campo_tiempo = f"tiempo_prod_unidad_linea{orden.get('linea_asignada')}"
                tiempo_por_unidad = Decimal(receta.get(campo_tiempo, '0.0'))

                if tiempo_por_unidad > 0:
                    unidades_por_hora = Decimal('60.0') / tiempo_por_unidad
                    # Asumiendo que 1 unidad = 1 kg. Esto podría necesitar ajuste.
                    ritmo_por_capacidad = unidades_por_hora

        # Usar el mayor de los dos (más exigente) o un default de 5 si ambos fallan
        ritmo_final = max(ritmo_necesario, ritmo_por_capacidad)

        return round(ritmo_final, 2) if ritmo_final > 0 else Decimal('5.00')


    # endregion

    def confirmar_ampliacion_op_por_desperdicio(self, orden_id: int, data: Dict, usuario_id: int) -> tuple:
        """
        Endpoint llamado tras la confirmación del usuario para ampliar una OP
        y cubrir el desperdicio usando stock disponible.
        """
        try:
            desperdicio_a_cubrir = Decimal(data.get('desperdicio_a_cubrir', '0'))
            if desperdicio_a_cubrir <= 0:
                return self.error_response("La cantidad de desperdicio a cubrir debe ser mayor a cero.", 400)

            orden_actual_res = self.model.find_by_id(orden_id)
            if not orden_actual_res.get('success'):
                return self.error_response("Orden no encontrada.", 404)
            orden_actual = orden_actual_res['data']

            # Doble chequeo: Verificar que aún haya stock antes de consumir
            orden_simulada = {'receta_id': orden_actual['receta_id'], 'cantidad_planificada': float(desperdicio_a_cubrir)}
            stock_check = self.inventario_controller.verificar_stock_para_op(orden_simulada)
            if not stock_check.get('success') or stock_check['data']['insumos_faltantes']:
                return self.error_response("El stock que estaba disponible ya no lo está. No se puede ampliar la orden.", 409)

            # Consumir el stock para el desperdicio
            self.inventario_controller.consumir_stock_por_cantidad_producto(
                receta_id=orden_actual['receta_id'],
                cantidad_producto=float(desperdicio_a_cubrir),
                op_id_referencia=orden_id,
                motivo='DESPERDICIO_PRODUCCION'
            )

            # Ampliar la cantidad planificada de la OP actual
            nueva_cantidad_planificada = Decimal(orden_actual['cantidad_planificada']) + desperdicio_a_cubrir
            self.model.update(orden_id, {'cantidad_planificada': nueva_cantidad_planificada})

            message = f"Confirmado. Se cubrió el desperdicio ({desperdicio_a_cubrir:.2f} kg) con stock. La orden se ha ampliado. Nueva meta: {nueva_cantidad_planificada:.2f} kg."
            detalle_log = f"Ampliación de OP {orden_actual.get('codigo')} confirmada por usuario para cubrir desperdicio de {desperdicio_a_cubrir:.2f} kg."
            self.registro_controller.crear_registro(get_current_user(), 'Ordenes de produccion', 'Ampliación por Desperdicio', detalle_log)

            return self.success_response(
                message=message,
                data={'nueva_cantidad_planificada': float(nueva_cantidad_planificada)}
            )

        except Exception as e:
            logger.error(f"Error en confirmar_ampliacion_op_por_desperdicio para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)


    def reportar_avance(self, orden_id: int, data: Dict, usuario_id: int) -> tuple:
        """
        Registra el avance de producción, implementando la lógica de "Punto de Control"
        al alcanzar la cantidad planificada para gestionar el desperdicio.
        """
        try:
            # 1. Validación de datos de entrada
            cantidad_buena = Decimal(data.get('cantidad_buena', '0'))
            cantidad_desperdicio = Decimal(data.get('cantidad_desperdicio', '0'))
            motivo_desperdicio_id = data.get('motivo_desperdicio_id')

            if cantidad_buena < 0 or cantidad_desperdicio < 0:
                return self.error_response("Las cantidades no pueden ser negativas.", 400)

            # 2. Obtener estado actual de la OP
            orden_actual_res = self.model.find_by_id(orden_id)
            if not orden_actual_res.get('success'): return self.error_response("Orden no encontrada.", 404)
            orden_actual = orden_actual_res['data']

            # 3. Calcular totales y validar sobreproducción
            cantidad_planificada = Decimal(orden_actual.get('cantidad_planificada', 0))
            cantidad_producida_actual = Decimal(orden_actual.get('cantidad_producida', 0))

            # La validación no debe ser sobre el total procesado, sino sobre la cantidad BUENA.
            # Esto permite "sobre-procesar" para cubrir desperdicios.
            cantidad_buena_proyectada = cantidad_producida_actual + cantidad_buena
            if cantidad_buena_proyectada > cantidad_planificada:
                 return self.error_response(f"El reporte de {cantidad_buena:.2f} unidades buenas excede la cantidad planificada de {cantidad_planificada}. La producción buena total sería {cantidad_buena_proyectada:.2f}.", 400)

            # 4. Registrar avance (siempre se hace)
            update_data = {'cantidad_producida': cantidad_producida_actual + cantidad_buena}
            nuevo_desperdicio_record = None

            if cantidad_desperdicio > 0:
                create_res = RegistroDesperdicioModel().create({
                    'orden_produccion_id': orden_id, 'motivo_desperdicio_id': int(motivo_desperdicio_id),
                    'cantidad': cantidad_desperdicio, 'usuario_id': usuario_id, 'fecha_registro': datetime.now().isoformat()
                })
                if create_res.get('success'):
                    nuevo_desperdicio_record = create_res.get('data')

            # 5. Lógica de "Punto de Control"
            # Se recalcula el total procesado para saber si llegamos al punto de control.
            # Nota: find_all podría incluir o no el nuevo registro dependiendo de la consistencia de lectura inmediata.
            # Para ser seguros, usamos la suma de la DB y le restamos el nuevo si está duplicado, o confiamos en el acumulado.
            # Mejor enfoque: Consultar todo. Si el nuevo no aparece, sumarlo manualmente para la lógica.

            desperdicios_db = RegistroDesperdicioModel().find_all({'orden_produccion_id': orden_id}).get('data', [])

            # Verificar si el nuevo registro ya está en la lista de la DB (por ID)
            nuevo_id = nuevo_desperdicio_record.get('id') if nuevo_desperdicio_record else None
            ids_en_db = {d['id'] for d in desperdicios_db}

            if nuevo_desperdicio_record and nuevo_id not in ids_en_db:
                desperdicios_db.append(nuevo_desperdicio_record)

            total_desperdicio_acumulado = sum(Decimal(d.get('cantidad', '0')) for d in desperdicios_db)

            # El total procesado es: Lo que ya había producido + Lo nuevo bueno + Todo el desperdicio acumulado (que incluye el nuevo)
            total_procesado_ahora = cantidad_producida_actual + cantidad_buena + total_desperdicio_acumulado

            response_data = {}
            response_message = "Avance reportado correctamente."

            if total_procesado_ahora >= cantidad_planificada:

                if total_desperdicio_acumulado > 0:
                    # Gestionar desperdicio (Reponer o Hija)
                    # Pasamos la lista completa de desperdicios (incluyendo el nuevo) para que el helper sepa qué reponer.
                    gestion_res = self._gestionar_desperdicio_en_punto_de_control(orden_actual, total_desperdicio_acumulado, usuario_id, desperdicios_db)
                    if not gestion_res.get('success'):
                        return self.error_response(gestion_res.get('error', 'Error al gestionar desperdicio.'), 500)

                    response_data = gestion_res.get('data', {})
                    response_message = gestion_res.get('message', response_message)

                    if response_data.get('accion') == 'finalizar_op_crear_hija':
                         # Ya se finalizó en el helper. Solo actualizamos cantidad producida.
                         self.model.update(orden_id, update_data)
                         return self.success_response(message=response_message, data=response_data)

                # Si llegamos aquí, o no había desperdicio, o se repuso (accion='continuar').
                # Verificamos si alcanzamos la meta de BUENAS.
                nueva_cantidad_buena = update_data['cantidad_producida']
                if nueva_cantidad_buena >= cantidad_planificada:
                    update_data['estado'] = 'CONTROL_DE_CALIDAD'
                    update_data['fecha_fin'] = datetime.now().isoformat()
                    response_message += " Orden completada."

            self.model.update(orden_id, update_data)
            return self.success_response(message=response_message, data=response_data)

        except Exception as e:
            logger.error(f"Error en reportar_avance para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    def _gestionar_desperdicio_en_punto_de_control(self, orden_actual: Dict, desperdicio_total: Decimal, usuario_id: int, waste_list: Optional[List[Dict]] = None) -> Dict:
        """
        Lógica transaccional para gestionar el desperdicio al alcanzar el punto de control.
        MODIFICADO: Ahora intenta reponer automáticamente sin preguntar al usuario.
        Acepta waste_list opcional para evitar latencia de DB.
        """
        orden_id = orden_actual['id']
        desperdicio_model = RegistroDesperdicioModel()

        # 1. Calcular desperdicio NO repuesto
        # Usamos la lista provista o consultamos la DB si no existe.
        if waste_list is None:
             waste_list = desperdicio_model.find_all({'orden_produccion_id': orden_id}).get('data', [])

        unreplenished_waste_items = []
        cantidad_a_reponer = Decimal(0)

        for w in waste_list:
            obs = w.get('observaciones') or ''
            if '[REPUESTO]' not in obs:
                unreplenished_waste_items.append(w)
                cantidad_a_reponer += Decimal(w.get('cantidad', 0))

        if cantidad_a_reponer <= 0:
             # Si todo está repuesto, permitimos continuar sin acción.
             return {'success': True, 'message': 'Desperdicio ya cubierto previamente.', 'data': {'accion': 'continuar'}}

        # 2. Verificar stock para la cantidad PENDIENTE de reponer
        orden_simulada = {'receta_id': orden_actual['receta_id'], 'cantidad_planificada': float(cantidad_a_reponer)}
        stock_check = self.inventario_controller.verificar_stock_para_op(orden_simulada)

        # --- CASO A: HAY STOCK SUFICIENTE -> REPONER AUTOMÁTICAMENTE ---
        if stock_check.get('success') and not stock_check['data']['insumos_faltantes']:
            logger.info(f"Stock disponible para {cantidad_a_reponer} de desperdicio en OP {orden_id}. Reponiendo automáticamente.")

            consume_res = self.inventario_controller.consumir_stock_por_cantidad_producto(
                receta_id=orden_actual['receta_id'],
                cantidad_producto=float(cantidad_a_reponer),
                op_id_referencia=orden_id,
                motivo='REPOSICION_AUTOMATICA_DESPERDICIO'
            )

            if not consume_res.get('success'):
                return {'success': False, 'error': f"Error al consumir stock: {consume_res.get('error')}"}

            # Marcar como repuesto
            for w in unreplenished_waste_items:
                new_obs = (w.get('observaciones') or '') + ' [REPUESTO]'
                desperdicio_model.update(w['id'], {'observaciones': new_obs})

            return {
                'success': True,
                'data': {
                    'accion': 'continuar', # Indica al frontend/controller que seguimos
                    'cantidad_repuesta': float(cantidad_a_reponer)
                }
            }

        # --- CASO B: NO HAY STOCK SUFICIENTE -> CREAR OP HIJA ---
        else:
            logger.warning(f"Stock insuficiente para desperdicio en OP {orden_id}. Intentando crear OP hija para {cantidad_a_reponer}.")

            # Usamos la cantidad NO repuesta para la OP hija
            desperdicio_total = cantidad_a_reponer # Actualizamos la variable para usarla abajo

            # --- INICIO DE LA NUEVA LÓGICA DE HERENCIA ---
            # 1. Buscar el pedido_id original a través de los items de la OP padre
            pedido_id_original = None
            items_padre_res = self.pedido_model.find_all_items({'orden_produccion_id': orden_id})
            if items_padre_res.get('success') and items_padre_res.get('data'):
                pedido_id_original = items_padre_res['data'][0].get('pedido_id')

            # 2. Preparar datos para la OP hija, incluyendo los heredados.
            productos_para_op_hija = [{
                'id': orden_actual['producto_id'],
                'cantidad': float(desperdicio_total)
            }]
            # --- INICIO CORRECCIÓN DEFINITIVA DE FORMATO DE FECHA ---
            # Convertir la fecha_meta a string 'YYYY-MM-DD' de forma robusta.
            fecha_meta_padre = orden_actual.get('fecha_meta')
            fecha_meta_str = None
            if isinstance(fecha_meta_padre, datetime):
                fecha_meta_str = fecha_meta_padre.date().isoformat()
            elif isinstance(fecha_meta_padre, date):
                fecha_meta_str = fecha_meta_padre.isoformat()
            elif isinstance(fecha_meta_padre, str):
                # Intentar parsear por si viene en formato con hora
                try:
                    fecha_meta_str = date.fromisoformat(fecha_meta_padre.split('T')[0]).isoformat()
                except ValueError:
                    fecha_meta_str = fecha_meta_padre # Usar como viene si falla el parseo
            # --- FIN CORRECCIÓN DEFINITIVA ---

            datos_op_hija = {
                'productos': productos_para_op_hija,
                'observaciones': f"OP hija para reponer desperdicio de OP: {orden_actual.get('codigo', orden_id)}.",
                'id_op_padre': orden_id,
                'fecha_meta': fecha_meta_str # <-- Visibilidad en Planificador
            }

            # 2. Intentar crear la OP hija PRIMERO (Transacción)
            creacion_res = self.crear_orden(datos_op_hija, usuario_id)

            if not creacion_res.get('success'):
                error_msg = f"No se pudo crear la OP hija para cubrir el desperdicio. La orden original no ha sido modificada. Error: {creacion_res.get('error')}"
                logger.error(error_msg)
                # Devolvemos el error, la OP original sigue 'EN PROCESO'.
                return {'success': False, 'error': error_msg, 'data': {'accion': 'error'}}

            # 3. SI la creación de la hija fue exitosa, finalizar la orden actual.
            logger.info(f"OP hija creada exitosamente. Finalizando OP padre {orden_id}.")
            self.model.update(orden_id, {'estado': 'CONTROL_DE_CALIDAD', 'fecha_fin': datetime.now().isoformat()})

            # La respuesta de `crear_orden` devuelve una lista de órdenes creadas.
            nueva_op_data = creacion_res['data'][0] if creacion_res.get('data') else {}

            # 4. Si la OP padre tenía pedidos asociados, heredar la asignación a la hija
            self._heredar_asignaciones_pedido_a_op_hija(op_padre=orden_actual, op_hija=nueva_op_data)

            return {
                'success': True,
                'message': f"Orden enviada a Control de Calidad. Se creó la OP hija {nueva_op_data.get('codigo')} para reponer el desperdicio.",
                'data': {
                    'op_hija_creada': True,
                    'accion': 'finalizar_op_crear_hija',
                    'nueva_op_codigo': nueva_op_data.get('codigo'),
                    'nueva_op_id': nueva_op_data.get('id')
                }
            }

    def _heredar_asignaciones_pedido_a_op_hija(self, op_padre: Dict, op_hija: Dict):
        """
        Hereda la asociación de pedidos de una OP padre a su hija, asignando la
        cantidad de la OP hija (desperdicio) solo a los ítems de pedido que
        aún no han sido completamente satisfechos por la OP padre.
        """
        try:
            op_padre_id = op_padre['id']
            op_hija_id = op_hija['id']
            cantidad_op_hija = Decimal(op_hija.get('cantidad_planificada', '0'))

            if cantidad_op_hija <= 0:
                logger.info(f"OP hija {op_hija_id} con cantidad cero. No se asignará a pedidos.")
                return

            # 1. Obtener todos los ítems de pedido asociados a la OP padre.
            items_res = self.pedido_model.find_all_items_with_pedido_info({'orden_produccion_id': op_padre_id})
            if not items_res.get('success') or not items_res.get('data'):
                logger.warning(f"OP padre {op_padre_id} sin asociación a pedidos. La OP hija {op_hija_id} queda sin asignación.")
                return
            items_asociados = items_res['data']

            # 2. Simular la distribución del stock bueno de la OP Padre (FIFO)
            #    Esto es crucial porque en este punto la OP Padre aún no ha reservado stock físicamente,
            #    pero sabemos que producirá una cierta cantidad "Buena" que cubrirá a los primeros pedidos.

            # Calcular stock bueno estimado del padre (Planificado - Desperdicio reportado en la hija)
            cantidad_planificada_padre = Decimal(str(op_padre.get('cantidad_planificada', '0')))
            stock_bueno_estimado_padre = cantidad_planificada_padre - cantidad_op_hija

            logger.info(f"Simulando asignación FIFO para OP Padre {op_padre_id}. Stock Bueno Est: {stock_bueno_estimado_padre}. Desperdicio (OP Hija): {cantidad_op_hija}")

            # Ordenar items por antigüedad del pedido (FIFO)
            try:
                items_asociados.sort(key=lambda x: x.get('pedido', {}).get('created_at', '9999-12-31'))
            except Exception as e:
                logger.warning(f"Fallo al ordenar items por fecha para simulación FIFO: {e}")

            items_para_op_hija = []
            stock_padre_remanente = stock_bueno_estimado_padre

            for item in items_asociados:
                cantidad_requerida = Decimal(str(item.get('cantidad', '0')))

                # 1. Verificar cuánto YA estaba reservado previamente (por si acaso hubo entregas parciales anteriores)
                reservas_previas_res = self.lote_producto_controller.reserva_model.find_all({'pedido_item_id': item['id'], 'estado': 'RESERVADO'})
                cantidad_ya_entregada = sum(Decimal(r.get('cantidad_reservada', '0')) for r in reservas_previas_res.get('data', []))

                pendiente_real = cantidad_requerida - cantidad_ya_entregada

                if pendiente_real <= 0:
                    continue

                # 2. Simular cuánto cubre el Padre
                cubierto_por_padre = min(pendiente_real, stock_padre_remanente)
                stock_padre_remanente -= cubierto_por_padre

                # 3. Calcular qué falta y debe cubrir la Hija
                falta_para_hija = pendiente_real - cubierto_por_padre

                logger.info(f"Item {item['id']} (Req: {cantidad_requerida}): Cubierto por Padre: {cubierto_por_padre}. Falta: {falta_para_hija}.")

                if falta_para_hija > 0.01:
                    items_para_op_hija.append({
                        'item_id': item['id'],
                        'faltante': falta_para_hija,
                        'pedido_id': item.get('pedido_id') # Guardamos para referencia
                    })

            if not items_para_op_hija:
                logger.warning(f"Simulación completada: El stock bueno del padre cubre toda la demanda pendiente. La OP hija {op_hija_id} no se asignará.")
                return

            # 3. Distribuir la cantidad de la OP hija
            cantidad_a_distribuir = cantidad_op_hija
            nuevas_asignaciones = []

            for item_faltante in items_para_op_hija:
                if cantidad_a_distribuir <= 0:
                    break

                cantidad_a_asignar = min(cantidad_a_distribuir, item_faltante['faltante'])

                nuevas_asignaciones.append({
                    'orden_produccion_id': op_hija_id,
                    'pedido_item_id': item_faltante['item_id'],
                    'cantidad_asignada': float(cantidad_a_asignar)
                })
                cantidad_a_distribuir -= cantidad_a_asignar
                logger.info(f"Herencia de asignación: Se asignarán {cantidad_a_asignar} unidades de la OP hija {op_hija_id} al item {item_faltante['item_id']}.")

            # 4. Insertar las nuevas asignaciones.
            if nuevas_asignaciones:
                logger.info(f"Creando {len(nuevas_asignaciones)} nueva(s) asignacion(es) para la OP hija {op_hija_id}, cubriendo los faltantes.")
                self.asignacion_pedido_model.db.table('asignaciones_pedidos').insert(nuevas_asignaciones).execute()

        except Exception as e:
            logger.error(f"Error crítico al heredar asignaciones a la OP hija {op_hija_id}: {e}", exc_info=True)


    def pausar_produccion(self, orden_id: int, motivo_id: int, usuario_id: int) -> tuple:
        """
        Pausa una orden de producción, cambiando su estado y registrando el paro.
        Si el motivo es "Cambio de Turno", solo pausa, no crea registro de paro.
        """
        try:
            # 1. Obtener la orden y verificar su estado
            orden_result = self.obtener_orden_por_id(orden_id)
            if not orden_result.get('success'):
                return self.error_response("Orden de producción no encontrada.", 404)
            orden = orden_result['data']

            if orden.get('estado') == 'PAUSADA':
                return self.success_response(message="La orden ya se encontraba pausada.")

            if orden.get('estado') != 'EN_PROCESO':
                return self.error_response(f"No se puede pausar una orden que no está 'EN PROCESO'. Estado actual: {orden.get('estado')}", 409)

            # --- LÓGICA DE PAUSA DIFERENCIADA ---
            motivo_paro_model = MotivoParoModel()
            motivo_result = motivo_paro_model.find_by_id(motivo_id)
            motivo_descripcion = motivo_result.get('data', {}).get('descripcion', '').lower()

            # 2. Cambiar el estado de la orden a PAUSADA (siempre)
            cambio_estado_result = self.model.cambiar_estado(orden_id, 'PAUSADA')
            if not cambio_estado_result.get('success'):
                return self.error_response(f"Error al cambiar el estado de la orden a PAUSADA: {cambio_estado_result.get('error')}", 500)

            # 3. Pausar el cronómetro (siempre)
            self.op_cronometro_controller.registrar_fin(orden_id)

            # 4. Crear registro de paro SOLO si NO es por cambio de turno
            if "cambio de turno" not in motivo_descripcion:
                paro_model = RegistroParoModel()
                datos_pausa = {
                    'orden_produccion_id': orden_id,
                    'motivo_paro_id': motivo_id,
                    'usuario_id': usuario_id,
                    'fecha_inicio': datetime.now().isoformat()
                }
                paro_model.create(datos_pausa)
                message = "Producción pausada correctamente."
            else:
                # Si es por cambio de turno, no se crea registro de paro aquí.
                # El flujo de traspaso se encargará de la lógica.
                message = "Orden lista para traspaso de turno."

            return self.success_response(message=message)

        except Exception as e:
            logger.error(f"Error en pausar_produccion para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    def reanudar_produccion(self, orden_id: int, usuario_id: int) -> tuple:
        """
        Reanuda una orden de producción, cambiando su estado a EN_PROCESO y
        cerrando el registro de paro activo.
        """
        try:
            # 1. Obtener la orden y verificar su estado
            orden_result = self.obtener_orden_por_id(orden_id)
            if not orden_result.get('success'):
                return self.error_response("Orden de producción no encontrada.", 404)
            orden = orden_result['data']

            if orden.get('estado') == 'EN_PROCESO':
                return self.success_response(message="La orden ya se encontraba en proceso.")

            if orden.get('estado') != 'PAUSADA':
                return self.error_response(f"No se puede reanudar una orden que no está 'PAUSADA'. Estado actual: {orden.get('estado')}", 409)

            # 2. Encontrar y cerrar el registro de paro activo
            paro_model = RegistroParoModel()
            pausa_activa_result = paro_model.find_all({'orden_produccion_id': orden_id, 'fecha_fin': 'is.null'}, limit=1)

            if not pausa_activa_result.get('data'):
                # Si no hay pausa activa pero el estado es PAUSADA, es una inconsistencia.
                # Forzamos la reanudación para desbloquear al usuario.
                logger.warning(f"Inconsistencia: OP {orden_id} está PAUSADA pero no tiene registro de paro activo. Se reanudará de todas formas.")
            else:
                pausa_activa = pausa_activa_result['data'][0]
                id_registro_paro = pausa_activa['id']
                update_data = {'fecha_fin': datetime.now().isoformat()}
                paro_model.update(id_registro_paro, update_data)

            # 3. Cambiar el estado de la orden de vuelta a EN_PROCESO
            cambio_estado_result = self.model.cambiar_estado(orden_id, 'EN_PROCESO')
            if not cambio_estado_result.get('success'):
                # Si esto falla, la OP podría quedar bloqueada en PAUSADA. Es un estado crítico.
                logger.error(f"CRÍTICO: La OP {orden_id} no pudo ser reanudada a EN_PROCESO y podría estar bloqueada.")
                return self.error_response(f"Error crítico al reanudar la orden: {cambio_estado_result.get('error')}", 500)

            # Reanudar el cronómetro
            self.op_cronometro_controller.registrar_inicio(orden_id)

            detalle = f"Se reanudó la producción de la OP {orden.get('codigo')}."
            self.registro_controller.crear_registro(get_current_user(), 'Ordenes de produccion', 'Reanudación de Producción', detalle)

            return self.success_response(message="Producción reanudada correctamente.")

        except Exception as e:
            logger.error(f"Error en reanudar_produccion para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    def reportar_merma_insumo(self, orden_id: int, data: Dict, usuario_id: int) -> tuple:
        """
        Maneja el reporte de mermas de insumos en una OP en curso.
        Soporta múltiples items. Ejecuta Paso A (Impacto) y Paso B (Resolución) para cada uno.
        """
        from app.models.reserva_insumo import ReservaInsumoModel
        reserva_model = ReservaInsumoModel()
        registro_merma_model = RegistroDesperdicioLoteInsumoModel()

        try:
            mermas = data.get('mermas', [])
            if not mermas:
                return self.error_response("No se recibieron datos de mermas.", 400)

            resultados_acumulados = []
            escenario_global = "REFILL" # Empezamos optimistas

            for item in mermas:
                insumo_id = item.get('insumo_id') 
                cantidad_perdida = float(item.get('cantidad_perdida'))
                motivo_id = int(item.get('motivo_id'))
                observacion = item.get('observacion', '')

                if cantidad_perdida <= 0:
                    continue

                # --- PASO A: VALIDACIÓN E IMPACTO SIMPLIFICADO ---
                
                # 1. Validar si la cantidad reportada es posible
                reservas_res = reserva_model.find_all({'orden_produccion_id': orden_id, 'insumo_id': insumo_id})
                total_asignado = sum(float(r.get('cantidad_reservada', 0)) for r in reservas_res.get('data', []))

                mermas_previas_res = registro_merma_model.find_all_by_op_and_insumo(orden_id, insumo_id)
                merma_acumulada = sum(float(m.get('cantidad', 0)) for m in mermas_previas_res)

                max_desperdiciable = total_asignado - merma_acumulada
                if cantidad_perdida > max_desperdiciable:
                    logger.warning(f"Merma reportada ({cantidad_perdida}) excede el máximo posible ({max_desperdiciable}). Se ajustará.")
                    cantidad_perdida = max_desperdiciable

                if cantidad_perdida <= 0:
                    continue

                # 2. Impactar stock físico y registrar merma
                # Priorizamos consumir de lotes con estado RESERVADO
                reservas_activas = [r for r in reservas_res.get('data', []) if r.get('estado') == 'RESERVADO']
                
                cantidad_restante_a_imputar = cantidad_perdida
                for reserva in sorted(reservas_activas, key=lambda x: x['id']):
                    if cantidad_restante_a_imputar <= 0: break

                    lote_id = reserva['lote_inventario_id']
                    cantidad_en_reserva = float(reserva.get('cantidad_reservada', 0))
                    cantidad_a_tomar = min(cantidad_en_reserva, cantidad_restante_a_imputar)
                    
                    # Registrar merma por cada lote afectado
                    registro_merma_model.create({
                        'lote_insumo_id': lote_id, 'motivo_id': motivo_id, 'cantidad': cantidad_a_tomar,
                        'created_at': datetime.now().isoformat(), 'usuario_id': usuario_id,
                        'orden_produccion_id': orden_id, 'detalle': f"Merma: {observacion}", 'comentarios': observacion
                    })

                    # Descontar de la reserva y del lote físico
                    self.inventario_controller.descontar_stock_fisico_y_reserva(reserva['id'], cantidad_a_tomar)
                    
                    cantidad_restante_a_imputar -= cantidad_a_tomar
                
                # Si aún queda merma por imputar, significa que se usó de stock ya 'CONSUMIDO'.
                # Solo registramos la merma sin descontar stock. Asumimos el primer lote como fuente.
                if cantidad_restante_a_imputar > 0 and reservas_res.get('data'):
                    lote_id_fallback = reservas_res.get('data')[0]['lote_inventario_id']
                    registro_merma_model.create({
                        'lote_insumo_id': lote_id_fallback, 'motivo_id': motivo_id, 'cantidad': cantidad_restante_a_imputar,
                        'created_at': datetime.now().isoformat(), 'usuario_id': usuario_id,
                        'orden_produccion_id': orden_id, 'detalle': f"Merma (sobre consumido): {observacion}", 'comentarios': observacion
                    })

                self.insumo_controller.actualizar_stock_insumo(insumo_id)

                # --- PASO B: RESOLUCIÓN AUTOMÁTICA ---
                resolucion = self._resolver_escenarios_merma(orden_id, insumo_id, cantidad_perdida, usuario_id)
                resultados_acumulados.append(resolucion)
                
                esc_res = resolucion.get('escenario', 'REFILL')
                if esc_res == 'RESET': escenario_global = 'RESET'
                elif esc_res == 'PARCIAL' and escenario_global != 'RESET': escenario_global = 'PARCIAL'

            datos_respuesta_api = {'escenario': escenario_global, 'detalles': resultados_acumulados}
            mensaje_final = "Mermas registradas. Material repuesto automáticamente."

            if escenario_global == 'RESET':
                mensaje_final = "Mermas registradas. ¡Atención! Por falta crítica de stock, la orden fue devuelta a Planificación."
            elif escenario_global == 'PARCIAL':
                # Tomamos el mensaje y los datos del primer (y probablemente único) evento parcial.
                detalle_parcial = next((res for res in resultados_acumulados if res.get('escenario') == 'PARCIAL'), None)
                if detalle_parcial:
                    mensaje_final = detalle_parcial.get('mensaje_usuario', "Mermas registradas con ajuste de meta.")
                    datos_respuesta_api.update(detalle_parcial.get('datos_adicionales', {}))

            return self.success_response(
                message=mensaje_final,
                data=datos_respuesta_api
            )

        except Exception as e:
            logger.error(f"Error en reportar_merma_insumo para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def _resolver_escenarios_merma(self, orden_id: int, insumo_id: int, cantidad_perdida: float, usuario_id: int) -> Dict:
        """
        Evalúa los 3 escenarios (Refill, Quiebre Parcial, Reset) tras una merma.
        Prioriza la REPOSICIÓN AUTOMÁTICA (Refill) si hay stock disponible.
        """
        # 1. Buscar si hay más stock disponible (Refill)
        # Usamos el helper existente que filtra por fecha y disponibilidad
        lotes_disponibles = self.inventario_controller._obtener_lotes_con_disponibilidad(insumo_id)
        stock_disponible_total = sum(lote['disponibilidad'] for lote in lotes_disponibles)

        orden_res = self.model.find_by_id(orden_id)
        orden = orden_res['data']

        # ESCENARIO 1: REPOSICIÓN AUTOMÁTICA (Refill)
        if stock_disponible_total >= cantidad_perdida:
            logger.info(f"Escenario 1 (Refill) para OP {orden_id}. Stock disponible ({stock_disponible_total}) cubre la pérdida ({cantidad_perdida}).")
            
            # --- INICIO DE LA CORRECCIÓN ---
            # Delegar el consumo y descuento físico al controlador de inventario
            consumo_result = self.inventario_controller.consumir_stock_para_reposicion(
                orden_produccion_id=orden_id,
                insumo_id=insumo_id,
                cantidad=cantidad_perdida,
                usuario_id=usuario_id
            )

            if not consumo_result.get('success'):
                logger.error(f"Fallo el REFILL automático para OP {orden_id}: {consumo_result.get('error')}")
                # Si falla la reposición, caemos en escenario PARCIAL por defecto.
                pass
            else:
                return {
                    "escenario": "REFILL",
                    "mensaje_usuario": "Material repuesto y consumido automáticamente. Continúe produciendo."
                }
            # --- FIN DE LA CORRECCIÓN ---

        # Si no hay suficiente para reponer todo...
        
        # Obtener la receta para calcular rendimientos
        receta_res = self.receta_model.find_by_id(orden['receta_id'], 'id')
        receta = receta_res['data']
        ingredientes_res = self.receta_model.get_ingredientes(orden['receta_id'])
        ingredientes = ingredientes_res.get('data', [])
        
        # Encontrar cuánto de este insumo se necesita por unidad de producto
        insumo_req_por_unidad = 0
        for ing in ingredientes:
            if ing['id_insumo'] == insumo_id:
                insumo_req_por_unidad = float(ing['cantidad'])
                break
        
        if insumo_req_por_unidad <= 0:
            # Error en receta? Asumimos no crítico o error
            return {"escenario": "ERROR", "mensaje_usuario": "Error en datos de receta. Avise a soporte."}

        # Calcular cuánto tenemos AHORA reservado (lo que quedó sano) + lo poco que haya disponible libre
        # (En realidad, el escenario 2 dice "Con lo que me queda...". Asumimos que usa lo que quedó en la OP + lo que pueda rascar del almacén)
        
        # Stock total accesible = (Reservas actuales sanas de la OP) + (Stock disponible en almacén)
        # Reservas actuales sanas = Ya las actualizamos en Paso A (quitamos lo perdido)
        reservas_actuales_res = self.inventario_controller.reserva_insumo_model.find_all({'orden_produccion_id': orden_id, 'insumo_id': insumo_id, 'estado': 'RESERVADO'})
        reservas_actuales_qty = sum(float(r.get('cantidad_reservada', 0)) for r in reservas_actuales_res.get('data', []))
        
        stock_total_accesible = reservas_actuales_qty + stock_disponible_total
        
        max_produccion_posible = math.floor(stock_total_accesible / insumo_req_por_unidad)
        
        cantidad_planificada_original = float(orden.get('cantidad_planificada', 0))
        
        # ESCENARIO 3: PÉRDIDA TOTAL (Reset)
        if max_produccion_posible <= 0:
            logger.info(f"Escenario 3 (Reset) para OP {orden_id}. No se puede producir nada. Se cancelará y creará una nueva.")
            
            # 1. Liberar solo el stock sano y no consumido
            self.inventario_controller.liberar_stock_no_consumido_para_op(orden_id)
            
            # 2. Cancelar la OP actual con una observación clara
            obs = f"{orden.get('observaciones', '')} | CANCELADA por pérdida total de insumo ID {insumo_id}. Replanificada automáticamente.".strip()
            self.model.cambiar_estado(orden_id, 'CANCELADA', observaciones=obs)

            # 3. Crear una nueva OP (copia) para replanificar
            form_data_copia = {
                'productos': [{'id': orden['producto_id'], 'cantidad': orden['cantidad_planificada']}],
                'fecha_meta': orden.get('fecha_meta'),
                'observaciones': f"Replanificación automática de OP-{orden.get('codigo')}.",
                'id_op_padre': orden.get('id_op_padre') 
            }
            creacion_res = self.crear_orden(form_data_copia, usuario_id)

            if not creacion_res.get('success'):
                # Esto es un estado problemático, la OP original fue cancelada pero la nueva no se pudo crear.
                error_msg = f"CRÍTICO: La OP {orden_id} fue cancelada pero no se pudo crear su reemplazo automático. Por favor, cree una nueva OP manualmente. Error: {creacion_res.get('error')}"
                logger.error(error_msg)
                return {"escenario": "ERROR", "mensaje_usuario": error_msg}

            nueva_op = creacion_res['data'][0]
            
            return {
                "escenario": "RESET",
                "mensaje_usuario": f"Pérdida crítica de insumo. La orden actual ({orden.get('codigo')}) fue cancelada y se creó una nueva orden ({nueva_op.get('codigo')}) para ser replanificada."
            }

        # ESCENARIO 2: QUIEBRE PARCIAL (Ajuste de Meta)
        else:
            logger.info(f"Escenario 2 (Parcial) para OP {orden_id}. Se notifica al usuario. Nueva meta posible: {max_produccion_posible}.")

            # 1. Si hay algo disponible en almacén (que no cubría todo pero ayuda), tómalo (Refill parcial)
            if stock_disponible_total > 0:
                cantidad_restante_tomar = stock_disponible_total
                for lote in lotes_disponibles:
                    if cantidad_restante_tomar <= 0: break
                    cant = min(lote['disponibilidad'], cantidad_restante_tomar)
                    self.inventario_controller.reserva_insumo_model.create({
                        'orden_produccion_id': orden_id, 'lote_inventario_id': lote['id_lote'],
                        'insumo_id': insumo_id, 'cantidad_reservada': cant, 'usuario_reserva_id': usuario_id
                    })
                    cantidad_restante_tomar -= cant

            # 2. NO se recorta la OP actual. Solo se informa.
            # self.model.update(orden_id, {'cantidad_planificada': max_produccion_posible}, 'id')
            
            # 3. NO se crea OP Hija automáticamente.
            cantidad_faltante = cantidad_planificada_original - max_produccion_posible

            return {
                "escenario": "PARCIAL",
                "mensaje_usuario": f"Stock insuficiente. Ahora solo puedes producir un máximo de {max_produccion_posible} unidades. La meta original de {cantidad_planificada_original} se mantiene como referencia.",
                "datos_adicionales": {
                    "max_produccion_posible": max_produccion_posible,
                    "cantidad_planificada_original": cantidad_planificada_original
                }
            }

    def obtener_ordenes_para_kanban_hoy(self, filtros: Optional[Dict] = None) -> tuple:
        """
        Obtiene las órdenes de producción relevantes para el tablero Kanban del día.
        Esto incluye OPs que comienzan hoy y aquellas que ya están en producción.
        """
        try:
            result = self.model.get_for_kanban_hoy(filtros_operario=filtros)

            if result.get('success'):
                return self.success_response(data=result.get('data', []))
            else:
                error_msg = result.get('error', 'Error desconocido al obtener órdenes para el Kanban de hoy.')
                return self.error_response(error_msg, 500)
        except Exception as e:
            logger.error(f"Error crítico en obtener_ordenes_para_kanban_hoy: {e}", exc_info=True)
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def iniciar_trabajo_op(self, orden_id: int, usuario_id: int) -> tuple:
        """
        Asigna una orden a un operario y cambia su estado a EN_PROCESO.
        Esta acción es idempotente: si la orden ya está asignada al usuario y en proceso, no hace nada.
        """
        try:
            # 1. Obtener la orden de producción
            orden_result = self.obtener_orden_por_id(orden_id)
            if not orden_result.get('success'):
                return self.error_response("Orden de producción no encontrada.", 404)
            orden = orden_result['data']

            # 2. Validar estado
            estado_actual = orden.get('estado')
            operario_actual = orden.get('operario_asignado_id')

            # Si ya está en proceso y asignada al mismo usuario, no hacer nada (éxito idempotente)
            if estado_actual == 'EN_PROCESO' and operario_actual == usuario_id:
                return self.success_response(message="El trabajo ya fue iniciado por este usuario.")

            # Solo se puede iniciar si está en "LISTA PARA PRODUCIR" (aceptamos ambos formatos por inconsistencia en DB)
            if estado_actual not in ['LISTA PARA PRODUCIR', 'LISTA_PARA_PRODUCIR']:
                return self.error_response(f"No se puede iniciar el trabajo. La orden está en estado '{estado_actual}'.", 409) # 409 Conflict

            # 3. Preparar y ejecutar la actualización
            update_data = {
                'operario_asignado_id': usuario_id,
                'estado': 'EN_PROCESO',
                'fecha_inicio': datetime.now().isoformat() # Registrar cuándo empezó realmente
            }

            update_result = self.model.update(orden_id, update_data)

            if update_result.get('success'):
                # Iniciar el cronómetro
                self.op_cronometro_controller.registrar_inicio(orden_id)

                logger.info(f"Iniciando consumo de stock físico para la OP {orden_id}...")
                consumo_result = self.inventario_controller.consumir_stock_reservado_para_op(orden_id)
                if not consumo_result.get('success'):
                    # Esto es un estado crítico. La OP está en proceso pero el stock no se pudo descontar.
                    # Se loggea como un error grave para revisión manual.
                    logger.error(f"CRÍTICO: La OP {orden_id} se inició pero falló el consumo de stock: {consumo_result.get('error')}")
                    # A pesar del fallo, se continúa para no bloquear al operario. El log es la alerta.

                return self.success_response(data=update_result.get('data'), message="Trabajo iniciado correctamente.")
            else:
                return self.error_response(f"Error al actualizar la orden: {update_result.get('error')}", 500)

        except Exception as e:
            logger.error(f"Error en iniciar_trabajo_op para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    # endregion

    # region Helpers de Consolidación

    def _validar_y_obtener_ops_para_consolidar(self, op_ids: List[int]) -> tuple:
        """Valida que las OPs existan, sean del mismo producto y estén en estado 'PENDIENTE'."""
        ops_a_consolidar_res = self.model.find_by_ids(op_ids)
        if not ops_a_consolidar_res.get('success') or not ops_a_consolidar_res.get('data'):
            return None, {'success': False, 'error': 'Una o más órdenes no fueron encontradas.'}

        ops_originales = ops_a_consolidar_res['data']
        if len(ops_originales) != len(op_ids):
            return None, {'success': False, 'error': 'Algunas órdenes no pudieron ser cargadas.'}

        primer_producto_id = ops_originales[0]['producto_id']
        if not all(op['producto_id'] == primer_producto_id for op in ops_originales):
            return None, {'success': False, 'error': 'Todas las órdenes deben ser del mismo producto.'}

        return ops_originales, None

    def _relinkear_items_pedido(self, op_ids: List[int], super_op_id: int) -> dict:
        """Actualiza los items de pedido de las OPs originales para que apunten a la nueva Super OP."""
        try:
            self.pedido_model.db.table('pedido_items').update({
                'orden_produccion_id': super_op_id
            }).in_('orden_produccion_id', op_ids).execute()
            logger.info(f"Relinkeo de items de pedido a Super OP {super_op_id} completado.")
            return {'success': True}
        except Exception as e:
            logger.error(f"CRÍTICO: Fallo al re-linkear items de pedido a Super OP {super_op_id}. Error: {e}", exc_info=True)
            return {'success': False, 'error': f'La Super OP fue creada, pero falló la asignación de pedidos. Contacte a soporte. Error: {str(e)}'}

    def _actualizar_ops_originales(self, op_ids: List[int], super_op_id: int):
        """Marca las OPs originales como 'CONSOLIDADA' y las vincula a la Super OP."""
        update_data = {
            'estado': 'CONSOLIDADA'
            # 'super_op_id': super_op_id
        }
        for op_id in op_ids:
            self.model.update(id_value=op_id, data=update_data, id_field='id')
        logger.info(f"OPs originales {op_ids} actualizadas a estado CONSOLIDADA.")

    def obtener_estado_produccion_op(self, op_id: int) -> tuple:
        """
        Obtiene el estado de producción en tiempo real para una OP específica.
        Calcula el avance y devuelve datos clave.
        """
        try:
            # 1. Obtener la orden de producción
            op_result = self.obtener_orden_por_id(op_id)
            if not op_result.get('success'):
                return self.error_response("Orden de Producción no encontrada.", 404)

            orden = op_result['data']

            # 2. Extraer cantidades y calcular avance
            cantidad_planificada = Decimal(orden.get('cantidad_planificada', 0))
            cantidad_producida = Decimal(orden.get('cantidad_producida', 0))

            avance_porcentaje = 0
            if cantidad_planificada > 0:
                avance_porcentaje = round((cantidad_producida / cantidad_planificada) * 100, 2)

            # 3. Preparar la respuesta
            estado_produccion = {
                'cantidad_planificada': float(cantidad_planificada),
                'cantidad_producida': float(cantidad_producida),
                'avance_porcentaje': float(avance_porcentaje),
                'estado_actual': orden.get('estado')
            }

            return self.success_response(data=estado_produccion)

        except Exception as e:
            logger.error(f"Error al obtener estado de producción para OP {op_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def obtener_ordenes_para_planificacion(self, inicio_semana: date, fin_semana: date, horizonte_dias: int) -> tuple:
        """
        Realiza una consulta unificada para obtener todas las OPs necesarias para la
        vista de planificación, abarcando las pendientes en el horizonte y las
        planificadas en la semana.
        """
        try:
            # Calcular fechas límite para los filtros
            hoy = date.today()
            fecha_fin_horizonte = hoy + timedelta(days=horizonte_dias)
            dias_previos_margen = 14
            fecha_inicio_filtro_semanal = inicio_semana - timedelta(days=dias_previos_margen)

            # Llamar a un nuevo método en el modelo que combina las consultas
            result = self.model.get_all_for_planificacion(
                fecha_fin_horizonte=fecha_fin_horizonte,
                fecha_inicio_semanal=fecha_inicio_filtro_semanal,
                fecha_fin_semanal=fin_semana
            )

            if result.get('success'):
                return self.success_response(data=result.get('data', []))
            else:
                return self.error_response(result.get('error', 'Error al obtener órdenes para planificación.'), 500)

        except Exception as e:
            logger.error(f"Error crítico en obtener_ordenes_para_planificacion: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)

    def cambiar_estado_a_pendiente_con_reemplazo(self, orden_id: int):
        """
        Intenta encontrar un lote de insumo de reemplazo. Si tiene éxito,
        cambia el estado de la OP a 'LISTA PARA PRODUCIR', de lo contrario a 'PENDIENTE'.
        """
        from app.models.reserva_insumo import ReservaInsumoModel
        reserva_insumo_model = ReservaInsumoModel()

        try:
            # 1. Obtener las reservas originales de la OP
            reservas_originales_res = reserva_insumo_model.find_all({'orden_produccion_id': orden_id})
            if not reservas_originales_res.get('success') or not reservas_originales_res.get('data'):
                self.model.cambiar_estado(orden_id, 'PENDIENTE')
                return {'success': True, 'message': 'OP movida a PENDIENTE ya que no tenía reservas.'}

            reservas_originales = reservas_originales_res['data']

            # 2. Agrupar la necesidad total por insumo_id
            necesidad_por_insumo = {}
            for res in reservas_originales:
                insumo_id = res['insumo_id']
                necesidad_por_insumo[insumo_id] = necesidad_por_insumo.get(insumo_id, 0) + float(res['cantidad_reservada'])

            # 3. Verificar si hay stock de reemplazo para CADA insumo
            nuevas_reservas_potenciales = []
            todos_reemplazados = True
            for insumo_id, cantidad_necesaria in necesidad_por_insumo.items():
                lotes_disponibles = self.inventario_controller._obtener_lotes_con_disponibilidad(insumo_id)
                stock_disponible_total = sum(lote['disponibilidad'] for lote in lotes_disponibles)

                if stock_disponible_total < cantidad_necesaria:
                    todos_reemplazados = False
                    break

                # Si hay stock, determinar de qué lotes se tomará
                cantidad_restante = cantidad_necesaria
                for lote in lotes_disponibles:
                    if cantidad_restante <= 0: break
                    cantidad_a_tomar = min(lote['disponibilidad'], cantidad_restante)
                    nuevas_reservas_potenciales.append({
                        'orden_produccion_id': orden_id, 'lote_inventario_id': lote['id_lote'],
                        'insumo_id': insumo_id, 'cantidad_reservada': cantidad_a_tomar,
                        'usuario_reserva_id': get_current_user().id if get_current_user() else 1
                    })
                    cantidad_restante -= cantidad_a_tomar

            # 4. Actuar según el resultado
            if todos_reemplazados:
                # Eliminar reservas viejas
                reserva_insumo_model.db.table('reserva_insumos').delete().eq('orden_produccion_id', orden_id).execute()
                # Crear reservas nuevas
                reserva_insumo_model.db.table('reserva_insumos').insert(nuevas_reservas_potenciales).execute()
                # Cambiar estado
                self.model.cambiar_estado(orden_id, 'LISTA PARA PRODUCIR')
                return {'success': True, 'message': 'Reemplazo de insumos exitoso. OP lista para producir.'}
            else:
                self.model.cambiar_estado(orden_id, 'PENDIENTE')
                return {'success': True, 'message': 'No se encontraron reemplazos de insumos. OP movida a pendiente.'}

        except Exception as e:
            logger.error(f"Error en cambiar_estado_a_pendiente_con_reemplazo para OP {orden_id}: {e}", exc_info=True)
            # Como fallback seguro, mover a pendiente
            self.model.cambiar_estado(orden_id, 'PENDIENTE')
            return {'success': False, 'error': str(e)}
        """
        Intenta encontrar un lote de insumo de reemplazo. Si tiene éxito,
        cambia el estado de la OP a 'LISTA PARA PRODUCIR', de lo contrario a 'PENDIENTE'.
        """
        from app.models.reserva_insumo import ReservaInsumoModel
        reserva_insumo_model = ReservaInsumoModel()

        try:
            # 1. Obtener las reservas originales de la OP
            reservas_originales_res = reserva_insumo_model.find_all({'orden_produccion_id': orden_id})
            if not reservas_originales_res.get('success') or not reservas_originales_res.get('data'):
                self.model.cambiar_estado(orden_id, 'PENDIENTE')
                return {'success': True, 'message': 'OP movida a PENDIENTE ya que no tenía reservas.'}

            reservas_originales = reservas_originales_res['data']

            # 2. Agrupar la necesidad total por insumo_id
            necesidad_por_insumo = {}
            for res in reservas_originales:
                insumo_id = res['insumo_id']
                necesidad_por_insumo[insumo_id] = necesidad_por_insumo.get(insumo_id, 0) + float(res['cantidad_reservada'])

            # 3. Verificar si hay stock de reemplazo para CADA insumo
            nuevas_reservas_potenciales = []
            todos_reemplazados = True
            for insumo_id, cantidad_necesaria in necesidad_por_insumo.items():
                lotes_disponibles = self.inventario_controller._obtener_lotes_con_disponibilidad(insumo_id)
                stock_disponible_total = sum(lote['disponibilidad'] for lote in lotes_disponibles)

                if stock_disponible_total < cantidad_necesaria:
                    todos_reemplazados = False
                    break

                # Si hay stock, determinar de qué lotes se tomará
                cantidad_restante = cantidad_necesaria
                for lote in lotes_disponibles:
                    if cantidad_restante <= 0: break
                    cantidad_a_tomar = min(lote['disponibilidad'], cantidad_restante)
                    nuevas_reservas_potenciales.append({
                        'orden_produccion_id': orden_id, 'lote_inventario_id': lote['id_lote'],
                        'insumo_id': insumo_id, 'cantidad_reservada': cantidad_a_tomar,
                        'usuario_reserva_id': get_current_user().id if get_current_user() else 1
                    })
                    cantidad_restante -= cantidad_a_tomar

            # 4. Actuar según el resultado
            if todos_reemplazados:
                # Eliminar reservas viejas
                reserva_insumo_model.db.table('reserva_insumos').delete().eq('orden_produccion_id', orden_id).execute()
                # Crear reservas nuevas
                reserva_insumo_model.db.table('reserva_insumos').insert(nuevas_reservas_potenciales).execute()
                # Cambiar estado
                self.model.cambiar_estado(orden_id, 'LISTA PARA PRODUCIR')
                return {'success': True, 'message': 'Reemplazo de insumos exitoso. OP lista para producir.'}
            else:
                self.model.cambiar_estado(orden_id, 'PENDIENTE')
                return {'success': True, 'message': 'No se encontraron reemplazos de insumos. OP movida a pendiente.'}

        except Exception as e:
            logger.error(f"Error en cambiar_estado_a_pendiente_con_reemplazo para OP {orden_id}: {e}", exc_info=True)
            # Como fallback seguro, mover a pendiente
            self.model.cambiar_estado(orden_id, 'PENDIENTE')
            return {'success': False, 'error': str(e)}
    # endregion


    def _obtener_cantidad_insumo_en_curso(self, orden_produccion_id: int, insumo_id: int) -> float:
        """
        Calcula la cantidad de un insumo que ya ha sido pedida en OCs vinculadas a esta OP
        y que todavía está en proceso.
        VERSIÓN ROBUSTA CON LOGS: Consulta directa a items para asegurar que no se pierdan datos.
        """
        from app.models.orden_compra_model import OrdenCompraModel
        oc_model = OrdenCompraModel()

        logger.info(f"--- [MRP Check] Iniciando verificación de insumo en curso para OP-{orden_produccion_id}, Insumo-{insumo_id} ---")

        try:
            # 1. Obtener IDs de las OCs vinculadas a esta OP
            ocs_res = oc_model.find_all(filters={'orden_produccion_id': orden_produccion_id})

            if not ocs_res.get('success') or not ocs_res.get('data'):
                logger.info(f"[MRP Check] No se encontraron OCs vinculadas a la OP-{orden_produccion_id}.")
                return 0.0

            # Estados que consideramos "Vivos/En Camino"
            # Excluimos RECEPCION_INCOMPLETA porque lo que llegó ya es stock físico,
            # y lo que no llegó se considera perdido/cancelado en esa OC
            estados_en_curso = ['PENDIENTE', 'APROBADA', 'EN_TRANSITO', 'EN_RECEPCION', 'EN ESPERA DE INSUMO']

            ocs_encontradas = ocs_res['data']
            ocs_validas_ids = []

            logger.info(f"[MRP Check] OCs encontradas vinculadas a la OP: {len(ocs_encontradas)}")

            for oc in ocs_encontradas:
                estado_oc = oc.get('estado')
                oc_id = oc.get('id')
                codigo_oc = oc.get('codigo_oc', f'ID {oc_id}')

                if estado_oc in estados_en_curso:
                    ocs_validas_ids.append(oc_id)
                    logger.info(f"  -> OC {codigo_oc} (ID: {oc_id}) está en estado '{estado_oc}' -> SE CUENTA.")
                else:
                    logger.info(f"  -> OC {codigo_oc} (ID: {oc_id}) está en estado '{estado_oc}' -> IGNORADA (No está en curso).")

            if not ocs_validas_ids:
                logger.info(f"[MRP Check] Ninguna OC cumple con los estados de 'En Curso'. Retornando 0.0")
                return 0.0

            # 2. Consultar directamente la tabla de items para esas OCs y ese insumo
            logger.info(f"[MRP Check] Consultando items para OCs IDs: {ocs_validas_ids} y Insumo ID: {insumo_id}...")

            # Usamos acceso directo a la tabla para evitar problemas de anidamiento en el modelo
            items_res = oc_model.db.table('orden_compra_items') \
                .select('cantidad_solicitada, id, orden_compra_id') \
                .in_('orden_compra_id', ocs_validas_ids) \
                .eq('insumo_id', insumo_id) \
                .execute()

            total_en_camino = 0.0

            if items_res.data:
                for item in items_res.data:
                    cant = float(item['cantidad_solicitada'])
                    oc_id_item = item['orden_compra_id']
                    total_en_camino += cant
                    logger.info(f"    -> Item encontrado en OC {oc_id_item}: {cant} unidades.")

                logger.info(f"[MRP Check] RESULTADO FINAL: Insumo {insumo_id} tiene {total_en_camino}u en camino.")
                return total_en_camino

            logger.info(f"[MRP Check] No se encontraron items de este insumo en las OCs válidas. Retornando 0.0")
            return 0.0

        except Exception as e:
            logger.error(f"[MRP Check] ERROR CRÍTICO calculando insumo en curso: {e}", exc_info=True)
            return 0.0

    def replanificar_op_con_copia(self, orden_id: int) -> Dict:
        """
        Replanifica una OP creando una nueva copia en estado 'PENDIENTE'
        y marcando la original como 'CANCELADA' (o 'REPLANIFICADA' si se prefiere,
        pero usaremos CANCELADA para evitar estados complejos en otros módulos).
        Manteniendo la trazabilidad del fallo en la original.
        """
        try:
            # 1. Obtener la OP original
            op_res = self.model.find_by_id(orden_id)
            if not op_res.get('success'):
                return {'success': False, 'error': f"OP {orden_id} no encontrada."}
            op_original = op_res['data']

            # 2. Crear datos para la nueva OP
            # Copiamos datos clave
            nueva_op_data = {
                'producto_id': op_original['producto_id'],
                'cantidad_planificada': op_original['cantidad_planificada'],
                'receta_id': op_original['receta_id'],
                'fecha_meta': op_original.get('fecha_meta'),
                'prioridad': op_original.get('prioridad', 'NORMAL'),
                'observaciones': f"Replanificación de OP-{op_original.get('codigo')} (ID: {orden_id}). Motivo: Insumo/Proceso no apto.",
                'estado': 'PENDIENTE',
                # Importante: No copiamos 'id_op_padre' ciegamente. Si la original era hija, la nueva también lo será.
                'id_op_padre': op_original.get('id_op_padre'),
                'pedido_id': op_original.get('pedido_id'), # Mantener vínculo con el pedido si existe
                'usuario_creador_id': get_current_user().id if get_current_user() else op_original.get('usuario_creador_id')
            }
            if nueva_op_data.get('fecha_meta'):
                fecha_meta_val = nueva_op_data['fecha_meta']
                if isinstance(fecha_meta_val, (date, datetime)):
                    nueva_op_data['fecha_meta'] = fecha_meta_val.isoformat().split('T')[0]
                elif isinstance(fecha_meta_val, str):
                    nueva_op_data['fecha_meta'] = fecha_meta_val.split('T')[0]

            # --- FIX: Excluir usuario_creador_id de load() ---
            data_to_load = {k: v for k, v in nueva_op_data.items() if k != 'usuario_creador_id'}
            

            # Validar datos sin campos de solo lectura
            validated_data = self.schema.load(data_to_load)

            # Agregar campos generados por el sistema post-validación
            validated_data['codigo'] = f"OP-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            # usuario_creador_id está marcado como dump_only en el schema, por lo que load() lo ignora.
            # Lo agregamos manualmente aquí.
            if 'usuario_creador_id' in nueva_op_data:
                validated_data['usuario_creador_id'] = nueva_op_data['usuario_creador_id']

            create_res = self.model.create(validated_data)
            if not create_res.get('success'):
                return {'success': False, 'error': f"Error al crear la nueva OP: {create_res.get('error')}"}

            nueva_op = create_res['data']

            # 4. Actualizar la OP original
            # La marcamos como CANCELADA para liberar recursos (aunque ya se consumieron insumos malos,
            # el estado CANCELADA es el más apropiado para 'no va a producir nada más').
            # Agregamos una observación.
            obs_original = op_original.get('observaciones') or ''
            update_original = {
                'estado': 'CANCELADA', # O podríamos usar un estado específico 'REPLANIFICADA' si el frontend lo soporta
                'observaciones': f"{obs_original} | Replanificada a {nueva_op['codigo']}."
            }
            self.model.update(orden_id, update_original)

            # 5. Migrar asignaciones de Pedido (Si aplica)
            # Si la OP original tenía items de pedido asignados en `asignaciones_pedidos`,
            # debemos mover esas asignaciones a la nueva OP para que el pedido apunte a la activa.
            try:
                self.asignacion_pedido_model.db.table('asignaciones_pedidos')\
                    .update({'orden_produccion_id': nueva_op['id']})\
                    .eq('orden_produccion_id', orden_id)\
                    .execute()

                # También actualizar `pedido_items` si tienen la columna directa `orden_produccion_id`
                self.pedido_model.db.table('pedido_items')\
                    .update({'orden_produccion_id': nueva_op['id']})\
                    .eq('orden_produccion_id', orden_id)\
                    .execute()
            except Exception as e:
                logger.warning(f"Error al migrar asignaciones de pedido: {e}")

            return {
                'success': True,
                'message': f"OP Replanificada. Nueva OP: {nueva_op['codigo']}",
                'data': nueva_op
            }

        except Exception as e:
            logger.error(f"Error crítico al replanificar OP {orden_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}


    def desvincular_orden_de_pedido(self, orden_id: int, motivo: str = "") -> Dict:
        """
        Caso 3 y 4: Desvincula una OP de un Pedido.
        LIMPIEZA TOTAL:
        1. Quita link en tabla ordenes_produccion.
        2. Borra asignaciones intermedias.
        3. Cancela reservas existentes.
        4. (NUEVO) Quita el link en pedido_items para evitar reservas futuras.
        """
        try:
            # 1. Obtener datos actuales
            op_actual_res = self.model.find_by_id(orden_id)
            if not op_actual_res.get('success'):
                return {'success': False, 'error': "OP no encontrada."}

            op_actual = op_actual_res.get('data')
            pedido_id_asociado = op_actual.get('pedido_id')

            # 2. Desvincular en la tabla de OPs (Header)
            obs_actual = op_actual.get('observaciones') or ''
            nueva_obs = f"{obs_actual}\n[Desvinculada de Pedido Cancelado]: {motivo}".strip()

            update_data = {
                'pedido_id': None,
                'observaciones': nueva_obs
            }
            result = self.model.update(orden_id, update_data)

            # 3. Limpiar tabla intermedia asignaciones_pedidos
            try:
                self.asignacion_pedido_model.db.table('asignaciones_pedidos')\
                    .delete().eq('orden_produccion_id', orden_id).execute()
            except Exception as e_assign:
                logger.warning(f"No se pudo limpiar asignaciones_pedidos para OP {orden_id}: {e_assign}")

            # 4. Limpiar Reservas Físicas Existentes (si las hubiera)
            if pedido_id_asociado:
                lotes_op_res = self.lote_producto_controller.model.find_all({'orden_produccion_id': orden_id})
                if lotes_op_res.get('success'):
                    for lote in lotes_op_res.get('data', []):
                        reservas_lote = self.lote_producto_controller.reserva_model.find_all({
                            'lote_producto_id': lote['id_lote'],
                            'pedido_id': pedido_id_asociado,
                            'estado': 'RESERVADO'
                        })
                        if reservas_lote.get('success'):
                            for reserva in reservas_lote.get('data', []):
                                self.lote_producto_controller.liberar_reserva_especifica(reserva['id'])

            # 5. (NUEVO CRÍTICO) Desvincular items del pedido para evitar reservas futuras
            # Esto asegura que cuando la OP termine, no encuentre estos items esperando.
            try:
                self.pedido_model.db.table('pedido_items')\
                    .update({'orden_produccion_id': None})\
                    .eq('orden_produccion_id', orden_id)\
                    .execute()
                logger.info(f"Items de pedido desvinculados de la OP {orden_id}.")
            except Exception as e_items:
                logger.error(f"Error desvinculando items de pedido de la OP {orden_id}: {e_items}")

            if result.get('success'):
                logger.info(f"OP {orden_id} desvinculada exitosamente. Pasa a Stock General.")
                return {'success': True, 'data': result.get('data')}
            return result

        except Exception as e:
            logger.error(f"Error desvinculando OP {orden_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

