from uuid import UUID
from app.controllers.base_controller import BaseController
from app.models.inventario import InventarioModel
from app.models.insumo import InsumoModel
from app.controllers.insumo_controller import InsumoController
from app.controllers.configuracion_controller import ConfiguracionController
#from app.services.stock_service import StockService
from app.schemas.inventario_schema import InsumosInventarioSchema
from typing import Dict, Optional
import logging
from decimal import Decimal
from datetime import datetime, date
from marshmallow import ValidationError

from app.models.receta import RecetaModel # O donde tengas la lógica de recetas
from app.models.reserva_insumo import ReservaInsumoModel # El nuevo modelo que debes crear
from app.schemas.reserva_insumo_schema import ReservaInsumoSchema # El nuevo schema


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

    def reservar_stock_insumos_para_op(self, orden_produccion: Dict, usuario_id: int) -> dict:
        """
        Calcula los insumos necesarios para una OP, los reserva y devuelve los faltantes.
        Ahora también actualiza el estado del lote a 'agotado' (minúscula) si se vacía.
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

            for ingrediente in ingredientes:
                insumo_id = ingrediente['id_insumo']
                cantidad_necesaria = float(ingrediente.get('cantidad', 0)) * cantidad_a_producir

                lotes_disponibles_res = self.inventario_model.find_all(
                    filters={'id_insumo': insumo_id, 'cantidad_actual': ('gt', 0)},
                    order_by='f_ingreso.asc'
                )
                lotes_disponibles = lotes_disponibles_res.get('data', [])
                cantidad_restante_a_reservar = cantidad_necesaria

                for lote in lotes_disponibles:
                    if cantidad_restante_a_reservar <= 0:
                        break
                    
                    cantidad_en_lote = float(lote.get('cantidad_actual', 0))
                    cantidad_a_reservar_de_lote = min(cantidad_en_lote, cantidad_restante_a_reservar)

                    datos_reserva = {
                        'orden_produccion_id': orden_produccion['id'],
                        'lote_inventario_id': lote['id_lote'],
                        'insumo_id': insumo_id,
                        'cantidad_reservada': cantidad_a_reservar_de_lote,
                        'usuario_reserva_id': usuario_id
                    }
                    reserva_insumo_model.create(datos_reserva)

                    # --- INICIO DE LA LÓGICA CORREGIDA ---
                    nueva_cantidad_lote = cantidad_en_lote - cantidad_a_reservar_de_lote

                    datos_actualizacion_lote = {
                        'cantidad_actual': nueva_cantidad_lote
                    }

                    # Si el lote se agota, añadimos el cambio de estado EN MINÚSCULAS
                    if nueva_cantidad_lote <= 0:
                        datos_actualizacion_lote['estado'] = 'agotado' # <-- CORREGIDO
                        logger.info(f"El lote de insumo ID {lote['id_lote']} ha sido marcado como agotado.")

                    self.inventario_model.update(lote['id_lote'], datos_actualizacion_lote, 'id_lote')
                    # --- FIN DE LA LÓGICA CORREGIDA ---

                    cantidad_restante_a_reservar -= cantidad_a_reservar_de_lote

                if cantidad_restante_a_reservar > 0:
                    insumos_faltantes.append({
                        'insumo_id': insumo_id,
                        'nombre': ingrediente.get('nombre_insumo', 'N/A'),
                        'cantidad_faltante': cantidad_restante_a_reservar
                    })

            return {'success': True, 'data': {'insumos_faltantes': insumos_faltantes}}

        except Exception as e:
            logger.error(f"Error crítico al reservar insumos para OP {orden_produccion['id']}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}


    def verificar_stock_para_op(self, orden_produccion: Dict) -> dict:
        """
        "Dry Run": Verifica si hay stock suficiente para una OP sin reservar.
        Calcula el stock disponible REAL sumando los lotes de inventario.
        Devuelve una lista de insumos faltantes.
        """
        receta_model = RecetaModel()
        try:
            receta_id = orden_produccion['receta_id']
            cantidad_a_producir = orden_produccion['cantidad_planificada']

            ingredientes_result = receta_model.get_ingredientes(receta_id)
            if not ingredientes_result.get('success'):
                raise Exception("No se pudieron obtener los ingredientes de la receta.")

            ingredientes = ingredientes_result.get('data', [])
            insumos_faltantes = []

            # Tolerancia para errores de punto flotante
            TOLERANCE = 1e-9

            for ingrediente in ingredientes:
                insumo_id = ingrediente['id_insumo']
                cantidad_necesaria = ingrediente['cantidad'] * cantidad_a_producir

                # --- INICIO DE LA LÓGICA CORREGIDA ---
                # En lugar de leer el resumen, calculamos el stock real sumando
                # los lotes que están 'disponibles' y tienen cantidad.
                lotes_disponibles_res = self.inventario_model.find_all(
                    filters={
                        'id_insumo': insumo_id,
                        'estado': 'disponible', # <-- Solo lotes 'disponible' (en minúscula)
                        'cantidad_actual': ('gt', 0)
                    }
                )

                if not lotes_disponibles_res.get('success'):
                    stock_actual = 0
                else:
                    # Sumamos la cantidad de todos los lotes que SÍ están disponibles
                    stock_actual = sum(lote.get('cantidad_actual', 0) for lote in lotes_disponibles_res.get('data', []))
                # --- FIN DE LA LÓGICA CORREGIDA ---

                # Calcular el faltante
                cantidad_faltante = cantidad_necesaria - stock_actual

                # Aplicar tolerancia
                if 0 < cantidad_faltante < TOLERANCE:
                    cantidad_faltante = 0
                if cantidad_faltante < 0:
                    cantidad_faltante = 0

                if cantidad_faltante > 0:
                    insumos_faltantes.append({
                        'insumo_id': insumo_id,
                        'nombre': ingrediente.get('nombre_insumo', 'N/A'),
                        'cantidad_necesaria': cantidad_necesaria,
                        'stock_disponible': stock_actual, # <-- Ahora es el stock real
                        'cantidad_faltante': cantidad_faltante
                    })

            return {'success': True, 'data': {'insumos_faltantes': insumos_faltantes}}

        except Exception as e:
            logger.error(f"Error verificando stock para OP {orden_produccion.get('id', 'N/A')}: {e}", exc_info=True)
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
            # --- LÓGICA CORREGIDA ---
            # Copiamos la cantidad inicial a la actual ANTES de la validación.
            # El formulario envía 'cantidad_inicial', así que lo usamos para crear 'cantidad_actual'.
            if 'cantidad_inicial' in data and data['cantidad_inicial']:
                data['cantidad_actual'] = data['cantidad_inicial']

            # Ahora sí, validamos los datos. El schema ya encontrará el campo 'cantidad_actual'.
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
            validated_data['numero_lote_proveedor'] = codigo_lote

            # Crear lote
            result = self.inventario_model.create(validated_data)

            if result['success']:
                logger.info(f"Lote creado exitosamente: {result['data']['id_lote']}")

                # Actualizar stock de seccion insumo automáticamente
                self.insumo_controller.actualizar_stock_insumo(validated_data['id_insumo'])

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

# --- Dentro de app/controllers/inventario_controller.py (clase InventarioController) ---

    def obtener_lote_por_id(self, id_lote: str) -> tuple:
        """Obtener un lote específico por su ID usando el método enriquecido."""
        try:
            result = self.inventario_model.get_lote_detail_for_view(id_lote)

            if result['success']:
                if result['data']:
                    # El dato ya viene aplanado con insumo_nombre y proveedor_nombre
                    serialized_data = self._serialize_data(result['data'])
                    return self.success_response(data=serialized_data)
                else:
                    return self.error_response('Lote no encontrado', 404)
            else:
                return self.error_response(result['error'])

        except Exception as e:
            logger.error(f"Error obteniendo lote por ID: {str(e)}")
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