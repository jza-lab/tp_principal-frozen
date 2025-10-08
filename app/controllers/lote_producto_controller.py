# app/controllers/lote_producto_controller.py
import logging
from app.controllers.base_controller import BaseController
from app.models.lote_producto import LoteProductoModel
from app.models.producto import ProductoModel
from app.schemas.lote_producto_schema import LoteProductoSchema
from typing import Dict, Optional
from marshmallow import ValidationError
from datetime import datetime

logger = logging.getLogger(__name__)

class LoteProductoController(BaseController):
    """
    Controlador para la gestión de lotes de productos.
    """

    def __init__(self):
        super().__init__()
        self.model = LoteProductoModel()
        self.producto_model = ProductoModel()
        self.schema = LoteProductoSchema()

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