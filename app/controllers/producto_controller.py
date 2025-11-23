from datetime import datetime, date
import logging
import re
from app.controllers.base_controller import BaseController
from app.controllers.receta_controller import RecetaController
from app.controllers.registro_controller import RegistroController
from app.controllers.costo_fijo_controller import CostoFijoController
from app.controllers.configuracion_produccion_controller import ConfiguracionProduccionController
from app.controllers.rol_controller import RolController
from flask_jwt_extended import get_current_user
from app.models.producto import ProductoModel
from app.models.receta import RecetaModel
from app.schemas.producto_schema import ProductoSchema
from typing import Dict, Optional, List
from marshmallow import ValidationError
from decimal import Decimal, InvalidOperation
from app.models.operacion_receta_model import OperacionRecetaModel

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
        self.operacion_receta_model = OperacionRecetaModel()
        self.costo_fijo_controller = CostoFijoController()
        self.config_produccion_controller = ConfiguracionProduccionController()
        self.rol_controller = RolController()

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
            if not data.get('codigo'):
                data['codigo'] = self._generar_codigo_producto(data.get('nombre', ''))

            receta_items = data.pop('receta_items', [])
            operaciones_data = data.pop('operaciones', []) # Cambiado de mano_de_obra
            linea_compatible_str = data.pop('linea_compatible', '2')

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
                'producto_id': producto_id,
                'linea_compatible': linea_compatible_str
            }
            result_receta = self.receta_model.create(receta_data)
            if not result_receta.get('success'):
                self.model.delete(producto_id, 'id')
                return self.error_response(result_receta.get('error', 'Error al crear la receta.'), 500)

            receta_id = result_receta['data']['id']

            if receta_items:
                self.receta_controller.gestionar_ingredientes_para_receta(receta_id, receta_items)

            if operaciones_data:
                self.receta_controller.gestionar_operaciones_para_receta(receta_id, operaciones_data)

            # Recalcular todos los costos
            self._recalcular_costos_producto(producto_id)

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
            operaciones_data = data.pop('operaciones', None) # Cambiado de mano_de_obra
            validated_data = self.schema.load(data, partial=True)

            if 'codigo' in validated_data and validated_data['codigo'] != self.model.find_by_id(producto_id, 'id')['data']['codigo']:
                 return self.error_response('El código de un producto no se puede modificar.', 400)

            validated_data['updated_at'] = datetime.now().isoformat()
            result_producto = self.model.update(producto_id, validated_data, 'id')
            if not result_producto.get('success'):
                 return self.error_response(result_producto.get('error', 'Error al actualizar el producto.'))

            receta_existente_res = self.receta_model.find_all({'producto_id': producto_id})
            receta_id = receta_existente_res['data'][0]['id'] if receta_existente_res.get('data') else None

            if not receta_id:
                # Si no hay receta, se crea una (caso borde)
                receta_data = {'nombre': f"Receta para {validated_data.get('nombre', '')}", 'producto_id': producto_id}
                receta_nueva_res = self.receta_model.create(receta_data)
                receta_id = receta_nueva_res['data']['id'] if receta_nueva_res.get('success') else None

            if not receta_id:
                return self.error_response('No se pudo encontrar o crear una receta para el producto.', 500)

            if receta_items is not None:
                self.receta_controller.gestionar_ingredientes_para_receta(receta_id, receta_items)

            if operaciones_data is not None:
                self.receta_controller.gestionar_operaciones_para_receta(receta_id, operaciones_data)

            # Siempre recalcular costos al final
            self._recalcular_costos_producto(producto_id)

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

    def _recalcular_costos_producto(self, producto_id: int) -> Dict:
        """
        Orquestador central para calcular todos los costos de un producto y actualizar la DB.
        """
        try:
            # 1. Obtener datos base
            producto_res = self.model.find_by_id(producto_id, 'id')
            if not producto_res.get('success'): return producto_res
            producto = producto_res['data']

            receta_res = self.receta_model.find_all({'producto_id': producto_id})
            if not receta_res.get('data'): return {'success': True, 'message': 'Producto sin receta, no se calculan costos.'}
            receta_id = receta_res['data'][0]['id']

            # 2. Calcular Costo de Materia Prima
            costo_materia_prima_res = self.receta_controller.calcular_costo_total_receta(receta_id)
            costo_materia_prima = costo_materia_prima_res['data']['costo_total'] if costo_materia_prima_res.get('success') else 0

            # 3. Calcular Costo de Mano de Obra basado en Operaciones
            receta_detallada_res, _ = self.receta_controller.obtener_receta_con_ingredientes(receta_id)
            operaciones = receta_detallada_res.get('data', {}).get('operaciones', [])
            
            roles_res, _ = self.rol_controller.get_all_roles()
            roles_data = roles_res.get('data', [])
            roles_costo_map = {rol['id']: Decimal(rol.get('costo_por_hora', 0) or 0) for rol in roles_data}

            costo_mano_obra = Decimal(0)
            total_minutos_mano_obra = Decimal(0)

            for op in operaciones:
                costo_por_minuto_operacion = sum(roles_costo_map.get(rol_id, 0) for rol_id in op.get('roles_asignados', [])) / Decimal(60)
                
                tiempo_prep = Decimal(op.get('tiempo_preparacion', 0))
                tiempo_ejec = Decimal(op.get('tiempo_ejecucion_unitario', 0))
                
                costo_mano_obra += (tiempo_prep + tiempo_ejec) * costo_por_minuto_operacion
                total_minutos_mano_obra += tiempo_prep + tiempo_ejec

            total_horas_mano_obra = total_minutos_mano_obra / Decimal(60)

            # 4. Calcular Costos Fijos
            # Filtramos explícitamente por 'activo': True para asegurarnos de no incluir costos deshabilitados
            costos_fijos_res, _ = self.costo_fijo_controller.get_all_costos_fijos({'activo': True})
            
            # Verificación adicional en Python por si el filtro de base de datos no es estricto
            costos_fijos_activos = [c for c in costos_fijos_res.get('data', []) if c.get('activo') is True]
            
            total_costos_fijos_mensual = sum(Decimal(c.get('monto_mensual', 0)) for c in costos_fijos_activos)

            config_prod_res, _ = self.config_produccion_controller.get_configuracion_produccion()
            horas_prod_config = config_prod_res.get('data', [])
            
            # Asumiendo 4 semanas por mes
            total_horas_prod_mes = sum(Decimal(d.get('horas', 0)) for d in horas_prod_config) * 4
            
            tasa_costo_fijo_por_hora = total_costos_fijos_mensual / total_horas_prod_mes if total_horas_prod_mes > 0 else 0
            costo_fijos_aplicado = tasa_costo_fijo_por_hora * total_horas_mano_obra

            # 5. Calcular Totales y Precio Final
            costo_total_produccion = Decimal(costo_materia_prima) + costo_mano_obra + costo_fijos_aplicado
            
            porcentaje_ganancia = Decimal(producto.get('porcentaje_ganancia', 0) or 0) / Decimal(100)
            precio_sin_iva = costo_total_produccion * (1 + porcentaje_ganancia)
            
            factor_iva = Decimal('1.21') if producto.get('iva') else Decimal('1.0')
            precio_final = precio_sin_iva * factor_iva

            # 6. Actualizar Producto en DB
            update_data = {
                'costo_mano_obra': float(costo_mano_obra),
                'costo_fijos': float(costo_fijos_aplicado),
                'costo_total_produccion': float(costo_total_produccion),
                'precio_unitario': float(precio_final)
            }
            self.model.update(producto_id, update_data, 'id')
            return {'success': True}

        except Exception as e:
            logger.error(f"Error crítico en _recalcular_costos_producto para ID {producto_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def obtener_producto_por_id(self, producto_id: int) -> Dict:
        """
        Obtiene un producto por su ID.
        Devuelve el diccionario de respuesta completo (success, data/error).
        """
        result = self.model.find_by_id(producto_id, 'id')

        # 'result' ya es {'success': True, 'data': ...} o {'success': False, 'error': ...}
        # Simplemente lo devolvemos
        return result

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
                producto_actualizado = result.get('data')
                detalle = f"Se actualizó el stock mínimo de producción para el producto '{producto_actualizado['nombre']}' a {stock_min}."
                self.registro_controller.crear_registro(get_current_user(), 'Alertas Productos', 'Configuración', detalle)
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
                producto_actualizado = result.get('data')
                detalle = f"Se actualizó la cantidad máxima por pedido para el producto '{producto_actualizado['nombre']}' a {cantidad_maxima}."
                self.registro_controller.crear_registro(get_current_user(), 'Alertas Productos', 'Configuración', detalle)
                return self.success_response(result.get('data'), "Cantidad máxima por pedido actualizada correctamente.", 200)
            else:
                return self.error_response(result.get('error', 'Error desconocido al actualizar.'), 500)

        except Exception as e:
            logger.error(f"Error en actualizar_cantidad_maxima_x_pedido: {str(e)}", exc_info=True)
            return self.error_response('Error interno del servidor.', 500)

    def actualizar_cantidad_minima_produccion(self, producto_id: int, cantidad_minima: Decimal) -> tuple:
        """
        Actualiza la cantidad mínima de producción para un producto específico.
        """
        try:
            if not isinstance(cantidad_minima, Decimal) or cantidad_minima < 0:
                return self.error_response("La cantidad mínima debe ser un número no negativo.", 400)

            update_data = {'cantidad_minima_produccion': cantidad_minima}

            result = self.model.update(producto_id, update_data, 'id')

            if result.get('success'):
                producto_actualizado = result.get('data')
                detalle = f"Se actualizó la cantidad mínima de producción para el producto '{producto_actualizado['nombre']}' a {cantidad_minima}."
                self.registro_controller.crear_registro(get_current_user(), 'Alertas Productos', 'Configuración', detalle)
                return self.success_response(result.get('data'), "Cantidad mínima de producción actualizada.", 200)
            else:
                return self.error_response(result.get('error', 'Error desconocido al actualizar.'), 500)

        except Exception as e:
            logger.error(f"Error en actualizar_cantidad_minima_produccion: {str(e)}", exc_info=True)
            return self.error_response('Error interno del servidor.', 500)

    def recalcular_costos_dinamicos(self, operaciones_data: List[Dict]) -> tuple:
        """
        Calcula dinámicamente el costo de mano de obra y los costos fijos aplicados
        basado en los datos de las operaciones de producción, sin guardarlos en la DB.
        """
        try:
            # Calcular Costo de Mano de Obra
            roles_res, _ = self.rol_controller.get_all_roles()
            roles_costo_map = {rol['id']: Decimal(rol.get('costo_por_hora', 0) or 0) for rol in roles_res.get('data', [])}
            
            costo_mano_obra = Decimal(0)
            total_minutos_mano_obra = Decimal(0)

            for op in operaciones_data:
                costo_por_minuto_operacion = sum(roles_costo_map.get(rol_id, 0) for rol_id in op.get('roles', [])) / Decimal(60)
                
                tiempo_prep = Decimal(op.get('tiempo_preparacion', 0))
                tiempo_ejec = Decimal(op.get('tiempo_ejecucion_unitario', 0))
                
                costo_mano_obra += (tiempo_prep + tiempo_ejec) * costo_por_minuto_operacion
                total_minutos_mano_obra += tiempo_prep + tiempo_ejec
            
            total_horas_mano_obra = total_minutos_mano_obra / Decimal(60)

            # Calcular Costos Fijos
            # Filtramos explícitamente por 'activo': True para asegurarnos de no incluir costos deshabilitados
            costos_fijos_res, _ = self.costo_fijo_controller.get_all_costos_fijos({'activo': True})
            
            # Verificación adicional en Python por si el filtro de base de datos no es estricto
            costos_fijos_activos = [c for c in costos_fijos_res.get('data', []) if c.get('activo') is True]
            
            total_costos_fijos_mensual = sum(Decimal(c.get('monto_mensual', 0)) for c in costos_fijos_activos)

            config_prod_res, _ = self.config_produccion_controller.get_configuracion_produccion()
            horas_prod_config = config_prod_res.get('data', [])
            
            total_horas_prod_mes = sum(Decimal(d.get('horas', 0)) for d in horas_prod_config) * 4
            
            tasa_costo_fijo_por_hora = total_costos_fijos_mensual / total_horas_prod_mes if total_horas_prod_mes > 0 else Decimal(0)
            costo_fijos_aplicado = tasa_costo_fijo_por_hora * total_horas_mano_obra

            return self.success_response({
                'costo_mano_obra': float(costo_mano_obra),
                'costo_fijos_aplicado': float(costo_fijos_aplicado)
            })

        except Exception as e:
            logger.error(f"Error en recalcular_costos_dinamicos: {e}", exc_info=True)
            return self.error_response('Error interno del servidor.', 500)