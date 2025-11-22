# app/models/lote_producto.py
from datetime import date, datetime, timedelta
from app.models.base_model import BaseModel
from typing import Dict, List, Optional
import logging
from app.models.configuracion import ConfiguracionModel
from app.utils.vida_util import calcular_semaforo
from app.controllers.configuracion_controller import DIAS_ALERTA_VENCIMIENTO_LOTE, DEFAULT_DIAS_ALERTA

logger = logging.getLogger(__name__)

class LoteProductoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de lotes_productos.
    """

    def get_table_name(self) -> str:
        return 'lotes_productos'

    def get_all_lotes_for_antiquity_view(self) -> Dict:
        """
        Obtiene todos los lotes de producto con su costo de producción calculado,
        listos para el reporte de antigüedad de stock.
        """
        from app.models.receta import RecetaModel # Importación local
        receta_model = RecetaModel()
        
        try:
            query = self.db.table(self.get_table_name()).select(
                'fecha_produccion, cantidad_actual, producto_id, fecha_vencimiento'
            ).gt('cantidad_actual', 0)

            lotes_res = query.execute()

            if not lotes_res.data:
                return {'success': True, 'data': []}

            lotes_data = lotes_res.data
            # Cache para no recalcular costos para el mismo producto
            costos_cache = {}

            for lote in lotes_data:
                producto_id = lote.get('producto_id')
                if not producto_id:
                    lote['costo_unitario'] = 0.0
                    continue

                if producto_id in costos_cache:
                    lote['costo_unitario'] = costos_cache[producto_id]
                else:
                    costo = receta_model.get_costo_produccion(producto_id)
                    costos_cache[producto_id] = costo
                    lote['costo_unitario'] = costo
                
                # Renombrar para consistencia
                lote['cantidad'] = lote.pop('cantidad_actual')
                # Proveer alias 'fecha_fabricacion' para mantener compatibilidad si alguien lo usa
                lote['fecha_fabricacion'] = lote.get('fecha_produccion')

            return {'success': True, 'data': lotes_data}

        except Exception as e:
            logger.error(f"Error en get_all_lotes_for_antiquity_view: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_by_numero_lote(self, numero_lote: str) -> Dict:
        """Busca un lote por su número de lote único."""
        try:
            result = self.db.table(self.get_table_name()).select('*').eq('numero_lote', numero_lote).single().execute()
            if result.data:
                return {'success': True, 'data': result.data}
            else:
                return {'success': False, 'error': 'Lote no encontrado'}
        except Exception as e:
            if "Missing data" in str(e):
                 return {'success': False, 'error': 'Lote no encontrado'}
            logger.error(f"Error buscando lote por número: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_by_producto_id(self, producto_id: int) -> Dict:
        """Busca todos los lotes de un producto específico."""
        try:
            result = self.db.table(self.get_table_name()).select('*').eq('producto_id', producto_id).execute()
            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error buscando lotes por producto: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_lotes_disponibles(self) -> Dict:
        """Busca lotes disponibles (no vencidos y con stock)."""
        try:
            # FILTRO MEJORADO: Excluir explícitamente los que vencen hoy o antes
            fecha_hoy = date.today().isoformat()
            
            result = (
                self.db.table(self.get_table_name())
                .select('*')
                .eq('estado', 'DISPONIBLE')
                .gt('cantidad_actual', 0)
                .gt('fecha_vencimiento', fecha_hoy) # Solo vencimiento futuro estricto (> HOY)
                .execute()
            )
            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error buscando lotes disponibles: {str(e)}")
            return {'success': False, 'error': str(e)}


    def obtener_composicion_inventario(self) -> Dict:
        """
        Obtiene el stock total agrupado por producto, excluyendo estados no disponibles.
        """
        try:
            result = self.db.table(self.table_name).select(
                'producto_id, cantidad_actual, producto:productos(nombre)'
            ).in_('estado', ['DISPONIBLE', 'RESERVADO']).gt('cantidad_actual', 0).execute()

            composicion = {}
            for lote in result.data:
                producto_id = lote['producto_id']
                nombre = lote.get('producto', {}).get('nombre', 'Producto Desconocido')
                cantidad = float(lote.get('cantidad_actual', 0) or 0)

                if nombre not in composicion:
                    composicion[nombre] = 0

                composicion[nombre] += cantidad

            final_data = [{'nombre': k, 'cantidad': v} for k, v in composicion.items()]

            return {'success': True, 'data': final_data}
        except Exception as e:
            logger.error(f"Error obteniendo composición de inventario de productos: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_all_lotes_for_view(self, filtros: Optional[Dict] = None):
        """
        Obtiene todos los lotes de productos con datos enriquecidos (nombre del producto y cantidad reservada)
        para ser mostrados en la vista de listado.
        """
        try:
            query = self.db.table(self.get_table_name()).select(
                '*, producto:productos(nombre)'
            )

            if filtros:
                for key, value in filtros.items():
                    query = query.eq(key, value)
            
            lotes_result = query.order('created_at', desc=True).execute()

            if not hasattr(lotes_result, 'data'):
                 raise Exception("La consulta de lotes no devolvió datos.")

            lotes_data = lotes_result.data

            # Obtener configuración de semáforos
            config_model = ConfiguracionModel()
            try:
                umbral_verde = float(config_model.obtener_valor('UMBRAL_VIDA_UTIL_VERDE', 75))
            except (ValueError, TypeError):
                umbral_verde = 75.0
            
            try:
                umbral_amarillo = float(config_model.obtener_valor('UMBRAL_VIDA_UTIL_AMARILLO', 50))
            except (ValueError, TypeError):
                umbral_amarillo = 50.0
            
            # Obtener configuración de días de alerta
            try:
                dias_alerta_str = config_model.obtener_valor(DIAS_ALERTA_VENCIMIENTO_LOTE, str(DEFAULT_DIAS_ALERTA))
                dias_alerta = int(dias_alerta_str)
            except (ValueError, TypeError):
                dias_alerta = DEFAULT_DIAS_ALERTA

            # 2. Obtener todas las reservas activas
            reservas_result = self.db.table('reservas_productos').select(
                'lote_producto_id, cantidad_reservada'
            ).eq('estado', 'RESERVADO').execute()

            if not hasattr(reservas_result, 'data'):
                 raise Exception("La consulta de reservas no devolvió datos.")

            # 3. Mapear las reservas a cada lote
            reservas_map = {}
            for reserva in reservas_result.data:
                lote_id = reserva['lote_producto_id']
                cantidad = reserva.get('cantidad_reservada', 0)
                reservas_map[lote_id] = reservas_map.get(lote_id, 0) + cantidad

            # 4. Enriquecer los datos de los lotes
            enriched_data = []
            for lote in lotes_data:
                # Aplanar nombre del producto
                if lote.get('producto'):
                    lote['producto_nombre'] = lote['producto']['nombre']
                else:
                    lote['producto_nombre'] = 'Producto no encontrado'
                del lote['producto']

                # Añadir cantidad reservada
                lote['cantidad_reservada'] = reservas_map.get(lote.get('id_lote'), 0)

                # --- CALCULO SEMAFORO ---
                # Fecha Inicio: fecha_produccion
                # Fecha Fin: fecha_vencimiento
                # Fecha Actual: calculada dentro de la función (date.today())
                semaforo = calcular_semaforo(
                    lote.get('fecha_produccion'),
                    lote.get('fecha_vencimiento'),
                    umbral_verde=umbral_verde,
                    umbral_amarillo=umbral_amarillo,
                    dias_alerta=dias_alerta
                )
                lote['semaforo_color'] = semaforo['color']
                lote['vida_util_percent'] = semaforo['percent']

                # --- CORRECCIÓN VISUAL DE ESTADO ---
                # Si vence HOY o ya venció, forzamos el estado visual a 'VENCIDO'
                # aunque en la base de datos siga como DISPONIBLE hasta que corra un cron.
                if lote.get('fecha_vencimiento'):
                    try:
                        venc_str = lote['fecha_vencimiento']
                        # Manejo robusto de formato fecha
                        if isinstance(venc_str, str):
                             venc = datetime.fromisoformat(venc_str.split('T')[0]).date()
                        else:
                             venc = venc_str # Asumimos date object
                        
                        if venc <= date.today():
                            lote['estado'] = 'VENCIDO'
                            lote['semaforo_color'] = 'danger' # Forzar rojo
                            lote['vida_util_percent'] = 0.0
                    except Exception as e_date:
                        logger.warning(f"Error parseando fecha vencimiento lote {lote.get('id_lote')}: {e_date}")

                enriched_data.append(lote)

            return {'success': True, 'data': enriched_data}
        except Exception as e:
            logger.error(f"Error obteniendo lotes de productos para la vista: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def get_lote_detail_for_view(self, id_lote: int):
        """
        Obtiene UN lote para la página 'detalle.html',
        incluyendo las reservas asociadas.
        """
        try:
            # --- PASO 1: Obtener el lote (Sin cambios) ---
            lote_result = self.db.table(self.get_table_name()).select(
                '*, producto:productos(nombre, codigo), orden_produccion:orden_produccion_id(id, codigo)'
            ).eq('id_lote', id_lote).single().execute()
            # ... (Manejo de 'item' y 'producto' sin cambios) ...
            
            if not lote_result.data:
                return {'success': False, 'error': 'Lote no encontrado'}
            item = lote_result.data
            if item.get('producto'):
                item['producto_nombre'] = item['producto']['nombre']
                item['producto_codigo'] = item['producto']['codigo']
            else:
                item['producto_nombre'] = 'Producto no encontrado'
                item['producto_codigo'] = 'N/A'
            del item['producto']

            # Paso 2: Si hay una OP, obtener los insumos que utilizó
            item['insumos_utilizados'] = []
            item['ordenes_compra_asociadas'] = []
            orden_produccion = item.get('orden_produccion')
            if orden_produccion and orden_produccion.get('id'):
                op_id = orden_produccion['id']
                insumos_result = self.db.table('reservas_insumos').select(
                     'cantidad_reservada, lote:insumos_inventario!inner(id_lote, documento_ingreso, numero_lote_proveedor, insumo:insumos_catalogo(nombre))'
                ).eq('orden_produccion_id', op_id).execute()

                if insumos_result.data:
                    item['insumos_utilizados'] = insumos_result.data
                                        
                    # Extraer los códigos de OC y buscar las OCs
                    codigos_oc = {
                        res['lote']['documento_ingreso'] 
                        for res in insumos_result.data 
                        if res.get('lote') and res['lote'].get('documento_ingreso')
                    }
                    
                    if codigos_oc:
                        ocs_result = self.db.table('ordenes_compra').select(
                            'id, codigo_oc, proveedores:proveedor_id(nombre)'
                        ).in_('codigo_oc', list(codigos_oc)).execute()
                        
                        if ocs_result.data:
                            # Usar un diccionario para evitar duplicados y facilitar el acceso
                            item['ordenes_compra_asociadas'] = {oc['codigo_oc']: oc for oc in ocs_result.data}.values()



            # Paso 3: Obtener las reservas de este lote de producto
            reservas_result = self.db.table('reservas_productos').select(
                '*, pedido:pedidos(id)' # <-- CAMBIO AQUÍ
            ).eq('lote_producto_id', id_lote).eq('estado', 'RESERVADO').execute()
            # --- FIN DE LA CORRECCIÓN ---

            item['reservas'] = reservas_result.data if reservas_result.data else []

            return {'success': True, 'data': item}

        except Exception as e:
            logger.error(f"Error obteniendo detalle de lote de producto {id_lote}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def update_lote_cantidad_por_despacho(self, lote_id: int, cantidad_despachada: float) -> dict:
        """
        Reduce la cantidad_actual y la cantidad_reservada de un lote
        al completar un pedido.
        """
        try:
            # 1. Obtener el lote para verificar el stock
            lote_result = self.find_by_id(lote_id)
            if not lote_result.get('data'):
                return {'success': False, 'error': f"Lote de producto ID {lote_id} no encontrado."}

            lote = lote_result['data']

            # 2. Calcular nuevas cantidades (deben ser >= 0)
            cantidad_actual_nueva = lote.get('cantidad_actual', 0.0) - cantidad_despachada
            cantidad_reservada_nueva = lote.get('cantidad_reservada', 0.0) - cantidad_despachada

            if cantidad_actual_nueva < 0 or cantidad_reservada_nueva < 0:
                # Esto no debería ocurrir si el sistema de reservas funciona bien, pero es una protección
                return {'success': False, 'error': 'Intento de despachar más cantidad de la reservada o disponible en el lote.'}

            # 3. Datos a actualizar
            update_data = {
                'cantidad_actual': cantidad_actual_nueva,
                'cantidad_reservada': cantidad_reservada_nueva,
                'fecha_actualizacion': datetime.now().isoformat()
            }

            # 4. Actualizar en la base de datos
            # Asumo que self.update() es el método de la clase base para actualizar el registro en la DB
            update_result = self.update(lote_id, update_data, 'id')

            if update_result.get('success'):
                return {'success': True, 'data': update_result['data']}
            else:
                return {'success': False, 'error': update_result.get('error', 'Error desconocido al actualizar lote.')}

        except Exception as e:
            logger.error(f"Error al despachar lote {lote_id}: {str(e)}")
            return {'success': False, 'error': f"Error interno en la BD al actualizar lote: {str(e)}"}

    def find_por_vencimiento(self, dias_adelante: int = 7) -> Dict:
        """Obtener lotes de productos que vencen en X días"""
        try:
            fecha_limite = (date.today() + timedelta(days=dias_adelante)).isoformat()
            fecha_hoy = date.today().isoformat()

            result = (self.db.table(self.table_name)
                     .select('*, producto:productos(nombre)')
                     .gte('fecha_vencimiento', fecha_hoy)
                     .lte('fecha_vencimiento', fecha_limite)
                     .eq('estado', 'DISPONIBLE')
                     .order('fecha_vencimiento')
                     .execute())

            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error obteniendo lotes de productos por vencimiento: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_stock_valorizado(self) -> List[Dict]:
        """
        Calcula el valor total del stock para cada producto terminado.
        Devuelve una lista de diccionarios, ordenada por valor descendente.
        """
        try:
            stock_response = self.obtener_composicion_inventario()
            if not stock_response.get('success'):
                return []
            stock_map = {item['nombre']: item['cantidad'] for item in stock_response.get('data', [])}

            productos_response = self.db.table('productos').select('nombre, precio_unitario').execute()
            if not productos_response.data:
                return []
            
            valores = []
            for producto in productos_response.data:
                nombre = producto.get('nombre')
                if nombre in stock_map:
                    cantidad = float(stock_map[nombre])
                    precio = float(producto.get('precio_unitario', 0))
                    valor_total = cantidad * precio
                    if valor_total > 0:
                        valores.append({'nombre': nombre, 'valor_total_stock': valor_total})

            return sorted(valores, key=lambda x: x['valor_total_stock'], reverse=True)
        except Exception as e:
            logger.error(f"Error obteniendo stock valorizado de productos: {str(e)}")
            return []

    def obtener_stock_por_estado(self) -> Dict:
        """
        Obtiene la cantidad total de stock de productos agrupada por estado.
        """
        try:
            result = self.db.table(self.table_name).select('estado, cantidad_actual').gt('cantidad_actual', 0).execute()

            if not result.data:
                return {'success': True, 'data': {}}

            stock_por_estado = {}
            for lote in result.data:
                estado = lote.get('estado', 'INDEFINIDO')
                cantidad = float(lote.get('cantidad_actual', 0))
                if estado in stock_por_estado:
                    stock_por_estado[estado] += cantidad
                else:
                    stock_por_estado[estado] = cantidad
            
            return {'success': True, 'data': stock_por_estado}
        except Exception as e:
            logger.error(f"Error obteniendo stock de productos por estado: {str(e)}")
            return {'success': False, 'error': str(e)}
