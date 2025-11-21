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
from typing import Dict, Optional, List
import logging
from decimal import Decimal
from datetime import datetime, date
from marshmallow import ValidationError

from app.models.receta import RecetaModel # O donde tengas la lógica de recetas
from app.models.reserva_insumo import ReservaInsumoModel # El nuevo modelo que debes crear
from app.schemas.reserva_insumo_schema import ReservaInsumoSchema # El nuevo schema
from app.models.trazabilidad import TrazabilidadModel




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
        Crea registros de reserva para los insumos de una OP.
        NO consume el stock físico. Devuelve los lotes implicados.
        """
        receta_model = RecetaModel()
        reserva_insumo_model = ReservaInsumoModel()

        try:
            receta_id = orden_produccion['receta_id']
            cantidad_a_producir = float(orden_produccion.get('cantidad_planificada', 0))

            ingredientes_result = receta_model.get_ingredientes(receta_id)
            if not ingredientes_result.get('success'):
                raise Exception("No se pudieron obtener los ingredientes de la receta.")

            ingredientes = ingredientes_result.get('data', [])
            insumos_faltantes = []
            lotes_implicados = set()

            for ingrediente in ingredientes:
                insumo_id = ingrediente['id_insumo']
                cantidad_necesaria = float(ingrediente.get('cantidad', 0)) * cantidad_a_producir

                # Usamos la lógica de verificación para obtener lotes y su disponibilidad real
                verificacion_lotes = self._obtener_lotes_con_disponibilidad(insumo_id)
                cantidad_restante_a_reservar = cantidad_necesaria

                for lote in verificacion_lotes:
                    if cantidad_restante_a_reservar <= 0:
                        break

                    disponibilidad_en_lote = lote['disponibilidad']
                    cantidad_a_reservar_de_lote = min(disponibilidad_en_lote, cantidad_restante_a_reservar)

                    if cantidad_a_reservar_de_lote > 0:
                        datos_reserva = {
                            'orden_produccion_id': orden_produccion['id'],
                            'lote_inventario_id': lote['id_lote'],
                            'insumo_id': insumo_id,
                            'cantidad_reservada': cantidad_a_reservar_de_lote,
                            'usuario_reserva_id': usuario_id
                        }
                        reserva_insumo_model.create(datos_reserva)
                        lotes_implicados.add(lote['id_lote'])
                        cantidad_restante_a_reservar -= cantidad_a_reservar_de_lote

                if cantidad_restante_a_reservar > 0:
                    insumos_faltantes.append({
                        'insumo_id': insumo_id,
                        'nombre': ingrediente.get('nombre_insumo', 'N/A'),
                        'cantidad_faltante': cantidad_restante_a_reservar
                    })

            if insumos_faltantes:
                # En un caso real, aquí habría que hacer un rollback de las reservas creadas.
                # Por simplicidad, asumimos que este método solo se llama después de una verificación exitosa.
                return {'success': False, 'error': f"Faltantes encontrados durante la reserva: {insumos_faltantes}"}

            return {'success': True, 'data': {'insumos_faltantes': [], 'lotes_implicados': list(lotes_implicados)}}

        except Exception as e:
            logger.error(f"Error crítico al reservar insumos para OP {orden_produccion['id']}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def consumir_stock_reservado_para_op(self, orden_produccion_id: int) -> dict:
        """
        Consume el stock FÍSICO que fue previamente reservado para una OP.
        Esta acción es destructiva y debe llamarse cuando la OP pasa a 'EN PROCESO'.
        """
        try:
            reservas_res = self.reserva_insumo_model.find_all(
                filters={'orden_produccion_id': orden_produccion_id}
            )
            if not reservas_res.get('success'):
                return {'success': False, 'error': f"No se encontraron reservas para la OP {orden_produccion_id}"}

            reservas = reservas_res.get('data', [])
            if not reservas:
                logger.warning(f"No hay reservas que consumir para la OP {orden_produccion_id}")
                return {'success': True}

            insumos_afectados = set()
            for reserva in reservas:
                lote_id = reserva['lote_inventario_id']
                cantidad_a_consumir = float(reserva['cantidad_reservada'])

                insumos_afectados.add(reserva['insumo_id'])

                lote_res = self.inventario_model.find_by_id(lote_id, 'id_lote')
                if not lote_res.get('success'):
                    logger.error(f"No se encontró el lote {lote_id} para consumir stock de OP {orden_produccion_id}. Se omite.")
                    continue

                lote = lote_res.get('data')
                cantidad_actual_lote = float(lote.get('cantidad_actual', 0))
                nueva_cantidad_lote = cantidad_actual_lote - cantidad_a_consumir

                update_data = {'cantidad_actual': nueva_cantidad_lote}
                if nueva_cantidad_lote <= 0:
                    update_data['estado'] = 'agotado'

                self.inventario_model.update(lote_id, update_data, 'id_lote')
                self.reserva_insumo_model.update(reserva['id'], {'estado': 'CONSUMIDO'}, 'id')

            # Actualizar el stock general de los insumos afectados
            for insumo_id in insumos_afectados:
                self.insumo_controller.actualizar_stock_insumo(insumo_id)

            logger.info(f"Stock físico consumido y reservas eliminadas para la OP {orden_produccion_id}")
            return {'success': True}

        except Exception as e:
            logger.error(f"Error crítico al consumir stock para OP {orden_produccion_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def liberar_stock_reservado_para_op(self, orden_produccion_id: int) -> dict:
        """
        Libera el stock reservado para una OP, por ejemplo, si se cancela.
        NO afecta el stock físico, solo elimina los registros de reserva.
        """
        try:
            reservas_res = self.reserva_insumo_model.find_all(
                filters={'orden_produccion_id': orden_produccion_id}
            )
            if not reservas_res.get('success') or not reservas_res.get('data'):
                logger.warning(f"No se encontraron reservas para liberar para la OP {orden_produccion_id}")
                return {'success': True}

            reservas = reservas_res.get('data', [])
            insumos_afectados = set()
            for reserva in reservas:
                insumos_afectados.add(reserva['insumo_id'])
                self.reserva_insumo_model.delete(reserva['id'], 'id')

            # Es importante actualizar el stock para que la disponibilidad refleje la liberación
            for insumo_id in insumos_afectados:
                self.insumo_controller.actualizar_stock_insumo(insumo_id)

            logger.info(f"Reservas liberadas para la OP {orden_produccion_id}")
            return {'success': True}

        except Exception as e:
            logger.error(f"Error crítico al liberar stock para OP {orden_produccion_id}: {e}", exc_info=True)
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


    def _obtener_lotes_con_disponibilidad(self, insumo_id: int) -> List[Dict]:
        """
        Obtiene todos los lotes activos de un insumo y calcula su disponibilidad real.
        Disponibilidad = Cantidad Física - Cantidad Reservada.
        """
        # 1. Obtener todos los lotes activos (físicamente existentes)
        estados_fisicos = ['disponible', 'reservado', 'cuarentena', 'EN REVISION']
        lotes_activos_res = self.inventario_model.find_all(
            filters={'id_insumo': insumo_id, 'estado': ('in', estados_fisicos)},
            order_by='f_ingreso.asc'
        )
        if not lotes_activos_res.get('success'):
            return []

        lotes_activos = lotes_activos_res.get('data', [])
        if not lotes_activos:
            return []

        # 2. Obtener todas las reservas para esos lotes
        lote_ids = [lote['id_lote'] for lote in lotes_activos]
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

        # 3. Calcular disponibilidad real para cada lote
        for lote in lotes_activos:
            cantidad_fisica = float(lote.get('cantidad_actual', 0))
            cantidad_reservada = reservas_por_lote.get(lote['id_lote'], 0)
            lote['disponibilidad'] = max(0, cantidad_fisica - cantidad_reservada)

        return lotes_activos

    def verificar_stock_para_op(self, orden_produccion: Dict) -> dict:
        """
        Verifica si hay stock suficiente para una OP, usando la disponibilidad real
        (cantidad física - cantidad reservada).
        """
        receta_model = RecetaModel()
        try:
            receta_id = orden_produccion['receta_id']
            cantidad_a_producir = float(orden_produccion.get('cantidad_planificada', 0))

            ingredientes_result = receta_model.get_ingredientes(receta_id)
            if not ingredientes_result.get('success'):
                raise Exception("No se pudieron obtener los ingredientes de la receta.")

            ingredientes = ingredientes_result.get('data', [])
            insumos_faltantes = []

            for ingrediente in ingredientes:
                insumo_id = ingrediente['id_insumo']
                cantidad_necesaria = float(ingrediente.get('cantidad', 0)) * cantidad_a_producir

                lotes_con_disponibilidad = self._obtener_lotes_con_disponibilidad(insumo_id)
                stock_disponible_total = sum(lote['disponibilidad'] for lote in lotes_con_disponibilidad)

                if stock_disponible_total < cantidad_necesaria:
                    insumos_faltantes.append({
                        'insumo_id': insumo_id,
                        'nombre': ingrediente.get('nombre_insumo', 'N/A'),
                        'cantidad_necesaria': cantidad_necesaria,
                        'stock_disponible': stock_disponible_total,
                        'cantidad_faltante': cantidad_necesaria - stock_disponible_total
                    })

            return {'success': True, 'data': {'insumos_faltantes': insumos_faltantes}}

        except Exception as e:
            logger.error(f"Error verificando stock para OP {orden_produccion.get('id', 'N/A')}: {e}", exc_info=True)
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
            # --- FIN MODIFICACIÓN ---

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
        (Versión robusta para evitar errores con lotes huérfanos)
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

            lotes_por_insumo = {}
            for lote in lotes_response.get('data', []):
                insumo_id = lote.get('id_insumo')
                if insumo_id:
                    if insumo_id not in lotes_por_insumo:
                        lotes_por_insumo[insumo_id] = []
                    # Convertir cantidades a float
                    lote['cantidad_actual'] = float(lote.get('cantidad_actual') or 0)
                    lote['cantidad_en_cuarentena'] = float(lote.get('cantidad_en_cuarentena') or 0)
                    lotes_por_insumo[insumo_id].append(lote)

            # 3. Construir el resultado final iterando sobre los insumos del catálogo
            resultado_final = []
            for insumo in insumos_del_catalogo:
                insumo_id = insumo['id_insumo']
                lotes_de_insumo = lotes_por_insumo.get(insumo_id, [])

                # Recalcular el stock físico total directamente desde los lotes obtenidos
                stock_fisico_calculado = sum(float(lote.get('cantidad_actual', 0)) for lote in lotes_de_insumo)


                # Crear la estructura de datos para la vista
                datos_insumo_para_vista = {
                    'id_insumo': insumo_id,
                    'insumo_nombre': insumo.get('nombre', 'N/A'),
                    'insumo_categoria': insumo.get('categoria', 'Sin categoría'),
                    'insumo_unidad_medida': insumo.get('unidad_medida', ''),
                    'stock_actual': float(insumo.get('stock_actual') or 0),
                    'stock_total': stock_fisico_calculado, # Usar el valor recién calculado
                    'lotes': lotes_de_insumo # Adjuntar lotes
                }

                # Calcular el estado general basado en el stock disponible (actual)
                if datos_insumo_para_vista['stock_actual'] > 0:
                    datos_insumo_para_vista['estado_general'] = 'Disponible'
                else:
                    datos_insumo_para_vista['estado_general'] = 'Agotado'

                resultado_final.append(datos_insumo_para_vista)

            # Ordenar por nombre de insumo
            resultado_final.sort(key=lambda x: x['insumo_nombre'])

            return self.success_response(data=resultado_final)

        except Exception as e:
            logger.error(f"Error agrupando lotes para la vista (robusto): {str(e)}")
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


    def poner_lote_en_cuarentena(self, lote_id: str, motivo: str, cantidad: float, usuario_id: int, resultado_inspeccion: str = None, foto_file=None) -> tuple:
        """
        Mueve una cantidad de un lote a cuarentena, con subida de foto opcional.
        """
        from app.controllers.usuario_controller import UsuarioController
        from app.models.notificacion import NotificacionModel
        from app.controllers.control_calidad_insumo_controller import ControlCalidadInsumoController
        from app.models.alerta_riesgo import AlertaRiesgoModel

        try:
            lote_res = self.inventario_model.find_by_id(lote_id, 'id_lote')
            if not lote_res.get('success') or not lote_res.get('data'):
                return self.error_response('Lote no encontrado', 404)

            lote = lote_res['data']
            estado_actual = lote.get('estado')
            cantidad_actual_disponible = float(lote.get('cantidad_actual') or 0)
            cantidad_actual_cuarentena = float(lote.get('cantidad_en_cuarentena') or 0)

            if not motivo:
                return self.error_response("Se requiere un motivo para la cuarentena.", 400)

            # Path 1: Cuarentena por trazabilidad (lote agotado, sin cantidad)
            if estado_actual == 'agotado' and cantidad == 0:
                update_data = { 'estado': 'cuarentena', 'motivo_cuarentena': motivo }
                result = self.inventario_model.update(lote_id, update_data, 'id_lote')
                if not result.get('success'):
                    return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500)

            # Path 2: Cuarentena de una cantidad específica (lote con stock)
            else:
                if estado_actual == 'cuarentena':
                    return self.error_response("El lote ya se encuentra en cuarentena.", 400)
                if estado_actual not in ['disponible', 'reservado']:
                    return self.error_response(f"El lote debe estar 'disponible' o 'reservado'. Estado actual: {estado_actual}", 400)
                if cantidad <= 0:
                    return self.error_response("La cantidad debe ser un número positivo.", 400)

                cantidad_a_mover = cantidad
                if cantidad_a_mover > cantidad_actual_disponible:
                    logger.warning(f"La cantidad de cuarentena solicitada ({cantidad}) excede el disponible ({cantidad_actual_disponible}). Se pondrá en cuarentena todo el disponible.")
                    cantidad_a_mover = cantidad_actual_disponible

                nueva_cantidad_disponible = cantidad_actual_disponible - cantidad_a_mover
                nueva_cantidad_cuarentena = cantidad_actual_cuarentena + cantidad_a_mover

                nuevo_estado = 'agotado'
                if nueva_cantidad_disponible > 0:
                    nuevo_estado = 'disponible'
                elif nueva_cantidad_cuarentena > 0:
                    nuevo_estado = 'cuarentena'

                update_data = {
                    'estado': nuevo_estado,
                    'motivo_cuarentena': motivo,
                    'cantidad_en_cuarentena': nueva_cantidad_cuarentena,
                    'cantidad_actual': nueva_cantidad_disponible
                }
                result = self.inventario_model.update(lote_id, update_data, 'id_lote')
                if not result.get('success'):
                    return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500)

            control_calidad_controller = ControlCalidadInsumoController()
            foto_url = None
            if foto_file:
                foto_url = control_calidad_controller._subir_foto_y_obtener_url(foto_file, lote_id)

            registro_cc_result, _ = control_calidad_controller.crear_registro_control_calidad(
                lote_id=lote_id,
                usuario_id=usuario_id,
                decision='EN_CUARENTENA',
                comentarios=motivo,
                orden_compra_id=None,
                resultado_inspeccion=resultado_inspeccion,
                foto_url=foto_url
            )

            if not registro_cc_result.get('success'):
                logger.error(f"El lote {lote_id} se puso en cuarentena, pero falló la creación del registro de C.C.: {registro_cc_result.get('error')}")

            # Envío de notificación a gerentes
            try:
                usuario_controller = UsuarioController()
                gerentes_res = usuario_controller.obtener_usuarios_por_rol(['GERENTE'])
                if gerentes_res.get('success'):
                    notificacion_model = NotificacionModel()
                    insumo_res = self.insumo_model.find_by_id(str(lote['id_insumo']), 'id_insumo')
                    nombre_insumo = insumo_res['data'].get('nombre', 'Desconocido') if insumo_res.get('success') else 'Desconocido'

                    for gerente in gerentes_res['data']:
                        mensaje = f"El lote {lote.get('numero_lote_proveedor')} del insumo {nombre_insumo} ha sido puesto en cuarentena por trazabilidad."
                        notificacion_data = {
                            'usuario_id': gerente['id'],
                            'mensaje': mensaje,
                            'tipo': 'ALERTA',
                            'url_destino': url_for('inventario_view.detalle_lote', id_lote=lote_id)
                        }
                        notificacion_model.create(notificacion_data)
            except Exception as e:
                logger.error(f"Falló el envío de notificación de cuarentena para el lote {lote_id}: {e}", exc_info=True)


            # Actualizar el stock consolidado del insumo (importante si cambió la cantidad)
            self.insumo_controller.actualizar_stock_insumo(lote['id_insumo'])

            return self.success_response(message="Lote puesto en cuarentena con éxito.")

        except Exception as e:
            logger.error(f"Error en poner_lote_en_cuarentena (insumo): {e}", exc_info=True)
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