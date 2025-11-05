from datetime import datetime
import re
from app.controllers.base_controller import BaseController
from app.models.insumo import InsumoModel
from app.models.inventario import InventarioModel
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
            
            # --- INICIO: Disparador automático de OCs ---
            self._revisar_y_generar_ocs_automaticas()
            # --- FIN: Disparador automático de OCs ---
            
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

                logger.info(f"Insumo actualizado exitosamente: {id_insumo}")
                return self.success_response(
                    data=result['data'],
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
                return self.error_response(f"No se pudieron obtener los lotes: {lotes_result.get('error')}", 500)

            # 2. Calcular el stock
            total_stock = sum(lote.get('cantidad_actual', 0) for lote in lotes_result.get('data', []))

            # 3. Actualizar el campo stock_actual en la tabla de insumos
            update_data = {'stock_actual': int(total_stock)}
            update_result = self.insumo_model.update(id_insumo, update_data, 'id_insumo')

            if not update_result.get('success'):
                return self.error_response(f"Error al actualizar el stock: {update_result.get('error')}", 500)

            logger.info(f"Stock actualizado para el insumo {id_insumo}: {total_stock}")

            # --- INICIO DE LA NUEVA LÓGICA ---
            # Después de actualizar, verificamos si necesita reposición.
            self._verificar_y_reponer_stock(update_result['data'])
            # --- FIN DE LA NUEVA LÓGICA ---

            # 4. Devolver el insumo actualizado.
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

                # Volvemos a chequear stock < minimo aquí
                if stock < minimo:
                    cantidad_a_pedir = math.ceil(minimo - stock)
                    precio_unitario = float(insumo.get('precio_unitario') or 0)
                    
                    items_para_oc.append({
                        'insumo_id': insumo['id_insumo'],
                        'cantidad_solicitada': cantidad_a_pedir,
                        'precio_unitario': precio_unitario,
                        'cantidad_recibida': 0.0
                    })
                    insumos_para_marcar_en_espera.append(insumo['id_insumo'])
                    
                    # === SOLUCIÓN PROBLEMA 1: Sumar al subtotal ===
                    subtotal_calculado += (cantidad_a_pedir * precio_unitario)

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
                'observaciones': f"Orden de compra generada automáticamente por bajo stock. Proveedor: {proveedor_nombre_logging}. Creada por: {username_log}.",
                # === SOLUCIÓN PROBLEMA 1: Añadir totales al dict ===
                'subtotal': round(subtotal_calculado, 2),
                'iva': round(iva_calculado, 2),
                'total': round(total_calculado, 2)
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