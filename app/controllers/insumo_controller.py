from datetime import datetime
import re
from app.controllers.base_controller import BaseController
from app.models.insumo import InsumoModel
from app.models.inventario import InventarioModel
from app.schemas.insumo_schema import InsumosCatalogoSchema
from typing import Dict, Optional
import logging
from app.utils.serializable import safe_serialize
from marshmallow import ValidationError


logger = logging.getLogger(__name__)

class InsumoController(BaseController):
    """Controlador para operaciones de insumos"""

    def __init__(self):
        super().__init__()
        self.insumo_model = InsumoModel()
        self.inventario_model = InventarioModel()
        #self.alertas_service = AlertasService()
        self.schema = InsumosCatalogoSchema()


    def _abrev(self, texto, length=3):
        """Devuelve una abreviación de la cadena, solo letras, en mayúsculas."""
        if not texto:
            return "XXX"
        texto = re.sub(r'[^A-Za-z]', '', texto)
        return texto.upper()[:length].ljust(length, "X")

    def _iniciales(self, texto):
        """Devuelve las iniciales de cada palabra, en mayúsculas."""
        if not texto:
            return "X"
        palabras = re.findall(r'\b\w', texto)
        return ''.join(palabras).upper()

    def _generar_codigo_interno(self, categoria, nombre):
        cat = self._abrev(categoria)
        nom = self._abrev(nombre)
        return f"INS-{cat}-{nom}"


    def crear_insumo(self, data: Dict) -> tuple:
        """Crear un nuevo insumo en el catálogo"""
        try:
            # Validar datos con esquema
            validated_data = self.schema.load(data)

            nombre = validated_data.get('nombre', '').strip().lower()
            existe_nombre = self.insumo_model.find_all({'nombre': nombre})
            if existe_nombre['success'] and existe_nombre['data']:
                return self.error_response('Ya existe un insumo con ese nombre.', 409)

            # Generar código interno si no viene
            if not validated_data.get('codigo_interno'):
                base_codigo = self._generar_codigo_interno(
                    validated_data.get('categoria', ''),
                    validated_data.get('nombre', '')
                )
                codigo = base_codigo
                sufijo = self._iniciales(validated_data.get('nombre', ''))

                intento = 1
                existe = self.insumo_model.find_by_codigo(codigo)
                while existe['success']: #Se repite hasta que no exista ninguno

                    if intento == 1:
                        codigo = f"{base_codigo}-{sufijo}"
                    else:
                        codigo = f"{base_codigo}-{sufijo}{intento}"

                    intento += 1
                    existe = self.insumo_model.find_by_codigo(codigo)

                validated_data['codigo_interno'] = codigo

            # Verificar que no existe código interno duplicado
            if validated_data.get('codigo_interno'):
                existing = self.insumo_model.find_by_codigo(validated_data['codigo_interno'])
                if existing['success']:
                    return self.error_response('El código interno ya existe', 409)

            # Crear en base de datos
            result = self.insumo_model.create(validated_data)

            if result['success']:
                logger.info(f"Insumo creado exitosamente: {result['data']['id_insumo']}")

                return self.success_response(
                    data=result['data'],  # Marshmallow se encarga
                    message='Insumo creado exitosamente',
                    status_code=201
                )
            else:
                return self.error_response(result['error'])

        except Exception as e:
            logger.error(f"Error creando insumo: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_insumos(self, filtros: Optional[Dict] = None) -> tuple:
        """Obtener lista de insumos con filtros, incluyendo filtro por stock bajo."""
        try:
            # Primero, actualizamos el stock de todos los insumos
            self.inventario_model.calcular_y_actualizar_stock_general()
            
            filtros = filtros or {}

            stock_status_filter = filtros.pop('stock_status', None)

            if stock_status_filter == 'bajo':
                # 1. Obtener la lista básica de insumos que están BAJO STOCK
                consolidado_result = self.inventario_model.obtener_stock_consolidado({'estado_stock': 'BAJO'})

                if not consolidado_result['success']:
                    return self.error_response(consolidado_result['error'])

                datos_consolidado = consolidado_result['data']

                # Crear un mapa para acceder rápidamente a los datos de stock calculados (stock_actual, stock_min)
                stock_map = {d['id_insumo']: d for d in datos_consolidado}
                insumo_ids = list(stock_map.keys())

                if not insumo_ids:
                    return self.success_response(data=[])

                # 2. Consultar los datos completos del catálogo con el join de proveedor
                query = self.insumo_model.db.table(self.insumo_model.get_table_name()).select("*, proveedor:id_proveedor(*)").in_('id_insumo', insumo_ids)

                # Aplicar filtros adicionales de búsqueda y categoría
                if filtros.get('busqueda'):
                    search_term = f"%{filtros['busqueda']}%"
                    query = query.or_(f"nombre.ilike.{search_term},codigo_interno.ilike.{search_term}")

                if filtros.get('categoria'):
                    query = query.eq('categoria', filtros['categoria'])

                result = query.execute()

                #Convertir los timestamps a objetos datetime antes de fusionar.
                insumos_completos = self.insumo_model._convert_timestamps(result.data)

                # 3. Fusionar los datos de stock calculados
                datos_finales = []
                for insumo_completo in insumos_completos:
                    stock_data = stock_map.get(insumo_completo['id_insumo'])
                    if stock_data:
                        # Forzar conversión a tipos primitivos (float/int)
                        stock_actual_val = stock_data.get('stock_actual')
                        stock_min_val = stock_data.get('stock_min')

                        insumo_completo['stock_actual'] = float(stock_actual_val) if stock_actual_val is not None else 0.0
                        insumo_completo['stock_min'] = int(stock_min_val) if stock_min_val is not None else 0
                        insumo_completo['estado_stock'] = stock_data.get('estado_stock')
                        datos_finales.append(insumo_completo)

                datos = datos_finales

            else:
                # Lógica existente para obtener todos los insumos con filtros normales
                result = self.insumo_model.find_all(filtros)

                if not result['success']:
                    return self.error_response(result['error'])

                datos = result['data']

            # Ordenar la lista: activos primero, luego inactivos
            sorted_data = sorted(datos, key=lambda x: x.get('activo', False), reverse=True)

            # Serializar y responder
            serialized_data = self.schema.dump(sorted_data, many=True)
            return self.success_response(data=serialized_data)

        except Exception as e:
            logger.error(f"Error obteniendo insumos: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_insumo_por_id(self, id_insumo: str) -> tuple:
        """Obtener un insumo específico por ID, incluyendo sus lotes en inventario."""
        try:
            # 1. Actualizar el stock y obtener los datos más recientes del insumo en una sola operación.
            # Esto evita race conditions y asegura que siempre mostramos la data más fresca.
            response_data, status_code = self.actualizar_stock_insumo(id_insumo)

            # Si la actualización/obtención falla, propagamos el error.
            if status_code >= 400:
                return response_data, status_code

            # Los datos del insumo ya vienen serializados y actualizados.
            insumo_data = response_data.get('data', {})

            # 2. Obtener los lotes asociados
            # Usamos el modelo de inventario que ya está instanciado en el controlador
            lotes_result = self.inventario_model.find_by_insumo(id_insumo, solo_disponibles=False)

            if lotes_result.get('success'):
                # Ordenar lotes por fecha de ingreso descendente para mostrar los más nuevos primero
                lotes_data = sorted(lotes_result['data'], key=lambda x: x.get('f_ingreso', ''), reverse=True)
                insumo_data['lotes'] = lotes_data
            else:
                # Si falla la obtención de lotes, no es un error fatal.
                # Simplemente se mostrará el insumo sin lotes.
                insumo_data['lotes'] = []
                logger.warning(f"No se pudieron obtener los lotes para el insumo {id_insumo}: {lotes_result.get('error')}")

            return self.success_response(data=insumo_data)

        except Exception as e:
            logger.error(f"Error obteniendo insumo por ID con lotes: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def actualizar_insumo(self, id_insumo: str, data: Dict) -> tuple:
        """Actualizar un insumo del catálogo"""
        try:
            # Validar datos parciales
            validated_data = self.schema.load(data, partial=True)

            # Verificar código interno duplicado si se está actualizando
            if validated_data.get('codigo_interno'):
                existing = self.insumo_model.find_by_codigo(validated_data['codigo_interno'])
                if existing['success'] and existing['data']['id_insumo'] != id_insumo:
                    return self.error_response('El código interno ya existe', 409)

            # Actualizar
            result = self.insumo_model.update(id_insumo, validated_data, 'id_insumo')

            if result['success']:

                logger.info(f"Insumo actualizado exitosamente: {id_insumo}")
                return self.success_response(
                    data=result['data'],
                    message='Insumo actualizado exitosamente'
                )
            else:
                return self.error_response(result['error'])

        except ValidationError as e:
            # Re-lanzar la excepción de validación para que la vista la maneje
            # y devuelva un JSON con los detalles del error.
            raise e
        except Exception as e:
            logger.error(f"Error actualizando insumo: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def eliminar_insumo(self, id_insumo: str, forzar_eliminacion: bool = False) -> tuple:
        """Eliminar un insumo del catálogo"""
        try:
            result = self.insumo_model.delete(id_insumo, 'id_insumo', soft_delete=not forzar_eliminacion)

            if result['success']:
                logger.info(f"Insumo eliminado: {id_insumo}")
                return self.success_response(message="Insumo desactivado correctamente.")
            else:
                return self.error_response(result['error'])

        except Exception as e:
            logger.error(f"Error eliminando insumo: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def eliminar_insumo_logico(self, id_insumo: str) -> tuple:
        """Eliminar un insumo del catálogo"""
        try:

            data = {'activo': False}
            result = self.insumo_model.update(id_insumo, data, 'id_insumo')

            if result['success']:
                logger.info(f"Insumo eliminado: {id_insumo}")
                return self.success_response(message="Insumo desactivado correctamente.")
            else:
                return self.error_response(result['error'])

        except Exception as e:
            logger.error(f"Error eliminando insumo: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def habilitar_insumo(self, id_insumo: str) -> tuple:
        """Habilita un insumo del catálogo que fue desactivado."""
        try:
            data = {'activo': True}
            result = self.insumo_model.update(id_insumo, data, 'id_insumo')

            if result.get('success'):
                logger.info(f"Insumo habilitado: {id_insumo}")
                return self.success_response(message='Insumo habilitado exitosamente.')
            else:
                logger.error(f"Fallo al habilitar insumo {id_insumo}: {result.get('error')}")
                return self.error_response(result.get('error', 'Error desconocido al habilitar el insumo.'))

        except Exception as e:
            logger.error(f"Error habilitando insumo: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)


    def obtener_con_stock(self, filtros: Optional[Dict] = None) -> tuple:
        """Obtener insumos con información de stock consolidado"""
        try:
            result = self.inventario_model.obtener_stock_consolidado(filtros)

            if result['success']:
                # Evaluar alertas para cada insumo
                datos_con_alertas = []
                for insumo in result['data']:
                    alertas = self.alertas_service.evaluar_insumo(insumo)
                    insumo['alertas'] = alertas
                    datos_con_alertas.append(insumo)

                return self.success_response(data=datos_con_alertas)
            else:
                return self.error_response(result['error'])

        except Exception as e:
            logger.error(f"Error obteniendo insumos con stock: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_categorias_distintas(self) -> tuple:
        """Obtener una lista de todas las categorías de insumos únicas."""
        try:
            result = self.insumo_model.get_distinct_categories()
            if result['success']:
                return self.success_response(data=result['data'])
            else:
                return self.error_response(result['error'])
        except Exception as e:
            logger.error(f"Error obteniendo insumos: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)


    def buscar_por_codigo_interno(self, codigo_interno: str) -> Optional[Dict]:
        """
        Busca un insumo por su código interno - AHORA CON LOGS
        """
        try:
            logger.info(f"[Controlador] Llamando al modelo para buscar código: {codigo_interno}")

            resultado_del_modelo = self.insumo_model.buscar_por_codigo_interno(codigo_interno)

            # --- LOGS CLAVE ---
            logger.debug(f"[Controlador] Resultado recibido del modelo: {resultado_del_modelo}")
            logger.debug(f"[Controlador] TIPO de resultado del modelo: {type(resultado_del_modelo)}")
            # -------------------

            return resultado_del_modelo

        except Exception as e:
            logger.error(f"Error en controlador buscando insumo por código interno: {str(e)}")
            return None

    def actualizar_precio(self, insumo_id: str, nuevo_precio: float):
        """
        Actualiza el precio unitario de un insumo en el catálogo.
        """
        if nuevo_precio is None or float(nuevo_precio) < 0:
            return self.error_response("El precio proporcionado no es válido.", 400)

        try:
            update_data = {"precio_unitario": float(nuevo_precio)}
            result = self.insumo_model.update(insumo_id, update_data, 'id_insumo')

            if result.get('success'):
                logger.info(f"Precio del insumo {insumo_id} actualizado a {nuevo_precio}.")
                return self.success_response(result['data'], "Precio actualizado correctamente.")
            else:
                logger.error(f"No se pudo actualizar el precio para el insumo {insumo_id}: {result.get('error')}")
                return self.error_response(f"No se pudo actualizar el precio: {result.get('error')}", 500)

        except Exception as e:
            logger.error(f"Error crítico al actualizar el precio del insumo {insumo_id}: {e}", exc_info=True)
            return self.error_response("Error interno del servidor al actualizar el precio.", 500)

    def buscar_por_codigo_proveedor(self, codigo_proveedor: str, proveedor_id: str = None) -> Optional[Dict]:
        """
        Busca insumo por código de proveedor usando el modelo

        Args:
            codigo_proveedor: Código del proveedor
            proveedor_id: ID del proveedor (opcional)

        Returns:
            Dict con datos del insumo o None
        """
        try:
            return self.model.buscar_por_codigo_proveedor(codigo_proveedor, proveedor_id)

        except Exception as e:
            logger.error(f"Error en controlador buscando insumo por código proveedor: {str(e)}")
            return None

    def actualizar_stock_insumo(self, id_insumo: str) -> tuple:
        """
        Calcula y actualiza el stock de un insumo basado en sus lotes en inventario.
        Devuelve el insumo actualizado.
        """
        try:
            # 1. Obtener todos los lotes disponibles para el insumo
            lotes_result = self.inventario_model.find_by_insumo(id_insumo, solo_disponibles=True)

            if not lotes_result.get('success'):
                # Si no se pueden obtener los lotes, devolvemos un error claro.
                return self.error_response(f"No se pudieron obtener los lotes: {lotes_result.get('error')}", 500)

            # 2. Calcular el stock sumando la cantidad actual de cada lote.
            # Si no hay lotes, la suma de una lista vacía es 0, lo cual es correcto.
            total_stock = sum(lote.get('cantidad_actual', 0) for lote in lotes_result.get('data', []))

            # 3. Actualizar el campo stock_actual en la tabla de insumos
            update_data = {'stock_actual': int(total_stock)}
            update_result = self.insumo_model.update(id_insumo, update_data, 'id_insumo')

            if not update_result.get('success'):
                # Si la actualización en la DB falla, devolvemos error.
                return self.error_response(f"Error al actualizar el stock: {update_result.get('error')}", 500)

            logger.info(f"Stock actualizado para el insumo {id_insumo}: {total_stock}")

            # 4. Devolver el insumo actualizado.
            return self.success_response(
                data=update_result['data'],
                message='Stock del insumo actualizado correctamente.'
            )

        except Exception as e:
            logger.error(f"Error crítico actualizando stock de insumo {id_insumo}: {str(e)}")
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)


