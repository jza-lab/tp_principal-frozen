from datetime import datetime, date
import logging
import re
from app.controllers.base_controller import BaseController
from app.controllers.receta_controller import RecetaController
from app.controllers.registro_controller import RegistroController
from flask_jwt_extended import get_current_user
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
        self.registro_controller = RegistroController()

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

    def obtener_categorias_distintas(self) -> tuple:
            """Obtener una lista de todas las categorías de productos únicas."""
            try:
                result = self.model.get_distinct_categories()
                if result['success']:
                    return self.success_response(data=result['data'])
                else:
                    return self.error_response(result['error'])
            except Exception as e:
                logger.error(f"Error obteniendo categorías de productos: {str(e)}")
                return self.error_response(f'Error interno: {str(e)}', 500)


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

            detalle = f"Se creó el producto '{producto_creado['nombre']}' (ID: {producto_id})."
            self.registro_controller.crear_registro(get_current_user(), 'Productos', 'Creación', detalle)

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
            
            validated_data['updated_at'] = datetime.now().isoformat()
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

            producto_actualizado = result_producto.get('data')
            detalle = f"Se actualizó el producto '{producto_actualizado['nombre']}' (ID: {producto_id})."
            self.registro_controller.crear_registro(get_current_user(), 'Productos', 'Actualización', detalle)
            
            return self.success_response(producto_actualizado, "Producto actualizado con éxito")

        except ValidationError as e:
            return self.error_response(f"Datos inválidos: {e.messages}", 422)
        except Exception as e:
            logger.error(f"Error en actualizar_producto: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def actualizar_costo_productos_insumo(self, insumos_id: Optional[Dict]) -> Dict:
        """Actualiza el costo de todos los productos que contienen los insumos dados."""
        try:

            productos_a_actualizar = set()
            
            # 1. Recorrer los insumos actualizados y recopilar todos los productos afectados.
            for insumo in insumos_id:
                insumo_id = insumo.get('id_insumo')
                if not insumo_id:
                    continue
                
                # Buscar todas las recetas que usan este insumo
                recetas_result = self.receta_model.find_all_recetas_by_insumo(insumo_id)
                

                if recetas_result.get('success') and recetas_result.get('data'):
                    recetas = recetas_result['data']
                    # Agrega los IDs de los productos a un conjunto (set) para asegurar unicidad
                    for receta in recetas:
                        if 'producto_id' in receta:
                            productos_a_actualizar.add(receta['producto_id'])

            productos_actualizados = []
            
            # 2. Iterar sobre el CONJUNTO único de productos afectados y actualizarlos solo una vez.
            for producto_id in productos_a_actualizar:
                costo_update_result, status = self.actualizar_costo_producto(producto_id)
                if costo_update_result.get('success'):
                    productos_actualizados.append(producto_id)
                else:
                    logger.error(f"Error actualizando costo para producto ID {producto_id}: {costo_update_result.get('error')}")

            return self.success_response(
                {'productos_actualizados': productos_actualizados},
                f"Costos actualizados para {len(productos_actualizados)} productos."
            )
            
        except Exception as e:
            logger.error(f"Error en actualizar_costo_productos_insumo: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)
        
    def actualizar_costo_producto(self, producto_id: int) -> Dict:
        """Actualiza el costo del producto basado en su receta."""
        try:
            receta_existente = self.receta_model.find_all({'producto_id': producto_id})

            if not (receta_existente.get('success') and receta_existente.get('data')):
                return self.error_response('El producto no tiene una receta asociada.', 400)
            
            receta_id = receta_existente['data'][0]['id']

            costo_result = self.receta_controller.calcular_costo_total_receta(receta_id)

            if not costo_result.get('success'):
                return self.error_response(costo_result.get('error', 'Error al calcular el costo de la receta.'), 500)
            
            producto = self.obtener_producto_por_id(producto_id)
            if not producto:
                return self.error_response('Producto no encontrado.', 404)
            
            nuevo_costo_base = costo_result['data']['costo_total']
            
            porcentaje_margen = producto.get('porcentaje_extra', 0) / 100
            costo_con_margen = nuevo_costo_base * (1 + porcentaje_margen)

            factor_iva = 1.21 if producto.get('iva') else 1.0
            
            nuevo_costo = round(costo_con_margen * factor_iva, 2)
            
            update_result = self.model.update(producto_id, {'precio_unitario': nuevo_costo}, 'id')

            if not update_result.get('success'):
                return self.error_response(update_result.get('error', 'Error al actualizar el costo del producto.'), 500)
            
            return self.success_response(update_result.get('data'), "Costo del producto actualizado con éxito")
        
        except Exception as e:
            logger.error(f"Error en actualizar_costo_producto: {e}", exc_info=True)
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
            return self.success_response(data=sorted_data)
        except Exception as e:
            return self.error_response(f'Error interno', 500)

    def eliminar_producto_logico(self, producto_id: int) -> Dict:
        """Desactiva un producto (eliminación lógica)."""
        try:
            data = {'activo': False}
            result = self.model.update(producto_id, data, 'id')
            if result['success']:
                producto_eliminado = result.get('data')
                detalle = f"Se eliminó lógicamente el producto '{producto_eliminado['nombre']}' (ID: {producto_id})."
                self.registro_controller.crear_registro(get_current_user(), 'Productos', 'Eliminación Lógica', detalle)
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
                producto_habilitado = result.get('data')
                detalle = f"Se habilitó el producto '{producto_habilitado['nombre']}' (ID: {producto_id})."
                self.registro_controller.crear_registro(get_current_user(), 'Productos', 'Habilitación', detalle)
                return self.success_response(message="Producto activado correctamente.")
            else:
                return self.error_response(result['error'])
        except Exception as e:
            logger.error(f"Error habilitando producto: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def actualizar_stock_min_produccion(self, producto_id: int, stock_min: int) -> tuple:
        """
        Actualiza el stock mínimo de producción para un producto específico.
        """
        try:
            # Validar que el stock_min sea un número entero no negativo
            if not isinstance(stock_min, int) or stock_min < 0:
                return self.error_response("El stock mínimo debe ser un número entero no negativo.", 400)

            # Preparar los datos para la actualización
            update_data = {'stock_min_produccion': stock_min}

            # Llamar al método de actualización del modelo
            result = self.model.update(producto_id, update_data, 'id')

            if result.get('success'):
                return self.success_response(result.get('data'), "Stock mínimo actualizado correctamente.", 200)
            else:
                return self.error_response(result.get('error', 'Error desconocido al actualizar.'), 500)

        except Exception as e:
            logger.error(f"Error en actualizar_stock_min_produccion: {str(e)}", exc_info=True)
            return self.error_response('Error interno del servidor.', 500)

    def actualizar_cantidad_maxima_x_pedido(self, producto_id: int, cantidad_maxima: int) -> tuple:
        """
        Actualiza la cantidad máxima por pedido para un producto específico.
        """
        try:
            if not isinstance(cantidad_maxima, int) or cantidad_maxima < 0:
                return self.error_response("La cantidad máxima debe ser un número entero no negativo.", 400)

            update_data = {'cantidad_maxima_x_pedido': cantidad_maxima}

            result = self.model.update(producto_id, update_data, 'id')

            if result.get('success'):
                return self.success_response(result.get('data'), "Cantidad máxima por pedido actualizada correctamente.", 200)
            else:
                return self.error_response(result.get('error', 'Error desconocido al actualizar.'), 500)

        except Exception as e:
            logger.error(f"Error en actualizar_cantidad_maxima_x_pedido: {str(e)}", exc_info=True)
            return self.error_response('Error interno del servidor.', 500)