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
            # Aplicar filtros por defecto
            filtros = filtros or {}

            # Determinar la fuente de los datos
            if filtros.get('busqueda'):
                result = self.insumo_model.buscar_texto(filtros['busqueda'])
            else:
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
        """Obtener un insumo específico por ID"""
        try:
            result = self.insumo_model.find_by_id(id_insumo, 'id_insumo')

            if result['success']:
                return self.success_response(
                    data=self.schema.dump(result['data'])
                )
            else:
                return self.error_response(result['error'], 404)

        except Exception as e:
            logger.error(f"Error obteniendo insumo por ID: {str(e)}")
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