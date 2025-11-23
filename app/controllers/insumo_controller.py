from datetime import datetime
import re
from app.controllers.base_controller import BaseController
from app.controllers.registro_controller import RegistroController
from app.models.insumo import InsumoModel
from app.models.inventario import InventarioModel
from flask_jwt_extended import get_current_user
from app.schemas.insumo_schema import InsumosCatalogoSchema
from typing import Dict, Optional, List
import logging
from app.utils.serializable import safe_serialize
from marshmallow import ValidationError
import math
from app.models.proveedor import ProveedorModel
from datetime import date


logger = logging.getLogger(__name__)

class InsumoController(BaseController):
    """Controlador para operaciones de insumos"""

    def __init__(self):
        super().__init__()
        self.insumo_model = InsumoModel()
        self.inventario_model = InventarioModel()
        #self.alertas_service = AlertasService()
        self.schema = InsumosCatalogoSchema()
        self.registro_controller = RegistroController()


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
                insumo_data = result['data']
                detalle = f"Se creó el insumo '{insumo_data['nombre']}' (ID: {insumo_data['id_insumo']})."
                self.registro_controller.crear_registro(get_current_user(), 'Insumos', 'Creación', detalle)
                logger.info(f"Insumo creado exitosamente: {insumo_data['id_insumo']}")

                return self.success_response(
                    data=insumo_data,
                    message='Insumo creado exitosamente',
                    status_code=201
                )
            else:
                return self.error_response(result['error'])

        except ValidationError as e:
            logger.warning(f"Error de validación al crear insumo: {e.messages}")
            return self.error_response(f"Datos inválidos: {e.messages}", 422)
        except Exception as e:
            logger.error(f"Error creando insumo: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_insumos(self, filtros: Optional[Dict] = None) -> tuple:
        """Obtener lista de insumos con filtros, incluyendo filtro por stock bajo y ordenamiento."""
        try:
            self.inventario_model.calcular_y_actualizar_stock_general()
            self._revisar_y_generar_ocs_automaticas()
            
            filtros = filtros or {}
            stock_status_filter = filtros.pop('stock_status', None)
            sort_by = filtros.pop('sort_by', 'nombre')
            order = filtros.pop('order', 'asc')

            # Primero, obtenemos todos los insumos (o los filtrados por otros criterios)
            result = self.insumo_model.find_all(filtros)
            if not result['success']:
                return self.error_response(result['error'])
            
            all_insumos = result['data']
            final_data = []

            # --- LÓGICA DE FILTRADO LOCALIZADA ---
            if stock_status_filter == 'bajo':
                for insumo in all_insumos:
                    try:
                        stock_actual = float(insumo.get('stock_actual') or 0.0)
                        stock_min = float(insumo.get('stock_min') or 0.0)
                        if stock_min > 0 and stock_actual < stock_min:
                            final_data.append(insumo)
                    except (ValueError, TypeError):
                        # Ignorar insumos con datos de stock no válidos en el filtro
                        continue
            else:
                # Si no hay filtro de stock, usar todos los datos
                final_data = all_insumos

            # --- LÓGICA DE ORDENAMIENTO ---
            # Separar activos e inactivos (Regla: Inactivos siempre al final)
            active_items = [i for i in final_data if i.get('activo')]
            inactive_items = [i for i in final_data if not i.get('activo')]
            
            def get_sort_key(item):
                val = item.get(sort_by)
                if val is None: 
                    # Manejo de nulos: 0 para números, string vacía para texto
                    return 0 if sort_by != 'nombre' else '' 
                if isinstance(val, str): 
                    return val.lower()
                return val
            
            reverse_sort = (order == 'desc')
            
            active_items.sort(key=get_sort_key, reverse=reverse_sort)
            inactive_items.sort(key=get_sort_key, reverse=reverse_sort)
            
            sorted_data = active_items + inactive_items
            
            serialized_data = self.schema.dump(sorted_data, many=True)
            return self.success_response(data=serialized_data)

        except Exception as e:
            logger.error(f"Error obteniendo insumos (con filtro localizado): {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_insumo_por_id(self, id_insumo: str) -> tuple:
        """Obtener un insumo específico por ID, incluyendo sus lotes en inventario."""
        try:
            # 1. Actualizar el stock y obtener los datos más recientes del insumo en una sola operación.
            response_data, status_code = self.actualizar_stock_insumo(id_insumo)

            # Si la actualización/obtención falla, propagamos el error.
            if status_code >= 400:
                return response_data, status_code

            # Los datos del insumo ya vienen serializados y actualizados.
            insumo_data = response_data.get('data', {})

            # 2. Obtener los lotes asociados
            lotes_result = self.inventario_model.find_by_insumo(id_insumo, solo_disponibles=False)

            if lotes_result.get('success'):
                # Ordenar lotes por fecha de ingreso descendente para mostrar los más nuevos primero
                lotes_data = sorted(lotes_result['data'], key=lambda x: x.get('f_ingreso', ''), reverse=True)
                insumo_data['lotes'] = lotes_data
            else:
                insumo_data['lotes'] = []
                logger.warning(f"No se pudieron obtener los lotes para el insumo {id_insumo}: {lotes_result.get('error')}")

            return self.success_response(data=insumo_data)

        except Exception as e:
            logger.error(f"Error obteniendo insumo por ID con lotes: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_stock_de_insumos_por_ids(self, ids_insumos: List[str]) -> tuple:
        """
        Obtiene el stock actual para una lista de IDs de insumos en una sola consulta.
        Es una versión optimizada para operaciones masivas.
        """
        if not ids_insumos:
            return self.success_response(data=[])

        try:
            # Seleccionar solo los campos necesarios para optimizar la consulta
            result = self.insumo_model.find_all(
                filters={'id_insumo': ids_insumos},
                select_columns=['id_insumo', 'stock_actual', 'nombre']
            )

            if result.get('success'):
                return self.success_response(data=result.get('data', []))
            else:
                logger.error(f"Error al obtener stock masivo de insumos: {result.get('error')}")
                return self.error_response(f"Error en BD: {result.get('error')}", 500)

        except Exception as e:
            logger.error(f"Error crítico en obtener_stock_de_insumos_por_ids: {e}", exc_info=True)
            return self.error_response(f"Error interno del servidor: {str(e)}", 500)


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
                insumo_data = result['data']
                
                # Registro general de actualización
                detalle_general = f"Se actualizó el insumo '{insumo_data['nombre']}' (ID: {id_insumo})."
                self.registro_controller.crear_registro(get_current_user(), 'Insumos', 'Actualización', detalle_general)

                # Registros específicos para umbrales de stock
                if 'stock_min' in validated_data:
                    detalle_stock_min = f"Se actualizó el stock mínimo para el insumo '{insumo_data['nombre']}' a {validated_data['stock_min']}."
                    self.registro_controller.crear_registro(get_current_user(), 'Alertas Insumos', 'Configuración', detalle_stock_min)
                
                if 'stock_max' in validated_data:
                    detalle_stock_max = f"Se actualizó el stock máximo para el insumo '{insumo_data['nombre']}' a {validated_data['stock_max']}."
                    self.registro_controller.crear_registro(get_current_user(), 'Alertas Insumos', 'Configuración', detalle_stock_max)

                logger.info(f"Insumo actualizado exitosamente: {id_insumo}")
                return self.success_response(
                    data=insumo_data,
                    message='Insumo actualizado exitosamente'
                )
            else:
                return self.error_response(result['error'])

        except ValidationError as e:
            raise e
        except Exception as e:
            logger.error(f"Error actualizando insumo: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def eliminar_insumo(self, id_insumo: str, forzar_eliminacion: bool = False) -> tuple:
        """Eliminar un insumo del catálogo"""
        try:
            # Obtener datos del insumo para el log ANTES de eliminarlo
            insumo_para_log = self.insumo_model.find_by_id(id_insumo, 'id_insumo')
            
            result = self.insumo_model.delete(id_insumo, 'id_insumo', soft_delete=not forzar_eliminacion)

            if result['success']:
                # Crear el registro si la eliminación fue exitosa
                if insumo_para_log.get('success') and insumo_para_log.get('data'):
                    insumo_data = insumo_para_log['data']
                    accion = 'Eliminación Lógica' if not forzar_eliminacion else 'Eliminación Física'
                    detalle = f"Se eliminó ({'lógica' if not forzar_eliminacion else 'física'}mente) el insumo '{insumo_data['nombre']}' (ID: {id_insumo})."
                    self.registro_controller.crear_registro(get_current_user(), 'Insumos', accion, detalle)

                logger.info(f"Insumo eliminado: {id_insumo}")
                
                message = "Insumo desactivado correctamente." if not forzar_eliminacion else "Insumo eliminado físicamente."
                return self.success_response(message=message)
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
                insumo_data = result['data']
                detalle = f"Se eliminó lógicamente el insumo '{insumo_data['nombre']}' (ID: {id_insumo})."
                self.registro_controller.crear_registro(get_current_user(), 'Insumos', 'Eliminación Lógica', detalle)
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
                insumo_data = result['data']
                detalle = f"Se habilitó el insumo '{insumo_data['nombre']}' (ID: {id_insumo})."
                self.registro_controller.crear_registro(get_current_user(), 'Insumos', 'Habilitación', detalle)
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

    def obtener_sugerencias_insumos(self, query: str) -> tuple:
        """Obtener una lista de nombres de insumos para sugerencias de autocompletado."""
        try:
            if not query or len(query) < 2:
                return self.success_response(data=[])

            result = self.insumo_model.find_all(
                filters={'busqueda': query},
                select_columns=['nombre'],
                limit=10 
            )

            if result['success']:
                nombres = [insumo['nombre'] for insumo in result['data']]
                return self.success_response(data=nombres)
            else:
                return self.error_response(result['error'])
        except Exception as e:
            logger.error(f"Error obteniendo sugerencias de insumos: {str(e)}")
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
        """
        try:
            return self.model.buscar_por_codigo_proveedor(codigo_proveedor, proveedor_id)

        except Exception as e:
            logger.error(f"Error en controlador buscando insumo por código proveedor: {str(e)}")
            return None

    def actualizar_stock_insumo(self, id_insumo: str) -> tuple:
        """
        Calcula y actualiza el stock disponible (actual) de un insumo basado en
        la disponibilidad real de sus lotes (físico - reservado).
        """
        try:
            from app.controllers.inventario_controller import InventarioController
            inventario_controller = InventarioController()
            
            lotes_con_disponibilidad = inventario_controller._obtener_lotes_con_disponibilidad(id_insumo)
            
            stock_disponible_total = sum(lote['disponibilidad'] for lote in lotes_con_disponibilidad)

            # Actualizar el campo stock_actual en la tabla de insumos
            update_data = {'stock_actual': stock_disponible_total}
            update_result = self.insumo_model.update(id_insumo, update_data, 'id_insumo')

            if not update_result.get('success'):
                return self.error_response(f"Error al actualizar el stock: {update_result.get('error')}", 500)

            logger.info(f"Stock disponible para el insumo {id_insumo} actualizado a: {stock_disponible_total}")

            # La lógica de reposición automática se mantiene
            self._verificar_y_reponer_stock(update_result['data'])

            return self.success_response(
                data=update_result['data'],
                message='Stock del insumo actualizado correctamente.'
            )

        except Exception as e:
            logger.error(f"Error crítico actualizando stock de insumo {id_insumo}: {str(e)}")
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def _verificar_y_reponer_stock(self, insumo_actualizado: Dict):
        """
        Wrapper que se llama desde 'actualizar_stock_insumo'.
        Verifica si el insumo está bajo stock y, de ser así,
        dispara la lógica de OC para *todo* su proveedor.
        """
        try:
            stock_actual = float(insumo_actualizado.get('stock_actual') or 0)
            stock_min = float(insumo_actualizado.get('stock_min') or 0)
            en_espera = insumo_actualizado.get('en_espera_de_reestock', False)

            if not en_espera and stock_actual < stock_min:
                logger.info(f"Disparador de detalle: Insumo {insumo_actualizado['nombre']} bajo stock. Verificando OC para su proveedor.")
                
                proveedor_id = insumo_actualizado.get('id_proveedor')
                proveedor_default_id = None
                
                # 1. Obtener el ID del proveedor default (PRV-0001)
                default_prov_res = ProveedorModel().get_all(filtros={'codigo': 'PRV-0001'})
                if default_prov_res.get('success') and default_prov_res.get('data'):
                    proveedor_default_id = default_prov_res['data'][0]['id']
                
                if not proveedor_id:
                    if proveedor_default_id:
                        proveedor_id = proveedor_default_id
                    else:
                        logger.error(f"Insumo {insumo_actualizado['nombre']} sin proveedor y no se encontró PRV-0001. No se puede generar OC.")
                        return
                
                # Llamamos a la función centralizada, pasando el ID del proveedor y el ID default
                self._generar_oc_automatica_por_proveedor(proveedor_id, proveedor_default_id)
        
        except Exception as e:
            logger.error(f"Error en _verificar_y_reponer_stock (wrapper) para insumo {insumo_actualizado.get('id_insumo')}: {e}", exc_info=True)

    def _revisar_y_generar_ocs_automaticas(self):
        """
        Método unificado para revisar todos los insumos y generar OCs automáticas.
        """
        try:
            # 1. Obtener el ID del proveedor default (PRV-0001)
            proveedor_default_id = None
            default_prov_res = ProveedorModel().get_all(filtros={'codigo': 'PRV-0001'})
            if default_prov_res.get('success') and default_prov_res.get('data'):
                proveedor_default_id = default_prov_res['data'][0]['id']
            else:
                logger.warning("Disparador automático: No se encontró proveedor 'PRV-0001'. Insumos sin proveedor no se repondrán.")

            # 2. Buscar *todos* los insumos activos que no estén ya en espera
            insumos_a_chequear_result = self.insumo_model.find_all(filters={
                'activo': True, 
                'en_espera_de_reestock': False
            })

            if insumos_a_chequear_result.get('success'):
                insumos_para_revisar = insumos_a_chequear_result.get('data', [])
                proveedores_para_oc = set() # Usamos un 'set' para evitar duplicados

                # 3. Iterar para encontrar *qué proveedores* necesitan una OC
                for insumo in insumos_para_revisar:
                    stock = float(insumo.get('stock_actual') or 0)
                    minimo = float(insumo.get('stock_min') or 0)
                    
                    if stock < minimo:
                        proveedor_id = insumo.get('id_proveedor')
                        if proveedor_id:
                            proveedores_para_oc.add(proveedor_id)
                        elif proveedor_default_id:
                            # Si no tiene proveedor, se asigna al default
                            proveedores_para_oc.add(proveedor_default_id)
                
                # 4. Ahora, para cada proveedor, generar *una* OC
                if proveedores_para_oc:
                    logger.info(f"Disparador automático: Se generarán OCs para {len(proveedores_para_oc)} proveedores.")
                    for prov_id in proveedores_para_oc:
                        # Llamamos a la función refactorizada, pasando el ID default
                        self._generar_oc_automatica_por_proveedor(prov_id, proveedor_default_id)
                
        except Exception as e_auto_oc:
            logger.error(f"Error crítico en el disparador automático de OCs: {e_auto_oc}", exc_info=True)

    def _generar_oc_automatica_por_proveedor(self, proveedor_id: str, default_prov_id: Optional[str]):
        """
        Función central: Genera UNA orden de compra para un proveedor,
        agrupando TODOS sus insumos con bajo stock.
        
        Si proveedor_id == default_prov_id, buscará insumos con ese ID Y también
        insumos con id_proveedor = NULL.
        """
        try:
            logger.info(f"Generando OC automática para Proveedor ID: {proveedor_id} (Default ID: {default_prov_id})")
            proveedor_model = ProveedorModel()

            # 1. Obtener datos del proveedor (para el log)
            prov_data = proveedor_model.find_by_id(proveedor_id)
            proveedor_nombre_logging = f"ID {proveedor_id}"
            if prov_data.get('success'):
                proveedor_nombre_logging = prov_data['data'].get('nombre', proveedor_nombre_logging)

            # 2. Determinar el ID del usuario creador
            from app.models.usuario import UsuarioModel 
            usuario_model = UsuarioModel()
            ID_USUARIO_SISTEMA = 1 
            usuario_res = usuario_model.find_by_id(ID_USUARIO_SISTEMA)
            if not (usuario_res and usuario_res.get('success') and usuario_res.get('data')):
                logger.error(f"FATAL: No se encontró al usuario de sistema con ID {ID_USUARIO_SISTEMA}. Abortando OC para {proveedor_nombre_logging}.")
                return
            id_usuario_creador = usuario_res['data']['id']
            username_log = usuario_res['data'].get('username', f"ID: {id_usuario_creador}")

            # 3. --- LÓGICA DE QUERY CORREGIDA ---
            # Buscar TODOS los insumos de este proveedor que necesiten reposición
            # Esta consulta es manual porque find_all() no soporta el 'OR' que necesitamos.
            
            query = (self.insumo_model.db.table(self.insumo_model.get_table_name())
                         .select("*, proveedor:id_proveedor(*)")
                         .eq('en_espera_de_reestock', False)
                         .eq('activo', True))

            if str(proveedor_id) == str(default_prov_id) and default_prov_id is not None:
                # Es el proveedor default, buscar su ID O 'NULL'
                logger.info(f"Consulta para proveedor DEFAULT: id_proveedor = {proveedor_id} O id_proveedor = NULL")
                query = query.or_(f'id_proveedor.eq.{proveedor_id},id_proveedor.is.null')
            else:
                # Es un proveedor normal, buscar solo su ID
                logger.info(f"Consulta para proveedor normal: id_proveedor = {proveedor_id}")
                query = query.eq('id_proveedor', proveedor_id)
            
            response = query.execute()
            
            if not response.data:
                logger.info(f"La consulta de insumos para {proveedor_nombre_logging} no devolvió resultados.")
                insumos_a_reponer_result = {'success': True, 'data': []}
            else:
                insumos_a_reponer_result = {'success': True, 'data': response.data}
                
            # --- FIN LÓGICA DE QUERY CORREGIDA ---

            if not insumos_a_reponer_result.get('success'):
                logger.error(f"No se pudieron obtener los insumos del proveedor {proveedor_nombre_logging}.")
                return

            items_para_oc = []
            insumos_para_marcar_en_espera = []
            subtotal_calculado = 0.0

            for insumo in insumos_a_reponer_result.get('data', []):
                stock = float(insumo.get('stock_actual') or 0)
                minimo = float(insumo.get('stock_min') or 0)

                if stock < minimo:
                    insumo_completo_res = self.insumo_model.find_by_id(insumo['id_insumo'], 'id_insumo')
                    if not insumo_completo_res.get('success'):
                        logger.warning(f"No se pudo obtener el detalle completo del insumo {insumo['id_insumo']} para OC automática.")
                        continue
                    
                    insumo_completo = insumo_completo_res.get('data', {})
                    cantidad_a_pedir = math.ceil(minimo - stock)
                    precio_unitario = float(insumo_completo.get('precio_unitario') or 0)
                    
                    items_para_oc.append({
                        'insumo_id': insumo['id_insumo'],
                        'cantidad_solicitada': cantidad_a_pedir,
                        'precio_unitario': precio_unitario,
                        'cantidad_recibida': 0.0
                    })
                    insumos_para_marcar_en_espera.append(insumo['id_insumo'])

            if not items_para_oc:
                logger.info(f"No se encontraron insumos CON BAJO STOCK (que no estén 'en espera') para el proveedor {proveedor_nombre_logging}.")
                return

            # 4. Calcular Totales (Asumimos IVA 21%)
            iva_calculado = subtotal_calculado * 0.21
            total_calculado = subtotal_calculado + iva_calculado

            # 5. Marcar los insumos como "en espera" ANTES de crear la OC
            #    para evitar que otro proceso los tome.
            for insumo_id in insumos_para_marcar_en_espera:
                self.insumo_model.marcar_en_espera(insumo_id)

            # 6. Crear la Orden de Compra
            from app.controllers.orden_compra_controller import OrdenCompraController
            orden_compra_controller = OrdenCompraController()
            datos_oc = {
                'proveedor_id': proveedor_id,
                'estado': 'APROBADA',
                'fecha_emision': date.today().isoformat(),
                'prioridad': 'ALTA',
                'observaciones': f"Orden de compra generada automáticamente por bajo stock. Proveedor: {proveedor_nombre_logging}. Creada por: {username_log}."
            }

            resultado_oc = orden_compra_controller.crear_orden(datos_oc, items_para_oc, id_usuario_creador)

            if resultado_oc.get('success'):
                oc_data = resultado_oc.get('data', {})
                oc_codigo = oc_data.get('codigo_oc', 'N/A')
                oc_id = oc_data.get('id')
                logger.info(f"Orden de compra {oc_codigo} creada exitosamente para {len(items_para_oc)} insumos del proveedor {proveedor_nombre_logging}.")
                
                # 7. Lógica de Notificación (sin cambios)
                from app.controllers.usuario_controller import UsuarioController
                from app.models.rol import RoleModel
                from app.models.notificacion import NotificacionModel

                usuario_controller = UsuarioController()
                role_model = RoleModel()
                notificacion_model = NotificacionModel()
                roles_a_notificar = ['GERENTE', 'SUPERVISOR']
                usuarios_a_notificar = []
                
                for codigo_rol in roles_a_notificar:
                    rol_result = role_model.find_by_codigo(codigo_rol)
                    if rol_result.get('success'):
                        rol_id = rol_result['data']['id']
                        usuarios = usuario_controller.obtener_todos_los_usuarios(filtros={'role_id': rol_id, 'activo': True})
                        usuarios_a_notificar.extend(usuarios)

                mensaje = f"OC automática {oc_codigo} creada por bajo stock."
                url_destino = f"/ordenes_compra/view/{oc_id}"

                for usuario in usuarios_a_notificar:
                    notificacion_data = {
                        'usuario_id': usuario['id'],
                        'mensaje': mensaje,
                        'tipo': 'ADVERTENCIA',
                        'url_destino': url_destino
                    }
                    notificacion_model.create(notificacion_data)
                logger.info(f"Notificaciones enviadas a {len(usuarios_a_notificar)} usuarios para la OC {oc_codigo}.")

            else:
                logger.error(f"Fallo al crear la orden de compra automática para {proveedor_nombre_logging}: {resultado_oc.get('error')}")
                # Revertir el estado 'en_espera_de_reestock' si la OC falla
                for insumo_id in insumos_para_marcar_en_espera:
                    self.insumo_model.quitar_en_espera(insumo_id)

        except Exception as e:
            logger.error(f"Error crítico en _generar_oc_automatica_por_proveedor para ID {proveedor_id}: {e}", exc_info=True)

    def obtener_insumos_para_reclamo(self, filtros: Dict) -> tuple:
        """
        Obtiene insumos para el formulario de reclamos.
        Filtra por proveedor_id y opcionalmente por una lista de orden_ids.
        """
        try:
            proveedor_id = filtros.get('proveedor_id')
            orden_ids = filtros.get('orden_ids')

            if not proveedor_id:
                return self.error_response("El proveedor_id es requerido.", 400)

            if orden_ids:
                response = self.insumo_model.find_by_orden_compra_ids(orden_ids)
            else:
                response = self.insumo_model.find_all(filters={'id_proveedor': proveedor_id})

            if response.get('success'):
                return self.success_response(data=response.get('data', []))
            else:
                logger.error(f"Error al obtener insumos para reclamo: {response.get('error')}")
                return self.error_response(response.get('error', 'Error al obtener insumos.'), 500)

        except Exception as e:
            logger.error(f"Error obteniendo insumos para reclamo: {str(e)}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)