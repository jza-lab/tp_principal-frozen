from uuid import UUID

from flask import url_for
from app.controllers.base_controller import BaseController
from app.models.alerta_riesgo import AlertaRiesgoModel
from app.models.inventario import InventarioModel
from app.models.insumo import InsumoModel
from app.controllers.insumo_controller import InsumoController
from app.controllers.configuracion_controller import ConfiguracionController
#from app.services.stock_service import StockService
from app.models.lote_producto import LoteProductoModel
from app.models.orden_compra_model import OrdenCompraModel
from app.models.orden_produccion import OrdenProduccionModel
from app.models.pedido import PedidoModel, PedidoItemModel
from app.models.reserva_producto import ReservaProductoModel
from app.schemas.inventario_schema import InsumosInventarioSchema
from app.models.control_calidad_insumo import ControlCalidadInsumoModel
from app.models.registro_desperdicio_lote_insumo_model import RegistroDesperdicioLoteInsumoModel
from app.models.motivo_desperdicio_model import MotivoDesperdicioModel
from typing import Dict, Optional, List
import logging
from decimal import Decimal
from datetime import datetime, date
from marshmallow import ValidationError

from app.models.receta import RecetaModel # O donde tengas la lógica de recetas
from app.models.reserva_insumo import ReservaInsumoModel # El nuevo modelo que debes crear
from app.schemas.reserva_insumo_schema import ReservaInsumoSchema # El nuevo schema
from app.models.trazabilidad import TrazabilidadModel
from app.controllers.riesgo_controller import RiesgoController # Importación tardía para evitar ciclos





logger = logging.getLogger(__name__)

