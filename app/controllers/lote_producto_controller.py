# app/controllers/lote_producto_controller.py
import logging
from datetime import datetime, date, timedelta
from flask_jwt_extended import get_jwt_identity
import pandas as pd
from io import BytesIO
from app.controllers.base_controller import BaseController
from app.models.lote_producto import LoteProductoModel
from app.models.producto import ProductoModel
from app.schemas.lote_producto_schema import LoteProductoSchema
from typing import Dict, Optional
from marshmallow import ValidationError
from datetime import datetime
from app.models.reserva_producto import ReservaProductoModel
from app.schemas.reserva_producto_schema import ReservaProductoSchema
from app.controllers.configuracion_controller import ConfiguracionController
from app.models.alerta_riesgo import AlertaRiesgoModel
from app.models.registro_desperdicio_lote_producto_model import RegistroDesperdicioLoteProductoModel
from app.controllers.control_calidad_producto_controller import ControlCalidadProductoController
from app.database import Database
from werkzeug.utils import secure_filename
import os
from storage3.exceptions import StorageApiError



logger = logging.getLogger(__name__)

class LoteProductoController(BaseController):
    def __init__(self):
        super().__init__()
        self.model = LoteProductoModel()
        self.producto_model = ProductoModel()
        self.schema = LoteProductoSchema()
        self.reserva_model = ReservaProductoModel()
        self.reserva_schema = ReservaProductoSchema()
        self.config_controller = ConfiguracionController()
        self.control_calidad_producto_controller = ControlCalidadProductoController()

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

    def eliminar_lote_logico(self, lote_id: int, usuario_id: int, motivo: str, resultado_inspeccion: str):
        """Eliminación lógica de un lote (cambia estado a RETIRADO) y crea un registro de CC."""
        try:
            # Primero, actualiza el estado del lote
            update_data = {'estado': 'RETIRADO', 'motivo_cuarentena': motivo}
            result = self.model.update(lote_id, update_data, 'id_lote')

            if not result.get('success'):
                return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500)

            # Luego, crea el registro de control de calidad
            cc_data = {
                'lote_producto_id': lote_id,
                'usuario_supervisor_id': usuario_id,
                'decision_final': 'RETIRADO',
                'comentarios': motivo,
                'resultado_inspeccion': resultado_inspeccion,
            }
            cc_res, _ = self.control_calidad_producto_controller.crear_registro_control_calidad(cc_data)
            if not cc_res.get('success'):
                logger.error(f"Lote {lote_id} retirado, pero falló la creación del registro de C.C.: {cc_res.get('error')}")

            return self.success_response(message="Lote retirado correctamente.")

        except Exception as e:
            logger.error(f"Error en eliminar_lote_logico: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)


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

    def obtener_stock_disponible_real(self, producto_id: int):
        """
        Calcula el stock real disponible para un producto en un modelo de "reserva dura".
        El stock disponible es la suma de `cantidad_actual` de todos los lotes 'DISPONIBLE'.
        No se restan las reservas porque `cantidad_actual` ya se descuenta al reservar.
        """
        try:
            filtros_lotes = {'producto_id': producto_id, 'estado': 'DISPONIBLE'}
            lotes_result = self.model.find_all(filtros_lotes)

            if not lotes_result.get('success'):
                return self.error_response(lotes_result.get('error'), 500)

            lotes_disponibles = lotes_result.get('data', [])
            stock_disponible_real = sum(lote.get('cantidad_actual', 0) for lote in lotes_disponibles)

            return self.success_response(data={'stock_disponible_real': stock_disponible_real, 'stock_fisico': stock_disponible_real, 'stock_reservado': 0})

        except Exception as e:
            logger.error(f"Error calculando stock real para producto {producto_id}: {e}", exc_info=True)
            return self.error_response('Error interno al calcular stock real', 500)

    def obtener_stock_disponible_real_para_productos(self, producto_ids: list, fecha_requisito: date = None) -> tuple:
        """
        Calcula el stock real disponible para una lista de productos.
        CORRECCIÓN: En un modelo de 'Reserva Dura', la 'cantidad_actual' de los lotes
        ya tiene descontadas las reservas. No se debe restar la tabla reservas nuevamente.

        NUEVO: Si se pasa 'fecha_requisito', solo suma lotes que venzan DESPUÉS o IGUAL a esa fecha.
        """
        if not producto_ids:
            return self.success_response(data={})

        try:
            # Preparar filtros base
            filtros_query = self.model.db.table(self.model.get_table_name()) \
                .select('*') \
                .in_('producto_id', producto_ids) \
                .eq('estado', 'DISPONIBLE')

            # --- NUEVO FILTRO DE VENCIMIENTO ---
            if fecha_requisito:
                # Solo lotes que vencen el mismo día del requisito o después (>=)
                # La fecha de vencimiento debe ser "mayor o igual" a la fecha requerida.
                filtros_query = filtros_query.gte('fecha_vencimiento', fecha_requisito.isoformat())
            else:
                # Si no hay fecha requerida, asumimos entrega inmediata.
                # Filtramos solo que no estén vencidos hoy.
                filtros_query = filtros_query.gte('fecha_vencimiento', date.today().isoformat())

            lotes_result = filtros_query.execute()

            if not lotes_result.data:
                # Si no hay datos, devolvemos mapa en 0
                return self.success_response(data={pid: 0 for pid in producto_ids})

            # 2. Sumar la cantidad_actual (que es el remanente libre)
            stock_disponible_map = {pid: 0 for pid in producto_ids}
            lotes_disponibles = lotes_result.data

            for lote in lotes_disponibles:
                pid = lote['producto_id']
                stock_disponible_map[pid] += float(lote.get('cantidad_actual', 0))

            return self.success_response(data=stock_disponible_map)

        except Exception as e:
            logger.error(f"Error calculando stock real para productos {producto_ids}: {e}", exc_info=True)
            return self.error_response('Error interno al calcular stock real en batch', 500)


    # === NUEVA FUNCIÓN AÑADIDA PARA SOPORTE DE LA LÓGICA DE COMPLETAR PEDIDO ===
    def obtener_lotes_producto_disponibles(self, producto_id: int) -> dict:
        """
        Obtiene la lista de lotes disponibles para un producto con stock, sin consumirlos.
        """
        try:
            filtros = {
                'producto_id': producto_id,
                'estado': 'DISPONIBLE',
                'cantidad_actual': ('gt', 0)
            }
            # FIFO (más antiguo primero) para sugerir qué lotes usar
            lotes_result = self.model.find_all(filters=filtros, order_by='created_at.asc')

            if not lotes_result.get('success'):
                return {'success': False, 'error': lotes_result.get('error')}

            lotes_disponibles = lotes_result.get('data', [])
            stock_total = sum(lote.get('cantidad_actual', 0) for lote in lotes_disponibles)

            # Devolvemos el stock total y los lotes para la vista
            return {'success': True, 'data': {'stock_total': stock_total, 'lotes': lotes_disponibles}}
        except Exception as e:
            logger.error(f"Error obteniendo lotes disponibles para producto {producto_id}: {e}", exc_info=True)
            return {'success': False, 'error': 'Error interno al obtener lotes'}
    # ===========================================================================


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
            lotes_disponibles_res = self.model.find_all(filters=filtros, order_by='fecha_vencimiento.asc.nullslast')

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

    def liberar_stock_por_cancelacion_de_pedido(self, pedido_id: int) -> dict:
        """
        Revierte una "reserva dura" para un pedido cancelado. Devuelve el stock
        físico a los lotes de origen y cancela el registro de la operación.
        """
        logger.info(f"Iniciando liberación de stock para pedido cancelado ID: {pedido_id}")
        try:
            reservas_a_revertir_res = self.reserva_model.find_all(filters={
                'pedido_id': pedido_id,
                'estado': 'RESERVADO'
            })

            if not reservas_a_revertir_res.get('success'):
                raise Exception(f"No se pudieron obtener las reservas para el pedido {pedido_id}.")

            reservas_a_revertir = reservas_a_revertir_res.get('data', [])
            if not reservas_a_revertir:
                logger.info(f"El pedido {pedido_id} no tenía stock descontado para liberar.")
                return {'success': True, 'message': 'No había stock para liberar.'}

            for reserva in reservas_a_revertir:
                lote_id = reserva['lote_producto_id']
                cantidad_a_devolver = reserva['cantidad_reservada']

                lote_actual_res = self.model.find_by_id(lote_id, 'id_lote')
                if not lote_actual_res.get('success') or not lote_actual_res.get('data'):
                    logger.error(f"¡INCONSISTENCIA GRAVE! No se encontró el lote {lote_id} para devolver stock del pedido cancelado {pedido_id}. Se omite la devolución para esta reserva.")
                    continue

                lote_actual = lote_actual_res['data']
                nueva_cantidad = lote_actual.get('cantidad_actual', 0) + cantidad_a_devolver

                update_data = {'cantidad_actual': nueva_cantidad}
                if lote_actual.get('estado') == 'AGOTADO':
                    update_data['estado'] = 'DISPONIBLE'

                logger.info(f"Devolviendo {cantidad_a_devolver} unidades al lote {lote_id}. Nueva cantidad: {nueva_cantidad}. Nuevo estado: {update_data.get('estado', lote_actual.get('estado'))}")
                update_lote_res = self.model.update(lote_id, update_data, 'id_lote')
                if not update_lote_res.get('success'):
                    logger.error(f"¡FALLO CRÍTICO! No se pudo devolver el stock al lote {lote_id}. El stock quedará inconsistente.")

                logger.info(f"Actualizando estado de reserva ID {reserva['id']} a CANCELADO.")
                self.reserva_model.update(reserva['id'], {'estado': 'CANCELADO'}, 'id')

            logger.info(f"Liberación de stock para el pedido {pedido_id} completada.")
            return {'success': True}

        except Exception as e:
            logger.error(f"Error crítico al liberar stock para el pedido {pedido_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}


    def crear_lote_desde_formulario(self, form_data: dict, usuario_id: int) -> tuple:
            """Crea un nuevo lote de producto desde un formulario web."""
            try:
                if hasattr(form_data, 'to_dict'):
                    data = form_data.to_dict()
                else:
                    data = form_data.copy()

                data.pop('csrf_token', None)

                # Asignar cantidad_actual si no se provee explícitamente
                if 'cantidad_actual' not in data and 'cantidad_inicial' in data:
                    data['cantidad_actual'] = data['cantidad_inicial']

                # Generar número de lote si no viene del formulario
                if 'numero_lote' not in data or not data['numero_lote']:
                     data['numero_lote'] = f"LP-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                # Añadir la fecha de producción (asumimos que es hoy)
                if 'fecha_produccion' not in data:
                    data['fecha_produccion'] = datetime.now().date().isoformat()

                validated_data = self.schema.load(data)

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

    def obtener_lote_por_id_para_vista(self, id_lote: int) -> tuple:
        """Obtiene el detalle de un lote de producto para la vista, incluyendo el historial de calidad."""
        from app.controllers.control_calidad_producto_controller import ControlCalidadProductoController
        from app.models.motivo_desperdicio_lote_model import MotivoDesperdicioLoteModel
        try:
            result = self.model.get_lote_detail_for_view(id_lote)
            if not result.get('success') or not result.get('data'):
                return self.error_response(result.get('error', 'Lote no encontrado.'), 404)

            lote = result.get('data')

            # Enriquecer con historial de calidad
            cc_controller = ControlCalidadProductoController()
            historial_res, _ = cc_controller.obtener_registros_por_lote_producto(id_lote)
            lote['historial_calidad'] = historial_res.get('data', []) if historial_res.get('success') else []

            # Enriquecer con historial de desperdicios
            registro_desperdicio_model = RegistroDesperdicioLoteProductoModel()
            historial_desp_res = registro_desperdicio_model.get_by_lote_id(id_lote)
            historial_desperdicios = historial_desp_res.get('data', []) if historial_desp_res.get('success') else []

            # Enriquecer con nombres de usuario (solución al join cross-schema)
            if historial_desperdicios:
                from app.models.usuario import UsuarioModel
                user_model = UsuarioModel()
                # CORRECCIÓN: Iterar y buscar cada usuario por su ID individualmente.
                for h in historial_desperdicios:
                    if h.get('usuario_id'):
                        user_res = user_model.find_by_id(h['usuario_id'])
                        if user_res.get('success'):
                            h['usuario'] = user_res.get('data')

                # CORRECCIÓN: Convertir 'created_at' de string a objeto datetime.
                for h in historial_desperdicios:
                    if h.get('created_at') and isinstance(h['created_at'], str):
                        try:
                            # Supabase devuelve timestamps con timezone (formato ISO 8601)
                            h['created_at'] = datetime.fromisoformat(h['created_at'])
                        except ValueError:
                            # Fallback por si el formato es inesperado
                            logger.warning(f"No se pudo convertir la fecha: {h['created_at']}")
                            pass


            lote['historial_desperdicios'] = historial_desperdicios

            # Cargar motivos de desperdicio para el formulario
            motivo_model = MotivoDesperdicioLoteModel()
            motivos_res = motivo_model.get_all()
            lote['motivos_desperdicio'] = motivos_res.get('data', []) if motivos_res.get('success') else []


            # Convertir strings de fecha a objetos datetime
            if lote.get('created_at') and isinstance(lote['created_at'], str):
                lote['created_at'] = datetime.fromisoformat(lote['created_at'])
            if lote.get('fecha_vencimiento') and isinstance(lote['fecha_vencimiento'], str):
                lote['fecha_vencimiento'] = datetime.fromisoformat(lote['fecha_vencimiento'])

            for evento in lote.get('historial_calidad', []):
                if evento.get('created_at') and isinstance(evento['created_at'], str):
                    evento['created_at'] = datetime.fromisoformat(evento['created_at'])

            return self.success_response(data=lote)
        except Exception as e:
            logger.error(f"Error obteniendo detalle de lote: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def obtener_conteo_productos_sin_lotes(self) -> tuple:
        """
        Calcula y devuelve el conteo y la lista de productos activos que no tienen lotes asociados.
        """
        try:
            # 1. Obtener todos los productos activos y crear un mapa {id: producto}
            productos_activos_result = self.producto_model.find_all(filters={'activo': True})
            if not productos_activos_result.get('success'):
                raise Exception("Error al obtener productos activos.")

            # Mapeamos ID a un objeto con ID y Nombre
            productos_map = {
                p['id']: {'id': p['id'], 'nombre': p['nombre']}
                for p in productos_activos_result['data']
            }

            # 2. Obtener IDs de productos que tienen al menos un lote DISPONIBLE
            productos_con_lotes_result = self.model.find_all(filters={'estado': 'DISPONIBLE'})
            if not productos_con_lotes_result.get('success'):
                raise Exception("Error al obtener lotes.")

            # Filtrar IDs únicos de productos que ya tienen lote
            productos_con_lotes_ids = {lote['producto_id'] for lote in productos_con_lotes_result['data']}

            # 3. Calcular la diferencia y obtener la lista de objetos de producto
            productos_sin_lotes_list = []

            for prod_id, prod_data in productos_map.items():
                if prod_id not in productos_con_lotes_ids:
                    productos_sin_lotes_list.append(prod_data)

            conteo = len(productos_sin_lotes_list)

            return self.success_response(data={
                'conteo_sin_lotes': conteo,
                'productos_sin_lotes': productos_sin_lotes_list
            })

        except Exception as e:
            logger.error(f"Error contando productos sin lotes: {str(e)}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def despachar_stock_directo_por_pedido(self, pedido_id: int, items_del_pedido: list) -> dict:
        """
        Despacha el stock directamente de los lotes de productos para un pedido,
        ignorando la tabla de reservas de productos. Consumo FIFO de lotes DISPONIBLES.
        """
        try:
            if not items_del_pedido:
                return {'success': True, 'message': 'Pedido sin items para despachar.'}

            # 1. Iterar sobre los ítems del pedido
            for item in items_del_pedido:
                producto_id = item['producto_id']
                cantidad_necesaria = float(item['cantidad'])
                cantidad_restante_a_consumir = cantidad_necesaria

                # 2. Obtener lotes disponibles (FIFO)
                filtros = {
                    'producto_id': producto_id,
                    'estado': 'DISPONIBLE', # Solo lotes disponibles
                    'cantidad_actual': ('gt', 0)
                }
                lotes_disponibles_res = self.model.find_all(filters=filtros, order_by='created_at.asc')

                if not lotes_disponibles_res.get('success'):
                    logger.error(f"Fallo al obtener lotes para producto {producto_id} del pedido {pedido_id}.")
                    continue

                lotes_disponibles = lotes_disponibles_res.get('data', [])

                # 3. Consumir stock de los lotes
                for lote in lotes_disponibles:
                    if cantidad_restante_a_consumir <= 0:
                        break

                    cantidad_en_lote = lote.get('cantidad_actual', 0)
                    cantidad_a_consumir_de_este_lote = min(cantidad_en_lote, cantidad_restante_a_consumir)

                    # a. Calcular la nueva cantidad y preparar la actualización
                    nueva_cantidad_lote = cantidad_en_lote - cantidad_a_consumir_de_este_lote
                    datos_actualizacion_lote = {'cantidad_actual': nueva_cantidad_lote}

                    # b. Si la cantidad llega a cero, cambiar el estado a 'AGOTADO'
                    if nueva_cantidad_lote <= 0:
                        datos_actualizacion_lote['estado'] = 'AGOTADO'
                        logger.info(f"El lote {lote['numero_lote']} ha sido marcado como AGOTADO por despacho directo.")

                    # c. Realizar la actualización del lote en la base de datos (descuento permanente)
                    update_result = self.model.update(lote['id_lote'], datos_actualizacion_lote, 'id_lote')

                    if not update_result.get('success'):
                        # Si falla la actualización, se detiene el proceso de despacho.
                        raise Exception(f"Fallo al descontar stock del lote {lote['id_lote']}: {update_result.get('error')}")

                    cantidad_restante_a_consumir -= cantidad_a_consumir_de_este_lote

                if cantidad_restante_a_consumir > 0:
                    # Si al final no se pudo consumir todo el stock necesario, el despacho falla
                    # y el PedidoController no podrá completar la orden.
                    raise Exception(f"Stock insuficiente para el producto {producto_id}. Faltaron {cantidad_restante_a_consumir} unidades.")

            # Si todos los ítems se procesaron sin levantar la excepción, es éxito.
            return {'success': True}

        except Exception as e:
            logger.error(f"Error crítico al despachar stock directo del pedido {pedido_id}: {e}", exc_info=True)
            # Devolvemos el error específico para el PedidoController
            return {'success': False, 'error': f'Error interno al despachar stock: {str(e)}'}


    def despachar_stock_reservado_por_pedido(self, pedido_id: int, dry_run: bool = False) -> dict:
        """
        Finaliza el proceso de "reserva dura" cambiando el estado del registro de
        reserva de 'RESERVADO' a 'COMPLETADO' para indicar que el despacho se efectuó.
        El stock físico no se toca, ya que fue descontado en la creación del pedido.
        """
        if dry_run:
            return {'success': True, 'message': 'Verificación de stock (dry run) omitida.'}

        logger.info(f"Iniciando despacho (cambio de estado de reserva) para pedido ID: {pedido_id}")
        try:
            reservas_a_completar_res = self.reserva_model.find_all(filters={'pedido_id': pedido_id, 'estado': 'RESERVADO'})
            if not reservas_a_completar_res.get('success'):
                raise Exception("No se pudieron obtener los registros de reserva para completar.")

            reservas_a_completar = reservas_a_completar_res.get('data', [])
            if not reservas_a_completar:
                logger.warning(f"No se encontraron reservas 'RESERVADO' para despachar el pedido {pedido_id}. La operación se considera exitosa.")
                return {'success': True, 'message': 'No había reservas pendientes para despachar.'}

            item_ids = [r['id'] for r in reservas_a_completar]

            logger.info(f"Marcando {len(item_ids)} reservas como 'COMPLETADO' para el pedido {pedido_id}.")
            update_res = self.reserva_model.db.table(self.reserva_model.get_table_name()) \
                .update({'estado': 'COMPLETADO', 'fecha_despacho': datetime.now().isoformat()}) \
                .in_('id', item_ids) \
                .execute()

            if len(update_res.data) != len(item_ids):
                logger.warning(f"Se esperaba actualizar {len(item_ids)} reservas para el pedido {pedido_id}, pero se actualizaron {len(update_res.data)}.")

            logger.info(f"Despacho para pedido {pedido_id} completado con éxito.")
            return {'success': True, 'message': 'Reservas marcadas como completadas.'}

        except Exception as e:
            logger.error(f"Error al marcar reservas como completadas para el pedido {pedido_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def reservar_stock_para_pedido(self, pedido_id: int, items: list, usuario_id: int) -> dict:
        """
        Implementa "reserva dura": descuenta físicamente el stock de los lotes y
        crea un registro de la operación con estado 'RESERVADO'.
        FILTRA LOTES POR FECHA DE VENCIMIENTO vs FECHA REQUERIDO.
        """
        from app.models.pedido import PedidoModel # Importación local para evitar ciclos

        logger.info(f"Iniciando reserva dura de stock para pedido ID: {pedido_id}")
        lotes_modificados = []

        try:
            # 1. Obtener la fecha requerida del pedido para validar vencimientos
            pedido_model = PedidoModel()
            pedido_res = pedido_model.find_by_id(pedido_id)
            fecha_requerido_str = None

            if pedido_res.get('success') and pedido_res.get('data'):
                fecha_requerido_str = pedido_res['data'].get('fecha_requerido')

            # Si no hay fecha requerida, usamos HOY como base (no aceptar vencidos)
            fecha_filtro = fecha_requerido_str if fecha_requerido_str else date.today().isoformat()

            for item in items:
                producto_id = item['producto_id']
                cantidad_necesaria = float(item['cantidad'])
                logger.info(f"Procesando item producto ID {producto_id}, cantidad requerida: {cantidad_necesaria}")
                cantidad_restante_a_descontar = cantidad_necesaria

                # --- CONSULTA FILTRADA POR VENCIMIENTO ---
                # Buscamos lotes DISPONIBLES, con stock > 0 y que NO venzan antes de la fecha requerida
                lotes_query = self.model.db.table(self.model.get_table_name()) \
                    .select('*') \
                    .eq('producto_id', producto_id) \
                    .eq('estado', 'DISPONIBLE') \
                    .gt('cantidad_actual', 0) \
                    .gte('fecha_vencimiento', fecha_filtro) \
                    .order('fecha_vencimiento', desc=False) # FEFO (Primero los que vencen más cerca, pero validos)

                lotes_disponibles_data = lotes_query.execute().data

                if not lotes_disponibles_data:
                    # Si no hay lotes validos por fecha, lanzamos error específico
                    raise Exception(f"No hay lotes con fecha de vencimiento válida (>= {fecha_filtro}) para el producto ID {producto_id}.")

                for lote in lotes_disponibles_data:
                    if cantidad_restante_a_descontar <= 0: break

                    stock_fisico_en_lote = float(lote.get('cantidad_actual', 0))
                    cantidad_a_tomar_de_lote = min(stock_fisico_en_lote, cantidad_restante_a_descontar)

                    if cantidad_a_tomar_de_lote <= 0: continue

                    # 1. Descontar stock del lote
                    nueva_cantidad_lote = stock_fisico_en_lote - cantidad_a_tomar_de_lote
                    update_data = {'cantidad_actual': nueva_cantidad_lote}
                    if nueva_cantidad_lote <= 0: update_data['estado'] = 'AGOTADO'

                    logger.info(f"Descontando {cantidad_a_tomar_de_lote} del lote {lote['id_lote']} (Vence: {lote['fecha_vencimiento']})")

                    update_result = self.model.update(lote['id_lote'], update_data, 'id_lote')

                    if not update_result.get('success'):
                        raise Exception(f"Fallo crítico al descontar stock del lote {lote['id_lote']}.")

                    lotes_modificados.append({'lote_id': lote['id_lote'], 'cantidad_devuelta': cantidad_a_tomar_de_lote, 'estado_anterior': lote.get('estado')})

                    # 2. Crear registro de trazabilidad
                    datos_reserva = {
                        'lote_producto_id': lote['id_lote'], 'pedido_id': pedido_id, 'pedido_item_id': item.get('id'),
                        'cantidad_reservada': cantidad_a_tomar_de_lote, 'usuario_reserva_id': usuario_id, 'estado': 'RESERVADO'
                    }
                    self.reserva_model.create(self.reserva_schema.load(datos_reserva))

                    cantidad_restante_a_descontar -= cantidad_a_tomar_de_lote

                if cantidad_restante_a_descontar > 0.01:
                    raise Exception(f"Stock insuficiente (válido por fecha) para el producto ID {producto_id}. Faltaron {cantidad_restante_a_descontar} unidades.")

            return {'success': True}

        except Exception as e:
            logger.error(f"Error en la reserva dura para el pedido {pedido_id}: {e}. Iniciando reversión...", exc_info=True)
            for modificacion in reversed(lotes_modificados):
                lote_id = modificacion['lote_id']
                cantidad_devuelta = modificacion['cantidad_devuelta']
                logger.warning(f"Revirtiendo: Devolviendo {cantidad_devuelta} unidades al lote ID {lote_id}.")

                lote_actual_res = self.model.find_by_id(lote_id, 'id_lote')
                if lote_actual_res.get('success') and lote_actual_res.get('data'):
                    lote_actual = lote_actual_res.get('data')
                    nueva_cantidad = lote_actual.get('cantidad_actual', 0) + cantidad_devuelta
                    self.model.update(lote_id, {'cantidad_actual': nueva_cantidad, 'estado': modificacion['estado_anterior']}, 'id_lote')
                else:
                    logger.error(f"FALLO CRÍTICO EN REVERSIÓN: No se pudo encontrar el lote {lote_id} para devolver el stock.")

            return {'success': False, 'error': str(e)}

    def obtener_lotes_y_conteo_vencimientos(self) -> dict:
        """Obtiene los lotes y el conteo de productos próximos a vencer."""
        try:
            dias_alerta = self.config_controller.obtener_dias_vencimiento()

            # Reutilizamos el método del modelo que ya busca por vencimiento
            vencimiento_result = self.model.find_por_vencimiento(dias_alerta)

            if vencimiento_result.get('success'):
                lotes = vencimiento_result.get('data', [])
                return {'count': len(lotes), 'data': lotes}
            return {'count': 0, 'data': []}
        except Exception as e:
            logger.error(f"Error obteniendo lotes próximos a vencer: {str(e)}")
            return {'count': 0, 'data': []}

    def obtener_datos_grafico_inventario(self) -> dict:
        """
        Prepara los datos del gráfico de composición del inventario de productos.
        Retorna (response_dict, status_code).
        """
        try:
            result = self.model.obtener_composicion_inventario()

            if not result.get('success'):
                # CORRECCIÓN: self.error_response(...) ya devuelve (dict, 500).
                return self.error_response(result.get('error', 'Error al obtener datos para el gráfico.'), 500)

            # CORRECCIÓN: self.success_response(data) ya devuelve (dict, 200).
            return self.success_response(result['data'])

        except Exception as e:
            logger.error(f"Error obteniendo datos de gráfico: {e}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def _validar_fila_para_lote(self, row, numero_fila):
        """Valida una única fila del archivo Excel para la creación de un lote."""
        try:
            def error_msg(mensaje):
                return f"Fila {numero_fila}: {mensaje}"

            # 1. Validar Codigo Producto
            codigo_producto = row.get('codigo_producto')
            if pd.isna(codigo_producto) or codigo_producto is None:
                return False, error_msg("La columna 'codigo_producto' no puede estar vacía.")

            producto_result = self.producto_model.find_by_codigo(str(codigo_producto))
            if not producto_result.get('success') or not producto_result.get('data'):
                return False, error_msg(f"Producto con código '{codigo_producto}' no encontrado.")

            producto_id = producto_result['data']['id']

            # 2. Validar Cantidad
            cantidad_inicial = row.get('cantidad_inicial')
            if pd.isna(cantidad_inicial) or cantidad_inicial is None:
                return False, error_msg("La columna 'cantidad_inicial' no puede estar vacía.")

            try:
                cantidad_inicial = float(cantidad_inicial)
                if cantidad_inicial <= 0:
                    return False, error_msg(f"La cantidad inicial debe ser un número positivo, pero se recibió: '{cantidad_inicial}'.")
            except (ValueError, TypeError):
                return False, error_msg(f"La cantidad inicial debe ser un número, pero se recibió: '{cantidad_inicial}'.")

            # 3. Validar y manejar Número de Lote
            numero_lote = row.get('numero_lote')
            if pd.isna(numero_lote) or numero_lote is None:
                numero_lote = f"LP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{numero_fila}"
            else:
                numero_lote = str(numero_lote)
                lote_existente = self.model.find_by_numero_lote(numero_lote)
                if lote_existente.get('data'):
                    return False, error_msg(f"El número de lote '{numero_lote}' ya existe.")

            # 4. Validar Fechas
            fecha_produccion_str = row.get('fecha_produccion')
            try:
                fecha_produccion = pd.to_datetime(fecha_produccion_str).date() if pd.notna(fecha_produccion_str) else date.today()
            except (ValueError, TypeError):
                return False, error_msg(f"Formato de 'fecha_produccion' inválido: '{fecha_produccion_str}'. Use AAAA-MM-DD.")

            fecha_vencimiento_str = row.get('fecha_vencimiento')
            fecha_vencimiento = None
            if pd.notna(fecha_vencimiento_str):
                try:
                    fecha_vencimiento = pd.to_datetime(fecha_vencimiento_str).date()
                except (ValueError, TypeError):
                    return False, error_msg(f"Formato de 'fecha_vencimiento' inválido: '{fecha_vencimiento_str}'. Use AAAA-MM-DD.")

            if fecha_vencimiento and fecha_vencimiento < fecha_produccion:
                return False, error_msg(f"La fecha de vencimiento ({fecha_vencimiento}) no puede ser anterior a la fecha de producción ({fecha_produccion}).")

            # 5. Si todo es válido, devolver los datos limpios
            lote_data = {
                'producto_id': producto_id,
                'numero_lote': numero_lote,
                'cantidad_inicial': cantidad_inicial,
                'cantidad_actual': cantidad_inicial,
                'fecha_produccion': fecha_produccion.isoformat(),
                'fecha_vencimiento': fecha_vencimiento.isoformat() if fecha_vencimiento else None,
                'estado': 'DISPONIBLE'
            }
            return True, lote_data

        except Exception as e:
            return False, f"Fila {numero_fila}: Error inesperado al validar la fila - {str(e)}"

    def procesar_archivo_lotes(self, archivo):
        """Procesa un archivo Excel para crear lotes de productos masivamente con validación completa previa."""
        try:
            df = pd.read_excel(archivo)

            lotes_a_crear = []
            errores = []

            # 1. Fase de Validación
            for index, row in df.iterrows():
                is_valid, data_o_error = self._validar_fila_para_lote(row, index + 2)
                if is_valid:
                    lotes_a_crear.append(data_o_error)
                else:
                    errores.append(data_o_error)

            # 2. Fase de Creación (Todo o Nada)
            if errores:
                resultados = {'creados': 0, 'errores': len(errores), 'detalles': errores, 'estado_general': 'ERROR'}
                return self.success_response(data=resultados)

            else:
                creados_count = 0
                detalles_creacion = []
                for lote_data in lotes_a_crear:
                    result = self.model.create(lote_data)
                    if result.get('success'):
                        creados_count += 1
                    else:
                        detalles_creacion.append(f"Error al crear lote para producto {lote_data.get('producto_id')}: {result.get('error')}")

                resultados = {
                    'creados': creados_count,
                    'errores': len(detalles_creacion),
                    'detalles': detalles_creacion,
                    'estado_general': 'OK' if not detalles_creacion else 'ERROR'
                }
                return self.success_response(data=resultados)

        except Exception as e:
            logger.error(f"Error crítico al procesar archivo de lotes: {str(e)}", exc_info=True)
            return self.error_response(f"Error al leer o procesar el archivo: {str(e)}", 500)

    def generar_plantilla_lotes(self):
        """Genera un archivo Excel en memoria para la carga masiva de lotes."""
        try:
            # Datos de ejemplo
            datos_ejemplo = {
                'codigo_producto': ['PROD-001', 'PROD-002'],
                'numero_lote': ['LOTE-A', 'LOTE-B'],
                'cantidad_inicial': [100, 200],
                'fecha_produccion': [date(2023, 1, 1), date(2023, 2, 1)],
                'fecha_vencimiento': [date(2024, 1, 1), date(2024, 2, 1)]
            }
            df = pd.DataFrame(datos_ejemplo)

            # Crear Excel en memoria
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Lotes', index=False)

            output.seek(0)
            return output

        except Exception as e:
            logger.error(f"Error al generar la plantilla de lotes: {str(e)}", exc_info=True)
            return None

    def poner_lote_en_cuarentena(self, lote_id: int, motivo: str, cantidad: float, usuario_id: int, resultado_inspeccion: str, foto_file) -> tuple:
        """
        Mueve una cantidad específica de un lote DISPONIBLE al estado CUARENTENA y crea un registro de control de calidad.
        """
        try:
            lote_res = self.model.find_by_id(lote_id, 'id_lote')
            if not lote_res.get('success') or not lote_res.get('data'):
                return self.error_response('Lote no encontrado', 404)

            lote = lote_res['data']
            cantidad_actual_disponible = lote.get('cantidad_actual') or 0
            cantidad_actual_cuarentena = lote.get('cantidad_en_cuarentena') or 0

            if lote.get('estado') not in ['DISPONIBLE', 'CUARENTENA']:
                msg = f"El lote debe estar DISPONIBLE o en CUARENTENA. Estado actual: {lote.get('estado')}"
                return self.error_response(msg, 400)

            # Fallback: si motivo (comentarios) está vacío, usar resultado_inspeccion (dropdown)
            motivo_final = motivo or resultado_inspeccion

            if not motivo_final:
                return self.error_response("Se requiere un motivo para la cuarentena.", 400)

            if cantidad <= 0:
                 return self.error_response("La cantidad debe ser un número positivo.", 400)

            cantidad_a_mover = cantidad
            if cantidad_a_mover > cantidad_actual_disponible:
                logger.warning(f"La cantidad de cuarentena solicitada ({cantidad}) excede el disponible ({cantidad_actual_disponible}). Se pondrá en cuarentena todo el disponible.")
                cantidad_a_mover = cantidad_actual_disponible

            nueva_cantidad_disponible = cantidad_actual_disponible - cantidad_a_mover
            nueva_cantidad_cuarentena = cantidad_actual_cuarentena + cantidad_a_mover

            update_data = {
                'estado': 'CUARENTENA',
                'motivo_cuarentena': motivo_final,
                'cantidad_en_cuarentena': nueva_cantidad_cuarentena,
                'cantidad_actual': nueva_cantidad_disponible
            }

            result = self.model.update(lote_id, update_data, 'id_lote')
            if not result.get('success'):
                return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500)

            foto_url = self._subir_foto_y_obtener_url(foto_file, lote_id)
            cc_data = {
                'lote_producto_id': lote_id,
                'usuario_supervisor_id': usuario_id,
                'decision_final': 'CUARENTENA',
                'comentarios': motivo_final,
                'resultado_inspeccion': resultado_inspeccion or 'Cuarentena Manual',
                'foto_url': foto_url,
                'cantidad_inspeccionada': cantidad
            }
            cc_res, _ = self.control_calidad_producto_controller.crear_registro_control_calidad(cc_data)
            if not cc_res.get('success'):
                 logger.error(f"Falló la creación del registro de C.C. para el lote {lote_id}: {cc_res.get('error')}")

            return self.success_response(message="Cantidad puesta en cuarentena con éxito.")

        except Exception as e:
            logger.error(f"Error en poner_lote_en_cuarentena: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    # --- MÉTODO MODIFICADO PARA ACEPTAR CANTIDAD ---
    def liberar_lote_de_cuarentena(self, lote_id: int, cantidad_a_liberar: float) -> tuple:
        """
        Mueve una cantidad específica de CUARENTENA de vuelta a DISPONIBLE.
        Si la cantidad en cuarentena llega a 0, el estado vuelve a DISPONIBLE.
        """
        try:
            lote_res = self.model.find_by_id(lote_id, 'id_lote')
            if not lote_res.get('success') or not lote_res.get('data'):
                return self.error_response('Lote no encontrado', 404)

            lote = lote_res['data']
            cantidad_actual_disponible = lote.get('cantidad_actual') or 0
            cantidad_actual_cuarentena = lote.get('cantidad_en_cuarentena') or 0

            # Validaciones
            if lote.get('estado') != 'CUARENTENA':
                return self.error_response(f"El lote no está en cuarentena.", 400)

            if cantidad_a_liberar <= 0:
                 return self.error_response("La cantidad a liberar debe ser un número positivo.", 400)

            if cantidad_a_liberar > cantidad_actual_cuarentena:
                msg = f"No puede liberar {cantidad_a_liberar} unidades. Solo hay {cantidad_actual_cuarentena} en cuarentena."
                return self.error_response(msg, 400)

            # Lógica de resta y suma
            nueva_cantidad_cuarentena = cantidad_actual_cuarentena - cantidad_a_liberar
            nueva_cantidad_disponible = cantidad_actual_disponible + cantidad_a_liberar

            # Decidir el nuevo estado
            nuevo_estado = 'CUARENTENA'
            nuevo_motivo = lote.get('motivo_cuarentena')

            if nueva_cantidad_cuarentena == 0:
                nuevo_estado = 'DISPONIBLE'
                nuevo_motivo = None # Limpiar motivo

            update_data = {
                'estado': nuevo_estado,
                'motivo_cuarentena': nuevo_motivo,
                'cantidad_en_cuarentena': nueva_cantidad_cuarentena,
                'cantidad_actual': nueva_cantidad_disponible
            }

            result = self.model.update(lote_id, update_data, 'id_lote')
            if not result.get('success'):
                return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500)
            usuario_id = get_jwt_identity()
            # Disparar la verificación de cierre de alertas
            try:
                alerta_model = AlertaRiesgoModel()
                afectaciones = alerta_model.db.table('alerta_riesgo_afectados').select('alerta_id').eq('tipo_entidad', 'lote_producto').eq('id_entidad', lote_id).eq('estado', 'pendiente').execute().data
                if afectaciones:
                    alerta_ids = {a['alerta_id'] for a in afectaciones}
                    for alerta_id in alerta_ids:
                       alerta_model.actualizar_estado_afectados(
                            alerta_id,
                            [lote_id],
                            'aprobado_calidad',
                            'lote_producto',
                            usuario_id
                        )

            except Exception as e_alert:
                logger.error(f"Error al verificar alertas tras liberar lote de producto {lote_id}: {e_alert}", exc_info=True)

            return self.success_response(message="Cantidad liberada de cuarentena con éxito.")

        except Exception as e:
            logger.error(f"Error en liberar_lote_de_cuarentena: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)


    def actualizar_lote_desde_formulario(self, lote_id: int, form_data) -> tuple:
        """Actualiza un lote existente desde un formulario web."""
        try:
            # 1. Verificar que el lote existe
            lote_existente = self.model.find_by_id(lote_id, 'id_lote')
            if not lote_existente.get('success') or not lote_existente.get('data'):
                return self.error_response('Lote no encontrado', 404)

            lote_actual = lote_existente['data'] # <-- Necesitamos esto

            # 2. Convertir form a dict y limpiar
            if hasattr(form_data, 'to_dict'):
                data = form_data.to_dict()
            else:
                data = form_data.copy()

            data.pop('csrf_token', None)
            data.pop('producto_id', None)
            data.pop('cantidad_inicial', None)
            data.pop('cantidad_actual', None)
            data.pop('cantidad_en_cuarentena', None)

            # --- INICIO DE LA VALIDACIÓN LÓGICA MANUAL ---
            if 'fecha_vencimiento' in data and data['fecha_vencimiento']:
                # 1. Obtener fecha de producción (del lote existente)
                fecha_produccion_str = lote_actual['fecha_produccion']
                if isinstance(fecha_produccion_str, (date, datetime)):
                    fecha_produccion_actual = fecha_produccion_str.date()
                else:
                    fecha_produccion_actual = date.fromisoformat(fecha_produccion_str.split(' ')[0]) # Maneja 'YYYY-MM-DD HH:MM:SS'

                # 2. Obtener nueva fecha de vencimiento (del form)
                fecha_vencimiento_nueva = date.fromisoformat(data['fecha_vencimiento'])

                # 3. Comparar
                if fecha_vencimiento_nueva < fecha_produccion_actual:
                    msg = f"La fecha de vencimiento ({fecha_vencimiento_nueva}) no puede ser anterior a la de producción ({fecha_produccion_actual})."
                    # Lanzamos un ValidationError para que sea capturado abajo
                    raise ValidationError(msg)
            # --- FIN DE LA VALIDACIÓN LÓGICA MANUAL ---

            # 3. Validar los datos restantes con el schema
            if 'fecha_vencimiento' in data and not data['fecha_vencimiento']:
                data['fecha_vencimiento'] = None
            if 'costo_produccion_unitario' in data and not data['costo_produccion_unitario']:
                data['costo_produccion_unitario'] = None

            validated_data = self.schema.load(data, partial=True)

            # 4. Actualizar el lote
            result = self.model.update(lote_id, validated_data, 'id_lote')
            if not result.get('success'):
                # Si aun así falla (por si acaso), lo capturamos
                if 'check_fechas_logicas' in result.get('error', ''):
                     raise ValidationError("Error de lógica de fechas. Verifique las fechas.")
                return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500)

            return self.success_response(result['data'], "Lote actualizado con éxito")

        except ValidationError as e:
            logger.warning(f"Error de validación al actualizar lote {lote_id}: {e.messages}")

            # Formatear el diccionario de errores en una lista HTML
            error_list = '<ul class="list-unstyled mb-0">'
            if isinstance(e.messages, dict):
                for field, messages in e.messages.items():
                    for message in messages:
                        error_list += f"<li>{message}</li>"
            else:
                error_list += f"<li>{e.messages}</li>"
            error_list += '</ul>'

            return self.error_response(error_list, 422)
        except Exception as e:
            logger.error(f"Error en actualizar_lote_desde_formulario: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def obtener_lotes_y_conteo_por_estado(self, estado: str) -> dict:
        """Obtiene los lotes y el conteo en un estado específico, usando datos enriquecidos."""
        try:
            # Usamos el método que ya trae los datos enriquecidos para la vista
            result = self.model.get_all_lotes_for_view(filtros={'estado': estado})
            if result.get('success'):
                lotes = result.get('data', [])
                return {'count': len(lotes), 'data': lotes}
            return {'count': 0, 'data': []}
        except Exception as e:
            logger.error(f"Error obteniendo lotes por estado '{estado}': {str(e)}")
            return {'count': 0, 'data': []}

    def obtener_conteo_lotes_sin_trazabilidad(self) -> int:
        """Obtiene el conteo de lotes sin una orden de producción asociada."""
        try:
            result = self.model.find_all(filters={'orden_produccion_id': ('is', None)})
            if result.get('success'):
                return len(result.get('data', []))
            return 0
        except Exception as e:
            logger.error(f"Error contando lotes sin trazabilidad: {str(e)}")
            return 0

    def crear_lote_y_reservas_desde_op(self, orden_produccion_data: Dict, usuario_id: int, qc_data: Optional[Dict] = None) -> tuple:
        """
        Crea un lote de producto a partir de una OP completada.
        Utiliza qc_data para determinar el estado inicial y las cantidades del lote.
        Si la OP está vinculada a items de pedido, crea registros de reserva.
        """
        from app.models.pedido import PedidoModel
        pedido_model = PedidoModel()
        from app.models.asignacion_pedido_model import AsignacionPedidoModel
        orden_id = orden_produccion_data['id']

        try:
            cantidad_producida = float(orden_produccion_data.get('cantidad_producida', 0))

            # --- LÓGICA COMPLETA DE CÁLCULO DE CANTIDADES ---
            cantidad_rechazada = 0
            cantidad_cuarentena = 0

            if qc_data:
                decision = qc_data.get('decision_inspeccion')
                cantidad_rechazada = float(qc_data.get('cantidad_rechazada', 0))
                cantidad_cuarentena = float(qc_data.get('cantidad_cuarentena', 0))

            # La cantidad inicial del lote es lo que se produjo menos lo que se rechazó.
            cantidad_inicial_lote = cantidad_producida - cantidad_rechazada

            # La cantidad actualmente disponible es la inicial menos lo que va a cuarentena.
            cantidad_actual_disponible = cantidad_inicial_lote - cantidad_cuarentena

            # Determinar el estado final del lote
            estado_lote_final = 'AGOTADO' # Estado por defecto si no hay cantidad disponible
            if cantidad_actual_disponible > 0:
                estado_lote_final = 'DISPONIBLE'
            elif cantidad_cuarentena == cantidad_inicial_lote and cantidad_inicial_lote > 0:
                estado_lote_final = 'CUARENTENA'

            motivo = qc_data.get('comentarios') or qc_data.get('motivo_inspeccion') if qc_data else None
            # --- FIN DE LA LÓGICA COMPLETA ---

            # --- NUEVA LÓGICA: CALCULAR FECHA DE VENCIMIENTO ---
            producto_id = orden_produccion_data['producto_id']
            producto_res = self.producto_model.find_by_id(producto_id, 'id')
            vida_util = 90  # Default de 90 días
            if producto_res.get('success') and producto_res.get('data'):
                vida_util = producto_res['data'].get('vida_util_dias') or 90

            fecha_vencimiento = (date.today() + timedelta(days=vida_util)).isoformat()
            # --- FIN NUEVA LÓGICA ---

            # 3. Preparar y crear el lote con el estado decidido
            datos_lote = {
                'producto_id': producto_id,
                'cantidad_inicial': cantidad_inicial_lote,
                'cantidad_actual': cantidad_actual_disponible,
                'cantidad_en_cuarentena': cantidad_cuarentena,
                'motivo_cuarentena': motivo,
                'orden_produccion_id': orden_id,
                'fecha_produccion': date.today().isoformat(),
                'fecha_vencimiento': fecha_vencimiento,
                'estado': estado_lote_final
            }

            resultado_lote, status_lote = self.crear_lote_desde_formulario(datos_lote, usuario_id=usuario_id)
            if status_lote >= 400:
                return self.error_response(f"Fallo al registrar el lote de producto: {resultado_lote.get('error')}", 500)

            lote_creado = resultado_lote['data']
            message_to_use = f"Lote N° {lote_creado['numero_lote']} creado como '{estado_lote_final}'."

            # 1. Buscar items vinculados directamente a la OP actual, ordenados por antigüedad del pedido (FIFO).
            items_a_surtir_res = pedido_model.find_all_items_with_pedido_info(filters={'orden_produccion_id': orden_id}, order_by='pedido.created_at.asc')
            items_vinculados = items_a_surtir_res.get('data', []) if items_a_surtir_res.get('success') else []

            # 2. Si no hay items directos Y es una OP hija, buscar en la tabla de asignaciones (vinculo por herencia).
            #    Esto es clave para que la OP Hija encuentre los items que le fueron asignados al nacer.
            if not items_vinculados and orden_produccion_data.get('id_op_padre'):
                logger.info(f"OP {orden_id} es una hija. Buscando asignaciones heredadas.")
                asignaciones_res = AsignacionPedidoModel().find_all_with_pedido_id(filters={'orden_produccion_id': orden_id})
                
                if asignaciones_res.get('success') and asignaciones_res.get('data'):
                     items_ids = [a['pedido_item_id'] for a in asignaciones_res['data']]
                     if items_ids:
                         items_vinculados_res = pedido_model.find_all_items_with_pedido_info(filters={'id': ('in', items_ids)}, order_by='pedido.created_at.asc')
                         if items_vinculados_res.get('success'):
                             items_vinculados = items_vinculados_res.get('data', [])
            
            # Si aún así no hay items (caso raro), intentar fallback a la OP Padre como último recurso
            if not items_vinculados and orden_produccion_data.get('id_op_padre'):
                 id_op_padre = orden_produccion_data['id_op_padre']
                 logger.warning(f"OP {orden_id} (Hija) sin asignaciones propias. Intentando buscar items de la OP Padre {id_op_padre}.")
                 items_padre_res = pedido_model.find_all_items_with_pedido_info(filters={'orden_produccion_id': id_op_padre}, order_by='pedido.created_at.asc')
                 items_vinculados = items_padre_res.get('data', []) if items_padre_res.get('success') else []


            if items_vinculados:
                from app.controllers.pedido_controller import PedidoController # Importar aquí para evitar ciclo
                pedido_controller = PedidoController()
                asignacion_model = AsignacionPedidoModel() # Ya importado arriba

                cantidad_disponible_para_reservar = cantidad_actual_disponible
                
                # --- CORRECCIÓN FIFO: ORDENAMIENTO PYTHON EXPLÍCITO ---
                # Para garantizar que se surte primero al pedido más antiguo, ordenamos la lista en Python.
                # Esto evita posibles fallos en la capa de base de datos/ORM.
                try:
                    items_vinculados.sort(key=lambda x: x.get('pedido', {}).get('created_at', '9999-12-31'))
                except Exception as e:
                    logger.warning(f"Fallo al ordenar items por fecha para FIFO: {e}")

                logger.info(f"Procesando {len(items_vinculados)} items vinculados para asignación de stock.")

                for item in items_vinculados:
                    if cantidad_disponible_para_reservar <= 0:
                        logger.info("Se agotó el stock disponible para reservar.")
                        break # No hay más stock para reservar.

                    pedido_item_id = item['id']
                    logger.info(f"Analizando Item {pedido_item_id} (Pedido {item.get('pedido_id')})...")

                    # 2. Calcular cuánto YA se reservó FÍSICAMENTE para este item.
                    #    CORRECCIÓN CRÍTICA: Usamos la tabla reservas_productos en lugar de asignaciones_pedidos.
                    #    Esto evita que la asignación heredada (que es solo un plan) cuente como stock ya entregado.
                    reservas_fisicas_existentes = self.reserva_model.find_all(filters={'pedido_item_id': pedido_item_id, 'estado': 'RESERVADO'})
                    cantidad_ya_reservada = sum(float(r['cantidad_reservada']) for r in reservas_fisicas_existentes.get('data', []))

                    # 3. Calcular lo que falta por cubrir
                    cantidad_total_necesaria = float(item['cantidad'])
                    cantidad_pendiente = cantidad_total_necesaria - cantidad_ya_reservada
                    
                    logger.info(f"Item {pedido_item_id}: Necesario {cantidad_total_necesaria}, Ya Reservado {cantidad_ya_reservada}, Pendiente {cantidad_pendiente}.")

                    if cantidad_pendiente <= 0.01: # Usar tolerancia pequeña para floats
                        logger.info(f"Item {pedido_item_id} ya cubierto. Saltando.")
                        continue # Este item ya está cubierto, pasar al siguiente (FIFO)

                    # 4. Reservar solo lo necesario o lo disponible
                    cantidad_a_reservar_para_item = min(cantidad_pendiente, cantidad_disponible_para_reservar)
                    logger.info(f"Intentando reservar {cantidad_a_reservar_para_item} para Item {pedido_item_id}. Disponible restante: {cantidad_disponible_para_reservar}.")

                    if cantidad_a_reservar_para_item > 0:
                        datos_reserva = {
                            'lote_producto_id': lote_creado['id_lote'],
                            'pedido_id': item['pedido_id'],
                            'pedido_item_id': pedido_item_id,
                            'cantidad_reservada': cantidad_a_reservar_para_item,
                            'usuario_reserva_id': usuario_id,
                            'estado': 'RESERVADO'
                        }
                        reserva_res = self.reserva_model.create(self.reserva_schema.load(datos_reserva))
                        if not reserva_res.get('success'):
                            logger.error(f"Fallo al crear registro de reserva para item {pedido_item_id}. Se omite asignación.")
                            continue

                        # Inmediatamente después de crear la reserva, verificamos/creamos la asignación.
                        # CORRECCIÓN: Verificar si ya existe la asignación para no duplicarla (caso OP Hija heredada)
                        existe_asignacion = asignacion_model.find_all(filters={
                            'orden_produccion_id': orden_id,
                            'pedido_item_id': pedido_item_id
                        })
                        
                        if existe_asignacion.get('success') and existe_asignacion.get('data'):
                            # Si ya existe (ej. creada por herencia), actualizamos la cantidad si es necesario o no hacemos nada.
                            # En este flujo, asumimos que la asignación heredada tenía la intención correcta.
                            # Podríamos sumar la cantidad si fuera acumulativa, pero por ahora solo registramos.
                            logger.info(f"La asignación para OP {orden_id} e Item {pedido_item_id} ya existía. No se duplica.")
                        else:
                            asignacion_res = asignacion_model.create({
                                'orden_produccion_id': orden_id,
                                'pedido_item_id': pedido_item_id,
                                'cantidad_asignada': cantidad_a_reservar_para_item
                            })
                            if not asignacion_res.get('success'):
                                logger.error(f"Fallo al crear registro de asignación para item {pedido_item_id}. La reserva podría quedar inconsistente.")

                        # Se descuenta lo que acabamos de reservar de lo que queda disponible.
                        cantidad_disponible_para_reservar -= cantidad_a_reservar_para_item

                        # --- LÓGICA DE DESCUENTO FÍSICO ---
                        self.model.update(lote_creado['id_lote'], {'cantidad_actual': cantidad_disponible_para_reservar}, 'id_lote')

                        # 5. Intentar actualizar el estado del pedido a LISTO_PARA_ENTREGAR si corresponde
                        try:
                            pedido_controller.actualizar_estado_segun_items(item['pedido_id'])
                        except Exception as e:
                            logger.error(f"Error al intentar actualizar estado del pedido {item['pedido_id']}: {e}")

                logger.info(f"Registros de reserva creados para el lote {lote_creado['numero_lote']}.")
                message_to_use += " y vinculado a los pedidos correspondientes."

            return self.success_response(data=lote_creado, message=message_to_use)

        except Exception as e:
            logger.error(f"Error crítico en crear_lote_y_reservas_desde_op para OP {orden_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)


    def marcar_lote_como_no_apto(self, lote_id: int, usuario_id: int, motivo: str, resultado_inspeccion: str) -> tuple:
        """
        Marca un lote de producto como 'NO_APTO' y anula su stock.
        (Legacy / Fallback)
        """
        try:
            lote_res = self.model.find_by_id(lote_id, 'id_lote')
            if not lote_res.get('success') or not lote_res.get('data'):
                return self.error_response('Lote no encontrado', 404)

            update_data = {
                'estado': 'NO_APTO',
                'cantidad_actual': 0,
                'cantidad_en_cuarentena': 0,
                'motivo_cuarentena': motivo
            }
            result = self.model.update(lote_id, update_data, 'id_lote')
            if not result.get('success'):
                return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500)

            cc_data = {
                'lote_producto_id': lote_id,
                'usuario_supervisor_id': usuario_id,
                'decision_final': 'NO_APTO',
                'comentarios': motivo,
                'resultado_inspeccion': resultado_inspeccion,
            }
            cc_res, _ = self.control_calidad_producto_controller.crear_registro_control_calidad(cc_data)
            if not cc_res.get('success'):
                logger.error(f"Lote {lote_id} marcado como NO APTO, pero falló la creación del registro de C.C.: {cc_res.get('error')}")

            try:
                alerta_model = AlertaRiesgoModel()
                alerta_model.actualizar_estado_afectados_por_entidad('lote_producto', lote_id, 'retirado_manual', usuario_id)
            except Exception as e_alert:
                logger.error(f"Error al actualizar alertas para el lote {lote_id} no apto: {e_alert}", exc_info=True)

            return self.success_response(message="Lote marcado como NO APTO con éxito.")

        except Exception as e:
            logger.error(f"Error en marcar_lote_como_no_apto (producto): {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def procesar_no_apto_avanzado(self, lote_id: int, form_data: dict, usuario_id: int) -> tuple:
        """
        Maneja el flujo avanzado de marcar un lote de producto como NO APTO.
        """
        try:
            lote_res = self.model.find_by_id(lote_id, 'id_lote')
            if not lote_res.get('success') or not lote_res.get('data'):
                return self.error_response('Lote no encontrado', 404)
            
            lote = lote_res['data']
            accion = form_data.get('accion_no_apto')

            if accion == 'retirar':
                return self._procesar_retiro_producto(lote, form_data, usuario_id)
            
            elif accion == 'alerta':
                return self._procesar_alerta_producto(lote, form_data, usuario_id)
            
            else:
                return self.error_response('Acción no válida.', 400)

        except Exception as e:
            logger.error(f"Error en procesar_no_apto_avanzado (producto): {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def _procesar_retiro_producto(self, lote, form_data, usuario_id):
        """Lógica para retirar stock de producto y registrar desperdicio."""
        
        try:
            cantidad_retiro = float(form_data.get('cantidad_retiro'))
            motivo_id = form_data.get('motivo_desperdicio_id')
            comentarios = form_data.get('comentarios_retiro')
            resultado_inspeccion = form_data.get('resultado_inspeccion')

            if cantidad_retiro <= 0:
                return self.error_response("La cantidad debe ser mayor a 0.", 400)
            if not motivo_id:
                return self.error_response("Debe seleccionar un motivo de desperdicio.", 400)

            stock_disp = float(lote.get('cantidad_actual', 0))
            stock_cuar = float(lote.get('cantidad_en_cuarentena', 0))
            stock_total = stock_disp + stock_cuar

            if cantidad_retiro > stock_total:
                return self.error_response(f"La cantidad a retirar ({cantidad_retiro}) excede el stock total del lote ({stock_total}).", 400)

            # 1. Registrar Desperdicio
            # Usamos el modelo RegistroDesperdicioLoteProductoModel
            desperdicio_model = RegistroDesperdicioLoteProductoModel()
            
            # El modelo requiere 'detalle', usaremos resultado_inspeccion, comentarios o un default
            detalle_final = resultado_inspeccion or comentarios or "Retiro manual de producto"

            datos_desperdicio = {
                'lote_producto_id': lote['id_lote'],
                'motivo_id': motivo_id,
                'cantidad': cantidad_retiro,
                'usuario_id': usuario_id,
                'detalle': detalle_final,
                'comentarios': comentarios, # Agregar comentarios también si el modelo lo soporta
                'created_at': datetime.now().isoformat()
            }
            
            res_desperdicio = desperdicio_model.create(datos_desperdicio)
            if not res_desperdicio.get('success'):
                return self.error_response(f"Error al registrar desperdicio: {res_desperdicio.get('error')}", 500)

            # 2. Actualizar Stock del Lote
            nueva_cantidad_cuar = stock_cuar
            nueva_cantidad_disp = stock_disp
            remanente_a_descontar = cantidad_retiro

            # Prioridad: Descontar de cuarentena primero
            # Fix TypeError: stock_cuar (float) must handle None
            stock_cuar = float(lote.get('cantidad_en_cuarentena') or 0)

            if stock_cuar > 0:
                descuento_cuar = min(stock_cuar, remanente_a_descontar)
                nueva_cantidad_cuar -= descuento_cuar
                remanente_a_descontar -= descuento_cuar
            
            if remanente_a_descontar > 0:
                nueva_cantidad_disp -= remanente_a_descontar

            nuevo_estado = lote['estado']
            if (nueva_cantidad_cuar + nueva_cantidad_disp) <= 0:
                if cantidad_retiro >= stock_total:
                    nuevo_estado = 'RETIRADO'
                else:
                    nuevo_estado = 'AGOTADO'
            
            update_data = {
                'cantidad_actual': nueva_cantidad_disp,
                'cantidad_en_cuarentena': nueva_cantidad_cuar,
                'estado': nuevo_estado
            }
            
            self.model.update(lote['id_lote'], update_data, 'id_lote')

            # 3. Crear registro de Control de Calidad para trazabilidad (opcional pero recomendado)
            cc_data = {
                'lote_producto_id': lote['id_lote'],
                'usuario_supervisor_id': usuario_id,
                'decision_final': 'RETIRADO' if nuevo_estado == 'RETIRADO' else 'APROBADO', # Parcial?
                'comentarios': f"Retiro manual de {cantidad_retiro}. {comentarios}",
                'resultado_inspeccion': resultado_inspeccion or 'Retiro por desperdicio',
                'cantidad_inspeccionada': cantidad_retiro
            }
            # Solo creamos registro si fue un retiro relevante, para dejar constancia
            self.control_calidad_producto_controller.crear_registro_control_calidad(cc_data)

            return self.success_response(message="Lote de producto retirado y desperdicio registrado correctamente.")

        except ValueError:
             return self.error_response("Datos numéricos inválidos.", 400)
        except Exception as e:
            logger.error(f"Error en _procesar_retiro_producto: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def _procesar_alerta_producto(self, lote, form_data, usuario_id):
        """Lógica para crear una alerta de riesgo desde un lote de producto."""
        from app.controllers.riesgo_controller import RiesgoController
        
        try:
            motivo = form_data.get('motivo_alerta')
            descripcion = form_data.get('descripcion_alerta')

            if not motivo:
                return self.error_response("El motivo de la alerta es obligatorio.", 400)

            datos_alerta = {
                "tipo_entidad": "lote_producto",
                "id_entidad": lote['id_lote'],
                "motivo": motivo,
                "comentarios": descripcion,
                "url_evidencia": None
            }

            riesgo_controller = RiesgoController()
            # Llamada que devuelve tuple
            res_alerta_tuple = riesgo_controller.crear_alerta_riesgo_con_usuario(datos_alerta, usuario_id)
            
            res_alerta = res_alerta_tuple[0] if isinstance(res_alerta_tuple, tuple) else res_alerta_tuple

            if res_alerta.get('success'):
                return self.success_response(message="Alerta de riesgo creada correctamente.")
            else:
                return self.error_response(f"Error al crear alerta: {res_alerta.get('error')}", 500)

        except Exception as e:
            logger.error(f"Error en _procesar_alerta_producto: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def _subir_foto_y_obtener_url(self, file_storage, lote_id: int) -> str | None:
        if not file_storage or not file_storage.filename:
            return None
        try:
            db_client = Database().client
            bucket_name = "registro_desperdicio_lote_producto"

            filename = secure_filename(file_storage.filename)
            extension = os.path.splitext(filename)[1]
            unique_filename = f"productos/lote_{lote_id}_{int(datetime.now().timestamp())}{extension}"

            file_content = file_storage.read()

            db_client.storage.from_(bucket_name).upload(
                path=unique_filename,
                file=file_content,
                file_options={"content-type": file_storage.mimetype}
            )

            url_response = db_client.storage.from_(bucket_name).get_public_url(unique_filename)
            logger.info(f"Foto subida con éxito para el lote {lote_id}. URL: {url_response}")
            return url_response

        except StorageApiError as e:
            if "Bucket not found" in str(e):
                error_message = f"Error de configuración: El bucket de almacenamiento '{bucket_name}' no se encontró en Supabase."
                logger.error(error_message)
                raise Exception(error_message)
            else:
                logger.error(f"Error de Supabase Storage al subir foto para el lote {lote_id}: {e}", exc_info=True)
                raise e
        except Exception as e:
            logger.error(f"Excepción general al subir foto para el lote {lote_id}: {e}", exc_info=True)
            raise e

    def liberar_lote_de_cuarentena_alerta(self, lote_id: int) -> tuple:
        """
        Libera un lote de producto de CUARENTENA, devolviéndolo a su estado previo a la alerta.
        """
        try:
            lote_res = self.model.find_by_id(lote_id, 'id_lote')
            if not lote_res.get('success') or not lote_res.get('data'):
                return self.error_response('Lote no encontrado', 404)

            lote = lote_res['data']

            afectado_res = self.db.table('alerta_riesgo_afectados').select('estado_previo').eq('tipo_entidad', 'lote_producto').eq('id_entidad', lote_id).order('id', desc=True).limit(1).execute().data

            estado_previo = 'disponible'
            if afectado_res and afectado_res[0].get('estado_previo'):
                estado_previo = afectado_res[0]['estado_previo']

            estado_destino = 'disponible' if 'en revision' in estado_previo.lower() else estado_previo

            cantidad_en_cuarentena = lote.get('cantidad_en_cuarentena', 0)
            cantidad_actual = lote.get('cantidad_actual', 0)
            nueva_cantidad_actual = cantidad_actual + cantidad_en_cuarentena

            update_data = {
                'estado': estado_destino,
                'cantidad_actual': nueva_cantidad_actual,
                'cantidad_en_cuarentena': 0,
                'motivo_cuarentena': None
            }

            result = self.model.update(lote_id, update_data, 'id_lote')
            if not result.get('success'):
                return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500)

            return self.success_response(message="Lote de producto liberado de cuarentena de alerta.")

        except Exception as e:
            logger.error(f"Error en liberar_lote_de_cuarentena_alerta (producto): {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def marcar_lote_retirado_alerta(self, lote_id: int):
        """
        Marca un lote de producto como 'retirado' por una alerta y anula su stock.
        """
        try:
            update_data = {
                'estado': 'RETIRADO',
                'cantidad_actual': 0,
                'cantidad_en_cuarentena': 0,
            }
            result = self.model.update(lote_id, update_data, 'id_lote')

            if not result.get('success'):
                return self.error_response(result.get('error', 'Error al actualizar el lote.'), 500)

            return self.success_response(message="Lote de producto marcado como retirado.")
        except Exception as e:
            logger.error(f"Error en marcar_lote_retirado_alerta (producto): {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def liberar_reserva_especifica(self, reserva_id: int) -> bool:
        """
        Cancela una reserva específica por su ID y DEVUELVE el stock al lote.
        """
        try:
            logger.info(f"Liberando reserva específica ID: {reserva_id}")

            # 1. Obtener datos de la reserva
            reserva_data_res = self.reserva_model.find_by_id(reserva_id)
            if not reserva_data_res.get('success') or not reserva_data_res.get('data'):
                logger.error(f"No se encontró la reserva {reserva_id} para liberar.")
                return False

            reserva_data = reserva_data_res['data']

            # Validar si ya está cancelada
            if reserva_data.get('estado') == 'CANCELADO':
                logger.warning(f"La reserva {reserva_id} ya estaba cancelada.")
                return True

            cantidad_a_devolver = float(reserva_data['cantidad_reservada'])
            lote_id = reserva_data['lote_producto_id']

            # --- PASO CRÍTICO 1: CAMBIAR ESTADO A 'CANCELADO' ---
            # Usamos update directo a la tabla para asegurar que no haya lógica intermedia del modelo que interfiera
            update_reserva = self.reserva_model.db.table('reservas_productos')\
                .update({'estado': 'CANCELADO'})\
                .eq('id', reserva_id)\
                .execute()

            if not update_reserva.data:
                logger.error(f"Fallo al actualizar estado de reserva {reserva_id} a CANCELADO en DB.")
                return False

            logger.info(f"Reserva {reserva_id} marcada como CANCELADO exitosamente.")

            # --- PASO CRÍTICO 2: DEVOLVER EL STOCK AL LOTE ---
            lote_res = self.model.find_by_id(lote_id, 'id_lote')
            if lote_res.get('success') and lote_res.get('data'):
                lote_actual = lote_res['data']
                nueva_cantidad = float(lote_actual.get('cantidad_actual', 0)) + cantidad_a_devolver

                # Si el lote estaba AGOTADO, lo volvemos a poner DISPONIBLE
                estado_lote = lote_actual.get('estado')
                if estado_lote == 'AGOTADO':
                    estado_lote = 'DISPONIBLE'

                self.model.update(lote_id, {
                    'cantidad_actual': nueva_cantidad,
                    'estado': estado_lote
                }, 'id_lote')

                logger.info(f"Stock devuelto al lote {lote_id}: +{cantidad_a_devolver}. Nueva cantidad: {nueva_cantidad}")
                return True
            else:
                logger.error(f"CRÍTICO: Se canceló la reserva {reserva_id} pero no se encontró el lote {lote_id} para devolver el stock.")
                # Intentar revertir la cancelación de reserva si falla la devolución de stock (Opcional pero recomendado)
                self.reserva_model.update(reserva_id, {'estado': 'RESERVADO'}, 'id')
                return False

        except Exception as e:
            logger.error(f"Error crítico en liberar_reserva_especifica: {e}", exc_info=True)
            return False


    def devolver_stock_a_lote(self, lote_id: int, cantidad: float) -> bool:
        """Devuelve stock físico a un lote sin tocar reservas."""
        try:
            lote = self.model.find_by_id(lote_id, 'id_lote').get('data')
            if not lote: return False

            nueva_cantidad = float(lote.get('cantidad_actual', 0)) + cantidad
            estado = 'DISPONIBLE' if lote.get('estado') == 'AGOTADO' else lote.get('estado')

            self.model.update(lote_id, {'cantidad_actual': nueva_cantidad, 'estado': estado}, 'id_lote')
            return True
        except Exception as e:
            logger.error(f"Error devolviendo stock a lote {lote_id}: {e}")
            return False