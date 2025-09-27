from app.controllers.base_controller import BaseController
from app.models.insumo import InsumoModel
from app.models.inventario import InventarioModel
from app.schemas.insumo_schema import InsumosCatalogoSchema
from typing import Dict, Optional
import logging
from app.utils.serializable import safe_serialize


logger = logging.getLogger(__name__)

class InsumoController(BaseController):
    """Controlador para operaciones de insumos"""

    def __init__(self):
        super().__init__()
        self.insumo_model = InsumoModel()
        self.inventario_model = InventarioModel()
        #self.alertas_service = AlertasService()
        self.schema = InsumosCatalogoSchema()

    def crear_insumo(self, data: Dict) -> tuple:
        """Crear un nuevo insumo en el catálogo"""
        try:
            # Validar datos con esquema
            validated_data = self.schema.load(data)

            # Verificar que no existe código interno duplicado
            if validated_data.get('codigo_interno'):
                existing = self.insumo_model.find_by_codigo(validated_data['codigo_interno'])
                if existing['success']:
                    return self.error_response('El código interno ya existe', 409)

            # Crear en base de datos
            result = self.insumo_model.create(validated_data)

            if result['success']:
                logger.info(f"Insumo creado exitosamente: {result['data']['id_insumo']}")

                # ✅ SIMPLIFICADO: El esquema ya maneja la serialización
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
            if 'activo' not in filtros:
                filtros['activo'] = True

            # Buscar en base de datos
            if filtros.get('busqueda'):
                result = self.insumo_model.buscar_texto(filtros['busqueda'])
            else:
                result = self.insumo_model.find_all(filtros)

            if result['success']:
                # ✅ CORREGIDO: Serializar los datos correctamente
                serialized_data = self.schema.dump(result['data'], many=True)
                return self.success_response(data=serialized_data)
            else:
                return self.error_response(result['error'])

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

        except Exception as e:
            logger.error(f"Error actualizando insumo: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def eliminar_insumo(self, id_insumo: str, forzar_eliminacion: bool = False) -> tuple:
        """Eliminar un insumo del catálogo"""
        try:
            result = self.insumo_model.delete(id_insumo, 'id_insumo', soft_delete=not forzar_eliminacion)

            if result['success']:
                logger.info(f"Insumo eliminado: {id_insumo}")
                return self.success_response(message=result['message'])
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
                return self.success_response(message=result['message'])
            else:
                return self.error_response(result['error'])

        except Exception as e:
            logger.error(f"Error eliminando insumo: {str(e)}")
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