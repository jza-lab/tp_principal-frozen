from uuid import UUID
from app.controllers.base_controller import BaseController
from app.models.inventario import InventarioModel
from app.models.insumo import InsumoModel
#from app.services.stock_service import StockService
from app.schemas.inventario_schema import InsumosInventarioSchema
from typing import Dict, Optional
import logging
from decimal import Decimal
from datetime import datetime, date
from marshmallow import ValidationError


logger = logging.getLogger(__name__)

class InventarioController(BaseController):
    """Controlador para operaciones de inventario"""

    def __init__(self):
        super().__init__()
        self.inventario_model = InventarioModel()
        self.insumo_model = InsumoModel()
        #self.stock_service = StockService()
        self.schema = InsumosInventarioSchema()

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

    def crear_lote(self, data: Dict) -> tuple:
        """Crear un nuevo lote de inventario"""
        try:
            # Validar datos
            validated_data = self.schema.load(data)

            # Verificar que el insumo existe
            insumo_result = self.insumo_model.find_by_id(str(validated_data['id_insumo']), 'id_insumo')
            if not insumo_result['success']:
                return self.error_response('El insumo especificado no existe', 404)

            # Crear lote
            result = self.inventario_model.create(validated_data)

            if result['success']:
                logger.info(f"Lote creado exitosamente: {result['data']['id_lote']}")

                # ✅ Serializar los datos correctamente
                serialized_data = self._serialize_data(result['data'])

                # Evaluar alertas después de crear
                if hasattr(self, 'stock_service'):
                    self.stock_service.evaluar_alertas_insumo(validated_data['id_insumo'])

                return self.success_response(
                    data=serialized_data,
                    message='Lote creado exitosamente',
                    status_code=201
                )
            else:
                return self.error_response(result['error'])

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

                # Si se actualizó la cantidad, evaluar alertas de stock
                if 'cantidad_actual' in datos_actualizacion:
                    if hasattr(self, 'stock_service') and self.stock_service:
                        self.stock_service.evaluar_alertas_insumo(lote_actual['id_insumo'])

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
            # Obtener alertas de stock bajo
            stock_result = self.inventario_model.obtener_stock_consolidado({'estado_stock': 'BAJO'})

            # Obtener alertas de vencimiento
            vencimiento_result = self.inventario_model.obtener_por_vencimiento(7)

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