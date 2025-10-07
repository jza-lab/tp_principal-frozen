import logging
import re
from app.controllers.base_controller import BaseController
from app.controllers.receta_controller import RecetaController
from app.models.producto import ProductoModel
from app.models.receta import RecetaModel
from app.schemas.producto_schema import ProductoSchema
from typing import Dict, Optional, List
from marshmallow import ValidationError

logger = logging.getLogger(__name__)

class ProductoController(BaseController):
    """
    Controlador para la lógica de negocio de los productos.
    Delega la gestión de recetas al RecetaController.
    """

    def __init__(self):
        super().__init__()
        self.model = ProductoModel()
        self.schema = ProductoSchema()
        self.receta_controller = RecetaController()
        self.receta_model = RecetaModel()

    def _abrev(self, texto, length=4):
        """Devuelve una abreviación de la cadena, solo letras, en mayúsculas."""
        if not texto:
            return "X" * length
        texto = re.sub(r'[^A-Za-z]', '', texto)
        return texto.upper()[:length].ljust(length, "X")

    def _generar_codigo_producto(self, nombre_producto: str) -> str:
        """Genera un código de producto único con el formato PROD-XXXX-YYYY."""
        # 1. Generar la base del código
        nombre_abrev = self._abrev(nombre_producto)
        base_codigo = f"PROD-{nombre_abrev}"

        # 2. Encontrar el último código con esa base para determinar el sufijo numérico
        last_producto_result = self.model.find_last_by_base_codigo(base_codigo)
        
        nuevo_sufijo_num = 1
        if last_producto_result.get('success') and last_producto_result.get('data'):
            ultimo_codigo = last_producto_result['data']['codigo']
            try:
                # Extraer el último número del código
                ultimo_num = int(ultimo_codigo.split('-')[-1])
                nuevo_sufijo_num = ultimo_num + 1
            except (ValueError, IndexError):
                # Si el formato no es el esperado, se inicia desde 1
                pass
        
        # 3. Formatear el nuevo código con ceros a la izquierda
        return f"{base_codigo}-{str(nuevo_sufijo_num).zfill(4)}"

    def crear_producto(self, data: Dict) -> Dict:
        """Valida y crea un nuevo producto, su receta y los ingredientes asociados."""
        try:
            # Generar código si no se proporciona
            if not data.get('codigo'):
                data['codigo'] = self._generar_codigo_producto(data.get('nombre', ''))

            receta_items = data.pop('receta_items', [])
            validated_data = self.schema.load(data)

            if self.model.find_by_codigo(validated_data['codigo']).get('data'):
                return self.error_response('El código del producto ya está en uso.', 409)

            result_producto = self.model.create(validated_data)
            if not result_producto.get('success'):
                return self.error_response(result_producto.get('error', 'Error al crear el producto.'))

            producto_creado = result_producto['data']
            producto_id = producto_creado['id']

            receta_data = {
                'nombre': f"Receta para {producto_creado['nombre']}",
                'version': '1.0',
                'producto_id': producto_id
            }
            result_receta = self.receta_model.create(receta_data)

            if not result_receta.get('success'):
                self.model.delete(producto_id, 'id') # Rollback manual
                return self.error_response(result_receta.get('error', 'Error al crear la receta para el producto.'), 500)
            
            receta_creada = result_receta['data']
            receta_id = receta_creada['id']

            if receta_items:
                gestion_result = self.receta_controller.gestionar_ingredientes_para_receta(receta_id, receta_items)
                if not gestion_result.get('success'):
                    self.receta_model.delete(receta_id, 'id')
                    self.model.delete(producto_id, 'id')
                    return self.error_response(gestion_result.get('error', 'Error al crear los ingredientes.'), 500)

            return self.success_response(producto_creado, "Producto creado con éxito", 201)

        except ValidationError as e:
            return self.error_response(f"Datos inválidos: {e.messages}", 422)
        except Exception as e:
            logger.error(f"Error en crear_producto: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def actualizar_producto(self, producto_id: int, data: Dict) -> Dict:
        """Actualiza un producto existente y su receta."""
        try:
            receta_items = data.pop('receta_items', None)
            validated_data = self.schema.load(data, partial=True)

            if 'codigo' in validated_data and validated_data['codigo'] != self.model.find_by_id(producto_id, 'id')['data']['codigo']:
                 return self.error_response('El código de un producto no se puede modificar.', 400)

            result_producto = self.model.update(producto_id, validated_data, 'id')
            if not result_producto.get('success'):
                 return self.error_response(result_producto.get('error', 'Error al actualizar el producto.'))

            receta_existente = self.receta_model.find_all({'producto_id': producto_id})
            receta_id = None
            if receta_existente.get('success') and receta_existente.get('data'):
                receta_id = receta_existente['data'][0]['id']
            else:
                receta_data = {
                    'nombre': f"Receta para {result_producto['data']['nombre']}",
                    'version': '1.0',
                    'producto_id': producto_id
                }
                result_receta = self.receta_model.create(receta_data)
                if not result_receta.get('success'):
                    return self.error_response('Error al crear la receta para el producto actualizado.', 500)
                receta_id = result_receta['data']['id']
            
            if receta_items is not None:
                gestion_result = self.receta_controller.gestionar_ingredientes_para_receta(receta_id, receta_items)
                if not gestion_result.get('success'):
                    return self.error_response(gestion_result.get('error', 'Error al actualizar la receta.'), 500)
            
            return self.success_response(result_producto.get('data'), "Producto actualizado con éxito")

        except ValidationError as e:
            return self.error_response(f"Datos inválidos: {e.messages}", 422)
        except Exception as e:
            logger.error(f"Error en actualizar_producto: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def obtener_producto_por_id(self, producto_id: int) -> Optional[Dict]:
        """Obtiene un producto por su ID."""
        result = self.model.find_by_id(producto_id, 'id')
        return result.get('data')

    def obtener_todos_los_productos(self, filtros: Optional[Dict] = None) -> List[Dict]:
        """Obtiene una lista de todos los productos."""
        try:
            filtros = filtros or {}
            result = self.model.find_all(filtros)
            if not result['success']:
                return self.error_response(result['error'])
            datos = result['data']
            sorted_data = sorted(datos, key=lambda x: x.get('activo', False), reverse=True)
            serialized_data = self.schema.dump(sorted_data, many=True)
            return self.success_response(data=serialized_data)
        except Exception as e:
            return self.error_response(f'Error interno', 500)

    def eliminar_producto_logico(self, producto_id: int) -> Dict:
        """Desactiva un producto (eliminación lógica)."""
        try:
            data = {'activo': False}
            result = self.model.update(producto_id, data, 'id')
            if result['success']:
                return self.success_response(message="Producto desactivado correctamente.")
            else:
                return self.error_response(result['error'])
        except Exception as e:
            logger.error(f"Error eliminando producto: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def habilitar_producto(self, producto_id: int) -> Dict:
        """Reactiva un producto."""
        try:
            data = {'activo': True}
            result = self.model.update(producto_id, data, 'id')
            if result['success']:
                return self.success_response(message="Producto activado correctamente.")
            else:
                return self.error_response(result['error'])
        except Exception as e:
            logger.error(f"Error habilitando producto: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)