# app/controllers/lote_producto_controller.py
import logging
from datetime import datetime, date, timedelta
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


    def crear_lote_desde_formulario(self, form_data: dict, usuario_id: int) -> tuple:
            """Crea un nuevo lote de producto desde un formulario web."""
            try:
                data = form_data
                data.pop('csrf_token', None)

                # Asignar cantidad_actual si existe cantidad_inicial
                if 'cantidad_inicial' in data:
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


    def despachar_stock_reservado_por_pedido(self, pedido_id: int) -> dict:
        """
        Despacha el stock que fue PREVIAMENTE RESERVADO para un pedido.
        Actualiza los lotes y el estado de las reservas.
        """
        try:
            # 1. Buscar todas las reservas activas para este pedido
            reservas_result = self.reserva_model.find_all(filters={
                'pedido_id': pedido_id,
                'estado': 'RESERVADO'
            })

            if not reservas_result.get('success'):
                raise Exception(f"No se pudieron obtener las reservas para el pedido {pedido_id}.")

            reservas = reservas_result.get('data', [])
            if not reservas:
                return {'success': True, 'message': 'El pedido no tenía reservas activas para despachar.'}

            # 2. Iterar sobre cada reserva y consumir el stock del lote correspondiente
            for reserva in reservas:
                lote_id = reserva['lote_producto_id']
                cantidad_a_despachar = reserva['cantidad_reservada']

                # Obtener el estado actual del lote
                lote_actual_res = self.model.find_by_id(lote_id, 'id_lote')
                if not lote_actual_res.get('success'):
                    raise Exception(f"No se pudo encontrar el lote ID {lote_id} asociado a la reserva.")

                lote_actual = lote_actual_res['data']
                cantidad_en_lote = lote_actual.get('cantidad_actual', 0)

                if cantidad_en_lote < cantidad_a_despachar:
                    raise Exception(f"Inconsistencia de stock: El lote {lote_actual.get('numero_lote')} no tiene suficiente cantidad para cubrir la reserva.")

                # a. Calcular nueva cantidad y preparar actualización del lote
                nueva_cantidad_lote = cantidad_en_lote - cantidad_a_despachar
                datos_actualizacion_lote = {'cantidad_actual': nueva_cantidad_lote}

                # b. Si el lote se agota, cambiar su estado
                if nueva_cantidad_lote <= 0:
                    datos_actualizacion_lote['estado'] = 'AGOTADO'
                    logger.info(f"El lote {lote_actual.get('numero_lote')} ha sido AGOTADO por el despacho del pedido {pedido_id}.")

                # c. Actualizar el lote
                self.model.update(lote_id, datos_actualizacion_lote, 'id_lote')

                # d. Actualizar la reserva a 'COMPLETADO'
                self.reserva_model.update(reserva['id'], {'estado': 'COMPLETADO'}, 'id')
                logger.info(f"Reserva {reserva['id']} para el pedido {pedido_id} marcada como COMPLETADA.")

            return {'success': True, 'message': 'Stock reservado despachado correctamente.'}

        except Exception as e:
            logger.error(f"Error crítico al despachar stock reservado del pedido {pedido_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def obtener_conteo_vencimientos(self) -> int:
            """Obtiene el conteo de lotes de productos próximos a vencer (crítico)."""
            try:
                # Obtener el umbral de días de la configuración
                dias_alerta = self.config_controller.obtener_dias_vencimiento() # <--- MODIFICADO

                # Llama al método del modelo que busca lotes por vencer en el número de días configurado
                vencimiento_result = self.model.find_por_vencimiento(dias_alerta)

                if vencimiento_result.get('success'):
                    return len(vencimiento_result.get('data', []))
                return 0
            except Exception as e:
                logger.error(f"Error contando alertas de vencimiento de producto: {str(e)}")
                return 0

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