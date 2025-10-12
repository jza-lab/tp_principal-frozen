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
                    data=self.schema.dump(result['data']),  # Marshmallow se encarga
                    message='Insumo creado exitosamente',
                    status_code=201
                )
            else:
                return self.error_response(result['error'])

        except Exception as e:
            logger.error(f"Error creando insumo: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_insumos(self, filtros: Optional[Dict] = None) -> tuple:
        """Obtener lista de insumos con filtros"""
        try:
            filtros = filtros or {}

            # La lógica de búsqueda ahora está unificada en el método find_all del modelo
            result = self.insumo_model.find_all(filtros)

            # Procesar el resultado
            if not result['success']:
                return self.error_response(result['error'])

            # Ordenar la lista: activos primero, luego inactivos
            datos = result['data']
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
            # 1. Obtener los datos del insumo
            insumo_result = self.insumo_model.find_by_id(id_insumo, 'id_insumo')

            if not insumo_result.get('success'):
                return self.error_response(insumo_result.get('error', 'Insumo no encontrado'), 404)

            insumo_data = self.schema.dump(insumo_result['data'])

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
                validated_data['updated_at'] = datetime.now().isoformat()
                logger.info(f"Insumo actualizado exitosamente: {id_insumo}")
                return self.success_response(
                    data=self.schema.dump(result['data']),
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
        Busca insumo por código interno usando el modelo

        Args:
            codigo_interno: Código interno del insumo

        Returns:
            Dict con datos del insumo o None
        """
        try:
            print('SE ESTA BUSCANDO---', codigo_interno)
            return self.insumo_model.buscar_por_codigo_interno(codigo_interno)

        except Exception as e:
            logger.error(f"Error en controlador buscando insumo por código interno: {str(e)}")
            return None

    def actualizar_precio(self, id_insumo: str, precio_nuevo: float) -> bool:
        """
        Actualiza el precio de un insumo usando el modelo

        Args:
            id_insumo: ID del insumo a actualizar
            precio_nuevo: Nuevo precio unitario

        Returns:
            bool: True si se actualizó correctamente, False en caso contrario
        """
        try:
            return self.insumo_model.actualizar_precio(id_insumo, precio_nuevo)

        except Exception as e:
            logger.error(f"Error en controlador actualizando precio: {str(e)}")
            return False

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
        """
        try:
            # 1. Obtener todos los lotes disponibles para el insumo
            lotes_result = self.inventario_model.find_by_insumo(id_insumo, solo_disponibles=True)

            if not lotes_result.get('success'):
                return self.error_response(f"No se pudieron obtener los lotes para el insumo: {lotes_result.get('error')}")

            # 2. Calcular el stock sumando la cantidad actual de cada lote
            total_stock = sum(lote.get('cantidad_actual', 0) for lote in lotes_result.get('data', []))

            # 3. Actualizar el campo stock_actual en la tabla de insumos
            update_data = {'stock_actual': int(total_stock)}
            update_result = self.insumo_model.update(id_insumo, update_data, 'id_insumo')

            if not update_result.get('success'):
                return self.error_response(f"Error al actualizar el stock del insumo: {update_result.get('error')}")

            logger.info(f"Stock actualizado para el insumo {id_insumo}: {total_stock}")

            # 4. Devolver el insumo actualizado
            return self.success_response(
                data=self.schema.dump(update_result['data']),
                message='Stock del insumo actualizado correctamente.'
            )

        except Exception as e:
            logger.error(f"Error actualizando stock de insumo {id_insumo}: {str(e)}")
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)