class InventarioController(BaseController):
    """Controlador para operaciones de inventario"""

    def __init__(self):
        super().__init__()
        self.inventario_model = InventarioModel()
        self.insumo_model = InsumoModel()
        self.insumo_controller = InsumoController()
        self.config_controller = ConfiguracionController()
        #self.stock_service = StockService()
        self.schema = InsumosInventarioSchema()
        self.reserva_insumo_model = ReservaInsumoModel()

        self.orden_compra_model = OrdenCompraModel()
        self.op_model = OrdenProduccionModel()
        self.lote_producto_model = LoteProductoModel()
        self.reserva_producto_model = ReservaProductoModel()
        self.pedido_model = PedidoModel()
        self.pedido_item_model = PedidoItemModel()

    def get_all_stock_disponible_map(self) -> Dict:
        """
        Obtiene el stock disponible de TODOS los insumos en una sola consulta
        y lo devuelve como un mapa {insumo_id: stock_disponible}.

        Utiliza la función RPC de Supabase 'get_stock_total_disponible'.
        """
        try:
            # --- ¡CORRECCIÓN! ---
            # Cambiamos 'self.db.rpc' por 'self.inventario_model.db.rpc'
            # (Usamos el modelo 'inventario_model' que se inicializa en __init__)
            result = self.inventario_model.db.rpc('get_stock_total_disponible').execute()
            # --- FIN CORRECCIÓN ---

            # Convertir la lista de resultados en un mapa {id: stock}
            stock_map = {
                item['insumo_id']: Decimal(item['stock_disponible'])
                for item in result.data
            }

            return {'success': True, 'data': stock_map}

        except Exception as e:
            logger.error(f"Error en get_all_stock_disponible_map: {e}", exc_info=True)
            return {'success': False, 'error': str(e), 'data': {}}

    def reservar_stock_insumos_para_op(self, orden_produccion: Dict, usuario_id: int) -> dict:
        """
        Crea reservas de insumos Y DESCUENTA EL STOCK FÍSICO.
        CORRECCIÓN: Descuenta las reservas YA existentes para esta OP antes de intentar reservar más.
        """
        receta_model = RecetaModel()
        reserva_insumo_model = ReservaInsumoModel()
        reservas_realizadas_temp = []

        try:
            receta_id = orden_produccion['receta_id']
            op_id = orden_produccion['id'] # Necesitamos el ID de la OP
            cantidad_a_producir = float(orden_produccion.get('cantidad_planificada', 0))

            # --- EXTRAER FECHA ---
            f_plan = orden_produccion.get('fecha_inicio_planificada') or orden_produccion.get('fecha_planificada') or orden_produccion.get('fecha_meta')
            fecha_uso = date.today()
            if f_plan:
                 if isinstance(f_plan, str):
                     fecha_uso = date.fromisoformat(f_plan.split('T')[0])
                 elif isinstance(f_plan, (date, datetime)):
                     fecha_uso = f_plan if isinstance(f_plan, date) else f_plan.date()
            # ---------------------

            # 1. Obtener Ingredientes
            ingredientes_result = receta_model.get_ingredientes(receta_id)
            if not ingredientes_result.get('success'):
                raise Exception("No se pudieron obtener los ingredientes.")
            ingredientes = ingredientes_result.get('data', [])

            # 2. Obtener Reservas PREVIAS de esta OP (Lo que ya tiene cubierto)
            reservas_previas_map = {}
            if op_id:
                previas = reserva_insumo_model.find_all({'orden_produccion_id': op_id, 'estado': 'RESERVADO'})
                if previas.get('success'):
                    for r in previas.get('data', []):
                        iid = r['insumo_id']
                        reservas_previas_map[iid] = reservas_previas_map.get(iid, 0.0) + float(r['cantidad_reservada'])

            insumos_faltantes = []
            lotes_implicados = set()

            # 3. Iterar sobre cada insumo
            for ingrediente in ingredientes:
                insumo_id = ingrediente['id_insumo']
                cantidad_total_necesaria = float(ingrediente.get('cantidad', 0)) * cantidad_a_producir

                # --- CÁLCULO DEL NETO A RESERVAR ---
                ya_reservado = reservas_previas_map.get(insumo_id, 0.0)
                cantidad_restante_a_reservar = max(0.0, cantidad_total_necesaria - ya_reservado)

                logger.info(f"OP {op_id} Insumo {insumo_id}: Req {cantidad_total_necesaria}, Tiene {ya_reservado}, Falta reservar {cantidad_restante_a_reservar}")

                # Si ya está cubierto, pasamos al siguiente sin tocar stock
                if cantidad_restante_a_reservar <= 0.01:
                    continue

                # --- SI FALTA, BUSCAMOS LOTES ---
                verificacion_lotes = self._obtener_lotes_con_disponibilidad(insumo_id, fecha_limite_validez=fecha_uso)

                for lote in verificacion_lotes:
                    if cantidad_restante_a_reservar <= 0:
                        break

                    stock_fisico_lote = float(lote.get('cantidad_actual', 0))
                    cantidad_a_reservar_de_lote = min(stock_fisico_lote, cantidad_restante_a_reservar)

                    if cantidad_a_reservar_de_lote > 0:
                        # Crear reserva
                        datos_reserva = {
                            'orden_produccion_id': op_id,
                            'lote_inventario_id': lote['id_lote'],
                            'insumo_id': insumo_id,
                            'cantidad_reservada': cantidad_a_reservar_de_lote,
                            'usuario_reserva_id': usuario_id
                        }
                        res_creada = reserva_insumo_model.create(datos_reserva)

                        if res_creada.get('success'):
                            reservas_realizadas_temp.append({
                                'id_reserva': res_creada['data']['id'],
                                'id_lote': lote['id_lote'],
                                'cantidad': cantidad_a_reservar_de_lote
                            })
                            lotes_implicados.add(lote['id_lote'])

                            # Descontar Físico
                            nueva_cantidad = stock_fisico_lote - cantidad_a_reservar_de_lote
                            update_data = {'cantidad_actual': nueva_cantidad}
                            if nueva_cantidad <= 0: update_data['estado'] = 'agotado'
                            self.inventario_model.update(lote['id_lote'], update_data, 'id_lote')

                            cantidad_restante_a_reservar -= cantidad_a_reservar_de_lote

                if cantidad_restante_a_reservar > 0.01:
                    insumos_faltantes.append({'insumo_id': insumo_id, 'cantidad_faltante': cantidad_restante_a_reservar})

            # 4. Rollback si falla
            if insumos_faltantes:
                logger.warning(f"Faltantes tras reserva parcial OP {op_id}. Rollback...")
                for item_rollback in reservas_realizadas_temp:
                    reserva_insumo_model.delete(item_rollback['id_reserva'], 'id')
                    lote_actual = self.inventario_model.find_by_id(item_rollback['id_lote'], 'id_lote').get('data')
                    if lote_actual:
                        cant_actual = float(lote_actual.get('cantidad_actual', 0))
                        cant_restaurada = cant_actual + item_rollback['cantidad']
                        st = 'disponible' if cant_restaurada > 0 else 'agotado'
                        self.inventario_model.update(item_rollback['id_lote'], {'cantidad_actual': cant_restaurada, 'estado': st}, 'id_lote')

                return {'success': False, 'error': f"Stock insuficiente al reservar: {insumos_faltantes}"}

            # Actualizar stocks consolidados
            for lote_id in lotes_implicados:
                l_data = self.inventario_model.find_by_id(lote_id, 'id_lote').get('data')
                if l_data: self.insumo_controller.actualizar_stock_insumo(l_data['id_insumo'])

            return {'success': True, 'data': {'insumos_faltantes': [], 'lotes_implicados': list(lotes_implicados)}}

        except Exception as e:
            logger.error(f"Error reservando insumos OP {orden_produccion.get('id')}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def consumir_stock_reservado_para_op(self, orden_produccion_id: int) -> dict:
        """
        Marca el stock reservado como CONSUMIDO.
        NO descuenta stock físico nuevamente porque ya se hizo en la 'Reserva Dura'.
        """
        try:
            reservas_res = self.reserva_insumo_model.find_all(
                filters={'orden_produccion_id': orden_produccion_id, 'estado': 'RESERVADO'}
            )

            if not reservas_res.get('success'):
                return {'success': False, 'error': f"Error buscando reservas: {reservas_res.get('error')}"}

            reservas = reservas_res.get('data', [])
            if not reservas:
                logger.warning(f"No hay reservas activas para consumir en OP {orden_produccion_id}")
                return {'success': True} # No es error, puede que no use insumos

            # Solo actualizamos el estado de la reserva
            ids_reservas = [r['id'] for r in reservas]

            # Usamos update masivo si el modelo lo soporta, o bucle
            for reserva in reservas:
                 self.reserva_insumo_model.update(reserva['id'], {'estado': 'CONSUMIDO'}, 'id')

            logger.info(f"Reservas para OP {orden_produccion_id} marcadas como CONSUMIDO.")
            return {'success': True}

        except Exception as e:
            logger.error(f"Error crítico al consumir stock para OP {orden_produccion_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def liberar_stock_no_consumido_para_op(self, orden_produccion_id: int, insumo_id_perdido: int = None) -> dict:
        """
        Libera el stock de una OP cancelada o reseteada, devolviendo solo el stock "sano".
        1. Obtiene todas las reservas (RESERVADO y CONSUMIDO).
        2. Obtiene todos los registros de merma.
        3. Calcula el stock sano remanente por lote (Reservado - Mermado) y lo devuelve al inventario.
        4. Cambia el estado de todos los registros de reserva de la OP a 'CANCELADO'.
        """
        from app.models.registro_desperdicio_lote_insumo_model import RegistroDesperdicioLoteInsumoModel
        registro_merma_model = RegistroDesperdicioLoteInsumoModel()

        try:
            # 1. Obtener todas las reservas de la OP
            reservas_res = self.reserva_insumo_model.find_all(filters={'orden_produccion_id': orden_produccion_id})
            if not reservas_res.get('success') or not reservas_res.get('data'):
                logger.warning(f"No se encontraron reservas para liberar para la OP {orden_produccion_id}")
                return {'success': True}

            reservas = reservas_res.get('data', [])

            # 2. Obtener todas las mermas de la OP
            mermas_res = registro_merma_model.find_all_by_op_id(orden_produccion_id)
            mermas_por_lote = {}
            if mermas_res:
                for merma in mermas_res:
                    lote_id = merma['lote_insumo_id']
                    mermas_por_lote[lote_id] = mermas_por_lote.get(lote_id, 0) + float(merma['cantidad'])

            # --- CORRECCIÓN: Agregar reservas por lote antes de iterar ---
            reservas_por_lote = {}
            for reserva in reservas:
                lote_id = reserva['lote_inventario_id']
                if lote_id not in reservas_por_lote:
                    reservas_por_lote[lote_id] = {'total_reservado': 0.0, 'insumo_id': reserva['insumo_id']}
                reservas_por_lote[lote_id]['total_reservado'] += float(reserva.get('cantidad_reservada', 0))

            # 3. Calcular y devolver stock sano, iterando sobre la agregación
            insumos_a_actualizar = set()
            for lote_id, reserva_data in reservas_por_lote.items():
                insumo_id = reserva_data['insumo_id']
                insumos_a_actualizar.add(insumo_id)

                total_reservado_en_lote = reserva_data['total_reservado']
                merma_en_lote = mermas_por_lote.get(lote_id, 0)

                cantidad_a_devolver = max(0, total_reservado_en_lote - merma_en_lote)

                if cantidad_a_devolver > 0:
                    lote_res = self.inventario_model.find_by_id(lote_id, 'id_lote')
                    if lote_res.get('success'):
                        lote = lote_res['data']
                        cantidad_actual_lote = float(lote.get('cantidad_actual', 0))
                        nueva_cantidad_lote = cantidad_actual_lote + cantidad_a_devolver

                        update_data = {'cantidad_actual': nueva_cantidad_lote}
                        if lote.get('estado') in ['agotado', 'retirado']:
                            update_data['estado'] = 'disponible'

                        self.inventario_model.update(lote_id, update_data, 'id_lote')
                        logger.info(f"Devueltas {cantidad_a_devolver} unidades al lote {lote_id} desde OP {orden_produccion_id}")

            # 4. Cambiar el estado de todas las reservas de la OP a 'CANCELADO'
            self.reserva_insumo_model.db.table('reservas_insumos').update({'estado': 'CANCELADO'}).eq('orden_produccion_id', orden_produccion_id).execute()

            # 5. Actualizar stock consolidado de todos los insumos implicados
            for insumo_id in insumos_a_actualizar:
                self.insumo_controller.actualizar_stock_insumo(insumo_id)

            logger.info(f"Stock sano liberado y reservas canceladas para la OP {orden_produccion_id}")
            return {'success': True}

        except Exception as e:
            logger.error(f"Error crítico al liberar stock no consumido para OP {orden_produccion_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def consumir_stock_por_cantidad_producto(self, receta_id: int, cantidad_producto: float, op_id_referencia: int, motivo: str, usuario_id: int = None) -> dict:
        """
        Calcula los insumos necesarios para una cantidad de producto y los consume del inventario.
        Esta función realiza una verificación (dry run) primero y solo consume si todos los
        materiales están disponibles.

        Crea registros de trazabilidad (reservas con estado 'CONSUMIDO') para cada consumo.
        """
        receta_model = RecetaModel()
        try:
            # 1. Obtener ingredientes y calcular necesidades
            ingredientes_result = receta_model.get_ingredientes(receta_id)
            if not ingredientes_result.get('success'):
                return {'success': False, 'error': "No se pudieron obtener los ingredientes de la receta."}

            ingredientes = ingredientes_result.get('data', [])
            if not ingredientes:
                return {'success': True, 'message': 'La receta no tiene ingredientes, no se consume stock.'}

            # 2. Verificación (Dry Run)
            insumos_a_consumir = []
            for ingrediente in ingredientes:
                insumo_id = ingrediente['id_insumo']
                cantidad_necesaria = float(ingrediente.get('cantidad', 0)) * cantidad_producto
                if cantidad_necesaria <= 0:
                    continue

                lotes_disponibles = self._obtener_lotes_con_disponibilidad(insumo_id)
                stock_total_disponible = sum(lote['disponibilidad'] for lote in lotes_disponibles)

                if stock_total_disponible < cantidad_necesaria:
                    return {
                        'success': False,
                        'error': f"Stock insuficiente para {ingrediente.get('nombre_insumo', 'N/A')}. "
                                 f"Necesario: {cantidad_necesaria:.2f}, Disponible: {stock_total_disponible:.2f}"
                    }
                insumos_a_consumir.append({
                    'insumo_id': insumo_id,
                    'cantidad_necesaria': cantidad_necesaria,
                    'lotes_disponibles': lotes_disponibles
                })

            # 3. Consumo (Ejecución)
            insumos_afectados = set()
            for insumo in insumos_a_consumir:
                cantidad_restante_a_consumir = insumo['cantidad_necesaria']
                insumos_afectados.add(insumo['insumo_id'])

                for lote in insumo['lotes_disponibles']:
                    if cantidad_restante_a_consumir <= 0:
                        break

                    cantidad_a_consumir_de_lote = min(lote['disponibilidad'], cantidad_restante_a_consumir)

                    if cantidad_a_consumir_de_lote > 0:
                        cantidad_actual_lote = float(lote.get('cantidad_actual', 0))
                        nueva_cantidad_lote = cantidad_actual_lote - cantidad_a_consumir_de_lote

                        update_data = {'cantidad_actual': nueva_cantidad_lote}
                        if nueva_cantidad_lote <= 0:
                            update_data['estado'] = 'agotado'

                        # Actualizar el lote físico

                        self.inventario_model.update(lote['id_lote'], update_data, 'id_lote')

                        # Crear registro de trazabilidad (Reserva CONSUMIDA)
                        try:
                            if usuario_id:
                                datos_reserva_consumida = {
                                    'orden_produccion_id': op_id_referencia,
                                    'lote_inventario_id': lote['id_lote'],
                                    'insumo_id': insumo['insumo_id'],
                                    'cantidad_reservada': cantidad_a_consumir_de_lote,
                                    'usuario_reserva_id': usuario_id,
                                    'estado': 'CONSUMIDO'
                                }
                                self.reserva_insumo_model.create(datos_reserva_consumida)
                        except Exception as e_trazabilidad:
                            logger.error(f"Error creando registro de trazabilidad para consumo en OP {op_id_referencia}: {e_trazabilidad}")

                        cantidad_restante_a_consumir -= cantidad_a_consumir_de_lote

            # 4. Actualizar stock general
            for insumo_id in insumos_afectados:
                self.insumo_controller.actualizar_stock_insumo(insumo_id)

            logger.info(f"Consumo adicional de stock para OP {op_id_referencia} ({motivo}) completado.")
            return {'success': True}

        except Exception as e:
            logger.error(f"Error crítico al consumir stock por cantidad para OP {op_id_referencia}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}


    def _obtener_lotes_con_disponibilidad(self, insumo_id: int, fecha_limite_validez: date = None) -> List[Dict]:
        """
        Obtiene lotes con stock físicamente disponible y calcula la cantidad real disponible.
        FILTRA lotes no aptos (cuarentena, agotados, etc.) y aquellos cuya disponibilidad neta es cero o menos.
        """
        # 1. Obtener solo lotes potencialmente útiles ('disponible' o 'reservado')
        estados_validos = ['disponible', 'reservado']
        lotes_potenciales_res = self.inventario_model.find_all(
            filters={'id_insumo': insumo_id, 'estado': ('in', estados_validos)},
            order_by='f_ingreso.asc' # FIFO
        )

        if not lotes_potenciales_res.get('success') or not lotes_potenciales_res.get('data'):
            return []

        lotes_potenciales = lotes_potenciales_res.get('data', [])

        # 2. Obtener todas las reservas activas para estos lotes
        lote_ids = [lote['id_lote'] for lote in lotes_potenciales]
        if not lote_ids:
            return []

        reservas_res = self.reserva_insumo_model.find_all(
            filters={
                'lote_inventario_id': ('in', lote_ids),
                'estado': 'RESERVADO'
            }
        )

        reservas_por_lote = {}
        if reservas_res.get('success'):
            for reserva in reservas_res.get('data', []):
                lote_id = reserva['lote_inventario_id']
                reservas_por_lote[lote_id] = reservas_por_lote.get(lote_id, 0) + float(reserva['cantidad_reservada'])

        lotes_disponibles = []

        # 3. Calcular disponibilidad real y aplicar todos los filtros
        for lote in lotes_potenciales:
            # Filtro de vencimiento
            if fecha_limite_validez and lote.get('f_vencimiento'):
                try:
                    vencimiento_str = lote.get('f_vencimiento')
                    vencimiento = date.fromisoformat(vencimiento_str.split('T')[0])
                    if vencimiento < fecha_limite_validez:
                        continue # Lote vencido, saltar
                except (ValueError, TypeError):
                    pass # Fecha inválida, se procesa

            cantidad_fisica = float(lote.get('cantidad_actual', 0))
            cantidad_reservada = reservas_por_lote.get(lote['id_lote'], 0)
            disponibilidad_neta = cantidad_fisica - cantidad_reservada

            # Filtro de disponibilidad > 0
            if disponibilidad_neta > 0.001: # Usar tolerancia pequeña
                lote['disponibilidad'] = disponibilidad_neta
                lotes_disponibles.append(lote)

        return lotes_disponibles

    def verificar_stock_para_op(self, orden_produccion: Dict, fecha_requisito: date = None) -> dict:
        """
        Verifica stock considerando disponibilidad real, VENCIMIENTO y RESERVAS PREVIAS de la misma OP.
        """
        receta_model = RecetaModel()
        # Importamos modelo de reservas si no está en self
        from app.models.reserva_insumo import ReservaInsumoModel
        reserva_insumo_model = ReservaInsumoModel()

        try:
            receta_id = orden_produccion['receta_id']
            op_id = orden_produccion.get('id')
            cantidad_a_producir = float(orden_produccion.get('cantidad_planificada', 0))

            # --- DETERMINAR FECHA DE USO ---
            fecha_uso = fecha_requisito
            if not fecha_uso:
                f_plan = orden_produccion.get('fecha_inicio_planificada') or orden_produccion.get('fecha_meta')
                if f_plan:
                    if isinstance(f_plan, str):
                        fecha_uso = date.fromisoformat(f_plan.split('T')[0])
                    elif isinstance(f_plan, (date, datetime)):
                         fecha_uso = f_plan if isinstance(f_plan, date) else f_plan.date()
                else:
                    fecha_uso = date.today()

            # 1. Obtener Ingredientes
            ingredientes_result = receta_model.get_ingredientes(receta_id)
            if not ingredientes_result.get('success'):
                raise Exception("No se pudieron obtener los ingredientes.")
            ingredientes = ingredientes_result.get('data', [])

            # 2. Obtener RESERVAS YA HECHAS para esta OP (Corrección Clave)
            reservas_propias_map = {}
            if op_id:
                mis_reservas = reserva_insumo_model.find_all({'orden_produccion_id': op_id, 'estado': 'RESERVADO'})
                if mis_reservas.get('success'):
                    for r in mis_reservas.get('data', []):
                        iid = r['insumo_id']
                        reservas_propias_map[iid] = reservas_propias_map.get(iid, 0.0) + float(r['cantidad_reservada'])

            insumos_faltantes = []

            for ingrediente in ingredientes:
                insumo_id = ingrediente['id_insumo']
                cantidad_total_necesaria = float(ingrediente.get('cantidad', 0)) * cantidad_a_producir

                # --- RESTAR LO QUE YA TENGO RESERVADO ---
                ya_tengo = reservas_propias_map.get(insumo_id, 0.0)
                cantidad_pendiente_de_cubrir = max(0.0, cantidad_total_necesaria - ya_tengo)

                # Si ya tengo todo reservado, este insumo está OK.
                if cantidad_pendiente_de_cubrir == 0:
                    continue

                # --- BUSCAR STOCK SOLO PARA LO QUE FALTA ---
                lotes_con_disponibilidad = self._obtener_lotes_con_disponibilidad(
                    insumo_id,
                    fecha_limite_validez=fecha_uso
                )

                stock_disponible_total = sum(lote['disponibilidad'] for lote in lotes_con_disponibilidad)

                if stock_disponible_total < cantidad_pendiente_de_cubrir:
                    insumos_faltantes.append({
                        'insumo_id': insumo_id,
                        'nombre': ingrediente.get('nombre_insumo', 'N/A'),
                        'cantidad_necesaria': cantidad_total_necesaria,
                        'cantidad_reservada': ya_tengo,       # Dato informativo útil
                        'stock_disponible': stock_disponible_total,
                        'cantidad_faltante': cantidad_pendiente_de_cubrir - stock_disponible_total # Faltante REAL
                    })

            return {'success': True, 'data': {'insumos_faltantes': insumos_faltantes}}

        except Exception as e:
            logger.error(f"Error verificando stock: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def obtener_stock_disponible_insumo(self, insumo_id: int) -> dict:
        """
        Calcula el stock REALMENTE disponible de un insumo.
        Fórmula: (Suma de cantidad_actual en lotes 'disponible') - (Suma de cantidad_reservada en reservas 'RESERVADO').
        """
        try:
            # 1. Calcular el stock físico total sumando los lotes DISPONIBLES
            lotes_result = self.inventario_model.find_all(
                filters={
                    'id_insumo': insumo_id,
                    'estado': ('ilike', 'disponible'),
                    'cantidad_actual': ('gt', 0)
                }
            )
            if not lotes_result.get('success'):
                logger.error(f"Fallo al obtener lotes disponibles para insumo {insumo_id}: {lotes_result.get('error')}")
                stock_fisico_disponible = 0
            else:
                stock_fisico_disponible = sum(lote.get('cantidad_actual', 0) for lote in lotes_result.get('data', []))

            stock_disponible_real = stock_fisico_disponible

            if stock_disponible_real < 0: stock_disponible_real = 0 # Asegurar no negativo

            logger.debug(f"Stock disponible calculado para insumo {insumo_id}: {stock_disponible_real}")
            return {'success': True, 'data': {'stock_disponible': stock_disponible_real}}

        except Exception as e:
            logger.error(f"Error calculando stock disponible para insumo {insumo_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def obtener_lotes(self, filtros: Optional[Dict] = None) -> tuple:
        """Obtener todos los lotes con filtros opcionales"""
        try:
            # Aplicar filtros por defecto si es necesario
            filtros = filtros or {}

            # Buscar en base de datos
            result = self.inventario_model.find_all(filtros)

            if result['success']:
                # Serializar los datos
                serialized_data = self.schema.dump(result['data'], many=True)
                return self.success_response(data=serialized_data)
            else:
                return self.error_response(result['error'])

        except Exception as e:
            logger.error(f"Error obteniendo lotes: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def crear_lote(self, data: Dict, id_usuario:int) -> tuple:
        """Crear un nuevo lote de inventario"""
        try:
            data.pop('csrf_token', None)

            # --- LÓGICA MODIFICADA PARA ACEPTAR CUARENTENA ---
            # Si 'cantidad_actual' no se provee, se asume que es la 'cantidad_inicial'.
            if 'cantidad_actual' not in data and 'cantidad_inicial' in data:
                # Si se provee 'cantidad_en_cuarentena', la 'cantidad_actual' es la diferencia.
                if 'cantidad_en_cuarentena' in data:
                    try:
                        inicial = float(data['cantidad_inicial'])
                        cuarentena = float(data['cantidad_en_cuarentena'])
                        data['cantidad_actual'] = max(0, inicial - cuarentena)
                    except (ValueError, TypeError):
                        return self.error_response("Valores de cantidad inválidos.", 400)
                else:
                    # Si no hay cuarentena, 'actual' es igual a 'inicial'.
                    data['cantidad_actual'] = data['cantidad_inicial']

            # Corrección Definitiva: Eliminar costo_total ANTES de la validación.
            data.pop('costo_total', None)

            # Ahora sí, validamos los datos.
            validated_data = self.schema.load(data)
            # --------------------------

            validated_data['usuario_ingreso_id'] = id_usuario

            # Verificar que el insumo existe
            insumo_result = self.insumo_model.find_by_id(str(validated_data['id_insumo']), 'id_insumo')
            if not insumo_result['success']:
                return self.error_response('El insumo especificado no existe', 404)

            # Generar código de lote único
            codigo_insumo = insumo_result['data'].get('codigo_interno', 'INS')
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            codigo_lote = f"{codigo_insumo}-{timestamp}"

            # --- MODIFICACIÓN: Usar 'numero_lote_proveedor' si viene, sino generar ---
            if 'numero_lote_proveedor' not in validated_data or not validated_data['numero_lote_proveedor']:
                validated_data['numero_lote_proveedor'] = codigo_lote

            # Crear lote
            result = self.inventario_model.create(validated_data)

            if result['success']:
                logger.info(f"Lote creado exitosamente: {result['data']['id_lote']}")

                # Actualizar stock de seccion insumo automáticamente
                self.insumo_controller.actualizar_stock_insumo(validated_data['id_insumo'])

                try:
                    from app.controllers.orden_produccion_controller import OrdenProduccionController
                    orden_produccion_controller = OrdenProduccionController()
                    orden_produccion_controller.verificar_y_actualizar_ordenes_en_espera()
                except Exception as e_op:
                    logger.error(f"Error al ejecutar la verificación proactiva de OPs tras crear un lote de insumo: {e_op}", exc_info=True)

                serialized_data = self._serialize_data(result['data'])
                return self.success_response(
                    data=serialized_data,
                    message='Lote creado exitosamente',
                    status_code=201
                )
            else:
                return self.error_response(result['error'])

        except ValidationError as e:
            # Si aún así hay un error de validación, lo lanzamos para que la vista lo muestre.
            raise e
        except Exception as e:
            logger.error(f"Error creando lote: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def _serialize_data(self, data):
        """Convierte objetos no serializables a tipos compatibles con JSON"""
        try:
            if isinstance(data, dict):
                return {key: self._serialize_data(value) for key, value in data.items()}
            elif isinstance(data, list):
                return [self._serialize_data(item) for item in data]
            elif isinstance(data, (Decimal, float)):
                return float(data)
            elif isinstance(data, UUID):
                return str(data)
            elif isinstance(data, (date, datetime)):
                # ✅ Asegurar que siempre devuelva string ISO
                if hasattr(data, 'isoformat'):
                    return data.isoformat()
                return str(data)
            elif data is None:
                return None
            else:
                return str(data)  # ✅ Convertir cualquier otro tipo a string
        except Exception as e:
            logger.error(f"Error serializando dato: {data}, error: {e}")
            return str(data)  # Fallback: convertir a string

    def success_response(self, data=None, message=None, status_code=200):
        """Override para asegurar serialización correcta"""
        response = {
            'success': True,
            'data': data,
            'message': message
        }
        return response, status_code

    def error_response(self, error_message, status_code=400):
        """Override para asegurar serialización correcta"""
        response = {
            'success': False,
            'error': str(error_message)
        }
        return response, status_code

    def obtener_lotes_por_insumo(self, id_insumo: str, solo_disponibles: bool = True) -> tuple:
        """Obtener lotes de un insumo específico"""
        try:
            result = self.inventario_model.find_by_insumo(id_insumo, solo_disponibles)

            if result['success']:
                return self.success_response(data=result['data'])
            else:
                return self.error_response(result['error'])

        except Exception as e:
            logger.error(f"Error obteniendo lotes: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)


    def obtener_lote_por_id(self, id_lote: str) -> tuple:
        """
        Obtener un lote específico por su ID, incluyendo su historial de control de calidad.
        """
        try:
            lote_result = self.inventario_model.get_lote_detail_for_view(id_lote)

            if not lote_result.get('success') or not lote_result.get('data'):
                return self.error_response('Lote no encontrado', 404)

            lote_data = lote_result['data']

            # Cargar el historial de control de calidad
            cc_model = ControlCalidadInsumoModel()

            # --- MODIFICACIÓN: Llamar a la función corregida ---
            historial_result = cc_model.find_by_lote_id(id_lote)

            if historial_result.get('success'):
                # Adjunta la lista (puede estar vacía) al lote
                lote_data['historial_calidad'] = historial_result.get('data', [])
            else:
                lote_data['historial_calidad'] = []
                logger.warning(f"No se pudo cargar el historial de calidad para el lote {id_lote}: {historial_result.get('error')}")

            # Cargar historial de desperdicios
            desperdicio_model = RegistroDesperdicioLoteInsumoModel()
            historial_desperdicio_result = desperdicio_model.find_all(filters={'lote_insumo_id': id_lote})
            if historial_desperdicio_result.get('success'):
                lote_data['historial_desperdicios'] = historial_desperdicio_result.get('data', [])
            else:
                lote_data['historial_desperdicios'] = []
                logger.warning(f"No se pudo cargar el historial de desperdicios para el lote {id_lote}: {historial_desperdicio_result.get('error')}")

            serialized_data = self._serialize_data(lote_data)
            return self.success_response(data=serialized_data)

        except Exception as e:
            logger.error(f"Error obteniendo el detalle del lote por ID: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def actualizar_lote_parcial(self, id_lote: str, data: Dict) -> tuple:
        """Actualizar campos específicos de un lote (PATCH)"""
        try:
            # Validar que el lote existe
            lote_existente = self.inventario_model.find_by_id(id_lote, 'id_lote')
            if not lote_existente['success']:
                return self.error_response('Lote no encontrado', 404)

            # ✅ Obtener datos actuales del lote para validaciones
            lote_actual = lote_existente['data']

            # Validar datos parciales con el esquema
            validated_data = self.schema.load(data, partial=True)

            # Filtrar solo los campos permitidos para actualización
            campos_permitidos = {
                'cantidad_actual', 'ubicacion_fisica', 'precio_unitario',
                'numero_lote_proveedor', 'f_vencimiento', 'observaciones'
            }

            datos_actualizacion = {}
            for campo, valor in validated_data.items():
                if campo in campos_permitidos and valor is not None:
                    datos_actualizacion[campo] = valor

            # Si no hay datos válidos para actualizar
            if not datos_actualizacion:
                return self.error_response('No se proporcionaron datos válidos para actualizar', 400)

            # ✅ Validación manual de cantidad_actual vs cantidad_inicial
            if 'cantidad_actual' in datos_actualizacion:
                cantidad_actual_nueva = datos_actualizacion['cantidad_actual']
                cantidad_inicial_actual = lote_actual.get('cantidad_inicial')

                if cantidad_inicial_actual is not None and cantidad_actual_nueva > cantidad_inicial_actual:
                    return self.error_response(
                        f'La cantidad actual ({cantidad_actual_nueva}) no puede ser mayor que la cantidad inicial ({cantidad_inicial_actual})',
                        400
                    )

            # ✅ AGREGAR timestamp de actualización (ahora con datetime importado)
            datos_actualizacion['updated_at'] = datetime.now().isoformat()

            # Actualizar el lote
            result = self.inventario_model.update(id_lote, datos_actualizacion, 'id_lote')

            if result['success']:
                logger.info(f"Lote {id_lote} actualizado: {list(datos_actualizacion.keys())}")

                # Si se actualizó la cantidad, actualizar el stock del insumo
                if 'cantidad_actual' in datos_actualizacion:
                    # ✅ Llamada automática de actualización de stock
                    self.insumo_controller.actualizar_stock_insumo(lote_actual['id_insumo'])

                # Obtener el lote actualizado con todos los datos
                lote_actualizado = self.inventario_model.find_by_id(id_lote, 'id_lote')

                if lote_actualizado['success']:
                    serialized_data = self._serialize_data(lote_actualizado['data'])
                else:
                    serialized_data = self._serialize_data(result['data'])

                return self.success_response(
                    data=serialized_data,
                    message='Lote actualizado exitosamente'
                )
            else:
                return self.error_response(result['error'])
        except ValidationError as e:
            # Re-lanzar la excepción de validación para que la vista la maneje
            # y devuelva un JSON con los detalles del error.
            raise e
        except Exception as e:
            logger.error(f"Error actualizando lote: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_stock_consolidado(self, filtros: Optional[Dict] = None) -> tuple:
        """Obtener stock consolidado"""
        try:
            result = self.inventario_model.obtener_stock_consolidado(filtros)

            if result['success']:
                return self.success_response(data=result['data'])
            else:
                return self.error_response(result['error'])

        except Exception as e:
            logger.error(f"Error obteniendo stock consolidado: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_alertas(self) -> tuple:
        """Obtener alertas de inventario"""
        try:
            dias_vencimiento = self.config_controller.obtener_dias_vencimiento()
            # Obtener alertas de stock bajo
            stock_result = self.inventario_model.obtener_stock_consolidado({'estado_stock': 'BAJO'})

            # Obtener alertas de vencimiento
            vencimiento_result = self.inventario_model.obtener_por_vencimiento(dias_vencimiento)

            alertas = {
                'stock_bajo': stock_result['data'] if stock_result['success'] else [],
                'proximos_vencimientos': vencimiento_result['data'] if vencimiento_result['success'] else []
            }

            total_alertas = len(alertas['stock_bajo']) + len(alertas['proximos_vencimientos'])

            if total_alertas > 0:
                from app.controllers.registro_controller import RegistroController
                registro_controller = RegistroController()
                from types import SimpleNamespace
                usuario_sistema = SimpleNamespace(nombre='Sistema', apellido='', roles=['SISTEMA'])

                if alertas['stock_bajo']:
                    detalle = f"Se detectaron {len(alertas['stock_bajo'])} insumos con bajo stock."
                    registro_controller.crear_registro(usuario_sistema, 'Alertas', 'Insumos', detalle)

                if alertas['proximos_vencimientos']:
                    detalle = f"Se detectaron {len(alertas['proximos_vencimientos'])} lotes próximos a vencer."
                    registro_controller.crear_registro(usuario_sistema, 'Alertas', 'Lotes', detalle)

            return self.success_response(
                data=alertas,
                message=f'Se encontraron {total_alertas} alertas activas'
            )

        except Exception as e:
            logger.error(f"Error obteniendo alertas: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_conteo_alertas_stock(self) -> int:
        """Obtiene el conteo de insumos con stock bajo (crítico)."""
        try:
            # Llamamos a obtener_stock_consolidado con el filtro 'estado_stock': 'BAJO'
            stock_bajo_result = self.inventario_model.obtener_stock_consolidado({'estado_stock': 'BAJO'})

            if stock_bajo_result.get('success'):
                # Devolvemos la cantidad de elementos en la lista de datos
                return len(stock_bajo_result.get('data', []))
            return 0
        except Exception as e:
            logger.error(f"Error contando alertas de stock: {str(e)}")
            return 0
    def obtener_conteo_vencimientos(self) -> int:
        """Obtiene el conteo de lotes próximos a vencer (crítico)."""
        try:
            dias_vencimiento = self.config_controller.obtener_dias_vencimiento()
            # Llama al método del modelo que busca lotes por vencer en el número de días configurable
            vencimiento_result = self.inventario_model.obtener_por_vencimiento(dias_vencimiento)

            if vencimiento_result.get('success'):
                return len(vencimiento_result.get('data', []))
            return 0
        except Exception as e:
            logger.error(f"Error contando alertas de vencimiento: {str(e)}")
            return 0

    def obtener_lotes_agrupados_para_vista(self) -> tuple:
        """
        Obtiene los lotes, los agrupa por insumo y enriquece con datos del catálogo.
        CORRECCIÓN: Calcula el stock total sumando los lotes físicos, ignorando el campo
        'stock_actual' de la tabla catálogo que puede estar desactualizado.
        """
        try:
            # 1. Obtener la lista definitiva de insumos desde el catálogo
            catalogo_response = self.insumo_model.find_all(filters={'activo': True})
            if not catalogo_response.get('success'):
                return self.error_response(catalogo_response.get('error', 'No se pudo obtener el catálogo de insumos.'), 500)

            insumos_del_catalogo = catalogo_response.get('data', [])

            # 2. Obtener todos los lotes y agruparlos por insumo_id
            lotes_response, _ = self.obtener_lotes_para_vista()
            if not lotes_response.get('success'):
                return self.error_response(lotes_response.get('error', 'No se pudieron obtener los lotes de inventario.'), 500)
           # START MODIFICATION: Calculate reserved quantities
            reservas_response = self.reserva_insumo_model.find_all(filters={'estado': 'RESERVADO'})
            reservas_por_lote = {}
            if reservas_response.get('success'):
                for reserva in reservas_response.get('data', []):
                    lote_id = reserva.get('lote_inventario_id')
                    if lote_id:
                        cantidad = float(reserva.get('cantidad_reservada', 0))
                        reservas_por_lote[lote_id] = reservas_por_lote.get(lote_id, 0) + cantidad
            # END MODIFICATION

            lotes_por_insumo = {}
            for lote in lotes_response.get('data', []):
                insumo_id = lote.get('id_insumo')
                if insumo_id:
                    if insumo_id not in lotes_por_insumo:
                        lotes_por_insumo[insumo_id] = []

                    # Convertir cantidades a float para asegurar suma correcta
                    # IMPORTANTE: Usamos cantidad_actual (físico disponible en lote)
                    lote['cantidad_actual'] = float(lote.get('cantidad_actual') or 0)
                    lote['cantidad_en_cuarentena'] = float(lote.get('cantidad_en_cuarentena') or 0)
                    # START MODIFICATION: Add reserved quantity to lot
                    lote['cantidad_reservada'] = reservas_por_lote.get(lote.get('id_lote'), 0)
                    # END MODIFICATION
                    lotes_por_insumo[insumo_id].append(lote)

            # 3. Construir el resultado final iterando sobre los insumos del catálogo
            resultado_final = []
            for insumo in insumos_del_catalogo:
                insumo_id = insumo['id_insumo']
                lotes_de_insumo = lotes_por_insumo.get(insumo_id, [])

                # --- CÁLCULO DE STOCK REAL ---
                # Sumamos la cantidad física actual de todos los lotes asociados.
                # Esto es la "única fuente de verdad" para el stock disponible.
                stock_fisico_calculado = sum(lote['cantidad_actual'] for lote in lotes_de_insumo)

                # Crear la estructura de datos para la vista
                datos_insumo_para_vista = {
                    'id_insumo': insumo_id,
                    'insumo_nombre': insumo.get('nombre', 'N/A'),
                    'insumo_categoria': insumo.get('categoria', 'Sin categoría'),
                    'insumo_unidad_medida': insumo.get('unidad_medida', ''),

                    # Usamos el valor calculado para ambos campos visuales
                    'stock_actual': stock_fisico_calculado,
                    'stock_total': stock_fisico_calculado,

                    'lotes': lotes_de_insumo
                }

                # Calcular el estado general basado en el stock disponible real
                if stock_fisico_calculado > 0:
                    datos_insumo_para_vista['estado_general'] = 'Disponible'
                else:
                    datos_insumo_para_vista['estado_general'] = 'Agotado'

                resultado_final.append(datos_insumo_para_vista)

            # Ordenar por nombre de insumo
            resultado_final.sort(key=lambda x: x['insumo_nombre'])

            return self.success_response(data=resultado_final)

        except Exception as e:
            logger.error(f"Error agrupando lotes para la vista (robusto): {str(e)}", exc_info=True)
            return self.error_response(f'Error interno: {str(e)}', 500)

    def eliminar_lote(self, id_lote: str) -> tuple:
        """Eliminar un lote de inventario"""
        try:
            # Verificar que el lote existe
            lote_existente = self.inventario_model.find_by_id(id_lote, 'id_lote')
            if not lote_existente['success']:
                return self.error_response('Lote no encontrado', 404)

            # Eliminar el lote
            result = self.inventario_model.delete(id_lote, 'id_lote')

            if result['success']:
                logger.info(f"Lote {id_lote} eliminado exitosamente")
                return self.success_response(message='Lote eliminado exitosamente')
            else:
                return self.error_response(result['error'])

        except Exception as e:
            logger.error(f"Error eliminando lote: {str(e)}")

            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_lotes_para_vista(self, filtros: Optional[Dict] = None) -> tuple:
        """
        Obtiene todos los lotes con datos enriquecidos para ser mostrados en una tabla.
        """
        try:
            result = self.inventario_model.get_all_lotes_for_view(filtros)
            if result['success']:
                # No es necesario serializar con el schema porque los datos ya están aplanados
                return self.success_response(data=result['data'])
            else:
                return self.error_response(result['error'])
        except Exception as e:
            logger.error(f"Error obteniendo lotes para la vista: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_insumos_bajo_stock(self) -> tuple:
        """
        Obtiene la lista de insumos con estado de stock 'BAJO'.
        Retorna (response_dict, status_code)
        """
        try:
            # Reutilizamos el método del modelo, filtrando por 'BAJO'
            stock_bajo_result = self.inventario_model.obtener_stock_consolidado({'estado_stock': 'BAJO'})

            if stock_bajo_result.get('success'):
                insumos_bajo_stock = stock_bajo_result.get('data', [])
                return self.success_response(data=insumos_bajo_stock)

            return self.error_response(stock_bajo_result.get('error', 'Error al obtener insumos bajo stock'), 500)

        except Exception as e:
            logger.error(f"Error obteniendo lista de insumos bajo stock: {str(e)}")

            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_conteo_vencimientos(self) -> int:
        """Obtiene el conteo de lotes próximos a vencer (crítico)."""
        try:
            # Llama al método del modelo que busca lotes por vencer en 7 días
            # Se asume que el método del modelo ya está implementado correctamente.
            vencimiento_result = self.inventario_model.obtener_por_vencimiento(7)

            if vencimiento_result.get('success'):
                return len(vencimiento_result.get('data', []))
            return 0
        except Exception as e:
            logger.error(f"Error contando alertas de vencimiento: {str(e)}")
            return 0

    def liberar_lote_de_cuarentena_alerta(self, lote_id: str, usuario_id: int) -> tuple:
        """
        Libera un lote de CUARENTENA, devolviéndolo a su estado previo a la alerta.
        """
        try:
            lote_res = self.inventario_model.find_by_id(lote_id, 'id_lote')
            if not lote_res.get('success') or not lote_res.get('data'):
                return self.error_response('Lote no encontrado', 404)

            lote = lote_res['data']

            afectado_res = self.db.table('alerta_riesgo_afectados').select('estado_previo').eq('tipo_entidad', 'lote_insumo').eq('id_entidad', lote_id).order('id', desc=True).limit(1).execute().data

            estado_previo = 'disponible'
            if afectado_res and afectado_res[0].get('estado_previo'):
                estado_previo = afectado_res[0]['estado_previo']

            estado_destino = 'disponible' if 'en revision' in estado_previo.lower() else estado_previo

            cantidad_en_cuarentena = float(lote.get('cantidad_en_cuarentena', 0))
            cantidad_actual = float(lote.get('cantidad_actual', 0))

            nueva_cantidad_actual = cantidad_actual + cantidad_en_cuarentena

            update_data = {
                'estado': estado_destino,
                'cantidad_actual': nueva_cantidad_actual,
                'cantidad_en_cuarentena': 0,
                'motivo_cuarentena': None
            }

            result = self.inventario_model.update(lote_id, update_data, 'id_lote')
            if not result.get('success'):
                return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500)

            self.insumo_controller.actualizar_stock_insumo(lote['id_insumo'])

            return self.success_response(message="Lote liberado de cuarentena de alerta.")

        except Exception as e:
            logger.error(f"Error en liberar_lote_de_cuarentena_alerta: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def marcar_lote_retirado_alerta(self, lote_id: str, usuario_id: int):
        """
        Marca un lote como 'retirado' por una alerta y anula su stock.
        """
        try:
            lote_res = self.inventario_model.find_by_id(lote_id, 'id_lote')
            if not lote_res.get('success'):
                return self.error_response('Lote no encontrado', 404)
            lote = lote_res['data']

            update_data = {
                'estado': 'retirado',
                'cantidad_actual': 0,
                'cantidad_en_cuarentena': 0,
                'observaciones': f"Lote retirado por alerta de riesgo. Usuario ID: {usuario_id}."
            }
            result = self.inventario_model.update(lote_id, update_data, 'id_lote')

            if not result.get('success'):
                return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500)

            self.insumo_controller.actualizar_stock_insumo(lote['id_insumo'])

            return self.success_response(message="Lote marcado como retirado.")
        except Exception as e:
            logger.error(f"Error en marcar_lote_retirado_alerta: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)


    def poner_lote_en_cuarentena(self, lote_id: str, motivo: str, cantidad: float, usuario_id: int, resultado_inspeccion: str = None, foto_file=None) -> tuple:
        """
        Mueve una cantidad de un lote a cuarentena.
        CORRECCIÓN: Considera el stock RESERVADO como parte del stock físico disponible para mover.
        Si se mueve a cuarentena, cancela las reservas asociadas y actualiza las OPs afectadas.
        """
        from app.controllers.usuario_controller import UsuarioController
        from app.models.notificacion import NotificacionModel
        from app.controllers.control_calidad_insumo_controller import ControlCalidadInsumoController
        # Importar modelo de reservas (asegurar que esté disponible)
        from app.models.reserva_insumo import ReservaInsumoModel

        try:
            # 1. Obtener el lote
            lote_res = self.inventario_model.find_by_id(lote_id, 'id_lote')
            if not lote_res.get('success') or not lote_res.get('data'):
                return self.error_response('Lote no encontrado', 404)

            lote = lote_res['data']
            cantidad_db_disponible = float(lote.get('cantidad_actual') or 0)
            cantidad_actual_cuarentena = float(lote.get('cantidad_en_cuarentena') or 0)

            # --- PASO CRÍTICO: RECUPERAR Y SUMAR STOCK RESERVADO ---
            # En reserva dura, 'cantidad_actual' es 0, pero el stock está ahí (en reservas).
            reserva_model = ReservaInsumoModel()
            reservas_activas_res = reserva_model.find_all(filters={'lote_inventario_id': lote_id, 'estado': 'RESERVADO'})
            reservas_activas = reservas_activas_res.get('data', []) if reservas_activas_res.get('success') else []

            cantidad_reservada = sum(float(r.get('cantidad_reservada', 0)) for r in reservas_activas)

            # Calculamos el "Físico Real" que podemos tocar
            stock_fisico_movible = cantidad_db_disponible + cantidad_reservada
            # -------------------------------------------------------

            # Validaciones
            motivo_final = motivo or resultado_inspeccion
            if not motivo_final:
                return self.error_response("Se requiere un motivo para la cuarentena.", 400)

            if cantidad <= 0:
                return self.error_response("La cantidad debe ser un número positivo.", 400)

            # Validar contra el stock físico total (no solo el disponible en DB)
            cantidad_a_mover = cantidad
            if cantidad_a_mover > stock_fisico_movible:
                logger.warning(f"Solicitado {cantidad} a cuarentena, pero físico real es {stock_fisico_movible}. Ajustando al máximo.")
                cantidad_a_mover = stock_fisico_movible

            # --- CÁLCULO DE NUEVOS SALDOS ---
            nueva_cantidad_cuarentena = cantidad_actual_cuarentena + cantidad_a_mover

            # El remanente (lo que no se fue a cuarentena) queda como DISPONIBLE
            # Nota: Al haber un problema de calidad, "rompemos" las reservas, así que todo lo que sobre se libera.
            nueva_cantidad_disponible = stock_fisico_movible - cantidad_a_mover

            # Determinar nuevo estado
            nuevo_estado = 'agotado'
            if nueva_cantidad_disponible > 0:
                nuevo_estado = 'disponible'
            elif nueva_cantidad_cuarentena > 0:
                nuevo_estado = 'cuarentena'

            # --- ACTUALIZACIÓN DE LOTE EN DB ---
            update_data = {
                'estado': nuevo_estado,
                'motivo_cuarentena': motivo_final,
                'cantidad_en_cuarentena': nueva_cantidad_cuarentena,
                'cantidad_actual': nueva_cantidad_disponible
            }
            result = self.inventario_model.update(lote_id, update_data, 'id_lote')

            if not result.get('success'):
                return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500)

            # --- GESTIÓN DE IMPACTO EN RESERVAS Y OPs ---
            # Si movimos stock que estaba comprometido, debemos cancelar las reservas.
            if reservas_activas:
                ops_afectadas = set()
                for reserva in reservas_activas:
                    if reserva.get('orden_produccion_id'):
                        ops_afectadas.add(reserva['orden_produccion_id'])

                    # Eliminar la reserva (ya no es válida porque el lote está en cuarentena/movido)
                    reserva_model.delete(reserva['id'], 'id')

                logger.info(f"Se cancelaron {len(reservas_activas)} reservas del lote {lote_id} al pasar a cuarentena.")

                # Regresar las OPs afectadas a "EN ESPERA" para que el planificador sepa que faltan materiales
                for op_id in ops_afectadas:
                    # Solo si estaba lista para producir (si ya inició, requiere intervención manual mayor)
                    op_data_res = self.op_model.find_by_id(op_id)
                    if op_data_res.get('success') and op_data_res['data'].get('estado') == 'LISTA PARA PRODUCIR':
                        self.op_model.cambiar_estado(
                            op_id, 'EN ESPERA',
                            observaciones=f"Regresada a EN ESPERA automáticamente. El lote {lote.get('numero_lote_proveedor')} pasó a cuarentena."
                        )

            # --- REGISTRO DE CALIDAD ---
            control_calidad_controller = ControlCalidadInsumoController()
            foto_url = None
            if foto_file:
                foto_url = control_calidad_controller._subir_foto_y_obtener_url(foto_file, lote_id)

            registro_cc_result, _ = control_calidad_controller.crear_registro_control_calidad(
                lote_id=lote_id,
                usuario_id=usuario_id,
                decision='EN_CUARENTENA',
                comentarios=motivo_final,
                orden_compra_id=None,
                resultado_inspeccion=resultado_inspeccion or 'Cuarentena Manual',
                foto_url=foto_url
            )

            if not registro_cc_result.get('success'):
                logger.error(f"Fallo al crear registro CC: {registro_cc_result.get('error')}")

            # --- NOTIFICACIONES (Opcional) ---
            try:
                usuario_controller = UsuarioController()
                gerentes_res = usuario_controller.obtener_usuarios_por_rol(['GERENTE'])
                if gerentes_res.get('success'):
                    notificacion_model = NotificacionModel()
                    insumo_res = self.insumo_model.find_by_id(str(lote['id_insumo']), 'id_insumo')
                    nombre_insumo = insumo_res['data'].get('nombre', 'Desconocido') if insumo_res.get('success') else 'Desconocido'

                    for gerente in gerentes_res['data']:
                        mensaje = f"El lote {lote.get('numero_lote_proveedor')} de {nombre_insumo} pasó a cuarentena."
                        notificacion_model.create({
                            'usuario_id': gerente['id'], 'mensaje': mensaje, 'tipo': 'ALERTA',
                            'url_destino': url_for('inventario_view.detalle_lote', id_lote=lote_id)
                        })
            except Exception as e_notif:
                logger.warning(f"Error enviando notificaciones: {e_notif}")

            # Actualizar stock consolidado
            self.insumo_controller.actualizar_stock_insumo(lote['id_insumo'])

            return self.success_response(message="Lote puesto en cuarentena con éxito. Reservas afectadas liberadas.")

        except Exception as e:
            logger.error(f"Error en poner_lote_en_cuarentena: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def liberar_lote_de_cuarentena(self, lote_id: str, cantidad_a_liberar: float) -> tuple:
        """
        Mueve una cantidad de CUARENTENA a DISPONIBLE.
        Si el lote está en cuarentena por trazabilidad (stock 0), lo devuelve al estado AGOTADO.
        Usa estados en minúscula.
        """
        try:
            lote_res = self.inventario_model.find_by_id(lote_id, 'id_lote')
            if not lote_res.get('success') or not lote_res.get('data'):
                return self.error_response('Lote no encontrado', 404)

            lote = lote_res['data']
            cantidad_actual_disponible = float(lote.get('cantidad_actual') or 0)
            cantidad_actual_cuarentena = float(lote.get('cantidad_en_cuarentena') or 0)
            estado_actual = lote.get('estado')

            # Caso especial: Liberar un lote de cuarentena por trazabilidad
            if estado_actual == 'cuarentena' and cantidad_actual_disponible <= 0 and cantidad_actual_cuarentena <= 0:
                update_data = {
                    'estado': 'agotado',
                    'motivo_cuarentena': None # Limpiar motivo
                }
                result = self.inventario_model.update(lote_id, update_data, 'id_lote')
                if not result.get('success'):
                    return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500)

                return self.success_response(message="Lote liberado de cuarentena con éxito.")

            # Caso normal: Liberar una cantidad de un lote con stock en cuarentena
            else:
                if cantidad_a_liberar <= 0:
                    return self.error_response("La cantidad a liberar debe ser un número positivo.", 400)

                if cantidad_a_liberar > cantidad_actual_cuarentena:
                    msg = f"No puede liberar {cantidad_a_liberar} unidades. Solo hay {cantidad_actual_cuarentena} en cuarentena."
                    return self.error_response(msg, 400)

                # Lógica de resta y suma
                nueva_cantidad_cuarentena = cantidad_actual_cuarentena - cantidad_a_liberar
                nueva_cantidad_disponible = cantidad_actual_disponible + cantidad_a_liberar

                # Decidir el nuevo estado y motivo
                nuevo_estado = 'cuarentena'
                nuevo_motivo = lote.get('motivo_cuarentena')

                if nueva_cantidad_cuarentena <= 0:
                    nuevo_motivo = None # Limpiar motivo
                    # Verificar si el lote estaba reservado antes de la cuarentena
                    reservas_existentes = self.reserva_insumo_model.find_all(filters={'lote_inventario_id': lote_id}).get('data', [])
                    if reservas_existentes:
                        nuevo_estado = 'reservado'
                    elif nueva_cantidad_disponible > 0:
                        nuevo_estado = 'disponible'
                    else:
                        nuevo_estado = 'agotado'

                update_data = {
                    'estado': nuevo_estado,
                    'motivo_cuarentena': nuevo_motivo,
                    'cantidad_en_cuarentena': nueva_cantidad_cuarentena,
                    'cantidad_actual': nueva_cantidad_disponible
                }

                result = self.inventario_model.update(lote_id, update_data, 'id_lote')
                if not result.get('success'):
                    return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500)

                # Actualizar el stock consolidado del insumo
                self.insumo_controller.actualizar_stock_insumo(lote['id_insumo'])

                # Disparar la verificación de cierre de alertas
                try:
                    alerta_model = AlertaRiesgoModel()
                    alertas_asociadas = alerta_model.db.table('alerta_riesgo_afectados').select('alerta_id').eq('tipo_entidad', 'lote_insumo').eq('id_entidad', lote_id).execute().data
                    if alertas_asociadas:
                        alerta_ids = {a['alerta_id'] for a in alertas_asociadas}
                        for alerta_id in alerta_ids:
                            alerta_model.verificar_y_cerrar_alerta(alerta_id)
                except Exception as e_alert:
                    logger.error(f"Error al verificar alertas tras liberar lote de insumo {lote_id}: {e_alert}", exc_info=True)

                return self.success_response(message="Cantidad liberada de cuarentena con éxito.")

        except Exception as e:
            logger.error(f"Error en liberar_lote_de_cuarentena (insumo): {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def obtener_lotes_y_conteo_insumos_en_cuarentena(self) -> dict:
        """Obtiene los lotes y el conteo de insumos en estado 'cuarentena'."""
        try:
            # Usamos el método que ya trae los datos enriquecidos para la vista
            result = self.inventario_model.get_all_lotes_for_view(filtros={'estado': 'cuarentena'})
            if result.get('success'):
                lotes = result.get('data', [])
                return {'count': len(lotes), 'data': lotes}
            return {'count': 0, 'data': []}
        except Exception as e:
            logger.error(f"Error obteniendo insumos en cuarentena: {str(e)}")
            return {'count': 0, 'data': []}

    def obtener_trazabilidad_lote(self, id_lote):
        """
        Obtiene la trazabilidad ascendente estricta para un lote de insumo:
        Lote Insumo -> OP -> Lote Producto -> Pedido.

        El ancho del flujo (value) se calcula por prorrateo en cada etapa
        para conservar la cantidad original del insumo trazado.
        """
        try:
            trazabilidad_model = TrazabilidadModel()
            # --- MODIFICACIÓN: Crear el node_map aquí ---
            links = []
            node_map = {}
            # --- FIN MODIFICACIÓN ---

            resultado = trazabilidad_model.obtener_trazabilidad_completa_lote_insumo(id_lote)

            # --- 1. NODO INICIAL: LOTE INSUMO ---
            lote_insumo_resp = self.inventario_model.find_by_id(id_lote, 'id_lote')
            if not lote_insumo_resp.get('success'):
                return self.error_response('Lote de insumo no encontrado', 404)

            lote_insumo = lote_insumo_resp.get('data')
            lote_insumo_node = f"Lote Insumo: {lote_insumo.get('numero_lote_proveedor') or id_lote[:8]}"

            # --- AÑADIR URL DEL NODO INICIAL ---
            node_map[lote_insumo_node] = url_for('inventario_view.detalle_lote', id_lote=id_lote)

            # --- 2. ENLACE 1: LOTE INSUMO -> OP ---

            reservas_insumo_resp = self.reserva_insumo_model.find_all(
                filters={'lote_inventario_id': str(id_lote)}
            )

            if not reservas_insumo_resp.get('success') or not reservas_insumo_resp.get('data'):
                logger.info(f"Lote {id_lote} no tiene reservas de insumos.")
                # --- DEVOLVER node_map INCLUSO SI ESTÁ VACÍO ---
                return self.success_response({"links": [], "node_map": node_map})

            op_consumo = {}
            op_ids = set()
            for reserva in reservas_insumo_resp.get('data', []):
                id_op = reserva.get('orden_produccion_id')
                if id_op:
                    op_ids.add(id_op)
                    cantidad = float(reserva.get('cantidad_reservada', 0) or 0) + float(reserva.get('cantidad_consumida', 0) or 0)
                    op_consumo[id_op] = op_consumo.get(id_op, 0.0) + cantidad

            if not op_ids:
                logger.info(f"El lote {id_lote} no ha sido utilizado en ninguna OP.")
                # --- DEVOLVER node_map ---
                return self.success_response({"links": [], "node_map": node_map})

            ops_resp = self.op_model.find_all(filters={'id': ('in', list(op_ids))})
            op_nodes = {}

            if not ops_resp.get('success'):
                 return self.error_response(f"Error al buscar OPs: {ops_resp.get('error')}")

            for op in ops_resp.get('data', []):
                op_id = op.get('id')
                op_node_name = f"OP: {op.get('codigo') or op_id}"
                op_nodes[op_id] = op_node_name

                # --- AÑADIR URL DE LA OP ---
                node_map[op_node_name] = url_for('orden_produccion.detalle', id=op_id)

                cantidad_trazada_op = op_consumo.get(op_id, 0.0)
                if cantidad_trazada_op > 0:
                    links.append({
                        "source_name": lote_insumo_node,
                        "target_name": op_node_name,
                        "value": cantidad_trazada_op
                    })

            # --- 3. ENLACE 2: OP -> LOTE PRODUCTO (Prorrateo) ---

            lotes_prod_resp = self.lote_producto_model.find_all(
                filters={'orden_produccion_id': ('in', list(op_ids))}
            )

            if not lotes_prod_resp.get('success') or not lotes_prod_resp.get('data'):
                logger.info(f"Las OPs {op_ids} no generaron lotes de producto.")
                # --- DEVOLVER node_map ---
                return self.success_response({"links": links, "node_map": node_map})

            op_total_producido = {}
            for lote_prod in lotes_prod_resp.get('data', []):
                op_id = lote_prod.get('orden_produccion_id')
                cantidad_lote = float(lote_prod.get('cantidad_inicial', 0) or 0)
                op_total_producido[op_id] = op_total_producido.get(op_id, 0.0) + cantidad_lote

            lote_prod_nodos = {}
            lote_prod_cantidad_trazada = {}
            lote_prod_ids = set()

            for lote_prod in lotes_prod_resp.get('data', []):
                lote_prod_id = lote_prod.get('id_lote')
                lote_prod_ids.add(lote_prod_id)
                op_id = lote_prod.get('orden_produccion_id')

                lote_prod_node = f"Lote Prod: {lote_prod.get('numero_lote') or lote_prod_id}"
                lote_prod_nodos[lote_prod_id] = lote_prod_node

                # --- AÑADIR URL DEL LOTE DE PRODUCTO ---
                node_map[lote_prod_node] = url_for('lote_producto.detalle_lote', id_lote=lote_prod_id)

                cantidad_trazada_op = op_consumo.get(op_id, 0.0)
                total_producido = op_total_producido.get(op_id, 0.0)
                cantidad_lote = float(lote_prod.get('cantidad_inicial', 0) or 0)

                cantidad_trazada_lote = 0.0
                if total_producido > 0:
                    proporcion = cantidad_lote / total_producido
                    cantidad_trazada_lote = cantidad_trazada_op * proporcion

                lote_prod_cantidad_trazada[lote_prod_id] = cantidad_trazada_lote

                if cantidad_trazada_lote > 0:
                    links.append({
                        "source_name": op_nodes[op_id],
                        "target_name": lote_prod_node,
                        "value": cantidad_trazada_lote
                    })

            # --- 4. ENLACE 3: LOTE PRODUCTO -> PEDIDO (Prorrateo) ---

            reservas_prod_resp = self.reserva_producto_model.find_all(
                filters={'lote_producto_id': ('in', list(lote_prod_ids))}
            )

            if not reservas_prod_resp.get('success') or not reservas_prod_resp.get('data'):
                logger.info(f"Los lotes de producto {lote_prod_ids} no están en ningún pedido.")
                # --- DEVOLVER node_map ---
                return self.success_response({"links": links, "node_map": node_map})

            lote_prod_total_reservado = {}
            pedido_reservas_agregadas = {}
            pedido_ids = set()

            for res_prod in reservas_prod_resp.get('data', []):
                lote_prod_id = res_prod.get('lote_producto_id')
                pedido_id = res_prod.get('pedido_id')

                if not pedido_id or not lote_prod_id:
                    continue

                cantidad = float(res_prod.get('cantidad_reservada', 0) or 0) + float(res_prod.get('cantidad_despachada', 0) or 0)

                if cantidad > 0:
                    lote_prod_total_reservado[lote_prod_id] = lote_prod_total_reservado.get(lote_prod_id, 0.0) + cantidad

                    key = (lote_prod_id, pedido_id)
                    pedido_reservas_agregadas[key] = pedido_reservas_agregadas.get(key, 0.0) + cantidad

                    pedido_ids.add(pedido_id)

            if not pedido_ids:
                 logger.info(f"Lotes {lote_prod_ids} reservados pero sin ID de pedido.")
                 # --- DEVOLVER node_map ---
                 return self.success_response({"links": links, "node_map": node_map})

            pedidos_resp = self.pedido_model.find_all(
                filters={'id': ('in', list(pedido_ids))}
            )

            if not pedidos_resp.get('success'):
                 return self.error_response("Error al buscar Pedidos")

            pedido_nodes = {}
            for pedido in pedidos_resp.get('data', []):
                pedido_id = pedido.get('id')
                cliente_nombre = pedido.get('nombre_cliente') or f"Cliente s/n"
                pedido_node_name = f"Pedido: #{pedido_id} ({cliente_nombre})"
                pedido_nodes[pedido_id] = pedido_node_name

                # --- AÑADIR URL DEL PEDIDO ---
                node_map[pedido_node_name] = url_for('orden_venta.detalle', id=pedido_id)

            for (lote_prod_id, pedido_id), cantidad_reservada_agg in pedido_reservas_agregadas.items():

                cantidad_trazada_lote = lote_prod_cantidad_trazada.get(lote_prod_id, 0.0)
                total_reservado_lote = lote_prod_total_reservado.get(lote_prod_id, 0.0)

                cantidad_trazada_pedido = 0.0
                if total_reservado_lote > 0:
                    proporcion = cantidad_reservada_agg / total_reservado_lote
                    cantidad_trazada_pedido = cantidad_trazada_lote * proporcion

                if cantidad_trazada_pedido > 0:
                    if lote_prod_id in lote_prod_nodos and pedido_id in pedido_nodes:
                        links.append({
                            "source_name": lote_prod_nodos[lote_prod_id],
                            "target_name": pedido_nodes[pedido_id],
                            "value": cantidad_trazada_pedido
                        })

            # --- DEVOLVER TODO AL FINAL ---
            return self.success_response({"links": links, "node_map": node_map})

        except Exception as e:
            logger.error(f"Error en obtener_trazabilidad_lote (manual) para {id_lote}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {e}", 500)


    def marcar_lote_como_no_apto(self, lote_id: str, usuario_id: int) -> tuple:
        """
        Delega la acción de marcar un lote como 'NO APTO' al controlador de calidad.
        (Método Legacy / Fallback)
        """
        from app.controllers.control_calidad_insumo_controller import ControlCalidadInsumoController

        try:
            lote_res = self.inventario_model.find_by_id(lote_id, 'id_lote')
            if not lote_res.get('success') or not lote_res.get('data'):
                return self.error_response('Lote no encontrado', 404)

            lote = lote_res['data']
            cantidad_total = float(lote.get('cantidad_actual', 0)) + float(lote.get('cantidad_en_cuarentena', 0))

            # Simular los datos del formulario que esperaría el controlador de calidad
            form_data = {
                'cantidad': str(cantidad_total),
                'comentarios': 'Marcado como NO APTO manualmente desde el listado de inventario.'
            }

            # Llamar al método centralizado en el controlador de calidad
            cc_controller = ControlCalidadInsumoController()
            response, status_code = cc_controller.procesar_inspeccion(
                lote_id=lote_id,
                decision='Rechazar',
                form_data=form_data,
                foto_file=None, # No hay foto en esta acción
                usuario_id=usuario_id
            )

            return response, status_code

        except Exception as e:
            logger.error(f"Error en marcar_lote_como_no_apto: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def procesar_no_apto_avanzado(self, lote_id: str, form_data: dict, usuario_id: int, foto_file=None) -> tuple:
        """
        Maneja el flujo avanzado de marcar un lote como NO APTO.
        Permite elegir entre:
        1. Retirar (Registrar desperdicio y reducir stock).
        2. Crear Alerta de Riesgo.
        """
        try:
            lote_res = self.inventario_model.find_by_id(lote_id, 'id_lote')
            if not lote_res.get('success') or not lote_res.get('data'):
                return self.error_response('Lote no encontrado', 404)

            lote = lote_res['data']
            accion = form_data.get('accion_no_apto')

            if accion == 'retirar':
                return self._procesar_retiro_insumo(lote, form_data, usuario_id, foto_file)

            elif accion == 'alerta':
                return self._procesar_alerta_insumo(lote, form_data, usuario_id)

            else:
                return self.error_response('Acción no válida.', 400)

        except Exception as e:
            logger.error(f"Error en procesar_no_apto_avanzado (insumo): {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def _procesar_retiro_insumo(self, lote, form_data, usuario_id, foto_file=None):
        """Wrapper legacy que usa el método unificado."""
        from app.models.registro_desperdicio_model import RegistroDesperdicioModel

        try:
            cantidad = float(form_data.get('cantidad_retiro'))
            motivo_id = form_data.get('motivo_desperdicio_id')
            comentarios = form_data.get('comentarios_retiro')
            usar_foto = form_data.get('usar_foto_cuarentena') == 'on'
            accion_ops = form_data.get('accion_ops', 'replanificar') # Default seguro

            return self.retirar_lote_insumo_unificado(
                lote['id_lote'], cantidad, motivo_id, comentarios, usuario_id,
                foto_file, usar_foto, accion_ops
            )
        except ValueError:
             return self.error_response("Datos numéricos inválidos.", 400)

    def _procesar_alerta_insumo(self, lote, form_data, usuario_id):
        """Lógica para crear una alerta de riesgo desde un lote de insumo."""
        try:
            motivo = form_data.get('motivo_alerta')
            descripcion = form_data.get('descripcion_alerta')

            if not motivo:
                return self.error_response("El motivo de la alerta es obligatorio.", 400)

            # Datos para el controlador de riesgos
            datos_alerta = {
                "tipo_entidad": "lote_insumo",
                "id_entidad": lote['id_lote'],
                "motivo": motivo,
                "comentarios": descripcion,
                "url_evidencia": None # Opcional, no manejado en este modal simple
            }

            # Llamar al controlador de riesgos
            riesgo_controller = RiesgoController()
            # Usamos crear_alerta_riesgo_con_usuario que maneja la lógica completa
            res_alerta, status = riesgo_controller.crear_alerta_riesgo_con_usuario(datos_alerta, usuario_id)

            # Ajuste: crear_alerta_riesgo_con_usuario retorna un dict directo, no una tupla en la firma, pero el wrapper BaseController podría confundir.
            # Revisando RiesgoController: devuelve (dict, status).
            # Ah no, devuelve {"success":...}, 201. Es una tupla.

            if isinstance(res_alerta, tuple):
                res_alerta = res_alerta[0]

            if res_alerta.get('success'):
                # Opcional: Poner el lote en un estado especial si la alerta no lo hizo automáticamente
                # La alerta ya pone en cuarentena o marca flags.
                return self.success_response(message="Alerta de riesgo creada correctamente.")
            else:
                return self.error_response(f"Error al crear alerta: {res_alerta.get('error')}", 500)

        except Exception as e:
            logger.error(f"Error en _procesar_alerta_insumo: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)


    def retirar_lote_insumo_unificado(self, lote_id: str, cantidad: float, motivo_id: int, comentarios: str, usuario_id: int, foto_file=None, usar_foto_cuarentena=False, accion_ops: str = 'replanificar') -> tuple:
        """
        Método centralizado para retirar stock de un lote de insumo, registrar desperdicio
        y gestionar las Órdenes de Producción afectadas.

        accion_ops: 'replanificar' (default), 'cancelar', 'ignorar'
        """
        from app.models.registro_desperdicio_lote_insumo_model import RegistroDesperdicioLoteInsumoModel
        from app.controllers.control_calidad_insumo_controller import ControlCalidadInsumoController
        from app.controllers.orden_produccion_controller import OrdenProduccionController
        from app.models.reserva_insumo import ReservaInsumoModel
        from app.models.trazabilidad import TrazabilidadModel

        try:
            lote_res = self.inventario_model.find_by_id(lote_id, 'id_lote')
            if not lote_res.get('success') or not lote_res.get('data'):
                return self.error_response('Lote no encontrado', 404)
            lote = lote_res['data']

            if cantidad <= 0:
                return self.error_response("La cantidad debe ser mayor a 0.", 400)
            if not motivo_id:
                return self.error_response("Debe seleccionar un motivo de desperdicio.", 400)

            # --- 1. Calcular Stock ---
            stock_disp = float(lote.get('cantidad_actual') or 0)
            stock_cuar = float(lote.get('cantidad_en_cuarentena') or 0)
            stock_total = stock_disp + stock_cuar

            if cantidad > stock_total:
                return self.error_response(f"La cantidad a retirar ({cantidad}) excede el stock total del lote ({stock_total}).", 400)

            # --- 2. Manejo de Foto ---
            foto_url_final = None
            if usar_foto_cuarentena:
                cc_model = ControlCalidadInsumoModel()
                historial = cc_model.find_by_lote_id(lote['id_lote'])
                if historial.get('success') and historial.get('data'):
                    for evento in historial['data']:
                        if evento.get('foto_url'):
                             foto_url_final = evento['foto_url']
                             break

            # --- 3. Registrar Desperdicio ---
            desperdicio_model = RegistroDesperdicioLoteInsumoModel()
            detalle_texto = "Retiro de inventario"
            if comentarios:
                detalle_texto += f": {comentarios}"

            datos_desperdicio = {
                'lote_insumo_id': lote['id_lote'],
                'motivo_id': motivo_id,
                'cantidad': cantidad,
                'created_at': datetime.now().isoformat(),
                'usuario_id': usuario_id,
                'detalle': detalle_texto,
                'comentarios': comentarios,
                'foto_url': foto_url_final
            }

            res_desperdicio = desperdicio_model.create(datos_desperdicio)
            if not res_desperdicio.get('success'):
                # Fallback sin foto si la columna no existe
                if "foto_url" in str(res_desperdicio.get('error')):
                     datos_desperdicio.pop('foto_url')
                     res_desperdicio = desperdicio_model.create(datos_desperdicio)
                if not res_desperdicio.get('success'):
                    return self.error_response(f"Error al registrar desperdicio: {res_desperdicio.get('error')}", 500)

            # --- 4. Actualizar Stock ---
            nueva_cantidad_cuar = stock_cuar
            nueva_cantidad_disp = stock_disp
            remanente_a_descontar = cantidad

            if stock_cuar > 0:
                descuento_cuar = min(stock_cuar, remanente_a_descontar)
                nueva_cantidad_cuar -= descuento_cuar
                remanente_a_descontar -= descuento_cuar

            if remanente_a_descontar > 0:
                nueva_cantidad_disp -= remanente_a_descontar

            nuevo_estado = lote['estado']
            if (nueva_cantidad_cuar + nueva_cantidad_disp) <= 0:
                if cantidad >= stock_total:
                    nuevo_estado = 'retirado'
                else:
                    nuevo_estado = 'agotado'

            update_data = {
                'cantidad_actual': nueva_cantidad_disp,
                'cantidad_en_cuarentena': nueva_cantidad_cuar,
                'estado': nuevo_estado
            }
            self.inventario_model.update(lote['id_lote'], update_data, 'id_lote')
            self.insumo_controller.actualizar_stock_insumo(lote['id_insumo'])

            # --- 5. Gestionar OPs Afectadas ---
            if accion_ops != 'ignorar':
                # Buscar OPs afectadas via reservas
                reserva_model = ReservaInsumoModel()
                op_controller = OrdenProduccionController()

                reservas_afectadas = reserva_model.find_all(filters={'lote_inventario_id': lote_id}).get('data', [])
                op_ids_afectadas = set(r['orden_produccion_id'] for r in reservas_afectadas)

                ops_procesadas = 0
                for op_id in op_ids_afectadas:
                    op_res = op_controller.obtener_orden_por_id(op_id)
                    if not op_res.get('success'): continue
                    op_data = op_res['data']

                    # Solo actuar sobre OPs activas
                    if op_data.get('estado') in ['COMPLETADA', 'FINALIZADA', 'CANCELADA']:
                        continue

                    if accion_ops == 'replanificar':
                        # Volver a PENDIENTE (esto elimina reservas automáticamente si el controlador está bien hecho, sino forzamos limpieza)
                        # La función 'cambiar_estado_orden' debería manejar esto, o usamos 'liberar_stock_reservado' explícitamente.
                        # Para seguridad, liberamos reservas primero.
                        self.liberar_stock_reservado_para_op(op_id)
                        op_controller.cambiar_estado_orden_simple(op_id, 'PENDIENTE')
                        logger.info(f"OP {op_id} reseteada a PENDIENTE por retiro de insumo {lote_id}.")
                        ops_procesadas += 1

                    elif accion_ops == 'cancelar':
                        op_controller.rechazar_orden(op_id, f"Cancelada por retiro de insumo Lote {lote.get('numero_lote_proveedor')}")
                        logger.info(f"OP {op_id} CANCELADA por retiro de insumo {lote_id}.")
                        ops_procesadas += 1

            return self.success_response(message="Lote retirado y desperdicio registrado correctamente.")

        except Exception as e:
            logger.error(f"Error en retirar_lote_insumo_unificado: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def liberar_lote_de_cuarentena_alerta(self, lote_id: str, usuario_id: int) -> tuple:
        """
        Libera un lote de CUARENTENA, devolviéndolo a su estado previo a la alerta.
        """
        try:
            lote_res = self.inventario_model.find_by_id(lote_id, 'id_lote')
            if not lote_res.get('success') or not lote_res.get('data'):
                return self.error_response('Lote no encontrado', 404)

            lote = lote_res['data']

            afectado_res = self.db.table('alerta_riesgo_afectados').select('estado_previo').eq('tipo_entidad', 'lote_insumo').eq('id_entidad', lote_id).order('id', desc=True).limit(1).execute().data

            estado_previo = 'disponible'
            if afectado_res and afectado_res[0].get('estado_previo'):
                estado_previo = afectado_res[0]['estado_previo']

            estado_destino = 'disponible' if 'en revision' in estado_previo.lower() else estado_previo

            cantidad_en_cuarentena = float(lote.get('cantidad_en_cuarentena', 0))
            cantidad_actual = float(lote.get('cantidad_actual', 0))

            nueva_cantidad_actual = cantidad_actual + cantidad_en_cuarentena

            update_data = {
                'estado': estado_destino,
                'cantidad_actual': nueva_cantidad_actual,
                'cantidad_en_cuarentena': 0,
                'motivo_cuarentena': None
            }

            result = self.inventario_model.update(lote_id, update_data, 'id_lote')
            if not result.get('success'):
                return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500)

            self.insumo_controller.actualizar_stock_insumo(lote['id_insumo'])

            return self.success_response(message="Lote liberado de cuarentena de alerta.")

        except Exception as e:
            logger.error(f"Error en liberar_lote_de_cuarentena_alerta: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def marcar_lote_retirado_alerta(self, lote_id: str, usuario_id: int):
        """
        Marca un lote como 'retirado' por una alerta y anula su stock.
        """
        try:
            lote_res = self.inventario_model.find_by_id(lote_id, 'id_lote')
            if not lote_res.get('success'):
                return self.error_response('Lote no encontrado', 404)
            lote = lote_res['data']

            update_data = {
                'estado': 'retirado',
                'cantidad_actual': 0,
                'cantidad_en_cuarentena': 0,
                'observaciones': f"Lote retirado por alerta de riesgo. Usuario ID: {usuario_id}."
            }
            result = self.inventario_model.update(lote_id, update_data, 'id_lote')

            if not result.get('success'):
                return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500)

            self.insumo_controller.actualizar_stock_insumo(lote['id_insumo'])

            return self.success_response(message="Lote marcado como retirado.")
        except Exception as e:
            logger.error(f"Error en marcar_lote_retirado_alerta: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def verificar_cobertura_reservas_op(self, orden_produccion: Dict) -> bool:
        """
        Verifica si una OP ya tiene todos sus insumos cubiertos por reservas existentes.
        CON LOGS DE DEPURACIÓN.
        """
        from app.models.receta import RecetaModel
        receta_model = RecetaModel()

        try:
            receta_id = orden_produccion['receta_id']
            op_id = orden_produccion['id']
            cantidad_a_producir = float(orden_produccion.get('cantidad_planificada', 0))

            logger.info(f"--- [DEBUG COBERTURA] Iniciando verificación para OP {op_id} (Cant: {cantidad_a_producir}) ---")

            # 1. Ingredientes
            ingredientes_result = receta_model.get_ingredientes(receta_id)
            if not ingredientes_result.get('success') or not ingredientes_result.get('data'):
                logger.warning(f"[DEBUG COBERTURA] OP {op_id}: No se encontraron ingredientes para receta {receta_id}")
                return False

            ingredientes = ingredientes_result.get('data')

            # 2. Reservas Existentes
            reservas_existentes = self.reserva_insumo_model.find_all(filters={'orden_produccion_id': op_id})
            reservas_data = reservas_existentes.get('data', [])

            logger.info(f"[DEBUG COBERTURA] Reservas encontradas en DB para OP {op_id}: {len(reservas_data)}")

            mapa_reservado = {}
            for res in reservas_data:
                iid = res['insumo_id']
                cant = float(res['cantidad_reservada'])
                estado_res = res.get('estado')

                # Solo sumamos si está activa
                if estado_res in ['RESERVADO', 'CONSUMIDO']:
                    mapa_reservado[iid] = mapa_reservado.get(iid, 0) + cant
                    logger.info(f"   -> Reserva ID {res['id']}: Insumo {iid} = {cant} ({estado_res})")
                else:
                    logger.info(f"   -> Reserva ID {res['id']} IGNORADA (Estado: {estado_res})")

            # 3. Comparación
            esta_cubierta = True
            for ingrediente in ingredientes:
                insumo_id = ingrediente['id_insumo']
                nombre_insumo = ingrediente.get('nombre_insumo', 'Unknown')
                cantidad_unitaria = float(ingrediente.get('cantidad', 0))
                cantidad_necesaria_total = cantidad_unitaria * cantidad_a_producir

                cantidad_reservada = mapa_reservado.get(insumo_id, 0)

                logger.info(f"[DEBUG COBERTURA] Insumo '{nombre_insumo}': Req={cantidad_necesaria_total:.2f} | Tiene={cantidad_reservada:.2f}")

                if cantidad_reservada < (cantidad_necesaria_total - 0.01):
                    logger.warning(f"[DEBUG COBERTURA] FALTA STOCK -> Insumo {insumo_id} incompleto.")
                    esta_cubierta = False
                    # No hacemos break para ver todos los insumos en el log

            logger.info(f"[DEBUG COBERTURA] Resultado Final OP {op_id}: {'CUBIERTA' if esta_cubierta else 'INCOMPLETA'}")
            return esta_cubierta

        except Exception as e:
            logger.error(f"[DEBUG COBERTURA] Error crítico: {e}", exc_info=True)
            return False

    def consumir_stock_para_reposicion(self, orden_produccion_id: int, insumo_id: int, cantidad: float, usuario_id: int) -> dict:
        """
        Consume una cantidad específica de un insumo para reponer una merma en una OP activa.
        Crea una reserva en estado CONSUMIDO y descuenta el stock físico del lote.
        """
        try:
            lotes_disponibles = self._obtener_lotes_con_disponibilidad(insumo_id)
            stock_total_disponible = sum(lote['disponibilidad'] for lote in lotes_disponibles)

            if stock_total_disponible < cantidad:
                return {'success': False, 'error': 'Stock insuficiente para la reposición.'}

            cantidad_restante = cantidad
            for lote in lotes_disponibles:
                if cantidad_restante <= 0:
                    break

                cantidad_a_tomar = min(lote['disponibilidad'], cantidad_restante)

                if cantidad_a_tomar > 0:
                    # Crear registro de trazabilidad
                    datos_reserva = {
                        'orden_produccion_id': orden_produccion_id,
                        'lote_inventario_id': lote['id_lote'],
                        'insumo_id': insumo_id,
                        'cantidad_reservada': cantidad_a_tomar,
                        'usuario_reserva_id': usuario_id,
                        'estado': 'CONSUMIDO' # Directo a consumido
                    }
                    self.reserva_insumo_model.create(datos_reserva)

                    # Descontar stock físico
                    nueva_cantidad_actual = float(lote.get('cantidad_actual', 0)) - cantidad_a_tomar
                    update_data = {'cantidad_actual': nueva_cantidad_actual}
                    if nueva_cantidad_actual <= 0.001:
                        update_data['estado'] = 'agotado'

                    self.inventario_model.update(lote['id_lote'], update_data, 'id_lote')

                    cantidad_restante -= cantidad_a_tomar

            self.insumo_controller.actualizar_stock_insumo(insumo_id)
            return {'success': True}

        except Exception as e:
            logger.error(f"Error en consumir_stock_para_reposicion: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def descontar_stock_fisico_y_reserva(self, reserva_id: int, cantidad_a_descontar: float):
        """
        Descuenta una cantidad del stock físico de un lote y actualiza la reserva correspondiente.
        """
        try:
            reserva_res = self.reserva_insumo_model.find_by_id(reserva_id, 'id')
            if not reserva_res.get('success'): return

            reserva = reserva_res['data']
            lote_id = reserva['lote_inventario_id']
            cantidad_reservada_actual = float(reserva.get('cantidad_reservada', 0))

            # Actualizar reserva
            nueva_cantidad_reservada = cantidad_reservada_actual - cantidad_a_descontar
            if nueva_cantidad_reservada <= 0.001:
                self.reserva_insumo_model.update(reserva_id, {'estado': 'CONSUMIDO'}, 'id')
            else:
                self.reserva_insumo_model.update(reserva_id, {'cantidad_reservada': nueva_cantidad_reservada}, 'id')

            # Actualizar lote físico
            lote_res = self.inventario_model.find_by_id(lote_id, 'id_lote')
            if lote_res.get('success'):
                lote = lote_res['data']
                cantidad_actual_lote = float(lote.get('cantidad_actual', 0))
                nueva_cantidad_lote = max(0, cantidad_actual_lote - cantidad_a_descontar)

                update_data = {'cantidad_actual': nueva_cantidad_lote}
                if nueva_cantidad_lote <= 0.001:
                    update_data['estado'] = 'agotado'

                self.inventario_model.update(lote_id, update_data, 'id_lote')

        except Exception as e:
            logger.error(f"Error en descontar_stock_fisico_y_reserva para reserva {reserva_id}: {e}")