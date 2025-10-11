# app/controllers/lote_producto_controller.py
import logging
from app.controllers.base_controller import BaseController
from app.models.lote_producto import LoteProductoModel
from app.models.producto import ProductoModel
from app.schemas.lote_producto_schema import LoteProductoSchema
from typing import Dict, Optional
from marshmallow import ValidationError
from datetime import datetime
from app.models.reserva_producto import ReservaProductoModel
from app.schemas.reserva_producto_schema import ReservaProductoSchema

logger = logging.getLogger(__name__)

class LoteProductoController(BaseController):
    def __init__(self):
        super().__init__()
        self.model = LoteProductoModel()
        self.producto_model = ProductoModel()
        self.schema = LoteProductoSchema()
        self.reserva_model = ReservaProductoModel()
        self.reserva_schema = ReservaProductoSchema()

    def crear_lote(self, data: Dict):
        """Crea un nuevo lote de producto."""
        try:
            # Validar que el producto exista
            producto = self.producto_model.find_by_id(data.get('producto_id'), 'id')
            if not producto.get('success') or not producto.get('data'):
                return self.error_response('El producto especificado no existe.', 400), 400

            # Verificar que el número de lote sea único
            lote_existente = self.model.find_by_numero_lote(data.get('numero_lote'))
            if lote_existente.get('data'):
                return self.error_response('El número de lote ya está en uso.', 409), 409

            # Validar datos con el schema
            validated_data = self.schema.load(data)

            # Establecer estado inicial si no se proporciona
            if 'estado' not in validated_data:
                validated_data['estado'] = 'DISPONIBLE'

            # Crear el lote
            result = self.model.create(validated_data)
            if not result.get('success'):
                return self.error_response(result.get('error', 'Error al crear el lote.'), 500), 500

            # Serializar respuesta
            response_data = self.schema.dump(result['data'])
            return self.success_response(response_data, "Lote creado con éxito", 201), 201

        except ValidationError as e:
            return self.error_response(f"Datos inválidos: {e.messages}", 422), 422
        except Exception as e:
            logger.error(f"Error en crear_lote: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500), 500

    def obtener_lotes(self, filtros: Optional[Dict] = None):
        """Obtiene todos los lotes con filtros opcionales."""
        try:
            filtros = filtros or {}
            result = self.model.find_all(filtros)

            if not result['success']:
                return self.error_response(result['error'], 500), 500

            # Serializar datos - ahora funciona porque el schema maneja strings
            serialized_data = self.schema.dump(result['data'], many=True)
            return self.success_response(serialized_data), 200

        except Exception as e:
            logger.error(f"Error en obtener_lotes: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500), 500

    def obtener_lote_por_id(self, lote_id: int):
        """Obtiene un lote por su ID."""
        try:
            result = self.model.find_by_id(lote_id, 'id_lote')
            if not result.get('success'):
                return self.error_response(result.get('error', 'Lote no encontrado'), 404), 404

            if not result.get('data'):
                return self.error_response('Lote no encontrado', 404), 404

            serialized_data = self.schema.dump(result['data'])
            return self.success_response(serialized_data), 200
        except Exception as e:
            logger.error(f"Error en obtener_lote_por_id: {e}")
            return self.error_response('Error interno del servidor', 500), 500

    def actualizar_lote(self, lote_id: int, data: Dict):
        """Actualiza un lote existente."""
        try:
            # Verificar que el lote existe
            lote_existente = self.model.find_by_id(lote_id, 'id_lote')
            if not lote_existente.get('success') or not lote_existente.get('data'):
                return self.error_response('Lote no encontrado', 404), 404

            # No permitir modificar el número de lote
            if 'numero_lote' in data:
                lote_actual = lote_existente['data']
                if data['numero_lote'] != lote_actual['numero_lote']:
                    return self.error_response('El número de lote no se puede modificar.', 400), 400

            # Validar datos
            validated_data = self.schema.load(data, partial=True)

            # Actualizar el lote
            result = self.model.update(lote_id, validated_data, 'id_lote')
            if not result.get('success'):
                return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500), 500

            return self.success_response(result['data'], "Lote actualizado con éxito"), 200

        except ValidationError as e:
            return self.error_response(f"Datos inválidos: {e.messages}", 422), 422
        except Exception as e:
            logger.error(f"Error en actualizar_lote: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500), 500

    def eliminar_lote_logico(self, lote_id: int):
        """Eliminación lógica de un lote (cambia estado a RETIRADO)."""
        try:
            data = {'estado': 'RETIRADO'}
            result = self.model.update(lote_id, data, 'id_lote')
            if result['success']:
                return self.success_response(message="Lote retirado correctamente."), 200
            else:
                return self.error_response(result['error'], 500), 500
        except Exception as e:
            logger.error(f"Error eliminando lote: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500), 500


    def obtener_stock_producto(self, producto_id: int):
        """
        Calcula el stock disponible para un producto.
        """
        try:
            filtros = {'producto_id': producto_id, 'estado': 'DISPONIBLE'}
            lotes_result = self.model.find_all(filtros)

            if not lotes_result.get('success'):
                return self.error_response(lotes_result.get('error'), 500)

            lotes_disponibles = lotes_result.get('data', [])
            stock_total = sum(lote.get('cantidad_actual', 0) for lote in lotes_disponibles)

            return self.success_response(data={'stock_total': stock_total})
        except Exception as e:
            logger.error(f"Error calculando stock para producto {producto_id}: {e}", exc_info=True)
            return self.error_response('Error interno al calcular stock', 500)


    def reservar_stock_para_item(self, pedido_id: int, pedido_item_id: int, producto_id: int, cantidad_necesaria: float, usuario_id: int) -> dict:
        """
        Intenta reservar la cantidad necesaria de un producto para un item de pedido.
        Utiliza una estrategia FIFO y actualiza el estado del lote a 'AGOTADO' si se vacía.
        """
        try:
            # 1. Obtener lotes disponibles (sin cambios)
            filtros = {
                'producto_id': producto_id,
                'estado': 'DISPONIBLE',
                'cantidad_actual': ('gt', 0)
            }
            lotes_disponibles_res = self.model.find_all(filters=filtros, order_by='created_at.asc')

            if not lotes_disponibles_res.get('success'):
                return {'success': False, 'error': 'No se pudieron obtener los lotes de productos.'}

            lotes_disponibles = lotes_disponibles_res.get('data', [])
            cantidad_restante_a_reservar = cantidad_necesaria
            cantidad_total_reservada = 0

            # 2. Iterar sobre los lotes y reservar
            for lote in lotes_disponibles:
                if cantidad_restante_a_reservar <= 0:
                    break

                cantidad_en_lote = lote.get('cantidad_actual', 0)
                cantidad_a_reservar_de_este_lote = min(cantidad_en_lote, cantidad_restante_a_reservar)

                # a. Crear el registro de reserva (sin cambios)
                datos_reserva = {
                    'lote_producto_id': lote['id_lote'],
                    'pedido_id': pedido_id,
                    'pedido_item_id': pedido_item_id,
                    'cantidad_reservada': cantidad_a_reservar_de_este_lote,
                    'usuario_reserva_id': usuario_id
                }
                # Verificamos que la reserva se crea antes de continuar
                resultado_reserva = self.reserva_model.create(self.reserva_schema.load(datos_reserva))
                if not resultado_reserva.get('success'):
                    raise Exception(f"No se pudo crear el registro de reserva para el lote {lote['id_lote']}.")

                # --- INICIO DE LA LÓGICA MEJORADA ---
                # b. Calcular la nueva cantidad y preparar la actualización
                nueva_cantidad_lote = cantidad_en_lote - cantidad_a_reservar_de_este_lote
                datos_actualizacion_lote = {'cantidad_actual': nueva_cantidad_lote}

                # c. Si la cantidad llega a cero, cambiar el estado a 'AGOTADO'
                if nueva_cantidad_lote <= 0:
                    datos_actualizacion_lote['estado'] = 'AGOTADO'
                    logger.info(f"El lote {lote['numero_lote']} ha sido marcado como AGOTADO.")

                # d. Realizar la actualización del lote en la base de datos
                self.model.update(lote['id_lote'], datos_actualizacion_lote, 'id_lote')
                # --- FIN DE LA LÓGICA MEJORADA ---

                # Actualizar contadores (sin cambios)
                cantidad_total_reservada += cantidad_a_reservar_de_este_lote
                cantidad_restante_a_reservar -= cantidad_a_reservar_de_este_lote

            # 3. Devolver resultado (sin cambios)
            cantidad_faltante = cantidad_necesaria - cantidad_total_reservada
            return {
                'success': True,
                'data': {'cantidad_reservada': cantidad_total_reservada, 'cantidad_faltante': cantidad_faltante}
            }

        except Exception as e:
            logger.error(f"Error crítico al reservar stock: {e}", exc_info=True)
            return {'success': False, 'error': f'Error interno al reservar stock: {str(e)}'}


    def crear_lote_desde_formulario(self, form_data: dict, usuario_id: int) -> tuple:
            """Crea un nuevo lote de producto desde un formulario web."""
            try:
                # Preparamos los datos ANTES de la validación
                data = {key: value for key, value in form_data.items() if value}

                # --- INICIO DE LA CORRECCIÓN ---

                # 1. Asignar cantidad_actual si existe cantidad_inicial
                if 'cantidad_inicial' in data:
                    data['cantidad_actual'] = data['cantidad_inicial']

                # 2. Generar número de lote si no viene del formulario
                if 'numero_lote' not in data or not data['numero_lote']:
                     data['numero_lote'] = f"LP-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                # 3. Añadir la fecha de producción (asumimos que es hoy)
                if 'fecha_produccion' not in data:
                    data['fecha_produccion'] = datetime.now().date().isoformat()

                # --- FIN DE LA CORRECCIÓN ---

                # Ahora validamos. Todos los campos requeridos ya existen en 'data'.
                validated_data = self.schema.load(data)

                # (El resto del método no necesita cambios)
                result = self.model.create(validated_data)

                if result.get('success'):
                    return self.success_response(data=result['data'], message="Lote de producto creado con éxito.")
                else:
                    return self.error_response(result.get('error', 'No se pudo crear el lote.'), 500)

            except ValidationError as e:
                return self.error_response(f"Datos inválidos: {e.messages}", 400)
            except Exception as e:
                logger.error(f"Error creando lote de producto: {e}", exc_info=True)
                return self.error_response(f"Error interno: {str(e)}", 500)

    # --- MÉTODO MODIFICADO ---
    def obtener_lotes_para_vista(self) -> tuple:
        """Obtiene todos los lotes de productos con datos enriquecidos para la vista."""
        try:
            result = self.model.get_all_lotes_for_view()
            if result.get('success'):
                lotes = result.get('data', [])

                # Convertir strings de fecha a objetos datetime
                for lote in lotes:
                    if lote.get('created_at') and isinstance(lote['created_at'], str):
                        lote['created_at'] = datetime.fromisoformat(lote['created_at'])
                    if lote.get('fecha_vencimiento') and isinstance(lote['fecha_vencimiento'], str):
                        lote['fecha_vencimiento'] = datetime.fromisoformat(lote['fecha_vencimiento'])

                return self.success_response(data=lotes)
            else:
                return self.error_response(result.get('error', 'Error al cargar los lotes.'), 500)
        except Exception as e:
            logger.error(f"Error obteniendo lotes para la vista: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    # --- MÉTODO MODIFICADO ---
    def obtener_lote_por_id_para_vista(self, id_lote: int) -> tuple:
        """Obtiene el detalle de un lote de producto para la vista."""
        try:
            result = self.model.get_lote_detail_for_view(id_lote)
            if result.get('success'):
                lote = result.get('data')

                # Convertir strings de fecha a objetos datetime
                if lote:
                    if lote.get('created_at') and isinstance(lote['created_at'], str):
                        lote['created_at'] = datetime.fromisoformat(lote['created_at'])
                    if lote.get('fecha_vencimiento') and isinstance(lote['fecha_vencimiento'], str):
                        lote['fecha_vencimiento'] = datetime.fromisoformat(lote['fecha_vencimiento'])

                return self.success_response(data=lote)
            else:
                return self.error_response(result.get('error', 'Lote no encontrado.'), 404)
        except Exception as e:
            logger.error(f"Error obteniendo detalle de lote: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)
